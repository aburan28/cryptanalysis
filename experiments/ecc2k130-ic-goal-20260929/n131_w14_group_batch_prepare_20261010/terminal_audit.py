#!/usr/bin/env python3
"""Read-only replay of frozen inputs, complete indexes, and query receipts."""

import json
import sys
from pathlib import Path

from audit_index import read_index
from freeze import HERE, OLD, SUPPORT, NATIVE, sha, sources


def v2_sources():
    return {"rotated_source": HERE / "prepare_rotated.cpp",
            "rotated_binary": HERE / "prepare_rotated",
            "freezer": HERE / "freeze_v2.py", "runner": HERE / "run_v2.py",
            "index_audit": HERE / "audit_index.py",
            "compiler_version": HERE / "compiler_version.txt",
            "field_source": NATIVE, "support": SUPPORT,
            "v1_protocol": HERE / "protocol.json", "v1_result": HERE / "result.json",
            "v1_index": HERE / "index.bin",
            "old_index": OLD / "index.bin", "old_query_binary": OLD / "stream",
            "old_query_protocol": OLD / "query_protocol_v2.json",
            "old_positive": OLD / "positive_v2.json",
            "old_negative": OLD / "trace_zero_control_v2.json"}


def main(record):
    p1 = json.loads((HERE / "protocol.json").read_text())
    p2 = json.loads((HERE / "protocol_v2.json").read_text())
    v1 = json.loads((HERE / "result.json").read_text())
    v2 = json.loads((HERE / "result_v2.json").read_text())
    prior = json.loads((OLD / "setup.json").read_text())
    assert p1["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert p2["source_sha256"] == {name: sha(path) for name, path in v2_sources().items()}
    assert v1["protocol_sha256"] == sha(HERE / "protocol.json")
    assert v2["protocol_sha256"] == sha(HERE / "protocol_v2.json")
    assert v1["status"] == "PASS_GROUP_BATCH_PREPARE_AND_QUERIES"
    assert v2["status"] == "PASS_ROTATED_GROUP_BATCH_PREPARE_AND_QUERIES"
    assert prior["status"] == "COMPLETE_PACKED_SEED_PREPARE"
    common = sha(HERE / "index.bin")
    assert common == sha(HERE / "index_rotated.bin")
    assert common == v1["index_sha256"] == v2["index_sha256"]
    assert common != sha(OLD / "index.bin")
    expected_pairs = prior["usable_mask_pairs"] == 132101
    assert expected_pairs
    assert prior["entries_per_rotation"] == 264202
    assert v1["setup"]["usable_mask_pairs"] == v2["setup"]["usable_mask_pairs"] == 132101
    assert v1["setup"]["entries_per_rotation"] == v2["setup"]["entries_per_rotation"] == 264202
    assert v2["setup"]["field_inversions"] == 1+4*64 == 257
    assert v2["setup"]["denominator_batch_terms"] == 2*132101
    assert v1["setup"]["setup_ns"] < p1["prepare_cap_seconds"]*10**9
    assert v2["setup"]["setup_ns"] < p2["prepare_cap_seconds"]*10**9
    assert v1["setup"]["peak_rss_bytes"] < p1["rss_cap_bytes"]
    assert v2["setup"]["peak_rss_bytes"] < p2["rss_cap_bytes"]
    old_iterator = iter(read_index(OLD / "index.bin"))
    new_iterator = iter(read_index(HERE / "index_rotated.bin"))
    entries, root_choice_differences = 0, 0
    for (old_seed, old_left, old_right), (new_seed, new_left, new_right) in \
            zip(old_iterator, new_iterator):
        assert old_seed == new_seed
        assert sorted(old_right) == sorted(new_right)
        old_left.sort(key=lambda row: (row[0], row[1]))
        new_left.sort(key=lambda row: (row[0], row[1]))
        assert len(old_left) == len(new_left)
        for old_row, new_row in zip(old_left, new_left):
            assert old_row[:2] == new_row[:2]
            assert old_row[3] == new_row[3] == 0
            assert old_row[2] ^ new_row[2] in (0, 1)
            root_choice_differences += old_row[2] != new_row[2]
        entries += len(new_left)
    assert entries == 264202
    assert next(old_iterator, None) is None
    assert next(new_iterator, None) is None
    for name in ("positive", "trace_zero_control"):
        old_path = OLD / ("positive_v2.json" if name == "positive" else
                          "trace_zero_control_v2.json")
        old = json.loads(old_path.read_text())
        first = json.loads((HERE / f"{name}.json").read_text())
        second = json.loads((HERE / f"{name}_rotated.json").read_text())
        assert old["status"] == first["status"] == second["status"] == \
            "COMPLETE_PACKED_SEED_QUERY"
        assert old["hits"] == first["hits"] == second["hits"]
        assert old["left_entries_checked"] == first["left_entries_checked"] == \
            second["left_entries_checked"] == 264202
        assert first["query_ns"] < p1["query_cap_seconds_per_case"]*10**9
        assert second["query_ns"] < p2["query_cap_seconds_per_case"]*10**9
        assert v1["queries"][name]["output_sha256"] == sha(HERE / f"{name}.json")
        assert v2["queries"][name]["output_sha256"] == sha(HERE / f"{name}_rotated.json")
    receipt = {"status": "PASS_GROUP_BATCH_TERMINAL_AUDIT",
               "curve_id": p2["curve_id"], "seed_range": [1, 64],
               "usable_mask_pairs": 132101, "entries_per_rotation": entries,
               "halftrace_root_choices_differ": root_choice_differences,
               "old_prepare_ns": prior["setup_ns"],
               "first_group_prepare_ns": v1["setup"]["setup_ns"],
               "rotated_group_prepare_ns": v2["setup"]["setup_ns"],
               "rotated_group_field_inversions": v2["setup"]["field_inversions"],
               "rotated_group_peak_rss_bytes": v2["setup"]["peak_rss_bytes"],
               "hits": {"positive": 1, "trace_zero_control": 0},
               "sha256": {"auditor": sha(Path(__file__)),
                          "protocol_v1": sha(HERE / "protocol.json"),
                          "protocol_v2": sha(HERE / "protocol_v2.json"),
                          "index_group": common,
                          "index_old": sha(OLD / "index.bin")}}
    target = HERE / "terminal_audit.json"
    if record:
        assert not target.exists()
        with target.open("x") as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2)
            stream.write("\n")
    else:
        assert json.loads(target.read_text()) == receipt
    print(json.dumps({"status": receipt["status"],
                      "entries_per_rotation": entries,
                      "root_choices_differ": root_choice_differences}, sort_keys=True))


if __name__ == "__main__":
    assert sys.argv[1:] in ([], ["--record"])
    main(sys.argv[1:] == ["--record"])
