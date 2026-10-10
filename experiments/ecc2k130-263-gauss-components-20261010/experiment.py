#!/usr/bin/env python3
"""Run matched matrix-selection policies on archived Q1420 ordinary Q0 XCNFs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "runs/R1"
WIDE = ROOT / "experiments/ecc2k130-263-wide-gauss-20261010/experiment.py"
spec = importlib.util.spec_from_file_location("archived_wide_runner", WIDE)
assert spec and spec.loader
wide = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wide)
POLICIES = ("source", "descendant_native")
VARIANTS = ("default", "selector_window", "largest", "all_five")
ORDER = tuple(f"{policy}_{variant}" for variant in VARIANTS
              for policy in POLICIES)
MATRIX_POLICIES = {
    "default": {"maxmatrixrows": 2000, "maxmatrixcols": 1000,
                "maxnummatrices": 5, "autodisablegauss": 1},
    "selector_window": {"maxmatrixrows": 8000, "maxmatrixcols": 12000,
                        "maxnummatrices": 1, "autodisablegauss": 0},
    "largest": {"maxmatrixrows": 20000, "maxmatrixcols": 30000,
                "maxnummatrices": 1, "autodisablegauss": 0},
    "all_five": {"maxmatrixrows": 20000, "maxmatrixcols": 30000,
                 "maxnummatrices": 5, "autodisablegauss": 0},
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def write_once(path: Path, value) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def source():
    cfg = read(HERE / "source.json")
    if (cfg["schema"] != "ecc2k130-263-gauss-components-source-v1"
            or cfg["parent_commit"] != "025e3a00afa9c0569a8bbb640d7bec6551e68ea3"
            or cfg["policies"] != list(POLICIES)
            or cfg["variants"] != list(VARIANTS)
            or cfg["matrix_policies"] != MATRIX_POLICIES
            or cfg["order"] != list(ORDER)
            or cfg["max_conflicts"] != 2000
            or cfg["internal_wall_seconds"] != 120
            or cfg["external_wall_seconds"] != 180
            or cfg["peak_rss_cap_bytes"] != 4 * (1 << 30)
            or cfg["solver_sha256"] !=
            "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"
            or any(file_digest(ROOT / name) != expected
                   for name, expected in cfg["pins"].items())):
        raise ValueError("frozen source, solver, or archive changed")
    return cfg


def policy_variant(stem: str) -> tuple[str, str]:
    for policy in POLICIES:
        for variant in VARIANTS:
            if stem == f"{policy}_{variant}":
                return policy, variant
    raise ValueError("cell outside frozen panel")


def prepare(policy: str, out: Path) -> dict:
    row = wide.prepare(f"{policy}_ordinary_q0", out)
    if row["kind"] != "ordinary_q0" or row["policy"] != policy:
        raise ValueError("archived ordinary Q0 input differs")
    return row


def freeze() -> None:
    cfg = source()
    if (RUN / "cells.json").exists():
        raise FileExistsError("input panel is write-once")
    input_rows = {}
    with tempfile.TemporaryDirectory(prefix="q1420-component-freeze-", dir="/private/tmp") as tmp:
        for policy in POLICIES:
            input_rows[policy] = prepare(policy, Path(tmp) / f"{policy}.xcnf")
    cells = {}
    for stem in ORDER:
        policy, variant = policy_variant(stem)
        cells[stem] = {**input_rows[policy], "variant": variant,
                       "matrix_policy": cfg["matrix_policies"][variant]}
    write_once(RUN / "cells.json", {
        "schema": "ecc2k130-263-gauss-components-cells-v1",
        "status": "FROZEN_EIGHT_SOLVER_CELLS", "candidate_id": None,
        "source_sha256": file_digest(HERE / "source.json"),
        "runner_sha256": file_digest(Path(__file__)),
        "order": list(ORDER), "cells": cells,
    })
    print(json.dumps({"status": "FROZEN_EIGHT_SOLVER_CELLS",
                      "cells": len(cells)}, sort_keys=True))


def frozen():
    cfg = source()
    panel = read(RUN / "cells.json")
    if (panel["schema"] != "ecc2k130-263-gauss-components-cells-v1"
            or panel["status"] != "FROZEN_EIGHT_SOLVER_CELLS"
            or panel["order"] != list(ORDER)
            or set(panel["cells"]) != set(ORDER)
            or panel["source_sha256"] != file_digest(HERE / "source.json")
            or panel["runner_sha256"] != file_digest(Path(__file__))):
        raise ValueError("frozen panel differs")
    return cfg, panel


def flags(cfg: dict, variant: str) -> list[str]:
    matrix = cfg["matrix_policies"][variant]
    return (["--threads=1", "--verb=1", "--printsol=1"]
            + [f"--{name}={value}" for name, value in matrix.items()]
            + [f"--maxconfl={cfg['max_conflicts']}",
               f"--maxtime={cfg['internal_wall_seconds']}"])


def solve(stem: str) -> None:
    cfg, panel = frozen()
    policy, variant = policy_variant(stem)
    expected = panel["cells"][stem]
    receipt = RUN / f"{stem}.solver.json"
    stdout_archive = RUN / f"{stem}.stdout.txt.gz"
    stderr = RUN / f"{stem}.stderr.txt"
    if any(path.exists() for path in (receipt, stdout_archive, stderr)):
        raise FileExistsError("solver evidence already exists")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat unavailable")
    solver = Path(solver_name).resolve()
    if file_digest(solver) != cfg["solver_sha256"]:
        raise ValueError("solver binary differs")
    version = subprocess.run([str(solver), "--version"], capture_output=True,
                             text=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version differs")
    if wide.rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS preflight failed before solver launch")
    with tempfile.TemporaryDirectory(prefix="q1420-component-solve-", dir="/private/tmp") as tmp:
        formula = Path(tmp) / "input.xcnf"
        observed = prepare(policy, formula)
        if expected != {**observed, "variant": variant,
                        "matrix_policy": cfg["matrix_policies"][variant]}:
            raise ValueError("solver input or policy differs from frozen cell")
        stdout = Path(tmp) / "stdout.txt"
        argv = flags(cfg, variant)
        started = time.perf_counter()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        peak, guard = 0, None
        with stdout.open("xb") as out, stderr.open("x") as err:
            proc = subprocess.Popen([str(solver), *argv, str(formula)],
                                    stdout=out, stderr=err, start_new_session=True)
            try:
                while proc.poll() is None:
                    peak = max(peak, wide.rss_bytes(proc.pid))
                    if peak > cfg["peak_rss_cap_bytes"]:
                        guard = "RSS_CAP"
                    elif time.perf_counter() - started > cfg["external_wall_seconds"]:
                        guard = "WALL_CAP"
                    if guard:
                        os.killpg(proc.pid, signal.SIGKILL)
                        break
                    time.sleep(0.2)
                exit_code = proc.wait()
            except BaseException:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                raise
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        raw = stdout.read_bytes()
        terminal = [line.strip() for line in raw.decode(errors="replace").splitlines()
                    if line.startswith("s ")]
        if guard == "RSS_CAP":
            status = "OOM_GUARD"
        elif guard == "WALL_CAP":
            status = "BOUNDED_UNKNOWN"
        elif terminal == ["s SATISFIABLE"] and exit_code == 10:
            status = "SAT_UNVERIFIED"
        elif terminal == ["s INDETERMINATE"] and exit_code == 15:
            status = "BOUNDED_UNKNOWN"
        elif terminal == ["s UNSATISFIABLE"] and exit_code == 20:
            status = "UNSAT"
        else:
            status = "PRODUCER_FAILURE"
        with stdout_archive.open("xb") as target:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target,
                               mtime=0) as compressed:
                compressed.write(raw)
        write_once(receipt, {
            "schema": "ecc2k130-263-gauss-components-solver-v1",
            "cell": stem, "policy": policy, "variant": variant,
            "candidate_id": None, "status": status, "guard": guard,
            "source_sha256": file_digest(HERE / "source.json"),
            "cells_sha256": file_digest(RUN / "cells.json"),
            "runner_sha256": file_digest(Path(__file__)),
            "formula_sha256": file_digest(formula),
            "solver_sha256": file_digest(solver), "solver_version": version,
            "command_flags": argv, "exit_code": exit_code,
            "terminal_status_lines": terminal,
            "wall_seconds": time.perf_counter() - started,
            "user_cpu_seconds": after.ru_utime - before.ru_utime,
            "system_cpu_seconds": after.ru_stime - before.ru_stime,
            "peak_sampled_rss_bytes": peak,
            "stdout_raw_sha256": digest(raw), "stdout_raw_bytes": len(raw),
            "stdout_archive_sha256": file_digest(stdout_archive),
            "stderr_sha256": file_digest(stderr),
        })
    print(json.dumps({"cell": stem, "status": status,
                      "guard": guard}, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "solve", "all"))
    parser.add_argument("--cell")
    args = parser.parse_args()
    if args.action == "freeze":
        if args.cell:
            parser.error("freeze takes no cell")
        freeze()
    elif args.action == "solve":
        if not args.cell:
            parser.error("solve requires --cell")
        solve(args.cell)
    else:
        if args.cell:
            parser.error("all takes no cell")
        _, panel = frozen()
        for stem in panel["order"]:
            solve(stem)


if __name__ == "__main__":
    main()
