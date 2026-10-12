#!/usr/bin/env python3
"""Count grouped-unit rotations on the paired exact-tau holdout."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prime-j0-orbit-swap-20261011/phase_cost.py"
SPEC = importlib.util.spec_from_file_location("tau_bound_phase_base", SOURCE)
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
TERMINAL = base.TERMINAL


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    certificate = (HERE / "holdout-paths.jsonl").read_bytes()
    screen = json.loads((HERE / "holdout-screen.json").read_bytes())
    assert digest(certificate) == screen["certificate_sha256"]
    terminal = TERMINAL.read_bytes()
    counts = {name: Counter() for name in ("swapped", "tau_exact")}
    differences = Counter()
    for line in certificate.splitlines():
        row = json.loads(line)
        rotations = {}
        for name in counts:
            masks, rotations[name] = base.phases(row[name], terminal)
            counts[name]["gauge_rotations"] += rotations[name]
            counts[name]["occupied_buckets"] += sum(bool(mask) for mask in masks)
        differences[rotations["tau_exact"] - rotations["swapped"]] += 1
    result = {"schema": 1, "status": "phase_occupancy_screen",
              "cases": screen["cases"],
              "swapped": dict(counts["swapped"]),
              "tau_exact": dict(counts["tau_exact"]),
              "rotation_difference_histogram": dict(sorted(differences.items())),
              "terminal_sha256": digest(terminal),
              "certificate_sha256": digest(certificate),
              "source_sha256": digest(Path(__file__).read_bytes())}
    (HERE / "phase-cost.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({name: result[name] for name in counts}, sort_keys=True))


if __name__ == "__main__":
    main()
