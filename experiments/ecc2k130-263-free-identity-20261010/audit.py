#!/usr/bin/env python3
"""Replay frozen Q1420 free-identity inputs, transcripts, and SAT group sums."""

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
NATIVE = ROOT / "experiments/ecc2k130-263-native-w24-m6-20261010"
GROUP = ROOT / "experiments/ecc2k130-263-projective-s3-20261010"
VERIFY = ROOT / "experiments/ecc2k130-263-projective-s3-sat-20261010"
ORDINARY = ROOT / "experiments/ecc2k130-263-bilinear-ordinary-q0-20261010"
WITNESS = ROOT / "experiments/ecc2k130-263-distinct-s3-control-20261010/runs/R1/witness.json"
sys.path.insert(0, str(NATIVE))
import field as ref  # noqa: E402
sys.path.insert(0, str(VERIFY))
from verify_model import parse_assignment, replay_signs, verify_xcnf  # noqa: E402
sys.path.insert(0, str(HERE))
import experiment as producer  # noqa: E402


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load independent archived auditor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def progress(raw: str):
    restarts = [line for line in raw.splitlines() if line.startswith("c rst ")]
    final = re.findall(r"^c conflicts\s*:\s*(\d+)", raw, re.MULTILINE)
    return {"restart_rows": len(restarts),
            "final_conflicts": int(final[-1]) if final else None,
            "last_restart_row": restarts[-1] if restarts else None}


def named_word(named: dict, prefix: str, values: list[int]) -> int:
    return sum(int(values[named[f"{prefix}:{i}"]] == 1) << i
               for i in range(ref.DEGREE))


