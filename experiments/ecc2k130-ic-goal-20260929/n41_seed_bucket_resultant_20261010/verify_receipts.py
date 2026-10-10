#!/usr/bin/env python3
"""Check the saved N41 bucket experiment's frozen identities and outcomes."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text())


def check_protocol(name, sources):
    protocol = load(name)
    assert protocol["status"] == "FROZEN"
    for label, path in sources.items():
        assert protocol["sha256"][label] == sha(path), (name, label)
    return protocol


def main():
    geometry = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
    predecessor = BASE / "n131_w14_s3_prefix_rank_20261010/result.json"
    row = BASE / "n41_two_free_pair_compact_lookup_20261009/public_search_v2.json"
    pair = (BASE / "n131_w14_pair_output_join_20261010" /
            "v2_n131_positive_filtered_pair_join.json")
    runtime = HERE / "sage_runtime_info.json"
    check_protocol("protocol.json", {"run": HERE / "run.py", "geometry": geometry,
                                     "predecessor": predecessor, "runtime": runtime})
    check_protocol("norm_protocol.json", {"source": HERE / "norm.py",
                                          "helper": HERE / "run.py", "geometry": geometry,
                                          "generic": HERE / "result.json", "runtime": runtime})
    check_protocol("bsgs_protocol.json", {"source": HERE / "norm_bsgs.py",
                                          "helper": HERE / "run.py", "geometry": geometry,
                                          "generic": HERE / "result.json",
                                          "horner": HERE / "norm_result.json", "runtime": runtime})
    check_protocol("audit_protocol.json", {"source": HERE / "audit.py",
                                           "geometry": geometry, "row": row,
                                           "generic": HERE / "result.json",
                                           "norm": HERE / "norm_result.json", "runtime": runtime})
    old = load("protocol_v1.json")
    failure = load("failure_v1.json")
    assert old["sha256"]["run"] == sha(HERE / "run_v1.py")
    assert failure["status"] == "PRODUCER_SERIALIZATION_FAILURE"
    assert failure["protocol_sha256"] == sha(HERE / "protocol_v1.json")
    assert failure["source_sha256"] == sha(HERE / "run_v1.py")
    packed = (HERE / "partial_result_v1.json.gz").read_bytes()
    assert failure["partial_result_gzip_sha256"] == hashlib.sha256(packed).hexdigest()
    assert failure["partial_result_sha256"] == hashlib.sha256(gzip.decompress(packed)).hexdigest()

    generic = load("result.json")
    horner = load("norm_result.json")
    bsgs = load("bsgs_result.json")
    audit = load("audit.json")
    projection = load("projection.json")
    for result, source, protocol in ((generic, "run.py", "protocol.json"),
                                    (horner, "norm.py", "norm_protocol.json"),
                                    (bsgs, "norm_bsgs.py", "bsgs_protocol.json")):
        assert result["status"] == "COMPLETE_BUCKET_DIAGNOSTIC"
        assert result["source_sha256"] == sha(HERE / source)
        assert result["protocol_sha256"] == sha(HERE / protocol)
        assert result["peak_rss_bytes"] < 4294967296
        assert result["elapsed_wall_ns"] < 120 * 10**9
        assert result["candidate_id"] is None and result["target_count"] == 1
    assert audit["status"] == "PASS"
    assert audit["source_sha256"] == sha(HERE / "audit.py")
    assert audit["audit_protocol_sha256"] == sha(HERE / "audit_protocol.json")
    assert audit["generic_result_sha256"] == sha(HERE / "result.json")
    assert audit["norm_result_sha256"] == sha(HERE / "norm_result.json")
    assert audit["eight_column_public_row_replay"] == "PASS"

    expected = {"negative": (0, 0, [], 27),
                "positive": (1, 1, [1873642659754], 25)}
    for label, (degree, group_hits, roots, products) in expected.items():
        g = next(case for case in generic["cases"] if case["label"] == label)
        h = next(case for case in horner["cases"] if case["label"] == label)
        b = next(case for case in bsgs["cases"] if case["label"] == label)
        a = next(case for case in audit["cases"] if case["label"] == label)
        assert g["gcd_degree"] == h["gcd_degree"] == b["gcd_degree"] == degree
        assert g["gcd_roots"] == h["gcd_roots"] == b["gcd_roots"] == roots
        assert len(g["group_hits"]) == a["direct_group_hit_count"] == group_hits
        assert g["x_hits"] == a["direct_x_hits"]
        assert b["modular_polynomial_products"] == products
        assert products == 2*b["block_width"] + 5*(b["blocks"] - 1) + 5
    assert projection["status"] == "EXACT_OPERATION_COUNT_PROJECTION"
    assert projection["source_sha256"] == sha(HERE / "projection.py")
    assert projection["input_pair_receipt_sha256"] == sha(pair)
    assert projection["left_bucket_polynomial_degree"] == 4124
    assert projection["bsgs_modular_polynomial_products"] == 407
    assert projection["horner_modular_polynomial_products"] == 8255
    assert (HERE / "RESULT.md").stat().st_size > 1000
    print("PASS: frozen sources, controls, group audit, caps, and transfer arithmetic")


if __name__ == "__main__":
    main()
