#!/usr/bin/env python3
"""Freeze and run exact W24 selector-coordinate cuts on Q1420 circuits."""

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
NATIVE = ROOT / "experiments/ecc2k130-263-native-w24-m6-20261010"
GROUP = ROOT / "experiments/ecc2k130-263-projective-s3-20261010"
ORDINARY = ROOT / "experiments/ecc2k130-263-bilinear-ordinary-q0-20261010/runs/R1"
CONTROL = ROOT / "experiments/ecc2k130-263-bilinear-leaf-20261010/runs/R1"
LADDER = ROOT / "experiments/ecc2k130-263-x-freedom-ladder-20261010/runs/R1"
sys.path.insert(0, str(NATIVE))
import field as ref  # noqa: E402
sys.path.insert(0, str(GROUP))
import binary_group as group  # noqa: E402

POLICIES = ("source", "descendant_native")
VARIANTS = ("selector_only", "coordinate_cut")
CONTROL_ORDER = tuple(f"control_{policy}_x{leaf}"
                      for leaf in (0, 5) for policy in POLICIES)
ORDINARY_ORDER = tuple(f"ordinary_m{i:02d}_{policy}_{variant}"
                       for i in range(8) for policy in POLICIES
                       for variant in VARIANTS)
ORDER = CONTROL_ORDER + ORDINARY_ORDER
DEFAULT_MATRIX = {"maxmatrixrows": 2000, "maxmatrixcols": 1000,
                  "maxnummatrices": 5, "autodisablegauss": 1}


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


def source() -> dict:
    cfg = read(HERE / "source.json")
    if (cfg["schema"] != "ecc2k130-263-selector-cut-source-v1"
            or cfg["parent_commit"]
            != "af6dd1566d368880233418d040cf05d9d58807f8"
            or cfg["proposal_id"] != "Q1420"
            or cfg["candidate_id"] is not None
            or cfg["policies"] != list(POLICIES)
            or cfg["ordinary_mask_count"] != 8
            or cfg["ordinary_variants"] != list(VARIANTS)
            or cfg["control_leaves"] != [0, 5]
            or cfg["ordinary_leaf"] != 0
            or cfg["order"] != list(ORDER)
            or cfg["ordinary_max_conflicts"] != 2000
            or cfg["ordinary_internal_wall_seconds"] != 120
            or cfg["ordinary_external_wall_seconds"] != 45
            or cfg["control_max_conflicts"] != 20000
            or cfg["control_internal_wall_seconds"] != 30
            or cfg["control_external_wall_seconds"] != 40
            or cfg["peak_rss_cap_bytes"] != 4 * (1 << 30)
            or cfg["default_matrix"] != DEFAULT_MATRIX
            or cfg["solver_sha256"]
            != "a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac"
            or any(file_digest(ROOT / path) != expected
                   for path, expected in cfg["pins"].items())):
        raise ValueError("frozen source, protocol, or parent artifact changed")
    return cfg


def inverse_euclid(value: int) -> int:
    """Inverse in the pinned polynomial basis, independently checked below."""
    if not 0 < value <= ref.MASK:
        raise ValueError("nonzero field element required")
    left, right = value, ref.MODULUS
    x, y = 1, 0
    while left != 1:
        if left == 0:
            raise ArithmeticError("modulus is not coprime to field element")
        shift = left.bit_length() - right.bit_length()
        if shift < 0:
            left, right = right, left
            x, y = y, x
            shift = -shift
        left ^= right << shift
        x ^= y << shift
    result = ref.reduce(x)
    if ref.multiply(value, result) != 1:
        raise ArithmeticError("extended-Euclid inverse check failed")
    return result


def leaf(mask: int, policy: str, basis: list[int], halves: list[int]):
    alpha, b = ref.coefficients(policy)
    w = ref.parameter(basis, mask)
    u = ref.parameter(halves, mask)
    if not w or not u or ref.square(u) ^ u != w:
        raise ValueError("mask has invalid W24 parameter")
    z = inverse_euclid(w)
    if ref.trace(ref.multiply(alpha, z)):
        raise ValueError("mask is outside the rational W24 base")
    x = ref.multiply(alpha, 1 ^ inverse_euclid(u))
    if x == 0 or ref.multiply(u, x ^ alpha) != alpha:
        raise ArithmeticError("derived leaf x equation failed")
    rhs = x ^ ref.multiply(b, inverse_euclid(ref.square(x)))
    if ref.trace(rhs):
        raise ValueError("derived x has no rational y")
    h = ref.halftrace(rhs)
    if ref.square(h) ^ h != rhs:
        raise ArithmeticError("leaf y halftrace failed")
    point = (x, ref.multiply(x, h))
    if not group.on_curve(point, b):
        raise ArithmeticError("derived point is off curve")
    projected = group.times(point, 4, b)
    if projected is None:
        raise ValueError("mask has identity fourfold projection")
    return {"mask": mask, "w": w, "u": u, "x": x, "z": z,
            "raw_point": list(point), "fourfold_point": list(projected)}


