#!/usr/bin/env python3
"""Freeze and run paired Q1420 free-selector identity XCNFs."""

from __future__ import annotations

import argparse
import ctypes
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
PARENT = ROOT / "experiments/ecc2k130-263-selector-cut-20261010"
NATIVE = ROOT / "experiments/ecc2k130-263-native-w24-m6-20261010"
CONTROL = ROOT / "experiments/ecc2k130-263-bilinear-leaf-20261010/runs/R1"
ORDINARY = ROOT / "experiments/ecc2k130-263-bilinear-ordinary-q0-20261010/runs/R1"
sys.path.insert(0, str(NATIVE))
import field as ref  # noqa: E402

POLICIES = ("source", "descendant_native")
KINDS = ("control", "ordinary")
VARIANTS = ("base", "identity")
ORDER = tuple(f"{kind}_{policy}_{variant}" for kind in KINDS
              for policy in POLICIES for variant in VARIANTS)
GAUSS = ("--maxmatrixrows=2000", "--maxmatrixcols=1000",
         "--maxnummatrices=5", "--autodisablegauss=1")
GATES = ref.DEGREE * ref.DEGREE


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def write_once(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as out:
        json.dump(obj, out, indent=2, sort_keys=True)
        out.write("\n")


def config() -> dict:
    cfg = read(HERE / "source.json")
    if (cfg["schema"] != "ecc2k130-free-identity-source-v1"
            or cfg["parent_commit"] != "5e972b6284bbf8f4108e49c723d45f873052045c"
            or cfg["order"] != list(ORDER)
            or cfg["candidate_id"] is not None
            or cfg["workload_id"] != "eee7f6ee5f6b"
            or cfg["solver_sha256"]
            != "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"
            or cfg["rss_cap_bytes"] != 4 * (1 << 30)
            or cfg["conflicts"] != {"control": 20000, "ordinary": 2000}
            or cfg["external_wall_seconds"] != {"control": 40, "ordinary": 45}
            or cfg["internal_wall_seconds"] != {"control": 30, "ordinary": 120}
            or any(sha(ROOT / name) != value for name, value in cfg["pins"].items())):
        raise ValueError("source identity or protocol changed")
    return cfg


def paths(kind: str, policy: str):
    if kind == "control":
        folder = CONTROL
        stem = f"{policy}_wz_only"
        return (folder / f"{stem}_base.xcnf.gz",
                folder / f"{stem}_base.json",
                folder / f"{stem}_inputs.json",
                PARENT / "runs/R1" / f"control_{policy}_x0.units.txt")
    folder = ORDINARY
    stem = f"{policy}_wz_only"
    return (folder / f"{stem}.xcnf.gz",
            folder / f"{stem}.formula.json",
            folder / f"{stem}.inputs.json", None)


def flags(kind: str, cfg: dict) -> list[str]:
    common = ["--threads=1", "--verb=1", "--printsol=1"]
    if kind == "ordinary":
        common += list(GAUSS)
    return common + [f"--maxconfl={cfg['conflicts'][kind]}",
                     f"--maxtime={cfg['internal_wall_seconds'][kind]}"]


def identity_lines(named: dict, old_vars: int, alpha: int):
    """Emit exact AND Tseitin gates and 131 native-XOR field equations."""
    products = [[] for _ in range(ref.DEGREE)]
    transformed = [ref.multiply(alpha, 1 << i)
                   for i in range(ref.DEGREE)]
    for i in range(ref.DEGREE):
        x = named[f"x0:{i}"]
        for j in range(ref.DEGREE):
            z = named[f"z0:{j}"]
            aux = old_vars + 1 + i * ref.DEGREE + j
            yield f"-{x} -{z} {aux} 0\n".encode()
            yield f"{x} -{aux} 0\n".encode()
            yield f"{z} -{aux} 0\n".encode()
            coefficient = ref.multiply(transformed[i], 1 << j)
            while coefficient:
                low = coefficient & -coefficient
                products[low.bit_length() - 1].append(aux)
                coefficient ^= low
    squares = [ref.square(1 << i) for i in range(ref.DEGREE)]
    constant = ref.square(alpha)
    for bit in range(ref.DEGREE):
        literals = products[bit] + [named[f"x0:{i}"]
                                    for i, word in enumerate(squares)
                                    if (word >> bit) & 1]
        if not literals:
            raise ValueError("empty identity output equation")
        # Extended DIMACS native XOR records demand signed-literal parity 1.
        # Flip one literal when the required parity of positive variables is 0.
        if not ((constant >> bit) & 1):
            literals[0] = -literals[0]
        yield ("x" + " ".join(map(str, literals)) + " 0\n").encode()


def build(kind: str, policy: str, variant: str, out: Path):
    archive, receipt_path, named_path, unit_path = paths(kind, policy)
    receipt, named = read(receipt_path), read(named_path)
    if sha(archive) != receipt["formula_gzip_sha256"]:
        raise ValueError("base archive hash mismatch")
    delta = unit_path.read_bytes() if unit_path else b""
    if delta and (not delta.endswith(b"\n") or
                  any(not line.endswith(b" 0") for line in delta.splitlines())):
        raise ValueError("malformed frozen unit delta")
    with gzip.open(archive, "rb") as stream:
        header = stream.readline().split()
        if len(header) != 4 or header[:2] != [b"p", b"cnf"]:
            raise ValueError("invalid XCNF header")
        old_vars, old_constraints = map(int, header[2:])
        added = (3 * GATES + ref.DEGREE) if variant == "identity" else 0
        variables = old_vars + (GATES if variant == "identity" else 0)
        constraints = old_constraints + added + len(delta.splitlines())
        base_hasher = hashlib.sha256()
        base_hasher.update(b" ".join(header) + b"\n")
        with out.open("xb") as target:
            target.write(f"p cnf {variables} {constraints}\n".encode())
            for block in iter(lambda: stream.read(1 << 20), b""):
                base_hasher.update(block)
                target.write(block)
            if variant == "identity":
                alpha, _ = ref.coefficients(policy)
                for line in identity_lines(named, old_vars, alpha):
                    target.write(line)
            target.write(delta)
    if base_hasher.hexdigest() != receipt["formula_raw_sha256"]:
        raise ValueError("base raw formula hash mismatch")
    return {"variables": variables, "constraints": constraints,
            "formula_sha256": sha(out), "formula_bytes": out.stat().st_size,
            "base_raw_sha256": receipt["formula_raw_sha256"],
            "base_archive_sha256": sha(archive),
            "named_sha256": sha(named_path),
            "delta_sha256": sha(unit_path) if unit_path else None,
            "delta_lines": len(delta.splitlines())}


def freeze() -> None:
    cfg = config()
    if RUN.exists():
        raise FileExistsError("frozen panel is write-once")
    rows = {}
    with tempfile.TemporaryDirectory(prefix="q1420-freeze-", dir="/private/tmp") as td:
        for stem in ORDER:
            kind, policy, variant = stem.split("_", 1)[0], None, None
            for known in POLICIES:
                for option in VARIANTS:
                    if stem == f"{kind}_{known}_{option}":
                        policy, variant = known, option
            if policy is None:
                raise ValueError("unexpected cell")
            path = Path(td) / f"{stem}.xcnf"
            row = build(kind, policy, variant, path)
            row.update({"kind": kind, "policy": policy, "variant": variant,
                        "flags": flags(kind, cfg)})
            rows[stem] = row
    write_once(RUN / "cells.json", {
        "schema": "ecc2k130-free-identity-cells-v1",
        "status": "FROZEN_8_EXACT_XCNFS", "candidate_id": None,
        "source_sha256": sha(HERE / "source.json"),
        "runner_sha256": sha(Path(__file__)),
        "order": list(ORDER), "cells": rows})
    print(json.dumps({"status": "FROZEN_8_EXACT_XCNFS",
                      "cells": len(rows)}, sort_keys=True))


def rss_bytes(pid: int) -> int:
    if sys.platform != "darwin":
        raise RuntimeError("this local RSS sampler requires Darwin libproc")

    class TaskInfo(ctypes.Structure):
        _fields_ = [
            ("virtual_size", ctypes.c_uint64),
            ("resident_size", ctypes.c_uint64),
            ("total_user", ctypes.c_uint64),
            ("total_system", ctypes.c_uint64),
            ("threads_user", ctypes.c_uint64),
            ("threads_system", ctypes.c_uint64),
            *[(name, ctypes.c_int32) for name in (
                "policy", "faults", "pageins", "cow_faults", "messages_sent",
                "messages_received", "syscalls_mach", "syscalls_unix", "csw",
                "threadnum", "numrunning", "priority")],
        ]

    libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    libproc.proc_pidinfo.argtypes = [
        ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p,
        ctypes.c_int]
    libproc.proc_pidinfo.restype = ctypes.c_int
    info = TaskInfo()
    size = libproc.proc_pidinfo(pid, 4, 0, ctypes.byref(info),
                               ctypes.sizeof(info))
    if size == 0:
        return 0  # The process may have exited between poll and sample.
    if size != ctypes.sizeof(info):
        raise RuntimeError("libproc returned incomplete task info")
    return info.resident_size


def solve(stem: str) -> None:
    cfg = config()
    panel = read(RUN / "cells.json")
    if (panel["status"] != "FROZEN_8_EXACT_XCNFS"
            or panel["order"] != list(ORDER)
            or panel["source_sha256"] != sha(HERE / "source.json")
            or panel["runner_sha256"] != sha(Path(__file__))
            or stem not in panel["cells"]):
        raise ValueError("unfrozen panel")
    row = panel["cells"][stem]
    archive = RUN / f"{stem}.stdout.txt.gz"
    stderr = RUN / f"{stem}.stderr.txt"
    result_path = RUN / f"{stem}.solver.json"
    if any(path.exists() for path in (archive, stderr, result_path)):
        raise FileExistsError("solver evidence already exists")
    solver_path = shutil.which("cryptominisat5")
    if solver_path is None:
        raise FileNotFoundError("CryptoMiniSat missing")
    solver = Path(solver_path).resolve()
    if sha(solver) != cfg["solver_sha256"]:
        raise ValueError("solver binary changed")
    version = subprocess.run([str(solver), "--version"], capture_output=True,
                             text=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version changed")
    if rss_bytes(os.getpid()) <= 0:
        raise ValueError("RSS sampler unavailable")
    with tempfile.TemporaryDirectory(prefix="q1420-identity-", dir="/private/tmp") as td:
        path = Path(td) / "input.xcnf"
        stdout = Path(td) / "stdout.txt"
        started_prep = time.perf_counter()
        actual = build(row["kind"], row["policy"], row["variant"], path)
        prep_wall = time.perf_counter() - started_prep
        if any(actual[key] != row[key] for key in actual):
            raise ValueError("input differs from precommitted hash")
        started = time.perf_counter()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        peak = 0
        guard = None
        with stdout.open("xb") as out, stderr.open("x") as err:
            proc = subprocess.Popen([str(solver), *row["flags"], str(path)],
                                    stdout=out, stderr=err, start_new_session=True)
            try:
                while proc.poll() is None:
                    peak = max(peak, rss_bytes(proc.pid))
                    if peak > cfg["rss_cap_bytes"]:
                        guard = "RSS_CAP"
                    elif time.perf_counter() - started > cfg[
                            "external_wall_seconds"][row["kind"]]:
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
        wall = time.perf_counter() - started
        raw = stdout.read_bytes()
        terminal = [line.strip() for line in raw.decode(errors="replace").splitlines()
                    if line.startswith("s ")]
        if guard == "RSS_CAP":
            status = "OOM_GUARD"
        elif guard == "WALL_CAP":
            status = "BOUNDED_UNKNOWN"
        elif terminal == ["s SATISFIABLE"] and exit_code == 10:
            status = "SAT_UNVERIFIED"
        elif terminal == ["s UNSATISFIABLE"] and exit_code == 20:
            status = "UNSAT_REPORTED"
        elif terminal == ["s INDETERMINATE"] and exit_code == 15:
            status = "BOUNDED_UNKNOWN"
        else:
            status = "PRODUCER_FAILURE"
        with archive.open("xb") as target:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target,
                               mtime=0) as compressed:
                compressed.write(raw)
        write_once(result_path, {
            "schema": "ecc2k130-free-identity-solver-v1",
            "cell": stem, "status": status, "guard": guard,
            "candidate_id": None, "source_sha256": sha(HERE / "source.json"),
            "cells_sha256": sha(RUN / "cells.json"),
            "runner_sha256": sha(Path(__file__)),
            "formula_sha256": sha(path), "solver_sha256": sha(solver),
            "solver_version": version, "flags": row["flags"],
            "exit_code": exit_code, "terminal": terminal,
            "preparation_wall_seconds": prep_wall,
            "solver_wall_seconds": wall,
            "user_cpu_seconds": after.ru_utime - before.ru_utime,
            "system_cpu_seconds": after.ru_stime - before.ru_stime,
            "peak_sampled_rss_bytes": peak,
            "stdout_raw_sha256": hashlib.sha256(raw).hexdigest(),
            "stdout_raw_bytes": len(raw),
            "stdout_archive_sha256": sha(archive),
            "stderr_sha256": sha(stderr)})
    print(json.dumps({"cell": stem, "status": status, "guard": guard,
                      "wall_seconds": wall}, sort_keys=True), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "solve", "all"))
    parser.add_argument("--cell", choices=ORDER)
    args = parser.parse_args()
    if args.action == "freeze":
        if args.cell:
            parser.error("freeze takes no cell")
        freeze()
    elif args.action == "solve":
        if args.cell is None:
            parser.error("solve requires --cell")
        solve(args.cell)
    else:
        if args.cell:
            parser.error("all takes no cell")
        for stem in ORDER:
            solve(stem)


if __name__ == "__main__":
    main()
