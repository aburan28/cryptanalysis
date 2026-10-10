#!/usr/bin/env sage -python
"""Check the W15 group lift against the frozen twelve-atom control."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import importlib.util
    spec = importlib.util.spec_from_file_location("w15_control_lift_module", HERE / "w15_lift.py")
    lift = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lift)
    protocol = json.loads((HERE / "protocol.json").read_text())
    circuit_control = json.loads((HERE / "control_result.json").read_text())
    original = json.loads((ORIGINAL / "control.json").read_text())
    assert circuit_control["status"] == "PASS_FULL_COMPACT_N131_CONSTRUCTED_ASSIGNMENT"
    assert circuit_control["target_q"] == original["target_q"]
    assert protocol["source_sha256"]["w15_lift"] == sha(HERE / "w15_lift.py")
    answer = lift.lift(original["masks"], original["middle_reciprocals"],
                       tuple(original["target_q"]), original["target_preimage_index"])
    assert answer["status"] == "GROUP_LIFT_FOUND"
    assert any(item["raw_leaves"] == original["raw_leaves"] for item in answer["solutions"])
    result = {
        "status": "PASS_W15_CONSTRUCTED_GROUP_LIFT",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "target_q": original["target_q"],
        "solutions": answer["solutions"],
        "pair_option_counts": answer["pair_option_counts"],
        "source_sha256": {
            "script": sha(__file__),
            "w15_lift": sha(HERE / "w15_lift.py"),
            "protocol": sha(HERE / "protocol.json"),
            "circuit_control": sha(HERE / "control_result.json"),
            "original_control": sha(ORIGINAL / "control.json"),
            "support": sha(HERE / "support_w15.tsv"),
        },
    }
    with (HERE / "control_group_lift.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "solutions": len(result["solutions"])}))


if __name__ == "__main__":
    main()
