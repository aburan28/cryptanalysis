#!/usr/bin/env python3
"""Independently replay six archived Q1420 inputs and wide-Gauss transcripts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "runs/R1"
LADDER = ROOT / "experiments/ecc2k130-263-x-freedom-ladder-20261010/runs/R1"
LEAF = ROOT / "experiments/ecc2k130-263-bilinear-leaf-20261010/runs/R1"
ORDINARY = ROOT / "experiments/ecc2k130-263-bilinear-ordinary-q0-20261010/runs/R1"
ORDINARY_DIR = ORDINARY.parents[1]
WITNESS = ROOT / "experiments/ecc2k130-263-distinct-s3-control-20261010/runs/R1/witness.json"
sys.path.insert(0, str(ORDINARY_DIR))
import audit as ordinary_audit  # noqa: E402
from verify_model import parse_assignment, replay_signs, verify_xcnf  # noqa: E402


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


def semantic_units(control: dict, named: dict, choice: list[int], leaf: int) -> bytes:
    fixed = {}
    for index, row in enumerate(control["leaves"]):
        for prefix, size, value in (("s", 24, row["mask"]),
                                    ("x", 131, row["raw_point_normalized"][0]),
                                    ("z", 131, row["z"])):
            for bit in range(size):
                if prefix == "x" and index == leaf:
                    continue
                var = named[f"{prefix}{index}:{bit}"]
                if var in fixed:
                    raise ValueError("overlapping semantic inputs")
                fixed[var] = bool(value & (1 << bit))
    for index, node in enumerate(control["intermediates"]):
        if node["finite"] is not True:
            raise ValueError("nonfinite archived S3 intermediate")
        for bit in range(131):
            var = named[f"t{index}:{bit}"]
            if var in fixed:
                raise ValueError("overlapping S3 input")
            fixed[var] = bool(node["x"] & (1 << bit))
        var = named[f"f:{index}"]
        if var in fixed:
            raise ValueError("overlapping S3 flag")
        fixed[var] = True
    for var in choice:
        if var in fixed:
            raise ValueError("overlapping target choice")
        fixed[var] = False
    if len(fixed) != 2115:
        raise ValueError("fixed unit count differs from archived full x-release")
    signed = sorted(var if value else -var for var, value in fixed.items())
    return b"".join(f"{literal} 0\n".encode() for literal in signed)


def reconstruct(stem: str, out: Path, control: dict) -> tuple[dict, dict | None, list[int] | None]:
    policy = "descendant_native" if stem.startswith("descendant_native") else "source"
    if stem.endswith("ordinary_q0"):
        receipt = read(ORDINARY / f"{policy}_wz_only.formula.json")
        archive = ORDINARY / f"{policy}_wz_only.xcnf.gz"
        if file_digest(archive) != receipt["formula_gzip_sha256"]:
            raise ValueError("ordinary gzip receipt differs")
        with gzip.open(archive, "rb") as stream:
            out.write_bytes(stream.read())
        named = read(ORDINARY / f"{policy}_wz_only.inputs.json")
        if file_digest(ORDINARY / f"{policy}_wz_only.inputs.json") != receipt["named_inputs_sha256"]:
            raise ValueError("ordinary input map differs")
        expected = {"kind": "ordinary_q0", "policy": policy,
                    "formula_sha256": receipt["formula_raw_sha256"],
                    "formula_bytes": receipt["formula_raw_bytes"]}
        choice = receipt["target_selector_variables"]
    else:
        match = re.fullmatch(r"(?:source|descendant_native)_x([05])_w131", stem)
        if not match:
            raise ValueError("cell outside frozen panel")
        leaf = int(match.group(1))
        receipt = read(LEAF / f"{policy}_wz_only_base.json")
        archive = LEAF / f"{policy}_wz_only_base.xcnf.gz"
        if file_digest(archive) != receipt["formula_gzip_sha256"]:
            raise ValueError("fixed base gzip receipt differs")
        with gzip.open(archive, "rb") as stream:
            raw = stream.read()
        if digest(raw) != receipt["formula_raw_sha256"]:
            raise ValueError("fixed base raw receipt differs")
        named = read(LEAF / f"{policy}_wz_only_inputs.json")
        if file_digest(LEAF / f"{policy}_wz_only_inputs.json") != receipt["input_vars_sha256"]:
            raise ValueError("fixed input map differs")
        choice = receipt["target_selector_variables"]
        delta = semantic_units(control["policies"][policy], named, choice, leaf)
        unit_path = LADDER / f"{stem}.units.txt"
        parent = read(LADDER / "cells.json")["cells"][stem]
        if unit_path.read_bytes() != delta or digest(delta) != parent["unit_delta_sha256"]:
            raise ValueError("semantic full-release unit delta differs")
        head, body = raw.split(b"\n", 1)
        tokens = head.split()
        if len(tokens) != 4 or tokens[:2] != [b"p", b"cnf"]:
            raise ValueError("bad fixed base XCNF header")
        out.write_bytes(f"p cnf {int(tokens[2])} {int(tokens[3])+len(delta.splitlines())}\n".encode()
                        + body + delta)
        expected = {"kind": "fixed_witness", "policy": policy,
                    "formula_sha256": parent["formula_sha256"],
                    "formula_bytes": parent["formula_bytes"]}
    if file_digest(out) != expected["formula_sha256"] or out.stat().st_size != expected["formula_bytes"]:
        raise ValueError("full XCNF differs from precommitted archive")
    with out.open("rb") as stream:
        header = stream.readline().split()
    if len(header) != 4 or header[:2] != [b"p", b"cnf"]:
        raise ValueError("bad reconstructed XCNF header")
    expected.update(variables=int(header[2]), constraints=int(header[3]))
    return expected, named, choice


def progress(output: str) -> dict:
    restarts = sum(line.startswith("c rst ") for line in output.splitlines())
    conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", output, re.MULTILINE)
    good = re.findall(r"\bGood\s+matrix\s+\d+\s+(\d+)\s*x\s*(\d+)", output)
    rejected = re.findall(r"Too many rows in matrix:\s*(\d+)", output)
    return {"restart_rows": restarts,
            "final_conflicts": int(conflicts[-1]) if conflicts else None,
            "accepted_matrix_dimensions": [[int(a), int(b)] for a, b in good],
            "rejected_large_matrix_rows": [int(value) for value in rejected],
            "search_started": restarts > 0 or bool(conflicts and int(conflicts[-1]) > 0)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    cfg = read(HERE / "source.json")
    cells = read(RUN / "cells.json")
    if (cfg["schema"] != "ecc2k130-263-wide-gauss-source-v1"
            or cells["schema"] != "ecc2k130-263-wide-gauss-cells-v1"
            or cells["source_sha256"] != file_digest(HERE / "source.json")
            or cells["runner_sha256"] != file_digest(HERE / "experiment.py")
            or cells["order"] != cfg["order"]
            or len(cells["order"]) != 6
            or set(cells["order"]) != set(cells["cells"])):
        raise ValueError("frozen protocol or panel differs")
    for name, expected in cfg["pins"].items():
        if file_digest(ROOT / name) != expected:
            raise ValueError("parent archive pin differs: " + name)
    control = read(WITNESS)
    rows = {}
    with tempfile.TemporaryDirectory(prefix="wide-gauss-audit-", dir="/private/tmp") as tmp:
        for stem in cells["order"]:
            formula = Path(tmp) / f"{stem}.xcnf"
            expected, named, choice = reconstruct(stem, formula, control)
            if cells["cells"][stem] != expected:
                raise ValueError("frozen cell differs from independent input reconstruction")
            solver = read(RUN / f"{stem}.solver.json")
            archive = RUN / f"{stem}.stdout.txt.gz"
            stderr = RUN / f"{stem}.stderr.txt"
            with gzip.open(archive, "rb") as stream:
                raw = stream.read()
            output = raw.decode("utf-8", errors="replace")
            terminal = [line.strip() for line in output.splitlines()
                        if line.startswith("s ")]
            flags = ["--threads=1", "--verb=1", "--printsol=1"]
            flags += [f"--{key}={value}" for key, value in cfg["gauss"].items()]
            if expected["kind"] == "fixed_witness":
                flags += [f"--maxconfl={cfg['fixed_max_conflicts']}",
                          f"--maxtime={cfg['fixed_internal_seconds']}"]
                cap = cfg["fixed_external_seconds"]
            else:
                flags += [f"--maxtime={cfg['ordinary_internal_seconds']}"]
                cap = cfg["ordinary_external_seconds"]
            if (solver["schema"] != "ecc2k130-263-wide-gauss-solver-v1"
                    or solver["cell"] != stem or solver["kind"] != expected["kind"]
                    or solver["policy"] != expected["policy"]
                    or solver["candidate_id"] is not None
                    or solver["source_sha256"] != file_digest(HERE / "source.json")
                    or solver["cells_sha256"] != file_digest(RUN / "cells.json")
                    or solver["runner_sha256"] != file_digest(HERE / "experiment.py")
                    or solver["formula_sha256"] != expected["formula_sha256"]
                    or solver["solver_sha256"] != cfg["solver_sha256"]
                    or solver["command_flags"] != flags
                    or solver["terminal_status_lines"] != terminal
                    or solver["stdout_raw_sha256"] != digest(raw)
                    or solver["stdout_raw_bytes"] != len(raw)
                    or solver["stdout_archive_sha256"] != file_digest(archive)
                    or solver["stderr_sha256"] != file_digest(stderr)
                    or solver["peak_sampled_rss_bytes"] > cfg["peak_rss_cap_bytes"] + 10000000
                    or solver["wall_seconds"] > cap + 3):
                raise ValueError("solver evidence differs or exceeds frozen guard")
            status = solver["status"]
            model = group = None
            if status == "SAT_UNVERIFIED":
                if terminal != ["s SATISFIABLE"] or solver["exit_code"] != 10:
                    raise ValueError("SAT lacks terminal state")
                values = parse_assignment(output, expected["variables"])
                model = verify_xcnf(formula, values)
                if expected["kind"] == "fixed_witness":
                    group = replay_signs(expected["policy"], named, choice,
                                         control["policies"][expected["policy"]], values)
                else:
                    ordinary_cfg = read(ORDINARY_DIR / "CONFIG.json")
                    group = ordinary_audit.replay_group(expected["policy"], named,
                                                        choice, values, ordinary_cfg)
                status = "SAT_VERIFIED_GROUP"
            elif status == "BOUNDED_UNKNOWN":
                if not (solver["guard"] == "WALL_CAP" or
                        (terminal == ["s INDETERMINATE"] and solver["exit_code"] == 15)):
                    raise ValueError("bounded status lacks recorded cap")
            elif status == "OOM_GUARD":
                if solver["guard"] != "RSS_CAP":
                    raise ValueError("OOM status lacks RSS guard")
            elif status == "UNSAT":
                if expected["kind"] == "fixed_witness":
                    raise ValueError("UNSAT contradicts verified fixed witness")
                status = "UNSAT_REPORTED"
            elif status != "PRODUCER_FAILURE":
                raise ValueError("unknown solver status")
            rows[stem] = {
                "status": status, "raw_status": solver["status"],
                "guard": solver["guard"], "exit_code": solver["exit_code"],
                "wall_seconds": solver["wall_seconds"],
                "cpu_seconds": solver["user_cpu_seconds"] + solver["system_cpu_seconds"],
                "peak_sampled_rss_bytes": solver["peak_sampled_rss_bytes"],
                "progress": progress(output),
                "formula_sha256": expected["formula_sha256"],
                "solver_receipt_sha256": file_digest(RUN / f"{stem}.solver.json"),
                "stdout_archive_sha256": file_digest(archive),
                "xcnf_checks": model, "group_replay": group,
            }
    audit = {
        "schema": "ecc2k130-263-wide-gauss-audit-v1",
        "status": "PASS_ARCHIVED_INPUTS_TRANSCRIPTS_AND_MODELS",
        "source_sha256": file_digest(HERE / "source.json"),
        "cells_sha256": file_digest(RUN / "cells.json"),
        "auditor_sha256": file_digest(Path(__file__)),
        "rows": rows,
    }
    data = json.dumps(audit, sort_keys=True, indent=2) + "\n"
    path = RUN / "audit.json"
    if args.write:
        if path.exists() and path.read_text() != data:
            raise ValueError("existing audit differs")
        if not path.exists():
            path.write_text(data)
    print(json.dumps({stem: {"status": row["status"],
                             "progress": row["progress"]}
                      for stem, row in rows.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
