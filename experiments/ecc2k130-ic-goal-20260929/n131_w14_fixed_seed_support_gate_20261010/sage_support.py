#!/usr/bin/env sage -python
"""Complete N41 group support of all shared-seed four-atom sums."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SCREEN = GOAL / "n41_n131_diagonal_atom_20261010/screen.json"
FOUR_INPUTS = GOAL / "n131_w14_coupled_fouratom_inverse_20261010/inputs.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_SUPPORT_GATE"
    for name, path in {
        "sage_support": Path(__file__),
        "n41_screen": SCREEN,
        "fouratom_inputs": FOUR_INPUTS,
        "sage_runtime": HERE / "sage_runtime_info.json",
    }.items():
        assert protocol["source_sha256"][name] == sha(path), name

    screen = json.loads(SCREEN.read_text())
    four = json.loads(FOUR_INPUTS.read_text())["panels"]["41"]
    base = PolynomialRing(GF(2), "t")
    t = base.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    identity = curve(0)
    order = int(screen["subgroup_order"])

    def decode(value):
        return field(base([(int(value) >> i) & 1 for i in range(41)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def key(point):
        return None if point == identity else (encode(point[0]), encode(point[1]))

    by_mask = {}
    for row in screen["slots"][0]:
        mask = int(row["mask"])
        point = curve(decode(row["point"][0]), decode(row["point"][1]))
        assert order * point == identity
        item = by_mask.setdefault(mask, {"column": int(row["source_column"]),
                                         "points": []})
        assert item["column"] == int(row["source_column"])
        item["points"].append(point)
    assert len(by_mask) == 32
    assert all(len(item["points"]) == 2 and
               item["points"][0] == -item["points"][1]
               for item in by_mask.values())

    global_outputs = set()
    per_seed = {}
    total_assignments = 0
    fixed_outputs = set()
    for seed in range(1, 64):
        pairs = []
        for a in sorted(by_mask):
            b = a ^ seed
            if a >= b or b not in by_mask:
                continue
            ca, cb = by_mask[a]["column"], by_mask[b]["column"]
            if ca == cb:
                continue
            for pa in by_mask[a]["points"]:
                for pb in by_mask[b]["points"]:
                    pairs.append((pa + pb, frozenset((ca, cb)), (a, b)))
        outputs = set()
        valid = 0
        for left, left_columns, _ in pairs:
            for right, right_columns, _ in pairs:
                if not left_columns.isdisjoint(right_columns):
                    continue
                value = left + right
                outputs.add(key(value))
                valid += 1
        assert all((None if row is None else (row[0], row[1] ^ row[0]))
                   in outputs for row in outputs)
        if seed == 1:
            fixed_outputs = outputs.copy()
        total_assignments += valid
        global_outputs.update(outputs)
        per_seed[str(seed)] = {
            "unordered_mask_pairs": len(pairs) // 4,
            "signed_pair_states": len(pairs),
            "valid_ordered_fouratom_assignments": valid,
            "distinct_group_outputs": len(outputs),
            "distinct_finite_x": len({row[0] for row in outputs if row is not None}),
            "identity_present": None in outputs,
            "combinatorial_upper": len(pairs) ** 2,
        }

    selected = tuple(four["positive_target_projected"])
    public = tuple(screen["public_target"])
    assert selected in fixed_outputs
    assert selected != public
    result = {
        "status": "PASS_COMPLETE_N41_FOURATOM_GROUP_SUPPORT",
        "candidate_id": None,
        "target_count": 0,
        "curve_id": screen["curve_id"],
        "field_modulus_exponents": [0, 3, 41],
        "source_masks": len(by_mask),
        "seed_count": 63,
        "fixed_seed_mask": 1,
        "fixed_seed_support": per_seed["1"],
        "all_seed_ordered_assignments": total_assignments,
        "all_seed_distinct_group_outputs": len(global_outputs),
        "all_seed_distinct_finite_x":
            len({row[0] for row in global_outputs if row is not None}),
        "all_seed_identity_present": None in global_outputs,
        "constructed_positive_in_fixed_seed_support": selected in fixed_outputs,
        "public_point_in_fixed_seed_support": public in fixed_outputs,
        "public_point_in_all_seed_support": public in global_outputs,
        "per_seed": per_seed,
        "source_sha256": {
            "script": sha(Path(__file__)),
            "protocol": sha(HERE / "protocol.json"),
            "n41_screen": sha(SCREEN),
            "fouratom_inputs": sha(FOUR_INPUTS),
            "sage_runtime": sha(HERE / "sage_runtime_info.json"),
        },
    }
    with (HERE / "support_n41.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({
        "status": result["status"],
        "fixed_seed_outputs": per_seed["1"]["distinct_group_outputs"],
        "all_seed_outputs": result["all_seed_distinct_group_outputs"],
        "public_in_support": result["public_point_in_fixed_seed_support"],
    }))


if __name__ == "__main__":
    main()
