#!/usr/bin/env python3
"""Freeze six of the independently screened N41 W6 diagonal-atom rotations."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCREEN = HERE.parent / "n41_n131_diagonal_atom_20261010/screen.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    screen = json.loads(SCREEN.read_text())
    assert screen["status"] == "complete"
    assert screen["curve_id"] == "EC1N41Ckb1h7d5e80d3c4d0"
    assert screen["public_target"] == [1458168294740, 1672312028033]
    assert screen["slot_rotations"][:6] == [0, 5, 10, 15, 20, 25]
    assert screen["source_masks"] == 32
    assert screen["signed_frobenius_columns_K"] == 26
    path = HERE / "w6_input.txt"
    with path.open("x") as out:
        out.write("1458168294740 1672312028033 549756390943 6\n")
        for rotation, slot in zip(screen["slot_rotations"][:6], screen["slots"][:6]):
            assert len(slot) == 64
            out.write(f"{rotation} {len(slot)}\n")
            for row in slot:
                assert row["rotation"] == rotation
                assert 0 <= row["source_column"] < 26
                out.write(f"{row['point'][0]} {row['point'][1]} {row['mask']} "
                          f"{row['sign']} {row['source_column']}\n")
    result = {"status": "PASS_FROZEN_W6_SIX_ROTATION_INPUT",
              "curve_id": screen["curve_id"], "public_target_q": screen["public_target"],
              "paired_rotations": screen["slot_rotations"][:6],
              "signed_states_per_rotation": 64,
              "actual_factor_base_points_B": 384,
              "effective_folded_columns_K": 26,
              "source_sha256": {"script": sha(Path(__file__)),
                                "screen": sha(SCREEN), "input": sha(path)}}
    with (HERE / "w6_export.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
