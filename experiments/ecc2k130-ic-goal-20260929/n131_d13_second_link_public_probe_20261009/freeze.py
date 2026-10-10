#!/usr/bin/env python3
"""Freeze one public-point second-link lookup query before execution."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOOKUP = ROOT / "n131_d13_second_link_lookup_20261009"
FIRST = ROOT / "n131_d13_first_link_branches_20261009"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RAW = ROOT / "n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/official_q_phi_fiber_d13_m12_v1.xcnf"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    dest = HERE / "protocol.json"
    if dest.exists():
        raise FileExistsError(dest)
    source = json.loads((FIRST / "protocol.json").read_text())
    exact = json.loads((LOOKUP / "protocol.json").read_text())
    audit = json.loads((LOOKUP / "encoding_audit.json").read_text())
    runtime_path = HERE / "sage_runtime_info.json"
    runtime = json.loads(runtime_path.read_text())
    if (runtime.get("status") != "verified" or
            source["curve_id"] != exact["curve_id"] or
            source["workload_id"] != exact["workload_id"] or
            source["target_count"] != exact["target_count"] != 1 or
            audit["status"] != "PASS_EXACT_APPEND_ONLY_ENCODING" or
            audit["local_truth_table"] != "PASS_SELECTOR_AND_OUTPUT_EQUIVALENCE"):
        raise ValueError("source, lookup, audit, or checked Sage mismatch")
    if len(audit["branches"]) != 2:
        raise ValueError("both exact first-link roots required")
    if sha(RAW) != source["source_sha256"]["raw"]:
        raise ValueError("original public-point XCNF changed")
    branches = []
    for index, entry in enumerate(audit["branches"]):
        formula = LOOKUP / f"branch{index}_lookup.xcnf"
        if entry["branch"] != index or sha(formula) != entry["lookup_formula_sha256"]:
            raise ValueError(f"lookup formula {index} differs from independent audit")
        branches.append({"branch": index, "formula_sha256": sha(formula),
                         "first_link_root": source["cubes"][index]["partial0_phi_mask"],
                         "first_leaf_codes": source["cubes"][index]["leaf_codes"]})
    protocol = {
        "kind": "n131_d13_second_link_public_point_probe",
        "status": "FROZEN_BEFORE_RUN", "proposal_id": "Q20261009170100",
        "candidate_id": None, "run_id": None,
        "curve_id": exact["curve_id"], "workload_id": exact["workload_id"],
        "target_count": 1, "branches": branches,
        "per_branch_parent_wall_cap_seconds": 285,
        "combined_solver_stage_cap_seconds": 570,
        "combined_process_rss_cap_bytes": 4 * 1024**3,
        "workers": 1, "solver_flags": source["solver_flags"],
        "model_gate": "audit lookup and original XCNF assignment, then independent checked-Sage subgroup and relation replay",
        "measurement_boundary": "solver stage only; source and lookup formula construction outside clock",
        "source_sha256": {
            "runner": sha(HERE / "run.py"), "freeze": sha(Path(__file__)),
            "source_protocol": sha(FIRST / "protocol.json"),
            "lookup_protocol": sha(LOOKUP / "protocol.json"),
            "encoding_audit": sha(LOOKUP / "encoding_audit.json"),
            "table_audit": sha(LOOKUP / "audit.json"),
            "runtime": sha(runtime_path), "solver": sha(SOLVER),
            "original_xcnf": source["source_sha256"]["raw"],
        },
    }
    dest.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": protocol["status"],
                      "formula_sha256": [x["formula_sha256"] for x in branches]}))


if __name__ == "__main__":
    main()