def threshold(index: int, bound: int) -> int:
    if not 0 <= index < 8:
        raise ValueError("stratum outside frozen panel")
    lo, hi = 1, bound
    right = (15 - 2 * index) * bound**6
    while lo < hi:
        mid = (lo + hi) // 2
        if 16 * (bound - mid)**6 <= right:
            hi = mid
        else:
            lo = mid + 1
    return lo


def select_masks(cfg: dict):
    projective = read(GROUP / "CONFIG.json")
    bound = min(projective[p + "_last_selected_mask"] for p in POLICIES)
    basis = ref.basis()
    halves = [ref.halftrace(value) for value in basis]
    if len(basis) != 24 or any(ref.square(h) ^ h != b
                               for b, h in zip(basis, halves)):
        raise ArithmeticError("W24 basis or halftrace changed")
    chosen, used = [], set()
    start = time.perf_counter()
    for index in range(cfg["ordinary_mask_count"]):
        target, candidate, attempts = threshold(index, bound), None, 0
        candidate = target
        while candidate <= bound:
            attempts += 1
            if candidate in used:
                candidate += 1
                continue
            try:
                values = {policy: leaf(candidate, policy, basis, halves)
                          for policy in POLICIES}
            except ValueError:
                candidate += 1
                continue
            used.add(candidate)
            chosen.append({"stratum": index, "threshold": target,
                           "mask": candidate, "tested_masks": attempts,
                           "curves": values})
            break
        else:
            raise RuntimeError("no common usable mask below cutoff")
    return {"bound": bound, "masks": chosen,
            "selection_wall_seconds": time.perf_counter() - start}


def base(policy: str, kind: str):
    if kind == "control":
        receipt_path = CONTROL / f"{policy}_wz_only_base.json"
        archive = CONTROL / f"{policy}_wz_only_base.xcnf.gz"
        named_path = CONTROL / f"{policy}_wz_only_inputs.json"
        raw_key, gzip_key = "formula_raw_sha256", "formula_gzip_sha256"
    elif kind == "ordinary":
        receipt_path = ORDINARY / f"{policy}_wz_only.formula.json"
        archive = ORDINARY / f"{policy}_wz_only.xcnf.gz"
        named_path = ORDINARY / f"{policy}_wz_only.inputs.json"
        raw_key, gzip_key = "formula_raw_sha256", "formula_gzip_sha256"
    else:
        raise ValueError("unknown circuit kind")
    receipt, named = read(receipt_path), read(named_path)
    if (receipt[raw_key] is None
            or receipt[gzip_key] != file_digest(archive)
            or len(named) != receipt.get("input_vars_count",
                                          receipt.get("named_inputs_count"))):
        raise ValueError("base formula receipt changed")
    return receipt, named, archive


def signed_units(named: dict, prefix: str, size: int, value: int) -> list[int]:
    return [named[f"{prefix}:{i}"] if value & (1 << i)
            else -named[f"{prefix}:{i}"] for i in range(size)]


def unit_bytes(units: list[int]) -> bytes:
    if len({abs(value) for value in units}) != len(units):
        raise ValueError("duplicate unit variable")
    return b"".join(f"{value} 0\n".encode()
                    for value in sorted(units))


def parse_units(data: bytes) -> dict[int, bool]:
    fixed = {}
    for raw in data.splitlines():
        words = raw.split()
        if len(words) != 2 or words[1] != b"0":
            raise ValueError("malformed archived unit clause")
        value = int(words[0])
        if not value or abs(value) in fixed:
            raise ValueError("zero or duplicate unit variable")
        fixed[abs(value)] = value > 0
    return fixed


