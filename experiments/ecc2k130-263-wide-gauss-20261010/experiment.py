#!/usr/bin/env python3
"""Run a frozen wide-Gauss CryptoMiniSat gate on archived Q1420 XCNFs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
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
LADDER = ROOT / "experiments/ecc2k130-263-x-freedom-ladder-20261010/runs/R1"
LEAF = ROOT / "experiments/ecc2k130-263-bilinear-leaf-20261010/runs/R1"
ORDINARY = ROOT / "experiments/ecc2k130-263-bilinear-ordinary-q0-20261010/runs/R1"
POLICIES = ("source", "descendant_native")
FIXED = tuple(f"{policy}_x{leaf}_w131" for leaf in (0, 5)
              for policy in POLICIES)
QUERY = tuple(f"{policy}_ordinary_q0" for policy in POLICIES)
ORDER = FIXED + QUERY


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
    if (cfg["schema"] != "ecc2k130-263-wide-gauss-source-v1"
            or cfg["parent_commit"] != "7c89061159840cc80fbf0bfc860464911cdf4dd4"
            or cfg["order"] != list(ORDER)
            or cfg["solver_sha256"] !=
            "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"
            or cfg["peak_rss_cap_bytes"] != 4 * (1 << 30)
            or cfg["fixed_max_conflicts"] != 20000
            or cfg["fixed_internal_seconds"] != 30
            or cfg["fixed_external_seconds"] != 40
            or cfg["ordinary_internal_seconds"] != 120
            or cfg["ordinary_external_seconds"] != 150
            or cfg["gauss"] != {"maxmatrixrows": 20000,
                                "maxmatrixcols": 30000,
                                "maxnummatrices": 5,
                                "autodisablegauss": 0}
            or any(file_digest(ROOT / name) != expected
                   for name, expected in cfg["pins"].items())):
        raise ValueError("source, archived input, or protocol changed")
    return cfg


def compose_fixed(policy: str, leaf: int, out: Path) -> None:
    base = LEAF / f"{policy}_wz_only_base.xcnf.gz"
    delta = (LADDER / f"{policy}_x{leaf}_w131.units.txt").read_bytes()
    with gzip.open(base, "rb") as stream:
        raw = stream.read()
    head, body = raw.split(b"\n", 1)
    fields = head.split()
    if len(fields) != 4 or fields[:2] != [b"p", b"cnf"]:
        raise ValueError("invalid archived XCNF header")
    count = int(fields[3]) + delta.count(b"\n")
    out.write_bytes(f"p cnf {int(fields[2])} {count}\n".encode() + body + delta)


def prepare(stem: str, out: Path) -> dict:
    policy = "descendant_native" if stem.startswith("descendant_native") else "source"
    if stem in FIXED:
        leaf = int(stem.split("_x")[1].split("_")[0])
        compose_fixed(policy, leaf, out)
        parent = read(LADDER / "cells.json")["cells"][stem]
        expected_hash, expected_bytes = parent["formula_sha256"], parent["formula_bytes"]
        kind = "fixed_witness"
    elif stem in QUERY:
        receipt = read(ORDINARY / f"{policy}_wz_only.formula.json")
        with gzip.open(ORDINARY / f"{policy}_wz_only.xcnf.gz", "rb") as stream:
            out.write_bytes(stream.read())
        expected_hash = receipt["formula_raw_sha256"]
        expected_bytes = receipt["formula_raw_bytes"]
        kind = "ordinary_q0"
    else:
        raise ValueError("cell outside frozen panel")
    if file_digest(out) != expected_hash or out.stat().st_size != expected_bytes:
        raise ValueError("reconstructed XCNF differs from archived receipt")
    header = out.open("rb").readline().split()
    return {"kind": kind, "policy": policy, "formula_sha256": expected_hash,
            "formula_bytes": expected_bytes, "variables": int(header[2]),
            "constraints": int(header[3])}


def freeze() -> None:
    cfg = source()
    if RUN.exists():
        raise FileExistsError("frozen panel is write-once")
    rows = {}
    with tempfile.TemporaryDirectory(prefix="wide-gauss-freeze-", dir="/private/tmp") as tmp:
        for stem in ORDER:
            path = Path(tmp) / f"{stem}.xcnf"
            rows[stem] = prepare(stem, path)
            path.unlink()
    write_once(RUN / "cells.json", {
        "schema": "ecc2k130-263-wide-gauss-cells-v1",
        "status": "FROZEN_SIX_ARCHIVED_XCNFS", "candidate_id": None,
        "source_sha256": file_digest(HERE / "source.json"),
        "runner_sha256": file_digest(Path(__file__)),
        "order": list(ORDER), "cells": rows,
    })
    print(json.dumps({"status": "FROZEN_SIX_ARCHIVED_XCNFS",
                      "cells": len(rows)}, sort_keys=True))


def frozen():
    cfg = source()
    cells = read(RUN / "cells.json")
    if (cells["schema"] != "ecc2k130-263-wide-gauss-cells-v1"
            or cells["status"] != "FROZEN_SIX_ARCHIVED_XCNFS"
            or cells["order"] != list(ORDER)
            or set(cells["cells"]) != set(ORDER)
            or cells["source_sha256"] != file_digest(HERE / "source.json")
            or cells["runner_sha256"] != file_digest(Path(__file__))):
        raise ValueError("frozen panel differs")
    return cfg, cells


def rss_bytes(pid: int) -> int:
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                            text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError("RSS sampler failed: " + result.stderr.strip())
    return int(result.stdout.strip() or 0) * 1024


def flags(cfg: dict, kind: str) -> list[str]:
    values = ["--threads=1", "--verb=1", "--printsol=1"]
    values.extend(f"--{name}={value}" for name, value in cfg["gauss"].items())
    if kind == "fixed_witness":
        values += [f"--maxconfl={cfg['fixed_max_conflicts']}",
                   f"--maxtime={cfg['fixed_internal_seconds']}"]
    else:
        values += [f"--maxtime={cfg['ordinary_internal_seconds']}"]
    return values


def solve(stem: str) -> None:
    cfg, cells = frozen()
    if stem not in cells["cells"]:
        raise ValueError("cell outside frozen panel")
    expected = cells["cells"][stem]
    paths = [RUN / f"{stem}.{suffix}" for suffix in
             ("solver.json", "stdout.txt.gz", "stderr.txt")]
    if any(path.exists() for path in paths):
        raise FileExistsError("cell evidence already exists")
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
    if rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS preflight failed before solver launch")
    with tempfile.TemporaryDirectory(prefix="wide-gauss-solve-", dir="/private/tmp") as tmp:
        formula = Path(tmp) / "input.xcnf"
        actual = prepare(stem, formula)
        if actual != expected:
            raise ValueError("solver input differs from frozen cell")
        stdout = Path(tmp) / "stdout.txt"
        argv = flags(cfg, expected["kind"])
        cap = (cfg["fixed_external_seconds"] if expected["kind"] == "fixed_witness"
               else cfg["ordinary_external_seconds"])
        started = time.perf_counter()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        peak, guard = 0, None
        with stdout.open("xb") as out, paths[2].open("x") as err:
            proc = subprocess.Popen([str(solver), *argv, str(formula)],
                                    stdout=out, stderr=err, start_new_session=True)
            try:
                while proc.poll() is None:
                    peak = max(peak, rss_bytes(proc.pid))
                    if peak > cfg["peak_rss_cap_bytes"]:
                        guard = "RSS_CAP"
                    elif time.perf_counter() - started > cap:
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
        with paths[1].open("xb") as target:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target,
                               mtime=0) as compressed:
                compressed.write(raw)
        write_once(paths[0], {
            "schema": "ecc2k130-263-wide-gauss-solver-v1",
            "cell": stem, "kind": expected["kind"], "policy": expected["policy"],
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
            "stdout_archive_sha256": file_digest(paths[1]),
            "stderr_sha256": file_digest(paths[2]),
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
