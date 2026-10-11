"""Exact source count for eight W18 pairs with one fixed pair seed."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010"
R = 680564733841876926932320129493409985129
ROTATIONS = [0, 16, 32, 48, 64, 80, 96, 112]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "support_protocol.json").read_text())
    paths = {"script": Path(__file__), "mask_columns": SOURCE / "support_w18.tsv",
             "width_census": SOURCE / "result.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    columns = {}
    for line in paths["mask_columns"].read_text().splitlines():
        mask, column = map(int, line.split())
        assert mask not in columns
        columns[mask] = column
    assert len(columns) == 131307
    width = json.loads(paths["width_census"].read_text())
    assert any(row["degree"] == 18 and row["rational_masks"] == len(columns)
               for row in width["widths"])

    rows = []
    for seed in range(1, 256):
        edges = [(mask, mask ^ seed) for mask, column in columns.items()
                 if mask < (mask ^ seed) and mask ^ seed in columns
                 and column != columns[mask ^ seed]]
        involved = {mask for edge in edges for mask in edge}
        folded = {columns[mask] for mask in involved}
        rows.append({"seed_mask": seed, "valid_unordered_source_pairs": len(edges),
                     "selected_rational_masks_per_window": len(involved),
                     "selected_folded_columns": len(folded)})
    best = max(rows, key=lambda row: (row["valid_unordered_source_pairs"],
                                      -row["seed_mask"]))
    assert best["seed_mask"] == 212
    pair_states = 4 * best["valid_unordered_source_pairs"]
    labeled = pair_states ** len(ROTATIONS)
    mean = Fraction(labeled, R)
    result = {"status": "PASS_EXACT_FIXED_SEED_W18_EIGHT_PAIR_SUPPORT",
              "candidate_id": None, "target_count": 0,
              "field_degree": 131, "subgroup_order": str(R), "source_dimension": 18,
              "searched_seed_masks": [1, 255], "selected": best,
              "slot_rotations": ROTATIONS,
              "signed_pair_states_per_slot": pair_states,
              "selected_usable_points_B_eight_rotations": 2 * len(ROTATIONS) * best["selected_rational_masks_per_window"],
              "selected_folded_columns_K": best["selected_folded_columns"],
              "labeled_eight_pair_tuple_ceiling": str(labeled),
              "uniform_target_labeled_mean_upper_ceiling": str(mean),
              "uniform_target_labeled_mean_upper_ceiling_decimal": format(float(mean), ".9g"),
              "cross_slot_column_exclusions": "omitted from tuple ceiling",
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(HERE / "support_protocol.json"),
              "per_seed": rows}
    with (HERE / "support_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "selected": best,
                      "mean_ceiling": result["uniform_target_labeled_mean_upper_ceiling_decimal"]}))


if __name__ == "__main__":
    main()
