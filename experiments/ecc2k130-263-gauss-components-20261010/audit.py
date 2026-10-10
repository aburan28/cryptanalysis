#!/usr/bin/env python3
"""Replay Q1420 component-policy inputs, solver receipts, and any group models."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "runs/R1"
ORDINARY_DIR = ROOT / "experiments/ecc2k130-263-bilinear-ordinary-q0-20261010"
INPUT = ORDINARY_DIR / "runs/R1"
sys.path.insert(0, str(ORDINARY_DIR))
import audit as ordinary_audit  # noqa: E402
from verify_model import parse_assignment, verify_xcnf  # noqa: E402

spec = importlib.util.spec_from_file_location("component_inventory", HERE / "component.py")
assert spec and spec.loader
component = importlib.util.module_from_spec(spec)
spec.loader.exec_module(component)


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


def progress(output: str) -> dict:
    lines = output.splitlines()
    accepted = []
    for i, line in enumerate(lines):
        if not re.search(r"\bGood\s+matrix\s+\d+", line):
            continue
        dimensions = re.search(r"(\d+)\s*x\s*(\d+)", line)
        if dimensions is None and i + 1 < len(lines):
            dimensions = re.search(r"(\d+)\s*x\s*(\d+)", lines[i + 1])
        if dimensions is None:
            raise ValueError("accepted matrix lacks printed dimensions")
        accepted.append([int(dimensions.group(1)), int(dimensions.group(2))])
    conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", output, re.MULTILINE)
    restarts = [line for line in lines if line.startswith("c rst ")]
    selected = re.findall(r"Using (\d+) matrices recovered from (\d+) xors", output)
    rejected = re.findall(r"Too many rows in matrix:\s*(\d+)", output)
    eliminations = re.findall(r"\beliminations\s*:\s*([^\n]+)", output)
    return {
        "accepted_matrix_dimensions": accepted,
        "selected_matrix_counts": [[int(a), int(b)] for a, b in selected],
        "rejected_large_matrix_rows": [int(value) for value in rejected],
        "restart_rows": len(restarts),
        "restart_rows_sha256": digest("\n".join(restarts).encode() + (b"\n" if restarts else b"")),
        "last_restart_row": restarts[-1] if restarts else None,
        "final_conflicts": int(conflicts[-1]) if conflicts else None,
        "printed_elimination_rows": eliminations,
        "search_started": bool(restarts or (conflicts and int(conflicts[-1]) > 0)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    cfg = read(HERE / "source.json")
    cells = read(RUN / "cells.json")
    expected_order = [f"{policy}_{variant}"
                      for variant in cfg["variants"]
                      for policy in cfg["policies"]]
    if (cfg["schema"] != "ecc2k130-263-gauss-components-source-v1"
            or cfg["parent_commit"] != "025e3a00afa9c0569a8bbb640d7bec6551e68ea3"
            or cells["schema"] != "ecc2k130-263-gauss-components-cells-v1"
            or cells["status"] != "FROZEN_EIGHT_SOLVER_CELLS"
            or cells["order"] != expected_order
            or set(cells["cells"]) != set(expected_order)
            or cells["source_sha256"] != file_digest(HERE / "source.json")
            or cells["runner_sha256"] != file_digest(HERE / "experiment.py")):
        raise ValueError("frozen protocol or panel differs")
    for name, expected in cfg["pins"].items():
        if file_digest(ROOT / name) != expected:
            raise ValueError("pinned archive or source differs: " + name)
    components = {}
    for policy in cfg["policies"]:
        observed = component.analyze(policy)
        saved = read(RUN / f"{policy}.components.json")
        if observed != saved:
            raise ValueError("component inventory differs: " + policy)
        components[policy] = file_digest(RUN / f"{policy}.components.json")

    rows = {}
    ordinary_cfg = read(ORDINARY_DIR / "CONFIG.json")
    with tempfile.TemporaryDirectory(prefix="q1420-component-audit-", dir="/private/tmp") as tmp:
        for stem in expected_order:
            policy = "descendant_native" if stem.startswith("descendant_native") else "source"
            variant = stem[len(policy) + 1:]
            receipt = read(INPUT / f"{policy}_wz_only.formula.json")
            named = read(INPUT / f"{policy}_wz_only.inputs.json")
            archive = INPUT / f"{policy}_wz_only.xcnf.gz"
            formula = Path(tmp) / f"{stem}.xcnf"
            with gzip.open(archive, "rb") as stream:
                formula.write_bytes(stream.read())
            with formula.open("rb") as stream:
                header = stream.readline().split()
            expected = {"kind": "ordinary_q0", "policy": policy,
                        "formula_sha256": receipt["formula_raw_sha256"],
                        "formula_bytes": receipt["formula_raw_bytes"],
                        "variables": int(header[2]), "constraints": int(header[3]),
                        "variant": variant,
                        "matrix_policy": cfg["matrix_policies"][variant]}
            if (file_digest(formula) != expected["formula_sha256"]
                    or formula.stat().st_size != expected["formula_bytes"]
                    or cells["cells"][stem] != expected):
                raise ValueError("solver input differs from frozen archive")
            result_path = RUN / f"{stem}.solver.json"
            result = read(result_path)
            stdout_archive = RUN / f"{stem}.stdout.txt.gz"
            stderr = RUN / f"{stem}.stderr.txt"
            with gzip.open(stdout_archive, "rb") as stream:
                raw = stream.read()
            output = raw.decode("utf-8", errors="replace")
            terminal = [line.strip() for line in output.splitlines()
                        if line.startswith("s ")]
            flags = (["--threads=1", "--verb=1", "--printsol=1"]
                     + [f"--{key}={value}" for key, value in
                        cfg["matrix_policies"][variant].items()]
                     + [f"--maxconfl={cfg['max_conflicts']}",
                        f"--maxtime={cfg['internal_wall_seconds']}"])
            if (result["schema"] != "ecc2k130-263-gauss-components-solver-v1"
                    or result["cell"] != stem or result["policy"] != policy
                    or result["variant"] != variant
                    or result["candidate_id"] is not None
                    or result["source_sha256"] != file_digest(HERE / "source.json")
                    or result["cells_sha256"] != file_digest(RUN / "cells.json")
                    or result["runner_sha256"] != file_digest(HERE / "experiment.py")
                    or result["formula_sha256"] != expected["formula_sha256"]
                    or result["solver_sha256"] != cfg["solver_sha256"]
                    or result["command_flags"] != flags
                    or result["terminal_status_lines"] != terminal
                    or result["stdout_raw_sha256"] != digest(raw)
                    or result["stdout_raw_bytes"] != len(raw)
                    or result["stdout_archive_sha256"] != file_digest(stdout_archive)
                    or result["stderr_sha256"] != file_digest(stderr)
                    or result["wall_seconds"] > cfg["external_wall_seconds"] + 3
                    or (result["peak_sampled_rss_bytes"] > cfg["peak_rss_cap_bytes"]
                        and result["guard"] != "RSS_CAP")):
                raise ValueError("solver transcript or guard differs")
            search = progress(output)
            status = result["status"]
            model = group = None
            if status == "SAT_UNVERIFIED":
                if terminal != ["s SATISFIABLE"] or result["exit_code"] != 10:
                    raise ValueError("SAT lacks terminal state")
                values = parse_assignment(output, expected["variables"])
                model = verify_xcnf(formula, values)
                group = ordinary_audit.replay_group(
                    policy, named, receipt["target_selector_variables"],
                    values, ordinary_cfg)
                status = "SAT_VERIFIED_GROUP"
            elif status == "BOUNDED_UNKNOWN":
                if not (result["guard"] == "WALL_CAP" or
                        (terminal == ["s INDETERMINATE"]
                         and result["exit_code"] == 15)):
                    raise ValueError("bounded status lacks exact cap")
            elif status == "OOM_GUARD":
                if result["guard"] != "RSS_CAP":
                    raise ValueError("OOM status lacks guard")
            elif status == "UNSAT":
                status = "UNSAT_REPORTED"
            elif status != "PRODUCER_FAILURE":
                raise ValueError("unknown solver status")
            rows[stem] = {
                "status": status, "raw_status": result["status"],
                "guard": result["guard"], "exit_code": result["exit_code"],
                "wall_seconds": result["wall_seconds"],
                "cpu_seconds": result["user_cpu_seconds"] + result["system_cpu_seconds"],
                "peak_sampled_rss_bytes": result["peak_sampled_rss_bytes"],
                "progress": search,
                "formula_sha256": expected["formula_sha256"],
                "solver_receipt_sha256": file_digest(result_path),
                "stdout_archive_sha256": file_digest(stdout_archive),
                "xcnf_checks": model, "group_replay": group,
            }
    audit = {
        "schema": "ecc2k130-263-gauss-components-audit-v1",
        "status": "PASS_COMPONENTS_INPUTS_TRANSCRIPTS_AND_MODELS",
        "source_sha256": file_digest(HERE / "source.json"),
        "cells_sha256": file_digest(RUN / "cells.json"),
        "auditor_sha256": file_digest(Path(__file__)),
        "component_receipt_sha256": components,
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
                             "selected": row["progress"]["accepted_matrix_dimensions"],
                             "conflicts": row["progress"]["final_conflicts"]}
                      for stem, row in rows.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
