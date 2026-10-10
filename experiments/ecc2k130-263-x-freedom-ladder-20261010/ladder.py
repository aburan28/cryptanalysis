#!/usr/bin/env python3
"""Freeze and execute the Q1420 fixed-witness x-release ladder."""

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
import sys
import tempfile
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "runs/R1"
PARENT = ROOT / "experiments/ecc2k130-263-bilinear-leaf-20261010/runs/R1"
WITNESS = ROOT / "experiments/ecc2k130-263-distinct-s3-control-20261010/runs/R1/witness.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text())


def write_json(path: Path, row) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, sort_keys=True, indent=2) + "\n")


def source():
    cfg = read_json(HERE / "source.json")
    if (cfg["schema"] != "ecc2k130-263-x-freedom-ladder-source-v1"
            or cfg["parent_commit"] != "ab168de3ef27f06e0b9ce1833b5623e08c7a8765"
            or cfg["policies"] != ["source", "descendant_native"]
            or cfg["leaf_indices"] != [0, 5]
            or cfg["release_widths"] != [1, 4, 8, 16, 32, 64, 96, 131]
            or cfg["max_conflicts"] != 20000
            or cfg["internal_wall_seconds"] != 30
            or cfg["external_wall_seconds"] != 40
            or cfg["peak_rss_cap_bytes"] != 4 * (1 << 30)
            or cfg["threads"] != 1
            or any(file_sha(ROOT / path) != digest
                   for path, digest in cfg["pins"].items())):
        raise ValueError("frozen protocol, archive, or named input changed")
    witness = read_json(WITNESS)
    if (witness["status"] != "PASS_TWO_FINITE_SIX_DISTINCT_CONTROLS"
            or set(witness["policies"]) != set(cfg["policies"])):
        raise ValueError("six-distinct control witness changed")
    return cfg, witness


def panel(policy: str):
    base = read_json(PARENT / f"{policy}_wz_only_base.json")
    named = read_json(PARENT / f"{policy}_wz_only_inputs.json")
    archive = PARENT / f"{policy}_wz_only_base.xcnf.gz"
    if (base["schema"] != "ecc2k130-263-bilinear-base-v1"
            or base["status"] != "CONTROL_FORMULA_BUILT"
            or base["policy"] != policy or base["variant"] != "wz_only"
            or base["formula_gzip_sha256"] != file_sha(archive)
            or base["input_vars_sha256"]
            != file_sha(PARENT / f"{policy}_wz_only_inputs.json")
            or base["input_vars_count"] != len(named)
            or len(base["target_selector_variables"]) != 2):
        raise ValueError("archived formula or named inputs changed")
    return base, named, archive


def bit_order():
    order = [(53 * j) % 131 for j in range(131)]
    if len(set(order)) != 131:
        raise AssertionError("x-coordinate release order is not a permutation")
    return order


def cell_name(policy: str, leaf: int, width: int) -> str:
    return f"{policy}_x{leaf}_w{width}"


def units(control, named, choice, leaf: int, width: int) -> bytes:
    released = set(bit_order()[:width])
    fixed: dict[int, int] = {}

    def word(name: str, size: int, value: int, omit=()) -> None:
        for bit in range(size):
            if bit in omit:
                continue
            literal = named[f"{name}:{bit}"]
            if literal <= 0 or literal in fixed:
                raise ValueError("repeated or invalid named input variable")
            fixed[literal] = (value >> bit) & 1

    for index, row in enumerate(control["leaves"]):
        word(f"s{index}", 24, row["mask"])
        word(f"x{index}", 131, row["raw_point_normalized"][0],
             released if index == leaf else ())
        word(f"z{index}", 131, row["z"])
    for index, point in enumerate(control["intermediates"]):
        if not point["finite"]:
            raise ValueError("frozen projective intermediate not finite")
        word(f"t{index}", 131, point["x"])
        variable = named[f"f:{index}"]
        if variable <= 0 or variable in fixed:
            raise ValueError("repeated projective flag")
        fixed[variable] = 1
    for variable in choice:
        if variable <= 0 or variable in fixed:
            raise ValueError("repeated target choice")
        fixed[variable] = 0
    if len(fixed) != 2246 - width:
        raise ValueError("unit count differs from fixed-witness contract")
    signed = sorted(variable if bit else -variable
                    for variable, bit in fixed.items())
    return "".join(f"{literal} 0\n" for literal in signed).encode()


