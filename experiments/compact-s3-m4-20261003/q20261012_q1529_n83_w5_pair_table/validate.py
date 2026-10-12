#!/usr/bin/env python3
"""Independently check frozen Q1529 source, inputs, counts, and control."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / "bases/n83_weight5_full_point_orbits.bin"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    assert protocol["proposal_id"] == "Q1529"
    assert protocol["candidate_id"] is None and protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["base_B"] == 30977592 and protocol["folded_K"] == 186612
    assert sha(BASE) == protocol["base_sha256"]
    assert BASE.stat().st_size == 21 * protocol["folded_K"]
    assert sha(Path("/Volumes/SSD990/llm/tmp/q1529-native-w5-query")) == protocol["binary_sha256"]
    for name, digest in protocol["source_sha256"].items():
        assert sha(HERE / name) == digest
    targets = {"selected": ROOT / "q20261011_wdsat_phase_restart/target.json",
               "holdout": ROOT / "q20261011_n83_selector_holdout/target.json"}
    for label, path in targets.items():
        assert sha(path) == protocol["target_sha256"][label]
        fixture = json.loads(path.read_text())
        assert fixture["curve_id"] == protocol["curve_id"]
        assert fixture["workload_id"] == ("2eb250a29072" if label == "selected"
                                           else "394256b9f901")
    assert len(result["rows"]) == 13
    controls = 0
    for cell in result["rows"]:
        name = cell["label"]
        native = cell["native"]
        assert cell["status"] == "COMPLETE" and native["actual_B"] == protocol["base_B"]
        assert native["lifted_query_pairs"] == 166 * native["query_representatives"]
        assert native["false_positive_queries"] + native["exact_hit_queries"] == native["bloom_positive_queries"]
        if name == "control":
            controls += 1
            assert native["table_descriptors"] == native["query_representatives"] == 1
            assert any(hit["table_position"] == 0 and
                       hit["query_representative_position"] == 0 and
                       hit["frobenius_shift"] == 0 and
                       not hit["negative_query_pair"] for hit in native["hits"])
        else:
            assert name in targets and native["exact_hit_queries"] == 0
            assert native["table_descriptors"] == 1 << 18
            assert native["query_representatives"] in (1 << 17, 1 << 20)
        folder = HERE / "runs" / (
            f"{name}_t{native['table_descriptors']}_q{native['query_representatives']}"
            f"_b{native['bloom_bits_per_key']}_h{native['bloom_hashes']}"
            f"_r{native['representative_batch']}_w{native['query_workers']}")
        receipt = json.loads((folder / "receipt.json").read_text())
        assert sha(folder / "receipt.json") == cell["receipt_sha256"]
        assert sha(folder / "stdout.txt") == receipt["stdout_sha256"]
        assert sha(folder / "stderr.txt") == receipt["stderr_sha256"]
        assert json.loads((folder / "stdout.txt").read_text()) == native
        assert receipt["native"] == native and receipt["status"] == "COMPLETE"
    assert controls == 1
    analysis = json.loads((HERE / "analysis.json").read_text())
    assert len(analysis["rows"]) == 13
    assert analysis["conditional_N83_W5_pair_domain"] == 83 * 186612 * 186611
    assert analysis["conditional_N83_W5_expected_representatives_per_relation_numerator"] == (
        2 * 2417851639230796216685689 * 83 * 186612 * 186611)
    assert analysis["conditional_N83_W5_expected_representatives_per_relation_denominator"] == (
        30977592**2 * (1 << 18) * 166)
    q1526 = HERE.parent / "q20261012_q1526_pair_hyperparams/analysis.json"
    assert sha(q1526) == analysis["q1526_analysis_sha256"]
    w7 = next(row for row in json.loads(q1526.read_text())["cells"]
              if row["weight_bound"] == 7 and row["table_fraction"] == "1/1")
    b, k, r = w7["B"], w7["K"], 680564733841876926932320129493409985129
    assert analysis["conditional_N131_W7_quotient_reuse_pair_additions_numerator"] == (
        131 * k*k * 262 * b*b + 263 * k * 2 * r)
    assert analysis["conditional_N131_W7_quotient_reuse_pair_additions_denominator"] == 262*b*b
    proof = json.loads((HERE / "lean/proof_receipt.json").read_text())
    for name, key in (("QueryUnits.lean", "source_sha256"),
                      ("build.stdout.txt", "stdout_sha256"),
                      ("build.stderr.txt", "stderr_sha256")):
        assert sha(HERE / "lean" / name) == proof[key]
    assert not (HERE / "lean/build.stderr.txt").read_text()
    assert (HERE / "lean/build.stdout.txt").read_text().count("does not depend on any axioms") == 6
    print("PASS Q1529: source/binary, base/targets, 13 receipts, control, counts, Lean")


if __name__ == "__main__":
    main()
