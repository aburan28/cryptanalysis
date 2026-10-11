"""Bind frozen source, sampled prefix screen, and independent Sage replay."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


protocol = load(HERE / "protocol.json")
result = load(HERE / "result.json")
replay = load(HERE / "sage_replay.json")
runtime = load(HERE / "sage_runtime_info.json")
proof = load(HERE / "universal_proof.json")
proof_replay = load(HERE / "universal_sage_audit.json")
assert runtime["status"] == "verified"
assert protocol["status"] == "FROZEN_N41_PREFIX_RANK_FRONTIER"
assert result["status"] == "COMPLETE_N41_PREFIX_RANK_FRONTIER"
assert replay["status"] == "PASS_INDEPENDENT_SAGE_PREFIX_AND_GROUP_REPLAY"
assert proof["status"] == "PROVED_UNIVERSAL_FULL_MASK_LINEAR_CONSISTENCY"
assert proof_replay["status"] == "PASS_INDEPENDENT_SAGE_UNIVERSAL_CERTIFICATE"
assert proof["source_sha256"] == sha(HERE / "universal_proof.py")
assert proof["system_sha256"] == sha(ROOT / "n41_w6_s8_quadratic_joint/ordinary_subgroup_root_R1/functional_system.ms")
assert proof["fixed_source_bits"] == 48
assert proof["equations"] == 498
assert proof["free_monomials"] == 10212
assert proof["cross_fixed_free_monomials"] == 0
assert proof["coefficient_rank"] == 413
assert proof["dependency_count"] == 85
assert proof["nonzero_fixed_dependency_polynomials"] == 0
assert len(proof["dependency_combinations_hex"]) == 85
for key, path in {
    "verifier": HERE / "universal_verify_sage.py",
    "proof": HERE / "universal_proof.json",
    "system": ROOT / "n41_w6_s8_quadratic_joint/ordinary_subgroup_root_R1/functional_system.ms",
    "runtime": HERE / "sage_runtime_info.json",
}.items():
    assert proof_replay["sha256"][key] == sha(path), key
assert proof_replay["low_pivot_coefficient_rank"] == 413
assert proof_replay["independent_dependency_count"] == 85
assert proof_replay["verified_zero_fixed_polynomials"] == 85
assert result["protocol_sha256"] == sha(HERE / "protocol.json")
assert result["source_sha256"] == sha(HERE / "run.py")
for key, path in {
    "runner": HERE / "run.py",
    "prior_screen": ROOT / "n41_w6_s8_quadratic_joint/linearized_prefix_screen/screen.py",
    "quadratic_system": ROOT / "n41_w6_s8_quadratic_joint/ordinary_subgroup_root_R1/functional_system.ms",
    "base": ROOT / "n131_w18_four_pairs/native_join/native_input.txt",
    "preflight": ROOT / "n41_w6_s8_quadratic_joint/preflight.json",
}.items():
    assert protocol["source_sha256"][key] == sha(path), key
for key, path in {
    "verifier": HERE / "verify_sage.py",
    "protocol": HERE / "protocol.json",
    "producer": HERE / "result.json",
    "runtime": HERE / "sage_runtime_info.json",
    "quadratic_system": ROOT / "n41_w6_s8_quadratic_joint/ordinary_subgroup_root_R1/functional_system.ms",
    "base": ROOT / "n131_w18_four_pairs/native_join/native_input.txt",
}.items():
    assert replay["sha256"][key] == sha(path), key
assert len(result["rows"]) == 4
for pair_count, row in enumerate(result["rows"], start=1):
    assert row["fixed_pairs"] == pair_count
    assert row["fixed_bits"] == 12 * pair_count
    assert row["prefix_count"] == len(row["decisions"])
    assert row["consistent_count"] == sum(d["consistent"] for d in row["decisions"])
    assert row["decisions"][row["known_positive_index"]]["consistent"]
    assert row["rank_min"] == min(d["rank"] for d in row["decisions"])
    assert row["rank_max"] == max(d["rank"] for d in row["decisions"])
    if pair_count == 1:
        assert row["prefix_count"] == 978
    else:
        assert row["prefix_count"] == 129
        assert [d["prefix"] for d in row["decisions"]] == protocol["samples"][str(pair_count)]
    assert row["consistent_count"] == row["prefix_count"]
    assert row["rank_min"] == row["rank_max"] == 413
assert len(replay["records"]) == 5
assert replay["records"][0]["group_target_match"]
for index, record in enumerate(replay["records"]):
    assert record["sample_index"] == index
    assert record["rank"] == result["rows"][3]["decisions"][index]["rank"]
    assert record["linear_relaxation_consistent"]
    if index:
        assert not record["group_target_match"]
out = {"status": "PASS_N41_PREFIX_RANK_FRONTIER_AUDIT",
       "candidate_id": None,
       "counts": {str(row["fixed_pairs"]): [row["consistent_count"], row["prefix_count"]]
                  for row in result["rows"]},
       "verified_false_positives": 4,
       "sha256": {"protocol": sha(HERE / "protocol.json"),
                  "result": sha(HERE / "result.json"),
                  "sage_replay": sha(HERE / "sage_replay.json"),
                  "universal_proof": sha(HERE / "universal_proof.json"),
                  "universal_sage_audit": sha(HERE / "universal_sage_audit.json"),
                  "runtime": sha(HERE / "sage_runtime_info.json")}}
(HERE / "audit.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], out["counts"])
