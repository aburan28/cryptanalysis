"""Check the frozen W18 oracle, complete low-pivot replay, and Sage controls."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def limbs(value):
    return value[0] | value[1] << 64 | value[2] << 128


def check_sources(frozen, paths):
    assert frozen["source_sha256"] == {key: sha(path) for key, path in paths.items()}


def main():
    run = read("protocol.json")
    old = BASE / "n131_w14_coupled_fouratom_inverse_20261010"
    w15 = BASE / "n131_w15_allseed_inverse_20261011"
    support = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"
    table = BASE / "n131_w18_seedwise_fouratom_20261011/table.tsv"
    check_sources(run, {
        "generator": HERE / "generate.py", "runner": HERE / "run.py",
        "native_source": HERE / "native.cpp", "native_binary": HERE / "native",
        "support": support, "w18_pair_table": table,
        "w15_controls": w15 / "protocol.json",
        "archived_field": old / "native.cpp", "archived_terms": old / "resultant_terms.hpp",
    })
    assert run["status"] == "FROZEN_BEFORE_QUERY"
    assert run["source_width"] == 18 and run["seed_count"] == 262143
    assert run["source_masks"] == 131307 and run["workers"] == 1
    assert run["query_cap_seconds"] == 120 and run["rss_cap_bytes"] == 4 * 1024**3
    summaries = []
    for index, case in enumerate(run["cases"]):
        result_path = HERE / f"query_{index:03d}.json"
        result = read(result_path.name)
        receipt = read(f"receipt_{index:03d}.json")
        assert receipt["status"] == result["status"] == "COMPLETE"
        assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
        assert receipt["output_sha256"] == sha(result_path)
        assert receipt["case"] == case and receipt["returncode"] == 0
        assert receipt["stdout_sha256"] == sha(HERE / f"stdout_{index:03d}.txt")
        assert receipt["stderr_sha256"] == sha(HERE / f"stderr_{index:03d}.txt")
        assert limbs(result["supplied_reciprocal"]) == case["coordinate"]
        assert result["rotation"] == case["rotation"]
        assert result["seed_count"] == run["seed_count"]
        assert result["seeds_checked"] == (0 if result["trace_bit"] else run["seed_count"])
        assert len(result["hits"]) == result["source_pair_hits"] - result["column_rejects"]
        assert result["peak_rss_bytes"] < run["rss_cap_bytes"]
        assert result["query_ns_exploratory"] < run["query_cap_seconds"] * 10**9
        if case["expected_pair"] is not None:
            assert tuple(case["expected_pair"]) in {tuple(hit["masks"]) for hit in result["hits"]}
        summaries.append({"name": case["name"], "seeds_checked": result["seeds_checked"],
                          "hits": len(result["hits"]),
                          "query_ns_exploratory": result["query_ns_exploratory"],
                          "peak_rss_bytes": result["peak_rss_bytes"]})
    assert [item["hits"] for item in summaries] == [1, 1, 0, 0]

    low = read("lowpivot_protocol.json")
    low_paths = {"auditor": HERE / "audit_lowpivot.py",
                 "generator": HERE / "generate_lowpivot.py",
                 "lowpivot_source": HERE / "native_lowpivot.cpp",
                 "lowpivot_binary": HERE / "native_lowpivot",
                 "original_source": HERE / "native.cpp", "support": support,
                 "run_protocol": HERE / "protocol.json"}
    low_paths.update({f"original_query_{i}": HERE / f"query_{i:03d}.json"
                      for i in range(3)})
    check_sources(low, low_paths)
    low_result = read("lowpivot_audit.json")
    assert low_result["status"] == "PASS"
    assert low_result["protocol_sha256"] == sha(HERE / "lowpivot_protocol.json")
    assert len(low_result["rows"]) == 3
    for index, row in enumerate(low_result["rows"]):
        assert row == read(f"lowpivot_receipt_{index:03d}.json")
        assert row["status"] == "PASS_FULL_SEED_SEMANTIC_REPLAY"
        assert row["output_sha256"] == sha(HERE / f"lowpivot_query_{index:03d}.json")

    sample = read("sample_protocol.json")
    sample_paths = {"sampler": HERE / "validate_sample.py",
                    "sage_methods": HERE / "validate.py", "support": support,
                    "run_protocol": HERE / "protocol.json",
                    "lowpivot_audit": HERE / "lowpivot_audit.json",
                    "runtime": HERE / "sage_runtime_info.json"}
    sample_paths.update({f"query_{i}": HERE / f"query_{i:03d}.json"
                         for i in range(4)})
    check_sources(sample, sample_paths)
    sage = read("sample_validation.json")
    assert sage["status"] == "PASS_SAMPLED_SAGE_AND_GROUP_REPLAY"
    assert sage["sample_seeds"] == len(sample["sample_seed_masks"]) == 260
    assert sage["group_sign_matches"] == [2, 2, 0, 0]
    assert sage["sample_protocol_sha256"] == sha(HERE / "sample_protocol.json")
    assert read("sage_runtime_info.json")["status"] == "verified"
    interrupted = read("sage_fullscan_interruption_v1.json")
    assert interrupted["status"] == "INTERRUPTED_HOST_RESOURCE"
    assert interrupted["validation_protocol_sha256"] == sha(HERE / "validation_protocol.json")
    assert interrupted["exit_code"] == 130 and interrupted["seed_checkpoints_emitted"] == 0
    receipt = {"status": "PASS_W18_ALLSEED_PAIR_INVERSE_ARCHIVE",
               "run_protocol_sha256": sha(HERE / "protocol.json"),
               "lowpivot_audit_sha256": sha(HERE / "lowpivot_audit.json"),
               "sample_validation_sha256": sha(HERE / "sample_validation.json"),
               "summaries": summaries}
    path = HERE / "terminal_audit.json"
    if path.exists():
        assert read(path.name) == receipt
    else:
        with path.open("x") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(receipt["status"])


if __name__ == "__main__":
    main()
