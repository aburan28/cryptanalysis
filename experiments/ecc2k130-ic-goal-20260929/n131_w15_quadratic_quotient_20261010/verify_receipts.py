#!/usr/bin/env python3
"""Bind exact N41/N131 bucket decisions, certificates, and censored runs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    freeze = read("terminal_protocol.json")
    assert freeze["status"] == "FROZEN_BEFORE_TERMINAL_AUDIT"
    for rel, expected in freeze["sha256"].items():
        assert sha((HERE / rel).resolve()) == expected, rel
    for name in ("protocol_n41.json", "protocol_n41_projective.json",
                 "protocol_n41_resultant.json", "protocol_n131.json",
                 "protocol_n131_resultant.json",
                 "protocol_n131_resultant_negative.json", "protocol_certificate.json",
                 "verify_protocol.json"):
        record = read(name)
        for rel, expected in record["sha256"].items():
            assert sha((HERE / rel).resolve()) == expected, (name, rel)
    for prefix in ("n41_negative", "n41_positive",
                   "projective_n41_negative", "projective_n41_positive",
                   "resultant_n41_negative", "resultant_n41_positive",
                   "resultant_n131_positive", "resultant_n131_negative"):
        output = read(prefix + ".json")
        receipt = read(prefix + ".receipt.json")
        assert output["status"] == "COMPLETE_QUOTIENT_INTERSECTION"
        assert receipt["status"] == "COMPLETE" and receipt["returncode"] == 0
        assert receipt["output_sha256"] == sha(HERE / (prefix + ".json"))
        expected = 1 if prefix.endswith("positive") else 0
        assert output["intersection_degree"] == expected
        assert output["left_degree"] == (64 if "n41" in prefix else 32768)
    for label in ("positive", "negative"):
        output = read(f"certificate_{label}.json")
        receipt = read(f"certificate_{label}.receipt.json")
        expected = 1 if label == "positive" else 0
        assert receipt["status"] == "COMPLETE" and receipt["returncode"] == 0
        assert output["status"] == "COMPLETE_QUOTIENT_INTERSECTION"
        assert output["intersection_degree"] == expected
        assert output["resultant_degree"] == 131072
        assert output["remainder_degree"] == 32767
        assert output["peak_rss_bytes"] < 4294967296
        assert output["elapsed_ns"] < 600 * 10**9
        assert receipt["output_sha256"] == sha(HERE / f"certificate_{label}.json")
        assert receipt["remainder_sha256"] == sha(HERE / f"certificate_{label}.remainder.bin")
        assert receipt["remainder_bytes"] == 32768 * 17
    witness = json.loads((BASE / "n131_w15_sparse_pair_bucket_join_20261010/as_result.json").read_text())
    hit = witness["positive"]["bucket_hits"][0]
    assert hit["left_masks"] == [5576, 8382]
    assert hit["right_masks"] == [3, 13685]
    assert hit["left_output"] == read("verify_protocol.json")["known_left_output"]
    assert hit["right_output"] == read("verify_protocol.json")["known_right_output"]
    assert witness["negative"]["bucket_hit_count"] == 0
    independent = read("verify_result.json")
    assert independent["status"] == "PASS_N131_REMAINDER_CERTIFICATE_CHECK"
    assert independent["positive_gcd_degree"] == 1
    assert independent["negative_gcd_degree"] == 0
    assert independent["known_left_root"] and independent["known_s3"]
    assert independent["negative_inverse_unit"]
    assert read("verify.receipt.json")["output_sha256"] == sha(HERE / "verify_result.json")
    for name, status in (("operator_stop_audit.json", "CENSORED_OPERATOR_STOP_AFTER_ROUND4"),
                         ("audit_v1_stop.json", "CENSORED_OPERATOR_STOP_SLOW_SAGE_DECODER"),
                         ("audit_v2_stop.json", "CENSORED_OPERATOR_STOP_SAGE_GENERIC_GCD")):
        record = read(name)
        assert record["status"] == status
        for rel, expected in record["sha256"].items():
            assert sha(HERE / rel) == expected
    summary = {"status": "PASS_N41_N131_QUOTIENT_RESULTANT_TERMINAL_AUDIT",
               "n41_intersection_degrees": [0, 1],
               "n131_intersection_degrees": [0, 1],
               "n131_resultant_degree": 131072,
               "n131_left_bucket_degree": 32768,
               "valid_nonzero_seed_pairs_for_eight_offsets": 32767*8-7,
               "positive_source_masks": [hit["left_masks"], hit["right_masks"]],
               "independent_negative_inverse_unit": True,
               "terminal_protocol_sha256": sha(HERE / "terminal_protocol.json"),
               "candidate_id": None, "target_count": 0}
    with (HERE / "terminal_result.json").open("x") as output:
        json.dump(summary, output, sort_keys=True, indent=2)
        output.write("\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