def control_delta(policy: str, target_leaf: int, named: dict,
                  basis: list[int], halves: list[int]) -> tuple[bytes, int]:
    stem = f"{policy}_x{target_leaf}_w131"
    original = (LADDER / f"{stem}.units.txt").read_bytes()
    fixed = parse_units(original)
    selectors = [named[f"s{target_leaf}:{i}"] for i in range(24)]
    mask = sum(int(fixed[variable]) << i for i, variable in enumerate(selectors))
    if any(named[f"x{target_leaf}:{i}"] in fixed for i in range(131)):
        raise ValueError("archived full-x release contains x hint")
    derived = leaf(mask, policy, basis, halves)
    for i in range(131):
        variable = named[f"z{target_leaf}:{i}"]
        if variable not in fixed or fixed[variable] != bool(derived["z"] & (1 << i)):
            raise ValueError("archived z differs from selector-derived inverse")
    return original + unit_bytes(signed_units(
        named, f"x{target_leaf}", 131, derived["x"])), mask


def ordinary_delta(policy: str, variant: str, mask: int, named: dict,
                   derived: dict) -> bytes:
    units = signed_units(named, "s0", 24, mask)
    if variant == "coordinate_cut":
        units += signed_units(named, "x0", 131, derived["x"])
        units += signed_units(named, "z0", 131, derived["z"])
    elif variant != "selector_only":
        raise ValueError("unknown branch variant")
    return unit_bytes(units)


def decompress(archive: Path, expected: dict, out: Path) -> None:
    with gzip.open(archive, "rb") as source, out.open("xb") as target:
        shutil.copyfileobj(source, target, length=1 << 20)
    if (file_digest(out) != expected["formula_raw_sha256"]
            or out.stat().st_size != expected["formula_raw_bytes"]):
        raise ValueError("base archive failed raw XCNF replay")


def compose(base_path: Path, delta: bytes, output: Path):
    lines = delta.splitlines()
    with base_path.open("rb") as source, output.open("xb") as target:
        header = source.readline().split()
        if len(header) != 4 or header[:2] != [b"p", b"cnf"]:
            raise ValueError("invalid base XCNF header")
        variables, constraints = map(int, header[2:])
        target.write(f"p cnf {variables} {constraints + len(lines)}\n".encode())
        shutil.copyfileobj(source, target, length=1 << 20)
        target.write(delta)
    return variables, constraints + len(lines)


def cell_parts(stem: str, masks: list[dict]):
    if stem in CONTROL_ORDER:
        for policy in POLICIES:
            for target_leaf in (0, 5):
                if stem == f"control_{policy}_x{target_leaf}":
                    return "control", policy, "coordinate_cut", None, target_leaf
    for index, mask in enumerate(masks):
        for policy in POLICIES:
            for variant in VARIANTS:
                if stem == f"ordinary_m{index:02d}_{policy}_{variant}":
                    return "ordinary", policy, variant, mask, 0
    raise ValueError("cell outside frozen panel")