def decompress_base(archive: Path, receipt, dest: Path) -> None:
    with gzip.open(archive, "rb") as src, dest.open("xb") as target:
        shutil.copyfileobj(src, target, length=1 << 20)
    if (file_sha(dest) != receipt["formula_raw_sha256"]
            or dest.stat().st_size != receipt["formula_raw_bytes"]):
        raise ValueError("base gzip does not reproduce archived XCNF")


def compose(base: Path, delta: bytes, dest: Path):
    with base.open("rb") as src, dest.open("xb") as target:
        head = src.readline().split()
        if len(head) != 4 or head[:2] != [b"p", b"cnf"]:
            raise ValueError("invalid XCNF header")
        variables, constraints = map(int, head[2:])
        count = delta.count(b"\n")
        target.write(f"p cnf {variables} {constraints + count}\n".encode())
        shutil.copyfileobj(src, target, length=1 << 20)
        target.write(delta)
    return variables, constraints + count


def freeze() -> None:
    cfg, witness = source()
    if RUN.exists():
        raise FileExistsError("R1 already exists; frozen inputs are write-once")
    RUN.mkdir(parents=True)
    rows, order = {}, []
    with tempfile.TemporaryDirectory(prefix="x-ladder-freeze-", dir="/private/tmp") as temp:
        scratch = Path(temp)
        bases = {}
        for policy in cfg["policies"]:
            receipt, named, archive = panel(policy)
            raw = scratch / f"{policy}.xcnf"
            decompress_base(archive, receipt, raw)
            bases[policy] = (receipt, named, raw)
        for leaf in cfg["leaf_indices"]:
            for width in cfg["release_widths"]:
                for policy in cfg["policies"]:
                    receipt, named, base = bases[policy]
                    stem = cell_name(policy, leaf, width)
                    delta = units(witness["policies"][policy], named,
                                  receipt["target_selector_variables"],
                                  leaf, width)
                    full = scratch / f"{stem}.xcnf"
                    variables, constraints = compose(base, delta, full)
                    (RUN / f"{stem}.units.txt").write_bytes(delta)
                    rows[stem] = {
                        "policy": policy, "leaf": leaf, "released_width": width,
                        "released_bit_positions": bit_order()[:width],
                        "unit_count": 2246 - width,
                        "unit_delta_sha256": sha(delta),
                        "formula_sha256": file_sha(full),
                        "formula_bytes": full.stat().st_size,
                        "variables": variables,
                        "total_constraints": constraints,
                        "base_gzip_sha256": receipt["formula_gzip_sha256"],
                    }
                    order.append(stem)
                    full.unlink()
    write_json(RUN / "cells.json", {
        "schema": "ecc2k130-263-x-freedom-ladder-cells-v1",
        "status": "FROZEN_32_SAT_INPUTS",
        "candidate_id": None,
        "source_sha256": file_sha(HERE / "source.json"),
        "runner_sha256": file_sha(Path(__file__)),
        "witness_sha256": file_sha(WITNESS),
        "order": order, "cells": rows,
    })
    print(json.dumps({"status": "FROZEN_32_SAT_INPUTS",
                      "cells": len(rows), "source_sha256":
                      file_sha(HERE / "source.json")}, sort_keys=True))


def frozen_cells():
    cfg, witness = source()
    frozen = read_json(RUN / "cells.json")
    expected = [cell_name(policy, leaf, width)
                for leaf in cfg["leaf_indices"]
                for width in cfg["release_widths"]
                for policy in cfg["policies"]]
    if (frozen["schema"] != "ecc2k130-263-x-freedom-ladder-cells-v1"
            or frozen["status"] != "FROZEN_32_SAT_INPUTS"
            or frozen["source_sha256"] != file_sha(HERE / "source.json")
            or frozen["runner_sha256"] != file_sha(Path(__file__))
            or frozen["witness_sha256"] != file_sha(WITNESS)
            or frozen["order"] != expected
            or set(frozen["cells"]) != set(expected)):
        raise ValueError("frozen cell panel or source changed")
    return cfg, witness, frozen


def rss_bytes(pid: int) -> int:
    check = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                           text=True, capture_output=True)
    if check.returncode:
        raise RuntimeError("RSS sampler unavailable: " + check.stderr.strip())
    return int(check.stdout.strip() or 0) * 1024


