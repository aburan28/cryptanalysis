"""Audit the frozen target-linear query and its exact reference replay."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PRIOR = BASE / "n131_w18_allseed_pair_inverse_20261011"
SUPPORT = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"
ARCH = BASE / "n131_w14_coupled_fouratom_inverse_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def semantic(value):
    return {key: item for key, item in value.items()
            if key not in ("setup_ns_exploratory", "query_ns_exploratory", "peak_rss_bytes")}


def main():
    protocol_path = HERE / "protocol.json"
    protocol = read(protocol_path)
    assert protocol["status"] == "FROZEN_BEFORE_PAIRED_QUERY"
    paths = {"generator": HERE / "generate.py", "runner": HERE / "run.py",
             "linear_source": HERE / "native.cpp", "linear_binary": HERE / "native",
             "prior_source": PRIOR / "native.cpp", "prior_binary": PRIOR / "native",
             "prior_protocol": PRIOR / "protocol.json",
             "prior_audit": PRIOR / "terminal_audit.json", "support": SUPPORT,
             "field_source": ARCH / "native.cpp", "field_terms": ARCH / "resultant_terms.hpp"}
    assert protocol["source_sha256"] == {key: sha(path) for key, path in paths.items()}
    assert read(PRIOR / "terminal_audit.json")["status"] == \
        "PASS_W18_ALLSEED_PAIR_INVERSE_ARCHIVE"
    assert protocol["seed_count"] == 262143 and protocol["workers"] == 1
    assert protocol["candidate_product_field_multiplies"] == {
        "reference_trace_zero": 524286, "target_linear_trace_zero": 19,
        "either_trace_one": 0}
    rows = []
    for index, case in enumerate(protocol["cases"]):
        results = {}
        for arm in protocol["case_arm_order"][index]:
            prefix = f"case_{index:03d}_{arm}"
            path = HERE / f"{prefix}.json"
            receipt = read(HERE / f"{prefix}.receipt.json")
            result = read(path)
            assert receipt["status"] == result["status"] == "COMPLETE"
            assert receipt["name"] == case["name"] and receipt["arm"] == arm
            assert receipt["protocol_sha256"] == sha(protocol_path)
            assert receipt["output_sha256"] == sha(path)
            assert receipt["stdout_sha256"] == sha(HERE / f"{prefix}.stdout.txt")
            assert receipt["stderr_sha256"] == sha(HERE / f"{prefix}.stderr.txt")
            assert result["seeds_checked"] == (0 if result["trace_bit"] else 262143)
            assert result["query_ns_exploratory"] < 120 * 10**9
            assert result["peak_rss_bytes"] < 4 * 1024**3
            results[arm] = result
        assert semantic(results["reference"]) == semantic(results["target_linear"])
        assert semantic(results["reference"]) == semantic(read(PRIOR / f"query_{index:03d}.json"))
        comparison = read(HERE / f"case_{index:03d}_comparison.json")
        assert comparison["status"] == "PASS_EXACT_SEMANTIC_MATCH"
        assert comparison["protocol_sha256"] == sha(protocol_path)
        assert comparison["reference_query_ns_exploratory"] == results["reference"]["query_ns_exploratory"]
        assert comparison["target_linear_query_ns_exploratory"] == results["target_linear"]["query_ns_exploratory"]
        rows.append(comparison)
    assert len(rows) == 4

    sage_protocol_path = HERE / "sage_validation_protocol.json"
    sage_protocol = read(sage_protocol_path)
    sage_paths = {"validator": HERE / "validate_sage.py", "protocol": protocol_path,
                  "runtime": HERE / "sage_runtime_info.json",
                  "sample_seeds": PRIOR / "sample_protocol.json",
                  "prior_validation": PRIOR / "sample_validation.json"}
    sage_paths.update({f"new_query_{i}": HERE / f"case_{i:03d}_target_linear.json"
                       for i in range(4)})
    assert sage_protocol["source_sha256"] == {key: sha(path) for key, path in sage_paths.items()}
    sage_result = read(HERE / "sage_validation.json")
    assert sage_result["status"] == "PASS_SAGE_LINEAR_TARGET_PRODUCTS"
    assert sage_result["sample_seed_count"] == 260
    assert [row["branch_checks"] for row in sage_result["cases"]] == [520, 520, 520, 0]
    assert sage_result["protocol_sha256"] == sha(sage_protocol_path)
    assert read(HERE / "sage_runtime_info.json")["status"] == "verified"
    output = {"status": "PASS_W18_ALLSEED_LINEAR_QUERY_ARCHIVE",
              "protocol_sha256": sha(protocol_path),
              "sage_validation_sha256": sha(HERE / "sage_validation.json"),
              "comparisons": rows}
    path = HERE / "terminal_audit.json"
    if path.exists():
        assert read(path) == output
    else:
        with path.open("x") as stream:
            json.dump(output, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(output["status"])


if __name__ == "__main__":
    main()
