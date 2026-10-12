#!/usr/bin/env python3
"""Read-only audit of all prospective held-out native word streams."""

import argparse
import hashlib
import json
from pathlib import Path

from check_periodic_pair_design import parse_trace
from make_inputs import read_fields


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MODE = "tail-pair-periodic-firstword27"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(bench):
    receipt = json.loads((ROOT / "firstword-pair-native-heldout-words.json").read_text())
    fixture = json.loads((ROOT / "firstword-pair-inputs.json").read_text())
    assert receipt["schema"] == 1 and receipt["status"] == "exact_match"
    assert len(receipt["runs"]) == 512
    assert len({(run["case_id"], run["chunk"]) for run in receipt["runs"]}) == 512
    if bench is not None:
        assert sha256(bench) == receipt["bench_sha256"]
    for name, digest in receipt["source_sha256"].items():
        assert sha256(REPO / name) == digest, name
    expected_cases = {case["id"]: case for case in fixture["cases"]}
    assert {run["case_id"] for run in receipt["runs"]} == set(expected_cases)
    for run in receipt["runs"]:
        case = expected_cases[run["case_id"]]
        chunk = run["chunk"]
        assert 0 <= chunk < 64
        scalar_path = ROOT / case["scalar_file"]
        raw = scalar_path.read_bytes()[512 * chunk:512 * (chunk + 1)]
        assert hashlib.sha256(raw).hexdigest() == run["input_sha256"]
        assert run["command"][1:4] == [MODE, case["curve"]["name"],
                                       str(case["point_index"])]
        assert run["status"] == "exited" and run["returncode"] == 0
        assert not run["problems"]
        traces, other_stderr = parse_trace(run["stderr"])
        assert len(traces) == 64 and not other_stderr
        digest = hashlib.sha256(json.dumps([traces[index] for index in range(64)],
                                            separators=(",", ":")).encode()).hexdigest()
        assert digest == run["native_word_sha256"] == run["expected_word_sha256"]
        fields = read_fields(run["stdout"])
        for name, expected in (("curve", case["curve"]["name"]),
                               ("point_index", str(case["point_index"])),
                               ("count", "64"), ("triples", str(run["expected_triples"])),
                               ("adds", str(run["expected_adds"])),
                               ("periodic_lookups", str(run["expected_lookups"])),
                               ("periodic_accepted", str(run["expected_selected"])),
                               ("periodic_fallbacks", "0"),
                               ("periodic_checks", "64"),
                               ("point_entries", "726"),
                               ("tail_complete_preparation_checks", "726"),
                               ("prep_bytes", "24336"),
                               ("static_map_bytes", "68157"), ("verified", "1")):
            assert fields.get(name) == expected, (run["case_id"], chunk, name)
    panel = json.loads((ROOT / "firstword-pair-native-panel.json").read_text())
    for case in fixture["cases"]:
        group = [run for run in receipt["runs"] if
                 run["case_id"] == case["id"]]
        assert len(group) == 64
        candidate = next(row for row in panel["rows"] if row["case_id"] == case["id"]
                         and row["arm"] == MODE)
        assert sum(10 * run["expected_triples"] + 16 * run["expected_adds"]
                   for run in group) == candidate["weighted_group_score"]
        assert sum(run["expected_selected"] for run in group) == candidate["periodic_accepted"]
        assert sum(run["expected_lookups"] for run in group) == candidate["periodic_lookups"]
    print("PASS: 512 raw runs, 32,768 exact word streams, and eight score totals")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, help="optional exact design64 executable")
    args = parser.parse_args()
    audit(args.bench)
