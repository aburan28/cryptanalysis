#!/usr/bin/env python3
"""Read-only audit of the first-word gate design screen and bitset."""

import csv
import hashlib
import json
from pathlib import Path
import re
import struct


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    summary = json.loads((ROOT / "firstword-pair-gate-screen.json").read_text())
    raw_path = ROOT / summary["raw_csv"]
    header = REPO / "src/generated/tau_pair_firstword_gate.h"
    assert summary["status"] == "retrospective_firstword_gate_design_screen"
    assert sha256(raw_path) == summary["raw_csv_sha256"]
    assert sha256(header) == summary["gate_sha256"]
    for name, digest in summary["source_sha256"].items():
        assert sha256(REPO / name) == digest, name
    rows = list(csv.DictReader(raw_path.open(newline="")))
    assert len(rows) == 16384
    fixture = json.loads((ROOT / "tail-pair-fused-inputs.json").read_text())
    seen = set()
    for case_index in (0, 1, 4, 5):
        case = fixture["cases"][case_index]
        key = (case["curve"]["name"], case["point_index"])
        sample = [row for row in rows if (row["curve"], int(row["point_index"])) == key]
        assert len(sample) == 4096 and key not in seen
        seen.add(key)
        raw = (ROOT / case["scalar_file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == case["scalar_file_sha256"]
        scalars = struct.unpack("<4096Q", raw)
        assert [int(row["scalar_index"]) for row in sample] == list(range(4096))
        assert [int(row["scalar"]) for row in sample] == list(scalars)
    assert len(seen) == 4
    training = [row for row in rows if row["point_index"] == "0"]
    assert len(training) == 8192
    stats = {}
    for row in training:
        word = int(row["first_word"])
        n, gain = stats.get(word, (0, 0))
        stats[word] = (n + 1, gain + int(row["reference_score"]) -
                       int(row["periodic_score"]))
    selected = {word for word, (n, gain) in stats.items() if n >= 2 and gain > 0}
    assert len(selected) == summary["selected_word_count"] == 269
    assert sorted(selected) == summary["selected_words"]
    body = header.read_text().split("ca_tau_pair_firstword_gate[128] = {", 1)[1]
    values = [int(value) for value in re.findall(r"\d+", body.split("};", 1)[0])]
    assert len(values) == 128
    assert {word for word in range(1024) if values[word >> 3] & (1 << (word & 7))} == selected
    for row in rows:
        chosen = int(row["first_word"]) in selected
        assert row["selected"] == str(chosen)
        assert int(row["chosen_score"]) == int(row["periodic_score"] if chosen else
                                                row["reference_score"])
    for case in summary["cases"]:
        sample = [row for row in rows if row["curve"] == case["curve"] and
                  int(row["point_index"]) == case["point_index"]]
        assert len(sample) == case["count"] == 4096
        assert sum(int(row["reference_score"]) for row in sample) == case["reference_score"]
        assert sum(int(row["periodic_score"]) for row in sample) == \
            case["direct_periodic_score"]
        assert sum(int(row["chosen_score"]) for row in sample) == case["chosen_score"]
        assert sum(row["selected"] == "True" for row in sample) == case["selected_scalars"]
        assert case["saved_score"] == case["reference_score"] - case["chosen_score"]
    print("PASS: 16,384 pinned rows, training rule, bitset, and four score totals")


if __name__ == "__main__":
    audit()
