"""Freeze the two W6 raw-source windows and nine middle-point queries."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
screen_path = ROOT / "n131_w18_four_pairs/screen.json"
fixture_path = ROOT / "n41_two_pair_relaxation_20261011/targets.json"
screen = json.loads(screen_path.read_text())["n41"]
fixture = json.loads(fixture_path.read_text())
assert screen["public_target_q"] == fixture["public_target_original"]
assert screen["slot_rotations"] == [0, 0, 10, 10, 20, 20, 30, 30]
rows = [("positive", *fixture["known_positive"]["right_middle_point"])]
rows += [(f"control_{i}", *row["right_middle_point"])
         for i, row in enumerate(fixture["controls"])]
lines = [str(len(rows))]
lines += [f"{label} {x} {y}" for label, x, y in rows]
for rotation in (20, 30):
    points = screen["point_rows_by_unique_rotation"][str(rotation)]
    assert len(points) == 64
    lines.append(f"{rotation} {len(points)}")
    lines += [" ".join(map(str, point)) for point in points]
input_path = HERE / "input.txt"
input_path.write_text("\n".join(lines) + "\n")
manifest = {"status": "FROZEN_EXACT_TRANSPORT_N41_INPUT",
            "rows": rows, "point_rows_per_rotation": 64,
            "public_target_q": screen["public_target_q"],
            "source_curve_ids": [screen["curve_id"], fixture["curve_id"]],
            "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
            "screen_sha256": hashlib.sha256(screen_path.read_bytes()).hexdigest(),
            "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
            "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(HERE / "input_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
print(manifest["status"], rows)