def check_known_identity(policy: str, named: dict, values: list[int]):
    alpha, _ = ref.coefficients(policy)
    x = named_word(named, "x0", values)
    z = named_word(named, "z0", values)
    if ref.multiply(alpha, ref.multiply(x, z)) != ref.square(x ^ alpha):
        raise ValueError("SAT model violates free-selector field identity")
    return {"x0": x, "z0": z, "field_identity": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    cfg = producer.config()
    panel = producer.read(RUN / "cells.json")
    if (panel["schema"] != "ecc2k130-free-identity-cells-v1"
            or panel["status"] != "FROZEN_8_EXACT_XCNFS"
            or panel["candidate_id"] is not None
            or panel["order"] != list(producer.ORDER)
            or set(panel["cells"]) != set(producer.ORDER)
            or panel["source_sha256"] != producer.sha(HERE / "source.json")
            or panel["runner_sha256"] != producer.sha(HERE / "experiment.py")):
        raise ValueError("frozen input panel changed")
    ordinary_audit = load_module(ORDINARY / "audit.py", "free_identity_ordinary_audit")
    ordinary_cfg = producer.read(ORDINARY / "CONFIG.json")
    witness = producer.read(WITNESS)
    rows = {}
    with tempfile.TemporaryDirectory(prefix="q1420-free-identity-audit-",
                                     dir="/private/tmp") as td:
        for stem in producer.ORDER:
            expected = panel["cells"][stem]
            kind, policy, variant = (expected[key] for key in
                                     ("kind", "policy", "variant"))
            if stem != f"{kind}_{policy}_{variant}" or expected["flags"] != producer.flags(kind, cfg):
                raise ValueError("cell name or flags changed")
            formula = Path(td) / f"{stem}.xcnf"
            actual = producer.build(kind, policy, variant, formula)
            if any(actual[key] != expected[key] for key in actual):
                raise ValueError("full XCNF does not match precommitted input")
            archive_path, receipt_path, named_path, _ = producer.paths(kind, policy)
            receipt = producer.read(receipt_path)
            named = producer.read(named_path)
            result_path = RUN / f"{stem}.solver.json"
            result = producer.read(result_path)
            stdout_path = RUN / f"{stem}.stdout.txt.gz"
            stderr_path = RUN / f"{stem}.stderr.txt"
            with gzip.open(stdout_path, "rb") as stream:
                raw = stream.read()
            output = raw.decode(errors="replace")
            terminal = [line.strip() for line in output.splitlines()
                        if line.startswith("s ")]
            if (result["schema"] != "ecc2k130-free-identity-solver-v1"
                    or result["cell"] != stem
                    or result["candidate_id"] is not None
                    or result["source_sha256"] != producer.sha(HERE / "source.json")
                    or result["cells_sha256"] != producer.sha(RUN / "cells.json")
                    or result["runner_sha256"] != producer.sha(HERE / "experiment.py")
                    or result["formula_sha256"] != expected["formula_sha256"]
                    or result["solver_sha256"] != cfg["solver_sha256"]
                    or result["flags"] != expected["flags"]
                    or result["terminal"] != terminal
                    or result["stdout_raw_sha256"] != hashlib.sha256(raw).hexdigest()
                    or result["stdout_raw_bytes"] != len(raw)
                    or result["stdout_archive_sha256"] != producer.sha(stdout_path)
                    or result["stderr_sha256"] != producer.sha(stderr_path)
                    or result["solver_wall_seconds"]
                    > cfg["external_wall_seconds"][kind] + 3
                    or (result["peak_sampled_rss_bytes"] > cfg["rss_cap_bytes"]
                        and result["guard"] != "RSS_CAP")):
                raise ValueError("solver transcript or receipt mismatch")
            status = result["status"]
            search = progress(output)
            verification = relation = identity = None
            if status == "SAT_UNVERIFIED":
                if terminal != ["s SATISFIABLE"] or result["exit_code"] != 10:
                    raise ValueError("SAT lacks terminal evidence")
                values = parse_assignment(output, expected["variables"])
                verification = verify_xcnf(formula, values)
                if variant == "identity":
                    identity = check_known_identity(policy, named, values)
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
                if not (result["guard"] == "WALL_CAP"
                        or terminal == ["s INDETERMINATE"]
                        and result["exit_code"] == 15):
                    raise ValueError("bounded status lacks cap evidence")
                if not search["restart_rows"] and not search["final_conflicts"]:
                    raise ValueError("bounded status lacks search progress")
            elif status == "OOM_GUARD":
                if result["guard"] != "RSS_CAP":
                    raise ValueError("memory guard missing")
            elif status == "UNSAT_REPORTED":
                if terminal != ["s UNSATISFIABLE"] or result["exit_code"] != 20:
                    raise ValueError("UNSAT status lacks terminal evidence")
                if kind == "control":
                    raise ValueError("UNSAT contradicts fixed positive witness")
            elif status != "PRODUCER_FAILURE":
                raise ValueError("unrecognized status")
            rows[stem] = {
                "kind": kind, "policy": policy, "variant": variant,
                "status": status, "raw_status": result["status"],
                "guard": result["guard"], "progress": search,
                "construction_wall_seconds": result["preparation_wall_seconds"],
                "solver_wall_seconds": result["solver_wall_seconds"],
                "child_cpu_seconds": result["user_cpu_seconds"]
                                     + result["system_cpu_seconds"],
                "peak_sampled_rss_bytes": result["peak_sampled_rss_bytes"],
                "formula_sha256": expected["formula_sha256"],
                "solver_receipt_sha256": producer.sha(result_path),
                "stdout_archive_sha256": producer.sha(stdout_path),
                "xcnf_checks": verification, "field_identity_check": identity,
                "group_replay": relation, "verified_relation": relation is not None,
                "novel_rank": None,
            }
            formula.unlink()
    audit = {
        "schema": "ecc2k130-free-identity-audit-v1",
        "status": "PASS_FROZEN_INPUTS_TRANSCRIPTS_AND_SAT_REPLAY",
        "candidate_id": None, "workload_id": cfg["workload_id"],
        "source_sha256": producer.sha(HERE / "source.json"),
        "cells_sha256": producer.sha(RUN / "cells.json"),
        "auditor_sha256": producer.sha(Path(__file__)),
        "rows": rows,
    }
    target = RUN / "audit.json"
    content = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    if args.write:
        if target.exists() and target.read_text() != content:
            raise ValueError("existing audit differs")
        if not target.exists():
            target.write_text(content)
    print(json.dumps({key: {"status": value["status"],
                            "final_conflicts": value["progress"]["final_conflicts"]}
                      for key, value in rows.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
