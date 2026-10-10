#!/usr/bin/env python3
"""Independent reconstruction and model/group replay of the x-release panel."""

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
BASE = ROOT / "experiments/ecc2k130-263-bilinear-leaf-20261010/runs/R1"
sys.path.insert(0, str(ROOT / "experiments/ecc2k130-263-projective-s3-sat-20261010"))
from verify_model import parse_assignment, replay_signs, verify_xcnf  # noqa: E402


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


def semantic_delta(control, named, choices, leaf, width):
    released = {(53 * index) % 131 for index in range(width)}
    fixed = {}
    for index, item in enumerate(control["leaves"]):
        fields = (("s", 24, item["mask"]),
                  ("x", 131, item["raw_point_normalized"][0]),
                  ("z", 131, item["z"]))
        for prefix, bits, integer in fields:
            for bit in range(bits):
                if prefix == "x" and index == leaf and bit in released:
                    continue
                variable = named[f"{prefix}{index}:{bit}"]
                if variable in fixed:
                    raise ValueError("overlapping leaf inputs")
                fixed[variable] = bool(integer & (1 << bit))
    for index, item in enumerate(control["intermediates"]):
        if item["finite"] is not True:
            raise ValueError("nonfinite archived intermediate")
        for bit in range(131):
            variable = named[f"t{index}:{bit}"]
            if variable in fixed:
                raise ValueError("overlapping S3 input")
            fixed[variable] = bool(item["x"] & (1 << bit))
        variable = named[f"f:{index}"]
        if variable in fixed:
            raise ValueError("overlapping S3 flag")
        fixed[variable] = True
    for variable in choices:
        if variable in fixed:
            raise ValueError("overlapping target mux")
        fixed[variable] = False
    if len(fixed) != 2246 - width:
        raise ValueError("unexpected semantic unit count")
    literals = sorted(key if value else -key for key, value in fixed.items())
    return b"".join(f"{literal} 0\n".encode() for literal in literals)


def reconstruct(base: Path, delta: bytes, out: Path):
    lines = delta.splitlines()
    if any(not re.fullmatch(rb"-?[1-9][0-9]* 0", line)
           for line in lines):
        raise ValueError("malformed unit delta")
    with base.open("rb") as source, out.open("xb") as target:
        header = source.readline().split()
        if len(header) != 4 or header[:2] != [b"p", b"cnf"]:
            raise ValueError("malformed base header")
        variables, constraints = map(int, header[2:])
        target.write(f"p cnf {variables} {constraints + len(lines)}\n".encode())
        shutil.copyfileobj(source, target, length=1 << 20)
        target.write(delta)
    return variables, constraints + len(lines)


