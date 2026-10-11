"""Verify frozen native sources and exact output identity on both controls."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVED = Path("/Volumes/SSD990/cryptanalysis/experiments/ecc2k130-ic-goal-20260929/n131_w15_rotated_fouratom_inverse_20261010")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    first = json.loads((HERE / "protocol.json").read_text())
    second = json.loads((HERE / "protocol_v2.json").read_text())
    paths1 = {"field_fast": HERE / "field_fast.hpp",
              "test_field": HERE / "test_field.cpp",
              "generator": HERE / "generate_fast.py",
              "generated": HERE / "native_fast.cpp",
              "archived_native": ARCHIVED / "native.cpp",
              "terms": ARCHIVED / "rotated_terms.hpp",
              "positive_input": ARCHIVED / "input_n131_positive.txt",
              "control_input": ARCHIVED / "input_n131_field_control.txt",
              "positive_reference": ARCHIVED / "receipt_n131_positive.json",
              "control_reference": ARCHIVED / "receipt_n131_field_control.json"}
    paths2 = {"generator_v2": HERE / "generate_fast_sq.py",
              "native_fast": HERE / "native_fast.cpp",
              "native_fast_sq": HERE / "native_fast_sq.cpp",
              "field_fast": HERE / "field_fast.hpp",
              "positive_input": ARCHIVED / "input_n131_positive.txt",
              "control_input": ARCHIVED / "input_n131_field_control.txt",
              "positive_reference": ARCHIVED / "native_n131_positive.json",
              "control_reference": ARCHIVED / "native_n131_field_control.json"}
    assert first["source_sha256"] == {key: sha(path) for key, path in paths1.items()}
    assert second["source_sha256"] == {key: sha(path) for key, path in paths2.items()}
    assert first["status"] == "FROZEN_BEFORE_N131_FAST_FIELD_INVERSE_REPLAY"
    assert second["status"] == "FROZEN_BEFORE_N131_PMULL_SQUARE_TABLE_REPLAY"
    assert first["worker_count"] == second["worker_count"] == 1
    micro = {}
    for name in ("test_field", "test_field_portable"):
        proc = subprocess.run([str(HERE / name)], capture_output=True, text=True,
                              check=True, timeout=30)
        assert proc.stdout.strip() == "PASS exact products=10036"
        assert not proc.stderr.strip()
        micro[name] = {"binary_sha256": sha(HERE / name),
                       "exact_products": 10036}
    rows = {}
    for case, reference in (("positive", "native_n131_positive.json"),
                            ("control", "native_n131_field_control.json")):
        old = json.loads((ARCHIVED / reference).read_text())
        row = {"archived_query_ns": old["query_ns"]}
        for suffix, name in (("v1", case), ("v2", case + "_v2")):
            path = HERE / (name + ".json")
            new = json.loads(path.read_text())
            for key in old:
                if key not in ("setup_ns", "query_ns", "peak_rss_bytes"):
                    assert new[key] == old[key], (case, suffix, key)
            assert new["status"] == "COMPLETE_ALGEBRAIC_SCAN"
            assert new["processed_product_states"] == 16384
            assert new["peak_rss_bytes"] < second["rss_cap_bytes"]
            assert new["query_ns"] < second["query_cap_seconds"] * 10**9
            row[suffix] = {"query_ns": new["query_ns"],
                           "peak_rss_bytes": new["peak_rss_bytes"],
                           "output_sha256": sha(path),
                           "semantic_fields_exactly_equal": True}
        rows[case] = row
    rebuilt = json.loads((HERE / "positive_rebuilt.json").read_text())
    measured = json.loads((HERE / "positive_v2.json").read_text())
    for key in measured:
        if key not in ("setup_ns", "query_ns", "peak_rss_bytes"):
            assert rebuilt[key] == measured[key], key
    assert sha(HERE / "native_fast_sq_rebuilt") != sha(HERE / "native_fast_sq")
    result = {"status": "PASS_EXACT_NATIVE_PMULL_AND_SQUARE_TABLE_REPLAY",
              "architecture": "arm64", "portable_fallback_tested": True,
              "microtests": micro, "cases": rows,
              "binary_sha256": {name: sha(HERE / name)
                                for name in ("native_fast", "native_fast_sq")},
              "source_rebuild": {
                  "binary_sha256": sha(HERE / "native_fast_sq_rebuilt"),
                  "byte_identical_to_measured_binary": False,
                  "positive_output_sha256": sha(HERE / "positive_rebuilt.json"),
                  "positive_semantic_fields_exactly_equal": True},
              "protocol_sha256": {"v1": sha(HERE / "protocol.json"),
                                  "v2": sha(HERE / "protocol_v2.json")},
              "audit_source_sha256": sha(__file__)}
    (HERE / "audit_result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": result["status"],
                      "positive_query_ns": rows["positive"]["v2"]["query_ns"],
                      "control_query_ns": rows["control"]["v2"]["query_ns"]}))


if __name__ == "__main__":
    main()
