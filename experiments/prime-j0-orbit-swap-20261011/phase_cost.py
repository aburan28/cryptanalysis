#!/usr/bin/env python3
"""Count exact grouped-unit rotations for both frozen holdout covers."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "prime-j0-carry-aware-v2-20261011/phase_cost.py"
SPEC = importlib.util.spec_from_file_location("swap_phase_base", SOURCE)
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
TERMINAL = base.TERMINAL


def digest(raw):
    return sha256(raw).hexdigest()


def phases(path, terminal):
    masks = [0, 0, 0, 0]
    for _, _, seed, map_id, unit in path["digits"]:
        if seed:
            masks[map_id] |= 1 << (unit // 2)
    a, b = path["terminal"]
    seed, exponent, unit = base.terminal_code(terminal, a, b)
    if seed:
        masks[exponent] |= 1 << (unit // 2)
    rotations = sum(mask.bit_count() - 1 + int(not mask & 1)
                    for mask in masks if mask)
    return tuple(masks), rotations


def main():
    certificate = (HERE / "holdout-paths.jsonl").read_bytes()
    screen = json.loads((HERE / "holdout-screen.json").read_bytes())
    assert digest(certificate) == screen["certificate_sha256"]
    terminal = TERMINAL.read_bytes()
    counts = {name: Counter() for name in ("priority", "swapped")}
    differences = Counter()
    for line in certificate.splitlines():
        row = json.loads(line)
        rotations = {}
        for name in counts:
            masks, rotations[name] = phases(row[name], terminal)
            counts[name]["gauge_rotations"] += rotations[name]
            counts[name]["occupied_buckets"] += sum(bool(mask) for mask in masks)
        differences[rotations["swapped"] - rotations["priority"]] += 1
    result = {"schema": 1, "status": "phase_occupancy_screen",
              "cases": screen["cases"],
              "priority": dict(counts["priority"]),
              "swapped": dict(counts["swapped"]),
              "rotation_difference_histogram": dict(sorted(differences.items())),
              "terminal_sha256": digest(terminal),
              "certificate_sha256": digest(certificate),
              "source_sha256": digest(Path(__file__).read_bytes())}
    (HERE / "phase-cost.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
