#!/usr/bin/env python3
"""Materialize canonical x coordinates for the exact shifted width-11 base."""

import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WIDTH = ROOT / "experiments/koblitz-n83-index-design-20260929/Q20261012_N83_WIDTH_FRONTIER"
sys.path[:0] = [str(ROOT / "ecc2k130/runner/codegen"),
                str(ROOT / "experiments/koblitz-pair-claw-20260929"),
                str(ROOT / "experiments/n83-orbit-key-x-20261012")]
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from fast_x import CanonicalXFromOrbitKey  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "d11_canonical_x.bin"
    receipt_path = HERE / "materialization.json"
    assert not output.exists() and not receipt_path.exists()
    frontier_path = WIDTH / "frontier.json"
    frontier = json.loads(frontier_path.read_text())
    assert frontier["status"] == "complete_geometry_stage"
    row = next(row for row in frontier["rows"] if row["dimension"] == 11
               and row["offset_onb_coordinates"] == 1 << 81)
    key_path = WIDTH / row["canonical_key_file"]
    assert sha(key_path) == row["canonical_key_sha256"]
    data = key_path.read_bytes()
    K = row["folded_columns_K"]
    assert len(data) == 21 * K
    keys = [int.from_bytes(data[i:i + 21], "little")
            for i in range(0, len(data), 21)]
    assert keys == sorted(set(keys))
    onb = field.Onb(83)
    orbit = OrbitKey(onb)
    lookup = CanonicalXFromOrbitKey(orbit)
    values = [lookup.canonical_x(key) for key in keys]
    assert len(set(values)) == K
    sample_indices = sorted(set([0, K // 2, K - 1] +
                                [(i * 514229) % K for i in range(257)]))
    for index in sample_indices:
        point = orbit.point_from_key(keys[index])
        assert point is not None
        expected = min(onb.toCoords(onb.frob(point[0], power))
                       for power in range(83))
        assert values[index] == expected
    payload = b"".join(value.to_bytes(11, "little") for value in values)
    with output.open("xb") as stream:
        stream.write(payload)
    receipt = {
        "kind": "n83_shifted_width11_canonical_x_materialization",
        "status": "PASS", "K": K,
        "B": row["actual_usable_points_B_before_folding"],
        "key_sha256": sha(key_path),
        "frontier_sha256": sha(frontier_path),
        "canonical_x_file": output.name,
        "canonical_x_sha256": sha(output),
        "canonical_x_bytes": len(payload),
        "sample_count": len(sample_indices),
        "sample_indices_sha256": hashlib.sha256(b"".join(
            index.to_bytes(4, "little") for index in sample_indices)).hexdigest(),
        "source_sha256": {
            "materialize.py": sha(Path(__file__)),
            "fast_x.py": sha(ROOT / "experiments/n83-orbit-key-x-20261012/fast_x.py"),
            "orbit_key.py": sha(ROOT / "experiments/koblitz-pair-claw-20260929/orbit_key.py"),
        },
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "K": K,
                      "bytes": len(payload),
                      "sample_count": len(sample_indices)}), flush=True)


if __name__ == "__main__":
    main()
