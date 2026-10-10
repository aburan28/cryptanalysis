#!/usr/bin/env python3
"""Freeze complete source and input identity before the target queries."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_pair_output_prefix_gate_20261010"
CONTROL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010" / "control.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return {"producer": HERE / "run.py", "freezer": HERE / "freeze.py",
            "pair_roots": BASE / "pair_roots.json",
            "pair_root_audit": BASE / "prefix_audit.json",
            "bit_field": BASE / "audit_prefix.py",
            "constructed_input": CONTROL,
            "published_input": BASE / "result.json",
            "checked_sage_runtime": HERE / "sage_runtime_info.json"}


def main():
    assert not (HERE / "protocol.json").exists()
    roots = json.loads((BASE / "pair_roots.json").read_text())
    audit = json.loads((BASE / "prefix_audit.json").read_text())
    control = json.loads(CONTROL.read_text())
    public = json.loads((BASE / "result.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    assert roots["status"] == "PASS_COMPLETE_W15_PAIR_OUTPUT_ROOTS"
    assert audit["status"] == "PASS_INDEPENDENT_W15_PAIR_OUTPUT_PREFIX_AUDIT"
    assert audit["sha256"]["roots"] == sha(BASE / "pair_roots.json")
    assert public["status"] == "CENSORED_TIME"
    assert control["masks"][:2] == [7887, 12331]
    assert control["masks"][2:4] == [5701, 13691]
    assert control["middle_reciprocals"][6] != 0
    assert not (HERE / "result.json").exists()
    protocol = {"status": "FROZEN_W15_FIXEDSEED_S3_JOIN",
                "candidate_id": None, "curve_id": roots["curve_id"],
                "target_count": 1, "query_count": 3,
                "domain_sizes": [8176, 8340],
                "positive_reciprocal": control["middle_reciprocals"][6],
                "positive_input_law": "constructed first-four-atom raw sum from frozen complete XCNF control",
                "public_target_q": public["target_q"],
                "public_input_law": "all trace-zero admissible raw preimages of the published subgroup point",
                "per_query_cap_seconds": 120,
                "rss_cap_bytes": 4*1024**3, "workers": 1,
                "source_sha256": {name: sha(path) for name, path in sources().items()}}
    with (HERE / "protocol.json").open("x") as out:
        json.dump(protocol, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": protocol["status"],
                      "domain_sizes": protocol["domain_sizes"],
                      "public_target_q": protocol["public_target_q"]}))


if __name__ == "__main__":
    main()
