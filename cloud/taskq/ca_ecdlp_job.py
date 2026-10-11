#!/usr/bin/env python3
"""Run the `ca` ECDLP solver on one instance as a taskq job.

    ca_ecdlp_job.py --ca build/taskq-cpu/ca --instance cloud/taskq/instances/generic-26.json \
        [--alg rho] [--seed 1] [--seed-from-repetition] [--threads 1] [--max-ops N] \
        [--out DIR] [-- EXTRA_CA_ARGS...]

or, without an instance file, the instance on the command line:

    ca_ecdlp_job.py --ca build/ca --p P --a A --b B --order N --P X,Y --Q X,Y

It runs `ca solve --alg ALG --group ec --p P --a A --b B --order N --g X,Y --h X,Y`,
parses the one JSON object the solver prints on stdout, and writes three files
into --out (default $TASKQ_OUTPUT_DIR, where taskq collects them):

  metrics.json      the solver's own counters (ops, iterations, table_entries,
                    collisions, bytes_peak, seconds, threads, launches for
                    gpu-rho), its status and exit code, the instance digest and
                    the exact argv.  `solver_seconds` is the time the solver
                    reports for its own solve; taskq's rusage wall time for the
                    whole process is separate and larger.
  certificate.json  {"kind": "discrete_log", ...} only when the solver printed
                    status "ok" with a scalar; {"kind": "none"} otherwise.  The
                    format is the one `taskq.verify` and crypto-autoresearcher's
                    docs/claims-and-verification.md check: k*P == Q on
                    y^2 = x^3 + a x + b over F_p, and n*P == O for the order n.
  solver.stdout     the solver's stdout, byte for byte (stderr too, if any).

This script does not check the answer itself: the certificate is a claim, and
the verifier that judges it (the taskq worker's `verify` step, or
`python -m taskq.verify certificate.json`) shares no code with the solver.

Exit status: the solver's own (0 solved; 1 a solver status such as "limit
reached" or "not found"; 2 bad arguments), or 3 if the solver exited 0 but
printed nothing this script can parse.  A nonzero exit makes the taskq run
`failed`; the metrics and certificate are still collected.

Standard library only: it runs in the worker image with no extra packages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA = "ca-ecdlp-job/v1"
# Counters `ca solve` prints for every algorithm (print_stats in tools/ca_cli.c),
# plus the per-algorithm extras.  Anything else it prints is kept under "solver".
STAT_FIELDS = ("ops", "iterations", "table_entries", "collisions", "bytes_peak",
               "seconds", "threads")
EXTRA_FIELDS = ("launches", "endomorphism", "aut_order", "lambda", "rho_speedup",
                "precomp_ops", "chains", "dp_bits", "r")


def to_int(value: Any) -> int:
    """A JSON int, a decimal string or a 0x-hex string."""
    if isinstance(value, bool):
        raise ValueError("boolean is not an integer")
    if isinstance(value, int):
        return value
    s = str(value).strip().lower()
    return int(s, 16) if s.startswith("0x") else int(s, 10)


def parse_point(value: Any) -> tuple[int, int]:
    """[x, y] or "x,y"."""
    if isinstance(value, str):
        parts = value.split(",")
    else:
        parts = list(value)
    if len(parts) != 2:
        raise ValueError(f"a point is [x, y] or 'x,y', got {value!r}")
    return to_int(parts[0]), to_int(parts[1])


def load_instance(args: argparse.Namespace) -> dict[str, Any]:
    """The instance as ints: p, a, b, order, P, Q, plus its name and digest."""
    if args.instance:
        raw = Path(args.instance).read_bytes()
        doc = json.loads(raw)
        curve = doc["curve"]
        if curve.get("field", "prime") != "prime":
            raise ValueError("ca solve handles prime-field curves only")
        inst = {"name": doc.get("name", Path(args.instance).stem),
                "p": curve["p"], "a": curve["a"], "b": curve["b"],
                "order": doc["order"], "P": doc["P"], "Q": doc["Q"],
                "sha256": hashlib.sha256(raw).hexdigest(), "path": args.instance}
    else:
        missing = [f for f in ("p", "a", "b", "order", "P", "Q") if getattr(args, f) is None]
        if missing:
            raise ValueError("without --instance, give " + ", ".join("--" + m for m in missing))
        inst = {"name": "argv", "p": args.p, "a": args.a, "b": args.b,
                "order": args.order, "P": args.P, "Q": args.Q, "sha256": None, "path": None}
    for k in ("p", "a", "b", "order"):
        inst[k] = to_int(inst[k])
    inst["P"], inst["Q"] = parse_point(inst["P"]), parse_point(inst["Q"])
    return inst


def solver_argv(ca: str, alg: str, inst: dict[str, Any], seed: int | None,
                threads: int | None, max_ops: int | None, extra: list[str]) -> list[str]:
    argv = [ca, "solve", "--alg", alg, "--group", "ec",
            "--p", str(inst["p"]), "--a", str(inst["a"]), "--b", str(inst["b"]),
            "--order", str(inst["order"]),
            "--g", "%d,%d" % inst["P"], "--h", "%d,%d" % inst["Q"]]
    if seed is not None:
        argv += ["--seed", str(seed)]
    if threads is not None:
        argv += ["--threads", str(threads)]
    if max_ops is not None:
        argv += ["--max-ops", str(max_ops)]
    return argv + extra


def parse_solver_stdout(text: str) -> dict[str, Any] | None:
    """The last line of stdout that is a JSON object with a "status" field.

    `ca solve` prints exactly one such line, on success and on a solver
    failure alike (tools/ca_cli.c); a usage error prints nothing on stdout.
    """
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        if isinstance(doc, dict) and "status" in doc:
            return doc
    return None


def solved_scalar(report: dict[str, Any] | None) -> int | None:
    """The scalar the solver claims, or None if it claims none."""
    if not report or report.get("status") != "ok" or "x" not in report:
        return None
    try:
        return to_int(report["x"])
    except (TypeError, ValueError):
        return None


def certificate(inst: dict[str, Any], k: int | None) -> dict[str, Any]:
    if k is None:
        return {"kind": "none"}
    return {
        "kind": "discrete_log",
        "curve": {"field": "prime", "p": str(inst["p"]), "a": str(inst["a"]),
                  "b": str(inst["b"])},
        "statement": {"P": [str(c) for c in inst["P"]], "Q": [str(c) for c in inst["Q"]],
                      "k": str(k), "n": str(inst["order"])},
    }


def metrics(inst: dict[str, Any], alg: str, argv: list[str], exit_code: int,
            report: dict[str, Any] | None, k: int | None, wall: float,
            seed: int | None) -> dict[str, Any]:
    report = report or {}
    out: dict[str, Any] = {
        "schema": SCHEMA,
        "alg": alg,
        "solver_exit_code": exit_code,
        "solver_status": report.get("status"),
        "solved": k is not None,
        "k": str(k) if k is not None else None,
        "seed": seed,
        "instance": {"name": inst["name"], "path": inst["path"], "sha256": inst["sha256"],
                     "p": str(inst["p"]), "order": str(inst["order"]),
                     "p_bits": inst["p"].bit_length(),
                     "order_bits": inst["order"].bit_length()},
        "argv": argv,
        # Parent-side wall time of the solver process, launch included.
        "wrapper_wall_seconds": wall,
        "parse_error": None if report else "no JSON status line on the solver's stdout",
    }
    for f in STAT_FIELDS + EXTRA_FIELDS:
        if f in report:
            out["solver_seconds" if f == "seconds" else f] = report[f]
    ops = report.get("ops")
    if isinstance(ops, int) and inst["order"] > 0:
        # The repo's unit (tools/ca_bench.c): S = group operations / sqrt(n).
        out["ops_per_sqrt_order"] = ops / math.sqrt(inst["order"])
    out["solver"] = report
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ca", default="build/taskq-cpu/ca", help="path to the ca binary")
    ap.add_argument("--instance", help="instance JSON (see cloud/taskq/instances/)")
    for f in ("p", "a", "b", "order"):
        ap.add_argument("--" + f)
    ap.add_argument("--P", help="base point x,y")
    ap.add_argument("--Q", help="target point x,y")
    ap.add_argument("--alg", default="rho",
                    help="ca solve --alg: rho, gpu-rho, glv, dlog, bsgs, kangaroo, grumpy, precomp")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--seed-from-repetition", action="store_true",
                    help="add $TASKQ_REPETITION to --seed, so each benchmark repetition "
                         "walks from a different start")
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--max-ops", type=int, default=None)
    ap.add_argument("--out", default=os.environ.get("TASKQ_OUTPUT_DIR"),
                    help="output directory (default $TASKQ_OUTPUT_DIR)")
    ap.add_argument("extra", nargs="*", help="after --: extra ca solve arguments")
    args = ap.parse_args(argv)
    if not args.out:
        ap.error("--out is required outside a taskq task ($TASKQ_OUTPUT_DIR is unset)")

    try:
        inst = load_instance(args)
    except (OSError, KeyError, ValueError) as err:
        print(f"ca_ecdlp_job: bad instance: {err}", file=sys.stderr)
        return 2
    seed = args.seed
    if args.seed_from_repetition:
        seed = (seed or 0) + int(os.environ.get("TASKQ_REPETITION", "0"))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cmd = solver_argv(args.ca, args.alg, inst, seed, args.threads, args.max_ops, args.extra)
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    wall = time.perf_counter() - t0
    (out / "solver.stdout").write_text(proc.stdout)
    if proc.stderr:
        (out / "solver.stderr").write_text(proc.stderr)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)

    report = parse_solver_stdout(proc.stdout)
    k = solved_scalar(report)
    (out / "certificate.json").write_text(json.dumps(certificate(inst, k), indent=1) + "\n")
    (out / "metrics.json").write_text(
        json.dumps(metrics(inst, args.alg, cmd, proc.returncode, report, k, wall, seed),
                   indent=1, sort_keys=True) + "\n")
    if proc.returncode == 0 and k is None:
        print("ca_ecdlp_job: solver exited 0 without a parseable solution", file=sys.stderr)
        return 3
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
