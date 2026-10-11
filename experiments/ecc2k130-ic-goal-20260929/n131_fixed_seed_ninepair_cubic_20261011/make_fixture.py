"""Extend the independently replayed eight-pair control by one source pair."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "n131_fixed_seed_eight_pair_circuit_20261010"
BASE = ROOT / "n131_fixed_seed_halftrace_cubic_20261011"
SUPPORT = ROOT / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"
sys.path.insert(0, str(BASE))
import verify as independent  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shifted_reciprocal_x(point):
    assert point is not None and point[0] != 1
    return independent.inverse(point[0] ^ 1)


def main():
    derive = json.loads((OLD / "derive_result.json").read_text())
    chain = json.loads((OLD / "planted_chain_result.json").read_text())
    assert len(derive["selected"]) == 8 and len(chain["intermediate_z"]) == 6
    columns = {int(mask): int(column) for mask, column in
               (line.split() for line in SUPPORT.read_text().splitlines())}
    occupied = {column for item in derive["selected"] for column in item["folded_columns"]}
    options = [(a, a ^ 212) for a in sorted(columns)
               if a < a ^ 212 and a ^ 212 in columns
               and columns[a] != columns[a ^ 212]
               and not ({columns[a], columns[a ^ 212]} & occupied)]
    assert options
    a, b = options[0]
    raw_pair = independent.point_add(independent.point_options(a)[0],
                                     independent.point_options(b)[0])
    assert raw_pair is not None and raw_pair[0] not in (0, 1)
    rotation = 128
    rotated = tuple(independent.frobenius(value, rotation) for value in raw_pair)
    original = tuple(chain["raw_target"])
    target = independent.point_add(original, rotated)
    assert target is not None and target[0] not in (0, 1)
    new_item = {"slot": 8, "rotation": rotation, "masks": [a, b],
                "folded_columns": [columns[a], columns[b]],
                "unrotated_pair_output_z": shifted_reciprocal_x(raw_pair),
                "product_p": independent.mul(independent.coordinate(a),
                                               independent.coordinate(b))}
    result = {"status": "PASS_NINE_PAIR_CONSTRUCTED_GROUP_FIXTURE",
              "seed_mask": 212, "selected": derive["selected"] + [new_item],
              "pair_rotated_z": chain["pair_rotated_z"] +
                  [shifted_reciprocal_x(rotated)],
              "intermediate_z": chain["intermediate_z"] + [chain["raw_target_z"]],
              "raw_target": list(target), "raw_target_z": shifted_reciprocal_x(target),
              "source_sha256": {"script": sha(Path(__file__)),
                                "independent_group": sha(BASE / "verify.py"),
                                "derive": sha(OLD / "derive_result.json"),
                                "chain": sha(OLD / "planted_chain_result.json"),
                                "support": sha(SUPPORT)}}
    with (HERE / "control_fixture.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "new_pair_masks": [a, b],
                      "new_columns": new_item["folded_columns"]}))


if __name__ == "__main__":
    main()