def freeze() -> None:
    cfg = source()
    if RUN.exists():
        raise FileExistsError("frozen panel is write-once")
    selection = select_masks(cfg)
    if len(selection["masks"]) != 8:
        raise AssertionError("wrong common-mask count")
    RUN.mkdir(parents=True)
    write_once(RUN / "masks.json", {
        "schema": "ecc2k130-263-selector-cut-masks-v1",
        "status": "FROZEN_COMMON_USABLE_MASKS",
        "source_sha256": file_digest(HERE / "source.json"),
        **selection,
    })
    basis = ref.basis()
    halves = [ref.halftrace(value) for value in basis]
    rows = {}
    with tempfile.TemporaryDirectory(prefix="q1420-selector-freeze-",
                                     dir="/private/tmp") as temporary:
        scratch = Path(temporary)
        for kind in ("control", "ordinary"):
            for policy in POLICIES:
                receipt, named, archive = base(policy, kind)
                raw = scratch / f"{kind}_{policy}.xcnf"
                decompress(archive, receipt, raw)
                for stem in ORDER:
                    entry_kind, entry_policy, variant, mask_row, target_leaf = (
                        cell_parts(stem, selection["masks"]))
                    if (entry_kind, entry_policy) != (kind, policy):
                        continue
                    if kind == "control":
                        delta, mask = control_delta(
                            policy, target_leaf, named, basis, halves)
                        archived = read(LADDER / "cells.json")["cells"][
                            f"{policy}_x{target_leaf}_w131"]
                        original = (LADDER / f"{policy}_x{target_leaf}_w131.units.txt").read_bytes()
                        check = scratch / "archived-control.xcnf"
                        compose(raw, original, check)
                        if file_digest(check) != archived["formula_sha256"]:
                            raise ValueError("archived full-x control changed")
                        check.unlink()
                        mask_index = None
                    else:
                        assert mask_row is not None
                        mask = mask_row["mask"]
                        mask_index = mask_row["stratum"]
                        delta = ordinary_delta(policy, variant, mask, named,
                                               mask_row["curves"][policy])
                    units_path = RUN / f"{stem}.units.txt"
                    units_path.write_bytes(delta)
                    full = scratch / f"{stem}.xcnf"
                    variables, constraints = compose(raw, delta, full)
                    rows[stem] = {
                        "kind": kind, "policy": policy, "variant": variant,
                        "mask_index": mask_index, "mask": mask,
                        "leaf": target_leaf,
                        "base_gzip_sha256": file_digest(archive),
                        "base_raw_sha256": receipt["formula_raw_sha256"],
                        "named_inputs_sha256": file_digest(
                            CONTROL / f"{policy}_wz_only_inputs.json"
                            if kind == "control" else
                            ORDINARY / f"{policy}_wz_only.inputs.json"),
                        "unit_count": len(delta.splitlines()),
                        "units_sha256": digest(delta),
                        "formula_sha256": file_digest(full),
                        "formula_bytes": full.stat().st_size,
                        "variables": variables,
                        "constraints": constraints,
                    }
                    full.unlink()
                raw.unlink()
    write_once(RUN / "cells.json", {
        "schema": "ecc2k130-263-selector-cut-cells-v1",
        "status": "FROZEN_36_EXACT_INPUTS",
        "candidate_id": None,
        "source_sha256": file_digest(HERE / "source.json"),
        "runner_sha256": file_digest(Path(__file__)),
        "masks_sha256": file_digest(RUN / "masks.json"),
        "order": list(ORDER), "cells": rows,
    })
    print(json.dumps({"status": "FROZEN_36_EXACT_INPUTS",
                      "masks": [row["mask"] for row in selection["masks"]],
                      "cells": len(rows)}, sort_keys=True))


def frozen():
    cfg = source()
    masks = read(RUN / "masks.json")
    panel = read(RUN / "cells.json")
    if (masks["schema"] != "ecc2k130-263-selector-cut-masks-v1"
            or masks["status"] != "FROZEN_COMMON_USABLE_MASKS"
            or masks["source_sha256"] != file_digest(HERE / "source.json")
            or len(masks["masks"]) != 8
            or panel["schema"] != "ecc2k130-263-selector-cut-cells-v1"
            or panel["status"] != "FROZEN_36_EXACT_INPUTS"
            or panel["order"] != list(ORDER)
            or set(panel["cells"]) != set(ORDER)
            or panel["source_sha256"] != file_digest(HERE / "source.json")
            or panel["runner_sha256"] != file_digest(Path(__file__))
            or panel["masks_sha256"] != file_digest(RUN / "masks.json")):
        raise ValueError("frozen panel or source changed")
    return cfg, masks, panel


def flags(cfg: dict, kind: str) -> list[str]:
    if kind == "control":
        return ["--threads=1", f"--maxconfl={cfg['control_max_conflicts']}",
                f"--maxtime={cfg['control_internal_wall_seconds']}",
                "--verb=1", "--printsol=1"]
    if kind == "ordinary":
        return (["--threads=1", "--verb=1", "--printsol=1"]
                + [f"--{key}={value}" for key, value in DEFAULT_MATRIX.items()]
                + [f"--maxconfl={cfg['ordinary_max_conflicts']}",
                   f"--maxtime={cfg['ordinary_internal_wall_seconds']}"])
    raise ValueError("unknown cell kind")


def rss_bytes(pid: int) -> int:
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("RSS sampler unavailable: " + result.stderr.strip())
    return int(result.stdout.strip() or 0) * 1024


