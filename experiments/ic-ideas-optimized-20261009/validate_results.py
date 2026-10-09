#!/usr/bin/env python3
"""Check receipts, exact witness invariants, and retained raw run hashes."""
from __future__ import annotations

import gzip
import hashlib
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-solver-gates-20261008"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data(name: str) -> dict:
    return json.loads((HERE / name).read_text())


def check_a1(name: str, arm: str) -> None:
    receipt = data(name)
    assert receipt["status"] == "matched_correctness_pass"
    driver = (HERE / f"a1_{arm}_bench.py" if arm in ("bucket", "offset")
              else HERE / "a1_index_bench_v2.py")
    assert receipt["driver_sha256"] == sha(driver)
    assert receipt["control_source_sha256"] == sha(
        HERE / "a1_n53_control/src/bin/target_probe.rs")
    assert receipt[f"{arm}_source_sha256"] == sha(
        HERE / f"a1_n53_{arm}_index/src/bin/target_probe.rs")
    rows = receipt["runs"]
    assert [row["label"] for row in rows] == ["control", arm, arm, "control"]
    invariants = ("target_point", "recovered_scalar", "witness_indices",
                  "base_hash_blake3",
                  "pair_sums", "distinct_pair_x_orbit_keys", "duplicate_pair_keys",
                  "actual_usable_B", "independent_log_columns")
    for row in rows:
        assert row["status"] == "process_complete" and row["exit_code"] == 0
        raw = HERE / f"a1_{arm}_runs" / row["raw_path"]
        assert sha(raw) == row["raw_sha256"]
        result = json.loads(raw.read_text())
        assert result == row["result"]
        assert result["status"] == "verified_recovery"
        assert result["recovered_scalar"] == 6_141_872_670_687
        assert result["witness_indices"] == [6893, 43623, 4487]
        assert result["charged_online_ns_exploratory"] == sum(
            result["phase_ns_exploratory"].values())
    for key in invariants:
        assert len({json.dumps(row["result"][key], sort_keys=True)
                    for row in rows}) == 1, key


def main() -> None:
    assert data("sage_runtime_info.json")
    g1 = data("g1_adaptive.json")
    assert g1["source_sha256"] == sha(HERE / "g1_adaptive.py")
    assert g1["adaptive_source_sha256"] == sha(HERE / "native_f4_adaptive.cpp")
    assert g1["control_source_sha256"] == sha(PRIOR / "native_f4_symbolic.cpp")
    for cell in g1["cells"]:
        assert len(cell["targets"]) == 16
        for row in cell["targets"]:
            if row["fresh_status"] == "gb":
                assert row["adaptive_status"] == "gb"
                assert row["basis_equal"] and row["proof_replays"]
                assert row["truth_set_equal"]
            else:
                assert row["fresh_status"] == row["adaptive_status"] == "inconclusive"
    for arm in ("sorted", "bucket", "offset"):
        check_a1(f"a1_{arm}_bench.json", arm)
    hash_audit = data("a1_hash_audit.json")
    assert hash_audit["source_sha256"] == sha(HERE / "a1_hash_audit.py")
    assert hash_audit["executed_driver_sha256"] == sha(HERE / "a1_index_bench.py")
    assert hash_audit["partial_sha256"] == sha(HERE / "a1_index_bench.partial.json")
    assert len(hash_audit["rows"]) == 4
    for row in hash_audit["rows"]:
        assert row["result"]["status"] == "verified_recovery"
        assert row["raw_sha256"] == sha(HERE / "a1_runs" / row["raw_path"])
    a2 = data("a2_sparse_membership.json")
    assert a2["source_sha256"] == sha(HERE / "a2_sparse_membership.py")
    assert a2["prior_receipt_sha256"] == sha(
        HERE.parent / "ic-ideas-20261007/results/a2_final.json")
    assert a2["sparse_sum_count"] == 17_296
    assert a2["exact_domain_matches"] == 1 << 23
    assert a2["frobenius_support_matches"] == 17_296
    bits_path = HERE / "a2_sparse_membership.bits.gz"
    map_path = HERE / "a2_sparse_membership.supports.gz"
    assert sha(bits_path) == a2["bitset_sha256"]
    assert sha(map_path) == a2["support_map_sha256"]
    bits = gzip.decompress(bits_path.read_bytes())
    supports = gzip.decompress(map_path.read_bytes())
    assert len(bits) == 1 << 20 and len(supports) == 7 * 17_296
    popcounts = [bin(byte).count("1") for byte in range(256)]
    assert sum(popcounts[byte] for byte in bits) == 17_296
    for x, a, b, c in struct.iter_unpack("<IBBB", supports):
        assert bits[x >> 3] & (1 << (x & 7))
        assert 0 <= a < b < 47
        assert c == 255 or b < c < 47
    a2_sage = data("a2_sage_verify.json")
    assert a2_sage["status"] == "all_sparse_supports_replayed"
    assert a2_sage["checked_supports"] == 17_296
    assert a2_sage["source_sha256"] == sha(HERE / "a2_sage_verify.py")
    assert a2_sage["membership_receipt_sha256"] == sha(
        HERE / "a2_sparse_membership.json")
    assert a2_sage["supports_gzip_sha256"] == sha(map_path)
    g4 = data("g4_exact_panel12.json")
    assert g4["source_sha256"] == sha(HERE / "g4_exact_matched_panel.py")
    assert len(g4["rows"]) == 24
    assert set(g4["target_indices"]) == set(range(12))
    for index in range(12):
        rows = [row for row in g4["rows"] if row["target_index"] == index]
        assert {row["encoding"] for row in rows} == {"mixed_chain4", "boolean"}
        assert all(row["status"] == "completed" for row in rows)
        for row in rows:
            if row["status"] == "completed":
                assert row["variables"] == (16 if row["encoding"] == "mixed_chain4" else 25)
    print("PASS: G1, A1, A2, G4 receipts and raw artifacts")


if __name__ == "__main__":
    main()