def solve(stem: str) -> None:
    cfg, witness, frozen = frozen_cells()
    if stem not in frozen["cells"]:
        raise ValueError("cell is outside frozen panel")
    row = frozen["cells"][stem]
    policy, leaf, width = row["policy"], row["leaf"], row["released_width"]
    receipt, named, archive = panel(policy)
    delta = units(witness["policies"][policy], named,
                  receipt["target_selector_variables"], leaf, width)
    unit_path = RUN / f"{stem}.units.txt"
    result_path = RUN / f"{stem}.solver.json"
    stdout_archive = RUN / f"{stem}.stdout.txt.gz"
    stderr_path = RUN / f"{stem}.stderr.txt"
    if any(path.exists() for path in (result_path, stdout_archive, stderr_path)):
        raise FileExistsError("solver evidence already exists")
    if unit_path.read_bytes() != delta or row["unit_delta_sha256"] != sha(delta):
        raise ValueError("frozen unit delta changed")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 unavailable")
    solver = Path(solver_name).resolve()
    if file_sha(solver) != cfg["solver_sha256"]:
        raise ValueError("solver binary differs from protocol")
    version = subprocess.run([str(solver), "--version"], text=True,
                             capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version differs from protocol")
    if rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS preflight failed before solver launch")
    with tempfile.TemporaryDirectory(prefix="x-ladder-solve-", dir="/private/tmp") as temp:
        scratch = Path(temp)
        base = scratch / "base.xcnf"
        full = scratch / "input.xcnf"
        stdout_path = scratch / "stdout.txt"
        decompress_base(archive, receipt, base)
        variables, constraints = compose(base, delta, full)
        if (file_sha(full) != row["formula_sha256"]
                or full.stat().st_size != row["formula_bytes"]
                or variables != row["variables"]
                or constraints != row["total_constraints"]):
            raise ValueError("full solver input differs from precommitted hash")
        flags = ["--threads=1", f"--maxconfl={cfg['max_conflicts']}",
                 f"--maxtime={cfg['internal_wall_seconds']}",
                 "--verb=1", "--printsol=1"]
        started = time.perf_counter()
        cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        peak, guard = 0, None
        with stdout_path.open("xb") as out, stderr_path.open("x") as err:
            proc = subprocess.Popen([str(solver), *flags, str(full)],
                                    stdout=out, stderr=err,
                                    start_new_session=True)
            try:
                while proc.poll() is None:
                    peak = max(peak, rss_bytes(proc.pid))
                    elapsed = time.perf_counter() - started
                    if peak > cfg["peak_rss_cap_bytes"]:
                        guard = "RSS_CAP"
                    elif elapsed > cfg["external_wall_seconds"]:
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
        cpu_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        wall = time.perf_counter() - started
        raw = stdout_path.read_bytes()
        output = raw.decode("utf-8", errors="replace")
        terminal = [line.strip() for line in output.splitlines()
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
                               mtime=0) as zipped:
                zipped.write(raw)
        write_json(result_path, {
            "schema": "ecc2k130-263-x-freedom-ladder-solver-v1",
            "status": status, "candidate_id": None,
            "cell": stem, "policy": policy, "leaf": leaf, "width": width,
            "source_sha256": file_sha(HERE / "source.json"),
            "cells_sha256": file_sha(RUN / "cells.json"),
            "runner_sha256": file_sha(Path(__file__)),
            "formula_sha256": file_sha(full),
            "solver_sha256": file_sha(solver),
            "solver_version": version,
            "command_flags": flags,
            "exit_code": exit_code, "terminal_status_lines": terminal,
            "guard": guard, "wall_seconds": wall,
            "user_cpu_seconds": cpu_after.ru_utime - cpu_before.ru_utime,
            "system_cpu_seconds": cpu_after.ru_stime - cpu_before.ru_stime,
            "peak_sampled_rss_bytes": peak,
            "stdout_raw_sha256": sha(raw), "stdout_raw_bytes": len(raw),
            "stdout_archive_sha256": file_sha(stdout_archive),
            "stderr_sha256": file_sha(stderr_path),
        })
    print(json.dumps({"cell": stem, "status": status,
                      "wall_seconds": wall, "cpu_seconds":
                      cpu_after.ru_utime - cpu_before.ru_utime
                      + cpu_after.ru_stime - cpu_before.ru_stime,
                      "guard": guard}, sort_keys=True), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "solve", "all"))
    parser.add_argument("--cell")
    args = parser.parse_args()
    if args.action == "freeze":
        if args.cell is not None:
            parser.error("freeze does not take --cell")
        freeze()
    elif args.action == "solve":
        if args.cell is None:
            parser.error("solve requires --cell")
        solve(args.cell)
    else:
        if args.cell is not None:
            parser.error("all does not take --cell")
        _, _, frozen = frozen_cells()
        for stem in frozen["order"]:
            solve(stem)


if __name__ == "__main__":
    main()