def solve(stem: str) -> None:
    cfg, masks, panel = frozen()
    if stem not in panel["cells"]:
        raise ValueError("cell outside frozen panel")
    expected = panel["cells"][stem]
    kind, policy, variant, mask_row, target_leaf = cell_parts(
        stem, masks["masks"])
    if ((expected["kind"], expected["policy"], expected["variant"],
         expected["leaf"], expected["mask"])
            != (kind, policy, variant, target_leaf,
                mask_row["mask"] if mask_row else expected["mask"])):
        raise ValueError("cell metadata differs from frozen plan")
    receipt_path = RUN / f"{stem}.solver.json"
    stdout_archive = RUN / f"{stem}.stdout.txt.gz"
    stderr_path = RUN / f"{stem}.stderr.txt"
    if any(path.exists() for path in (receipt_path, stdout_archive, stderr_path)):
        raise FileExistsError("solver evidence already exists")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat unavailable")
    solver = Path(solver_name).resolve()
    if file_digest(solver) != cfg["solver_sha256"]:
        raise ValueError("solver binary differs")
    version = subprocess.run([str(solver), "--version"], text=True,
                             capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version differs")
    if rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS sampler failed before solver launch")
    preparation_started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="q1420-selector-solve-",
                                     dir="/private/tmp") as temporary:
        scratch = Path(temporary)
        base_row, _, archive = base(policy, kind)
        raw = scratch / "base.xcnf"
        full = scratch / "input.xcnf"
        stdout = scratch / "stdout.txt"
        decompress(archive, base_row, raw)
        delta = (RUN / f"{stem}.units.txt").read_bytes()
        variables, constraints = compose(raw, delta, full)
        if (digest(delta) != expected["units_sha256"]
                or file_digest(full) != expected["formula_sha256"]
                or full.stat().st_size != expected["formula_bytes"]
                or variables != expected["variables"]
                or constraints != expected["constraints"]):
            raise ValueError("solver input differs from precommitted hash")
        preparation_wall = time.perf_counter() - preparation_started
        argv = flags(cfg, kind)
        external = cfg[f"{kind}_external_wall_seconds"]
        started = time.perf_counter()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        peak, guard = 0, None
        with stdout.open("xb") as out, stderr_path.open("x") as err:
            proc = subprocess.Popen([str(solver), *argv, str(full)],
                                    stdout=out, stderr=err, start_new_session=True)
            try:
                while proc.poll() is None:
                    peak = max(peak, rss_bytes(proc.pid))
                    if peak > cfg["peak_rss_cap_bytes"]:
                        guard = "RSS_CAP"
                    elif time.perf_counter() - started > external:
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
        raw_output = stdout.read_bytes()
        terminal = [line.strip() for line in
                    raw_output.decode(errors="replace").splitlines()
                    if line.startswith("s ")]
        if guard == "RSS_CAP":
            status = "OOM_GUARD"
        elif guard == "WALL_CAP":
            status = "BOUNDED_UNKNOWN"
        elif terminal == ["s SATISFIABLE"] and exit_code == 10:
            status = "SAT_UNVERIFIED"
        elif terminal == ["s UNSATISFIABLE"] and exit_code == 20:
            status = "UNSAT"
        elif terminal == ["s INDETERMINATE"] and exit_code == 15:
            status = "BOUNDED_UNKNOWN"
        else:
            status = "PRODUCER_FAILURE"
        with stdout_archive.open("xb") as target:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target,
                               mtime=0) as compressed:
                compressed.write(raw_output)
        write_once(receipt_path, {
            "schema": "ecc2k130-263-selector-cut-solver-v1",
            "cell": stem, "kind": kind, "policy": policy,
            "variant": variant, "mask": expected["mask"],
            "candidate_id": None, "status": status, "guard": guard,
            "source_sha256": file_digest(HERE / "source.json"),
            "cells_sha256": file_digest(RUN / "cells.json"),
            "runner_sha256": file_digest(Path(__file__)),
            "formula_sha256": file_digest(full),
            "solver_sha256": file_digest(solver), "solver_version": version,
            "command_flags": argv, "exit_code": exit_code,
            "terminal_status_lines": terminal,
            "preparation_wall_seconds": preparation_wall,
            "solver_wall_seconds": wall,
            "user_cpu_seconds": after.ru_utime - before.ru_utime,
            "system_cpu_seconds": after.ru_stime - before.ru_stime,
            "peak_sampled_rss_bytes": peak,
            "stdout_raw_sha256": digest(raw_output),
            "stdout_raw_bytes": len(raw_output),
            "stdout_archive_sha256": file_digest(stdout_archive),
            "stderr_sha256": file_digest(stderr_path),
        })
    print(json.dumps({"cell": stem, "status": status,
                      "guard": guard, "solver_wall_seconds": wall},
                     sort_keys=True), flush=True)


def main() -> None:
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
        _, _, panel = frozen()
        for stem in panel["order"]:
            solve(stem)


if __name__ == "__main__":
    main()
