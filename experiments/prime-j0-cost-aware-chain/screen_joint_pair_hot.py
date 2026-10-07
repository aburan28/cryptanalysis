#!/usr/bin/env python3
"""Screen a sparse hot-pair table on training and disjoint held-out scalars."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

from check_joint_pair_panel import independent_atlas, unit_images
from run import representatives


ROOT = Path(__file__).resolve().parent
HOT_SLOTS = 2048


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def position_counts(manifest_path, curve, record, preferred, rank):
    manifest = json.loads(manifest_path.read_text())
    counts = [Counter() for _ in range(record["pair_positions"] - 1)]
    scalars = 0
    for case in manifest["cases"]:
        if case["curve"]["name"] != curve:
            continue
        scalar_path = manifest_path.parent / case["scalar_file"]
        if sha256(scalar_path) != case["scalar_file_sha256"]:
            raise ValueError("scalar custody changed: " + case["id"])
        for (k,) in struct.iter_unpack("<Q", scalar_path.read_bytes()):
            _, a, b = min(representatives(record["order"], record["omega_eigen"], k),
                          key=lambda item: item[0])
            x, y = a + b, -b
            for position in range(record["pair_positions"]):
                digits = []
                for _ in range(2):
                    digit = preferred[(x % 16, y % 16)]
                    digits.append(digit)
                    x, y = (x - digit[0]) // 16, (y - digit[1]) // 16
                coefficient = (digits[0][0] + 16 * digits[1][0],
                               digits[0][1] + 16 * digits[1][1])
                if position < len(counts) and coefficient != (0, 0):
                    counts[position][rank[min(unit_images(coefficient))]] += 1
            if x or y:
                raise ValueError("the frozen pair expansion overflowed")
            scalars += 1
    return counts, scalars


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: screen_joint_pair_hot.py OUTPUT.json")
    training_path = ROOT / "joint-pair-top-inputs/inputs.json"
    heldout_path = ROOT / "joint-pair-width-inputs/inputs.json"
    design_path = ROOT / "joint-pair-design.json"
    top_path = ROOT / "joint-pair-top-design.json"
    panel_path = ROOT / "joint-pair-width-native-panel.json"
    panel = json.loads(panel_path.read_text())
    if panel.get("status") != "pass" or panel.get("inputs_sha256") != sha256(heldout_path):
        raise ValueError("held-out panel is not verified")
    design = json.loads(design_path.read_text())
    top = {row["curve"]: row for row in json.loads(top_path.read_text())["records"]}
    preferred, reps = independent_atlas()
    rank = {rep: index for index, rep in enumerate(reps)}
    mandatory = set()
    for digit in preferred.values():
        if digit != (0, 0):
            mandatory.add(rank[min(unit_images(digit))])
            mandatory.add(rank[min(unit_images((16 * digit[0], 16 * digit[1])))])
    if len(mandatory) != 86:
        raise ValueError("single-digit fallback basis changed")
    for first in preferred.values():
        for second in preferred.values():
            if first == (0, 0) and second == (0, 0):
                continue
            coefficient = (first[0] + 16 * second[0],
                           first[1] + 16 * second[1])
            orbit = rank[min(unit_images(coefficient))]
            if orbit not in mandatory and (first == (0, 0) or second == (0, 0)):
                raise ValueError("a cold pair has fewer than two nonzero digits")
    records = []
    for record in design["records"]:
        curve = record["curve"]
        training, training_scalars = position_counts(training_path, curve, record,
                                                      preferred, rank)
        heldout, heldout_scalars = position_counts(heldout_path, curve, record,
                                                    preferred, rank)
        if training_scalars != 16384 or heldout_scalars != 16384:
            raise ValueError("unexpected scalar count")
        positions = []
        extra_adds = 0
        for position, (train, test) in enumerate(zip(training, heldout)):
            optional = sorted((orbit for orbit in range(len(reps)) if orbit not in mandatory),
                              key=lambda orbit: (-train[orbit], orbit))
            selected = mandatory | set(optional[:HOT_SLOTS - len(mandatory)])
            training_total = sum(train.values())
            heldout_total = sum(test.values())
            training_hits = sum(train[orbit] for orbit in selected)
            heldout_hits = sum(test[orbit] for orbit in selected)
            extra_adds += heldout_total - heldout_hits
            positions.append({"position": position, "training_uses": training_total,
                              "training_hits": training_hits,
                              "heldout_uses": heldout_total,
                              "heldout_hits": heldout_hits,
                              "heldout_cold_pair_adds_predicted": heldout_total - heldout_hits})
        baseline_adds = sum(int(row["fields"]["adds"]) for row in panel["rows"]
                            if row["mode"] == "joint-pair-top-triple-pos" and
                            row["fields"]["curve"] == curve)
        records.append({"curve": curve, "hot_slots_per_lower_position": HOT_SLOTS,
                        "mandatory_fallback_orbits": len(mandatory),
                        "positions": positions,
                        "heldout_pair_adds_measured_control": baseline_adds,
                        "heldout_sparse_adds_predicted": baseline_adds + extra_adds,
                        "triple_table_bytes_predicted":
                            24 * ((record["pair_positions"] - 1) * HOT_SLOTS +
                                  top[curve]["top_orbits"])})
    report = {"schema": 1, "status": "screen_only_no_native_candidate",
              "method": "choose 2048 lower-pair orbits per position from training frequencies, forcing all 86 single-digit fallback orbits; cold pairs need one extra group addition",
              "training_inputs_sha256": sha256(training_path),
              "heldout_inputs_sha256": sha256(heldout_path),
              "heldout_panel_sha256": sha256(panel_path),
              "pair_design_sha256": sha256(design_path),
              "top_design_sha256": sha256(top_path),
              "source_sha256": sha256(Path(__file__)), "records": records}
    output = Path(sys.argv[1])
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "records": records}, sort_keys=True))


if __name__ == "__main__":
    main()
