#!/usr/bin/env python3
"""Count grouped-unit rotations and tau buckets on the budgeted panel."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prime-j0-orbit-swap-20261011/phase_cost.py"
SPEC = importlib.util.spec_from_file_location("phase_optimal_cost_base", SOURCE)
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    certificate = (HERE / "holdout-paths.jsonl").read_bytes()
    screen = json.loads((HERE / "holdout-screen.json").read_bytes())
    assert digest(certificate) == screen["certificate_sha256"]
    terminal = base.TERMINAL.read_bytes()
    names = ("phase_optimal", "budget_optimal")
    counts = {name: Counter() for name in names}
    differences = Counter()
    for line in certificate.splitlines():
        row = json.loads(line)
        rotations = {}
        for name in names:
            masks, rotations[name] = base.phases(row[name], terminal)
            counts[name]["gauge_rotations"] += rotations[name]
            counts[name]["occupied_buckets"] += sum(bool(mask) for mask in masks)
            counts[name]["tau2_bucket_active"] += bool(masks[2])
        differences[rotations["budget_optimal"] - rotations["phase_optimal"]] += 1
    result = {"schema": 1, "status": "phase_occupancy_screen",
              "cases": screen["cases"],
              "phase_optimal": dict(counts["phase_optimal"]),
              "budget_optimal": dict(counts["budget_optimal"]),
              "rotation_difference_histogram": dict(sorted(differences.items())),
              "terminal_sha256": digest(terminal),
              "certificate_sha256": digest(certificate),
              "source_sha256": digest(Path(__file__).read_bytes())}
    (HERE / "phase-cost.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({name: result[name] for name in names}, sort_keys=True))


if __name__ == "__main__":
    main()
