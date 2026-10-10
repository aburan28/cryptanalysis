#!/usr/bin/env python3
"""Independently replay Q1420 selector-cut inputs, transcripts, and models."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "runs/R1"
NATIVE = ROOT / "experiments/ecc2k130-263-native-w24-m6-20261010"
GROUP = ROOT / "experiments/ecc2k130-263-projective-s3-20261010"
CONTROL = ROOT / "experiments/ecc2k130-263-bilinear-leaf-20261010/runs/R1"
LADDER = ROOT / "experiments/ecc2k130-263-x-freedom-ladder-20261010/runs/R1"
ORDINARY = ROOT / "experiments/ecc2k130-263-bilinear-ordinary-q0-20261010"
sys.path.insert(0, str(NATIVE))
import field as ref  # noqa: E402
sys.path.insert(0, str(GROUP))
import binary_group as group  # noqa: E402
sys.path.insert(0, str(ROOT / "experiments/ecc2k130-263-projective-s3-sat-20261010"))
from verify_model import parse_assignment, replay_signs, verify_xcnf  # noqa: E402
sys.path.insert(0, str(ORDINARY))
import audit as ordinary_audit  # noqa: E402

POLICIES = ("source", "descendant_native")
VARIANTS = ("selector_only", "coordinate_cut")
CONTROL_ORDER = tuple(f"control_{policy}_x{leaf}"
                      for leaf in (0, 5) for policy in POLICIES)
ORDER = CONTROL_ORDER + tuple(
    f"ordinary_m{i:02d}_{policy}_{variant}"
    for i in range(8) for policy in POLICIES for variant in VARIANTS)
DEFAULT_MATRIX = {"maxmatrixrows": 2000, "maxmatrixcols": 1000,
                  "maxnummatrices": 5, "autodisablegauss": 1}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def independent_leaf(mask: int, policy: str, basis: list[int], halves: list[int]):
    alpha, coefficient = ref.coefficients(policy)
    w = ref.parameter(basis, mask)
    u = ref.parameter(halves, mask)
    if w == 0 or u == 0 or ref.square(u) ^ u != w:
        raise ValueError("invalid trace-zero W24 parameter")
    z = ref.inverse(w)
    if ref.trace(ref.multiply(alpha, z)):
        raise ValueError("nonrational W24 mask")
    x = ref.multiply(alpha, 1 ^ ref.inverse(u))
    if x == 0 or ref.multiply(u, x ^ alpha) != alpha:
        raise ArithmeticError("W24 x identity failed")
    rhs = x ^ ref.multiply(coefficient, ref.inverse(ref.square(x)))
    if ref.trace(rhs):
        raise ValueError("W24 x has no rational y")
    y = ref.multiply(x, ref.halftrace(rhs))
    point = (x, y)
    if not group.on_curve(point, coefficient):
        raise ArithmeticError("derived point is off curve")
    projected = group.times(point, 4, coefficient)
    if projected is None:
        raise ValueError("identity fourfold projection")
    return {"mask": mask, "w": w, "u": u, "x": x, "z": z,
            "raw_point": list(point), "fourfold_point": list(projected)}


def threshold(index: int, bound: int) -> int:
    left, right = 1, bound
    limit = (15 - 2 * index) * bound**6
    while left < right:
        middle = (left + right) // 2
        if 16 * (bound - middle)**6 <= limit:
            right = middle
        else:
            left = middle + 1
    return left


def check_masks(source: dict, masks: dict):
    projective = read(GROUP / "CONFIG.json")
    bound = min(projective[p + "_last_selected_mask"] for p in POLICIES)
    basis = ref.basis()
    halves = [ref.halftrace(v) for v in basis]
    if (masks["schema"] != "ecc2k130-263-selector-cut-masks-v1"
            or masks["status"] != "FROZEN_COMMON_USABLE_MASKS"
            or masks["source_sha256"] != file_digest(HERE / "source.json")
            or masks["bound"] != bound
            or len(masks["masks"]) != source["ordinary_mask_count"]):
        raise ValueError("common-mask receipt differs")
    used = set()
    for index, row in enumerate(masks["masks"]):
        target = threshold(index, bound)
        candidate, attempts = target, 0
        while candidate <= bound:
            attempts += 1
            if candidate in used:
                candidate += 1
                continue
            try:
                values = {p: independent_leaf(candidate, p, basis, halves)
                          for p in POLICIES}
            except ValueError:
                candidate += 1
                continue
            break
        else:
            raise ValueError("no jointly usable mask in stratum")
        if (row["stratum"] != index or row["threshold"] != target
                or row["mask"] != candidate
                or row["tested_masks"] != attempts
                or row["curves"] != values):
            raise ValueError("selected mask or field derivation differs")
        used.add(candidate)
    return basis, halves


def signed_word(named: dict, name: str, value: int, size: int) -> list[int]:
    return [named[f"{name}:{bit}"] if value & (1 << bit)
            else -named[f"{name}:{bit}"] for bit in range(size)]


def unit_bytes(units: list[int]) -> bytes:
    if len({abs(value) for value in units}) != len(units):
        raise ValueError("duplicate fixed variable")
    return b"".join(f"{value} 0\n".encode() for value in sorted(units))


def parse_units(raw: bytes):
    values = {}
    for line in raw.splitlines():
        if not re.fullmatch(rb"-?[1-9][0-9]* 0", line):
            raise ValueError("malformed unit clause")
        literal = int(line.split()[0])
        if abs(literal) in values:
            raise ValueError("duplicate unit clause variable")
        values[abs(literal)] = literal > 0
    return values


def cell_parts(stem: str, masks: list[dict]):
    for leaf in (0, 5):
        for policy in POLICIES:
            if stem == f"control_{policy}_x{leaf}":
                return "control", policy, "coordinate_cut", None, leaf
    for index, mask in enumerate(masks):
        for policy in POLICIES:
            for variant in VARIANTS:
                if stem == f"ordinary_m{index:02d}_{policy}_{variant}":
                    return "ordinary", policy, variant, mask, 0
    raise ValueError("cell outside frozen panel")


def semantic_delta(stem: str, masks: list[dict], named: dict,
                   basis: list[int], halves: list[int]):
    kind, policy, variant, mask_row, leaf = cell_parts(stem, masks)
    if kind == "ordinary":
        assert mask_row is not None
        mask = mask_row["mask"]
        units = signed_word(named, "s0", mask, 24)
        if variant == "coordinate_cut":
            derivation = independent_leaf(mask, policy, basis, halves)
            units += signed_word(named, "x0", derivation["x"], 131)
            units += signed_word(named, "z0", derivation["z"], 131)
        return unit_bytes(units), mask
    original = (LADDER / f"{policy}_x{leaf}_w131.units.txt").read_bytes()
    fixed = parse_units(original)
    mask = sum(int(fixed[named[f"s{leaf}:{bit}"]]) << bit
               for bit in range(24))
    if any(named[f"x{leaf}:{bit}"] in fixed for bit in range(131)):
        raise ValueError("archived full-x cell contains x hint")
    derivation = independent_leaf(mask, policy, basis, halves)
    for bit in range(131):
        variable = named[f"z{leaf}:{bit}"]
        if fixed.get(variable) != bool(derivation["z"] & (1 << bit)):
            raise ValueError("archived z differs from selector-derived z")
    return (original + unit_bytes(signed_word(
        named, f"x{leaf}", derivation["x"], 131))), mask


def compose(raw_base: Path, delta: bytes, full: Path):
    with raw_base.open("rb") as source, full.open("xb") as target:
        header = source.readline().split()
        if len(header) != 4 or header[:2] != [b"p", b"cnf"]:
            raise ValueError("invalid XCNF header")
        variables, constraints = map(int, header[2:])
        target.write(f"p cnf {variables} {constraints + len(delta.splitlines())}\n".encode())
        shutil.copyfileobj(source, target, length=1 << 20)
        target.write(delta)
    return variables, constraints + len(delta.splitlines())


def progress(output: str):
    restarts = [line for line in output.splitlines()
                if line.startswith("c rst ")]
    conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", output,
                           re.MULTILINE)
    return {"restart_rows": len(restarts),
            "restart_rows_sha256": digest(
                "\n".join(restarts).encode() + (b"\n" if restarts else b"")),
            "final_conflicts": int(conflicts[-1]) if conflicts else None,
            "last_restart_row": restarts[-1] if restarts else None}


def expected_flags(source: dict, kind: str):
    if kind == "control":
        return ["--threads=1",
                f"--maxconfl={source['control_max_conflicts']}",
                f"--maxtime={source['control_internal_wall_seconds']}",
                "--verb=1", "--printsol=1"]
    return (["--threads=1", "--verb=1", "--printsol=1"]
            + [f"--{key}={value}" for key, value in DEFAULT_MATRIX.items()]
            + [f"--maxconfl={source['ordinary_max_conflicts']}",
               f"--maxtime={source['ordinary_internal_wall_seconds']}"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    source = read(HERE / "source.json")
    masks = read(RUN / "masks.json")
    cells = read(RUN / "cells.json")
    if (source["schema"] != "ecc2k130-263-selector-cut-source-v1"
            or source["parent_commit"]
            != "af6dd1566d368880233418d040cf05d9d58807f8"
            or source["default_matrix"] != DEFAULT_MATRIX
            or source["order"] != list(ORDER)
            or source["candidate_id"] is not None
            or source["workload_id"] != "eee7f6ee5f6b"
            or cells["schema"] != "ecc2k130-263-selector-cut-cells-v1"
            or cells["status"] != "FROZEN_36_EXACT_INPUTS"
            or cells["order"] != list(ORDER)
            or set(cells["cells"]) != set(ORDER)
            or cells["source_sha256"] != file_digest(HERE / "source.json")
            or cells["runner_sha256"] != file_digest(HERE / "experiment.py")
            or cells["masks_sha256"] != file_digest(RUN / "masks.json")):
        raise ValueError("frozen source or cell panel changed")
    for path, sha in source["pins"].items():
        if file_digest(ROOT / path) != sha:
            raise ValueError("pinned archive or source changed: " + path)
    basis, halves = check_masks(source, masks)
    witness = read(ROOT / "experiments/ecc2k130-263-distinct-s3-control-20261010/runs/R1/witness.json")
    ordinary_cfg = read(ORDINARY / "CONFIG.json")
    rows = {}
    with tempfile.TemporaryDirectory(prefix="q1420-selector-audit-",
                                     dir="/private/tmp") as temporary:
        scratch = Path(temporary)
        bases = {}
        for kind in ("control", "ordinary"):
            for policy in POLICIES:
                folder = CONTROL if kind == "control" else ORDINARY / "runs/R1"
                archive = folder / (f"{policy}_wz_only_base.xcnf.gz"
                                    if kind == "control" else
                                    f"{policy}_wz_only.xcnf.gz")
                named_path = folder / (f"{policy}_wz_only_inputs.json"
                                       if kind == "control" else
                                       f"{policy}_wz_only.inputs.json")
                receipt_path = folder / (f"{policy}_wz_only_base.json"
                                         if kind == "control" else
                                         f"{policy}_wz_only.formula.json")
                receipt = read(receipt_path)
                named = read(named_path)
                base = scratch / f"{kind}_{policy}.xcnf"
                with gzip.open(archive, "rb") as stream, base.open("xb") as out:
                    shutil.copyfileobj(stream, out, length=1 << 20)
                if (file_digest(archive) != receipt["formula_gzip_sha256"]
                        or file_digest(base) != receipt["formula_raw_sha256"]
                        or base.stat().st_size != receipt["formula_raw_bytes"]):
                    raise ValueError("archived base XCNF does not replay")
                bases[kind, policy] = (base, archive, named_path, named, receipt)
        for stem in ORDER:
            cell = cells["cells"][stem]
            kind, policy, variant, mask_row, leaf = cell_parts(
                stem, masks["masks"])
            base, archive, named_path, named, receipt = bases[kind, policy]
            delta, mask = semantic_delta(
                stem, masks["masks"], named, basis, halves)
            saved_delta = RUN / f"{stem}.units.txt"
            if (saved_delta.read_bytes() != delta
                    or digest(delta) != cell["units_sha256"]
                    or len(delta.splitlines()) != cell["unit_count"]
                    or cell["kind"] != kind or cell["policy"] != policy
                    or cell["variant"] != variant or cell["leaf"] != leaf
                    or cell["mask"] != mask
                    or cell["mask_index"] != (
                        mask_row["stratum"] if mask_row else None)
                    or cell["base_gzip_sha256"] != file_digest(archive)
                    or cell["base_raw_sha256"] != file_digest(base)
                    or cell["named_inputs_sha256"] != file_digest(named_path)):
                raise ValueError("cell unit delta or metadata differs")
            full = scratch / f"{stem}.xcnf"
            variables, constraints = compose(base, delta, full)
            if (file_digest(full) != cell["formula_sha256"]
                    or full.stat().st_size != cell["formula_bytes"]
                    or variables != cell["variables"]
                    or constraints != cell["constraints"]):
                raise ValueError("precommitted full XCNF hash differs")
            result_path = RUN / f"{stem}.solver.json"
            result = read(result_path)
            stdout_archive = RUN / f"{stem}.stdout.txt.gz"
            stderr_path = RUN / f"{stem}.stderr.txt"
            with gzip.open(stdout_archive, "rb") as stream:
                raw_output = stream.read()
            output = raw_output.decode(errors="replace")
            terminal = [line.strip() for line in output.splitlines()
                        if line.startswith("s ")]
            if (result["schema"] != "ecc2k130-263-selector-cut-solver-v1"
                    or result["cell"] != stem or result["kind"] != kind
                    or result["policy"] != policy
                    or result["variant"] != variant
                    or result["mask"] != mask
                    or result["candidate_id"] is not None
                    or result["source_sha256"] != file_digest(HERE / "source.json")
                    or result["cells_sha256"] != file_digest(RUN / "cells.json")
                    or result["runner_sha256"] != file_digest(HERE / "experiment.py")
                    or result["formula_sha256"] != cell["formula_sha256"]
                    or result["solver_sha256"] != source["solver_sha256"]
                    or result["command_flags"] != expected_flags(source, kind)
                    or result["terminal_status_lines"] != terminal
                    or result["stdout_raw_sha256"] != digest(raw_output)
                    or result["stdout_raw_bytes"] != len(raw_output)
                    or result["stdout_archive_sha256"] != file_digest(stdout_archive)
                    or result["stderr_sha256"] != file_digest(stderr_path)
                    or result["solver_wall_seconds"]
                    > source[f"{kind}_external_wall_seconds"] + 3
                    or (result["peak_sampled_rss_bytes"]
                        > source["peak_rss_cap_bytes"]
                        and result["guard"] != "RSS_CAP")):
                raise ValueError("solver receipt or raw transcript differs")
            status = result["status"]
            search = progress(output)
            model = relation = None
            if status == "SAT_UNVERIFIED":
                if terminal != ["s SATISFIABLE"] or result["exit_code"] != 10:
                    raise ValueError("SAT lacks complete terminal result")
                values = parse_assignment(output, variables)
                model = verify_xcnf(full, values)
                if kind == "control":
                    relation = replay_signs(
                        policy, named, receipt["target_selector_variables"],
                        witness["policies"][policy], values)
                else:
                    relation = ordinary_audit.replay_group(
                        policy, named, receipt["target_selector_variables"],
                        values, ordinary_cfg)
                status = "SAT_VERIFIED_GROUP"
            elif status == "BOUNDED_UNKNOWN":
                if not (result["guard"] == "WALL_CAP" or
                        terminal == ["s INDETERMINATE"] and
                        result["exit_code"] == 15):
                    raise ValueError("bounded result lacks recorded cap")
                if not search["restart_rows"] and not search["final_conflicts"]:
                    raise ValueError("bounded result lacks search evidence")
            elif status == "OOM_GUARD":
                if result["guard"] != "RSS_CAP":
                    raise ValueError("OOM status lacks guard")
            elif status == "UNSAT":
                if terminal != ["s UNSATISFIABLE"] or result["exit_code"] != 20:
                    raise ValueError("UNSAT lacks complete terminal result")
                if kind == "control":
                    raise ValueError("UNSAT contradicts archived positive control")
                status = "UNSAT_REPORTED"
            elif status != "PRODUCER_FAILURE":
                raise ValueError("unknown solver status")
            rows[stem] = {
                "kind": kind, "policy": policy, "variant": variant,
                "mask": mask, "status": status,
                "raw_status": result["status"],
                "guard": result["guard"], "exit_code": result["exit_code"],
                "preparation_wall_seconds": result["preparation_wall_seconds"],
                "solver_wall_seconds": result["solver_wall_seconds"],
                "cpu_seconds": result["user_cpu_seconds"]
                               + result["system_cpu_seconds"],
                "peak_sampled_rss_bytes": result["peak_sampled_rss_bytes"],
                "progress": search,
                "formula_sha256": cell["formula_sha256"],
                "solver_receipt_sha256": file_digest(result_path),
                "stdout_archive_sha256": file_digest(stdout_archive),
                "xcnf_checks": model, "group_replay": relation,
                "verified_decomposition": relation is not None,
                "novel_rank": None,
            }
            full.unlink()
    audit = {
        "schema": "ecc2k130-263-selector-cut-audit-v1",
        "status": "PASS_INPUTS_TRANSCRIPTS_AND_MODELS",
        "candidate_id": None,
        "workload_id": source["workload_id"],
        "source_sha256": file_digest(HERE / "source.json"),
        "masks_sha256": file_digest(RUN / "masks.json"),
        "cells_sha256": file_digest(RUN / "cells.json"),
        "auditor_sha256": file_digest(Path(__file__)),
        "rows": rows,
    }
    data = json.dumps(audit, sort_keys=True, indent=2) + "\n"
    path = RUN / "audit.json"
    if args.write:
        if path.exists() and path.read_text() != data:
            raise ValueError("archived audit differs from independent replay")
        if not path.exists():
            path.write_text(data)
    print(json.dumps({stem: {"status": row["status"],
                             "conflicts": row["progress"]["final_conflicts"]}
                      for stem, row in rows.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
