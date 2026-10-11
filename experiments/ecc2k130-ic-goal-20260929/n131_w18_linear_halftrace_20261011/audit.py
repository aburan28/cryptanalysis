"""Audit the paired linear-halftrace replay against the checked-Sage archive."""

import hashlib
import json
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n131_w18_ondemand_seedjoin_20261011"
TIMING_KEYS = {"table_build_ns_exploratory", "lookup_ns_exploratory",
               "query_ns_exploratory", "peak_rss_bytes"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def untimed(result):
    return {key: value for key, value in result.items() if key not in TIMING_KEYS}


def main():
    protocol = load(HERE / "protocol.json")
    receipt = load(HERE / "run_receipt.json")
    assert receipt["status"] == "COMPLETE"
    assert receipt["protocol_sha256"] == digest(HERE / "protocol.json")
    assert len(receipt["cases"]) == 2 * len(protocol["cases"])
    assert digest(OLD / "validation.json") == protocol["source_sha256"]["baseline_validation"]
    assert load(OLD / "terminal_audit.json")["status"] == "verified"
    assert receipt["resume_source_sha256"] == digest(HERE / "resume.py")
    files = {"runner": HERE / "run.py", "candidate_source": HERE / "native.cpp",
             "candidate_binary": HERE / "native", "baseline_source": OLD / "native.cpp",
             "baseline_binary": OLD / "native", "inherited_base": HERE.parent / "n131_w18_seedwise_hashjoin_20261011/base.hpp",
             "archived_field": HERE.parent / "n131_w14_coupled_fouratom_inverse_20261010/native.cpp",
             "support": run.SUPPORT, "baseline_protocol": OLD / "protocol.json",
             "baseline_receipt": OLD / "run_receipt.json", "baseline_validation": OLD / "validation.json"}
    assert protocol["source_sha256"] == {name: digest(path) for name, path in files.items()}
    comparison = []
    for index, case in enumerate(protocol["cases"]):
        archived = load(OLD / f"query_{index:03d}.json")
        archived_table = digest(OLD / f"table_{index:03d}.tsv")
        rows = [row for row in receipt["cases"] if row["case_index"] == index]
        assert [row["variant"] for row in rows] == case["order"]
        assert len(rows) == 2
        for row in rows:
            stem = f"{index:03d}_{row['variant']}"
            query = HERE / f"query_{stem}.json"
            table = HERE / f"table_{stem}.tsv"
            assert row["name"] == case["name"]
            assert row["status"] == "COMPLETE" and row["returncode"] == 0
            assert row["output_sha256"] == digest(query)
            assert row["table_sha256"] == archived_table
            if table.exists():
                assert digest(table) == archived_table
            for kind in ("stdout", "stderr"):
                assert row[f"{kind}_sha256"] == digest(HERE / f"{kind}_{stem}.txt")
            assert row["native_result"] == load(query)
            raw = row["native_result"]
            assert raw["status"] == "COMPLETE"
            assert raw["seed_mask"] == case["seed_mask"]
            assert len(raw["output_z"]) == 3
            assert sum(word << (64 * position) for position, word in enumerate(raw["output_z"])) == case["output_z"]
            assert untimed(raw) == untimed(archived)
            assert raw["peak_rss_bytes"] < protocol["rss_cap_bytes"]
            build = raw["table_build_ns_exploratory"]
            lookup = raw["lookup_ns_exploratory"]
            charged = raw["query_ns_exploratory"]
            assert 0 <= charged - build - lookup < 10_000_000
            assert charged < protocol["native_cap_seconds"] * 1_000_000_000
            assert row["parent_wall_ns_exploratory"] < protocol["parent_cap_seconds"] * 1_000_000_000
        paired = {row["variant"]: row["native_result"] for row in rows}
        pairs = paired["linear"]["source_pairs"]
        outputs = paired["linear"]["left_outputs"]
        # The archived kernel computes one halftrace per source pair, left
        # output, and query. The linear kernel computes 131 basis images.
        iterative_calls = pairs + outputs + 1
        comparison.append({
            "name": case["name"], "seed_mask": case["seed_mask"],
            "source_pairs": pairs, "pair_outputs": outputs,
            "s3_candidates": paired["linear"]["right_checked"],
            "hits": len(paired["linear"]["hits"]),
            "table_sha256": archived_table,
            "iterative_halftrace_calls_removed": iterative_calls,
            "iterative_halftrace_squarings_removed": iterative_calls * 130,
            "basis_halftrace_squarings_charged": 131 * 130,
            "baseline_query_ns_exploratory": paired["baseline"]["query_ns_exploratory"],
            "linear_query_ns_exploratory": paired["linear"]["query_ns_exploratory"],
            "baseline_build_ns_exploratory": paired["baseline"]["table_build_ns_exploratory"],
            "linear_build_ns_exploratory": paired["linear"]["table_build_ns_exploratory"],
            "baseline_lookup_ns_exploratory": paired["baseline"]["lookup_ns_exploratory"],
            "linear_lookup_ns_exploratory": paired["linear"]["lookup_ns_exploratory"],
            "baseline_peak_rss_bytes": paired["baseline"]["peak_rss_bytes"],
            "linear_peak_rss_bytes": paired["linear"]["peak_rss_bytes"],
        })
    audit = {"status": "verified", "protocol_sha256": digest(HERE / "protocol.json"),
             "run_receipt_sha256": digest(HERE / "run_receipt.json"),
             "archived_validation_sha256": digest(OLD / "validation.json"),
             "comparison": comparison}
    (HERE / "audit.json").write_text(json.dumps(audit, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": audit["status"], "cases": len(comparison)}))


if __name__ == "__main__":
    main()