def search_progress(output: str):
    restarts = sum(line.startswith("c rst ") for line in output.splitlines())
    conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", output, re.MULTILINE)
    return {"restart_rows": restarts,
            "final_conflicts": int(conflicts[-1]) if conflicts else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    cfg = read(HERE / "source.json")
    cells = read(RUN / "cells.json")
    witness = read(ROOT / "experiments/ecc2k130-263-distinct-s3-control-20261010/runs/R1/witness.json")
    if (cfg["schema"] != "ecc2k130-263-x-freedom-ladder-source-v1"
            or cells["schema"] != "ecc2k130-263-x-freedom-ladder-cells-v1"
            or cells["status"] != "FROZEN_32_SAT_INPUTS"
            or cells["source_sha256"] != file_digest(HERE / "source.json")
            or cells["runner_sha256"] != file_digest(HERE / "ladder.py")
            or cells["witness_sha256"] != file_digest(ROOT / "experiments/ecc2k130-263-distinct-s3-control-20261010/runs/R1/witness.json")
            or len(cells["order"]) != 32
            or len(set(cells["order"])) != 32
            or set(cells["order"]) != set(cells["cells"])):
        raise ValueError("frozen source or panel differs")
    for name, expected in cfg["pins"].items():
        if file_digest(ROOT / name) != expected:
            raise ValueError("parent archive pin differs: " + name)
    panels = {}
    with tempfile.TemporaryDirectory(prefix="x-ladder-audit-", dir="/private/tmp") as temp:
        scratch = Path(temp)
        for policy in cfg["policies"]:
            receipt = read(BASE / f"{policy}_wz_only_base.json")
            archive = BASE / f"{policy}_wz_only_base.xcnf.gz"
            named = read(BASE / f"{policy}_wz_only_inputs.json")
            if (receipt["formula_gzip_sha256"] != file_digest(archive)
                    or receipt["input_vars_count"] != len(named)):
                raise ValueError("archive metadata differs")
            raw = scratch / f"{policy}.xcnf"
            with gzip.open(archive, "rb") as source, raw.open("xb") as target:
                shutil.copyfileobj(source, target, length=1 << 20)
            if (file_digest(raw) != receipt["formula_raw_sha256"]
                    or raw.stat().st_size != receipt["formula_raw_bytes"]):
                raise ValueError("base XCNF does not reproduce")
            panels[policy] = (receipt, named, raw)
        rows = {}
        for stem in cells["order"]:
            cell = cells["cells"][stem]
            policy, leaf, width = (cell["policy"], cell["leaf"],
                                   cell["released_width"])
            if (policy not in panels or leaf not in cfg["leaf_indices"]
                    or width not in cfg["release_widths"]
                    or stem != f"{policy}_x{leaf}_w{width}"
                    or cell["released_bit_positions"]
                    != [(53 * j) % 131 for j in range(width)]):
                raise ValueError("cell metadata outside protocol")
            receipt, named, base = panels[policy]
            delta = semantic_delta(witness["policies"][policy], named,
                                   receipt["target_selector_variables"],
                                   leaf, width)
            unit_path = RUN / f"{stem}.units.txt"
            if (unit_path.read_bytes() != delta
                    or cell["unit_delta_sha256"] != digest(delta)
                    or cell["unit_count"] != len(delta.splitlines())
                    or cell["base_gzip_sha256"]
                    != receipt["formula_gzip_sha256"]):
                raise ValueError("unit delta differs from semantic replay")
            full = scratch / f"{stem}.xcnf"
            variables, constraints = reconstruct(base, delta, full)
            if (file_digest(full) != cell["formula_sha256"]
                    or full.stat().st_size != cell["formula_bytes"]
                    or variables != cell["variables"]
                    or constraints != cell["total_constraints"]):
                raise ValueError("full precommitted XCNF differs")
            solver_path = RUN / f"{stem}.solver.json"
            result = read(solver_path)
            archive = RUN / f"{stem}.stdout.txt.gz"
            stderr = RUN / f"{stem}.stderr.txt"
            with gzip.open(archive, "rb") as stream:
                raw_output = stream.read()
            output = raw_output.decode("utf-8", errors="replace")
            terminal = [line.strip() for line in output.splitlines()
                        if line.startswith("s ")]
            expected_flags = ["--threads=1",
                              f"--maxconfl={cfg['max_conflicts']}",
                              f"--maxtime={cfg['internal_wall_seconds']}",
                              "--verb=1", "--printsol=1"]
            if (result["schema"] != "ecc2k130-263-x-freedom-ladder-solver-v1"
                    or result["cell"] != stem or result["policy"] != policy
                    or result["leaf"] != leaf or result["width"] != width
                    or result["candidate_id"] is not None
                    or result["source_sha256"]
                    != file_digest(HERE / "source.json")
                    or result["cells_sha256"]
                    != file_digest(RUN / "cells.json")
                    or result["runner_sha256"]
                    != file_digest(HERE / "ladder.py")
                    or result["formula_sha256"] != cell["formula_sha256"]
                    or result["solver_sha256"] != cfg["solver_sha256"]
                    or result["command_flags"] != expected_flags
                    or result["terminal_status_lines"] != terminal
                    or result["stdout_raw_sha256"] != digest(raw_output)
                    or result["stdout_raw_bytes"] != len(raw_output)
                    or result["stdout_archive_sha256"] != file_digest(archive)
                    or result["stderr_sha256"] != file_digest(stderr)
                    or result["peak_sampled_rss_bytes"]
                    > cfg["peak_rss_cap_bytes"]
                    or result["wall_seconds"]
                    > cfg["external_wall_seconds"] + 3):
                raise ValueError("solver transcript or receipt differs")
            progress = search_progress(output)
            status = result["status"]
            if status == "SAT_UNVERIFIED":
                if terminal != ["s SATISFIABLE"] or result["exit_code"] != 10:
                    raise ValueError("SAT output missing complete terminal state")
                assignment = parse_assignment(output, variables)
                checked = verify_xcnf(full, assignment)
                replay = replay_signs(policy, named,
                                      receipt["target_selector_variables"],
                                      witness["policies"][policy], assignment)
                status = "SAT_VERIFIED_GROUP"
            else:
                checked = replay = None
                if status == "BOUNDED_UNKNOWN":
                    if not (result["guard"] == "WALL_CAP"
                            or (terminal == ["s INDETERMINATE"]
                                and result["exit_code"] == 15)):
                        raise ValueError("bounded status lacks recorded cap")
                    if (progress["restart_rows"] == 0
                            and not progress["final_conflicts"]):
                        raise ValueError("bounded status lacks search progress")
                elif status == "OOM_GUARD":
                    if result["guard"] != "RSS_CAP":
                        raise ValueError("OOM status lacks guard")
                elif status == "UNSAT":
                    raise ValueError("UNSAT contradicts the archived satisfying witness")
                elif status != "PRODUCER_FAILURE":
                    raise ValueError("unknown solver status")
            rows[stem] = {
                "status": status,
                "raw_status": result["status"],
                "exit_code": result["exit_code"],
                "guard": result["guard"],
                "wall_seconds": result["wall_seconds"],
                "cpu_seconds": result["user_cpu_seconds"]
                               + result["system_cpu_seconds"],
                "peak_sampled_rss_bytes": result["peak_sampled_rss_bytes"],
                "progress": progress,
                "formula_sha256": cell["formula_sha256"],
                "solver_receipt_sha256": file_digest(solver_path),
                "stdout_archive_sha256": file_digest(archive),
                "xcnf_checks": checked,
                "group_replay": replay,
            }
            full.unlink()
    audit = {
        "schema": "ecc2k130-263-x-freedom-ladder-audit-v1",
        "status": "PASS_FULL_PANEL_INPUTS_TRANSCRIPTS_AND_MODELS",
        "source_sha256": file_digest(HERE / "source.json"),
        "cells_sha256": file_digest(RUN / "cells.json"),
        "auditor_sha256": file_digest(Path(__file__)),
        "rows": rows,
    }
    data = json.dumps(audit, sort_keys=True, indent=2) + "\n"
    path = RUN / "audit.json"
    if args.write:
        if path.exists():
            if path.read_text() != data:
                raise ValueError("archived audit differs from independent replay")
        else:
            path.write_text(data)
    print(json.dumps({"status": audit["status"],
                      "statuses": {key: value["status"]
                                   for key, value in rows.items()}},
                     sort_keys=True))


if __name__ == "__main__":
    main()
