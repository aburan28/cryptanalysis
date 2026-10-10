#!/usr/bin/env python3
"""Read-only integrity and mathematical receipt checks for this gate."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
PRIOR = HERE.parent / "n131_w15_unrestricted_fivepair_public_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text())


def main():
    protocol = load("protocol.json")
    census = load("census.json")
    audit = load("audit.json")
    count = load("count.json")
    count_audit = load("count_audit.json")
    degree_protocol = load("degree_protocol.json")
    degree = load("degree_result.json")
    degree_audit = load("degree_audit.json")
    seed_protocol = load("seed_protocol.json")
    seed = load("seed_result.json")
    seed_audit = load("seed_audit.json")
    bits = (HERE / "class_bits.bin").read_bytes()
    assert len(bits) == 1 << 15
    assert protocol["status"] == "FROZEN_BEFORE_W15_COFACTOR_CLASS_CENSUS"
    for key, name in (("census", "census.py"),
                      ("runtime", "sage_runtime_info.json"),
                      ("probe", "probe.py")):
        assert protocol["sha256"][key] == sha(HERE / name)
    assert protocol["sha256"]["support"] == sha(SUPPORT)
    assert census["status"] == "PASS_EXACT_W15_COFACTOR_CLASS_CENSUS"
    assert census["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert census["sha256"]["class_bits"] == sha(HERE / "class_bits.bin")
    assert audit["status"] == "PASS_INDEPENDENT_SAGE_W15_COFACTOR_CLASS_REPLAY"
    assert audit["signed_lifts_checked"] == 512
    assert audit["sha256"]["census"] == sha(HERE / "census.json")
    assert count["status"] == "PASS_EXACT_FIVEPAIR_SUBGROUP_CLASS_COUNT"
    assert count_audit["status"] == "PASS_INDEPENDENT_BINOMIAL_CLASS_PAIR_COUNT"
    assert count_audit["sha256"]["count"] == sha(HERE / "count.json")
    assert count["source_sha256"]["prior_input"] == sha(PRIOR / "input.json")
    assert count["source_sha256"]["prior_count"] == sha(PRIOR / "support_count.json")
    assert count["subgroup_pair_tuple_count"] == count_audit["subgroup_pair_tuple_count"]
    assert degree_protocol["status"] == "FROZEN_BEFORE_W15_COFACTOR_DEGREE_GATES"
    assert degree_protocol["sha256"]["script"] == sha(HERE / "degree_gate.py")
    assert degree["sha256"]["protocol"] == sha(HERE / "degree_protocol.json")
    assert degree_audit["sha256"]["result"] == sha(HERE / "degree_result.json")
    assert degree_audit["status"] == "PASS_INDEPENDENT_W15_DEGREE_CERTIFICATES"
    for row in degree["rows"]:
        masks = row["certificate_masks"]
        d = row["degree_bound"]
        assert sum(bits[mask] for mask in masks) % 2 == 1
        assert all(sum((mask & mono) == mono for mask in masks) % 2 == 0
                   for mono in range(1 << 15) if mono.bit_count() <= d)
    assert seed_protocol["status"] == "FROZEN_BEFORE_W15_CLASS_SEED_CENSUS"
    assert seed_protocol["sha256"]["script"] == sha(HERE / "seed_class.py")
    assert seed["sha256"]["protocol"] == sha(HERE / "seed_protocol.json")
    assert seed["sha256"]["counts"] == sha(HERE / "seed_class_counts.bin")
    assert seed_audit["status"] == "PASS_INDEPENDENT_W15_SEED_CLASS_COUNTS"
    assert seed_audit["sha256"]["seed_result"] == sha(HERE / "seed_result.json")
    assert seed["totals"] == census["signed_unordered_pair_states_by_output_class"]
    assert seed["distribution"]["zero_class0_seeds"] == 0
    assert seed["distribution"]["zero_class1_seeds"] == 0
    print(json.dumps({"status": "PASS_W15_COFACTOR_CLASS_GATE",
                      "support_classes": census["support_class_counts"],
                      "subgroup_pair_target_mean":
                      count["uniform_subgroup_target_mean_before_nonzero_filter"],
                      "degree_obstructions": [row["degree_bound"] for row in degree["rows"]],
                      "seeds_brute_forced": seed_audit["seeds_brute_forced"]}))


if __name__ == "__main__":
    main()
