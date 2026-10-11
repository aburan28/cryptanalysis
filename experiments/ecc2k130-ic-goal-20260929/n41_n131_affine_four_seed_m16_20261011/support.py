"""Exact source counts for the affine four-seed N41/N131 m16 policy."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
N41 = ROOT / "n41_transport_cubic_s8_20261011" / "fixture.json"
N131 = ROOT / "n131_w16_w18_sixpair_width_gate_20261010" / "support_w18.tsv"
R41 = 549756390943
R131 = 680564733841876926932320129493409985129
SEEDS41 = (32, 33, 34, 35)
SEEDS131 = (212, 213, 214, 215)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pairs(columns, seeds):
    return {seed: [(a, a ^ seed) for a in sorted(columns)
                   if a < (a ^ seed) and (a ^ seed) in columns
                   and columns[a] != columns[a ^ seed]]
            for seed in seeds}


def square(value, degree, taps):
    result = 0
    while value:
        low = value & -value
        result ^= 1 << (2*(low.bit_length()-1))
        value ^= low
    modulus = (1 << degree) | sum(1 << bit for bit in taps)
    for bit in range(2*degree-2, degree-1, -1):
        if result >> bit & 1:
            result ^= modulus << (bit-degree)
    return result


def rank(values):
    pivots = {}
    for value in values:
        while value:
            pivot = value.bit_length()-1
            if pivot not in pivots:
                pivots[pivot] = value
                break
            value ^= pivots[pivot]
    return len(pivots)


def disjoint_rotated_subspaces(degree, dimension, taps, rotations):
    images = []
    for rotation in rotations:
        row = []
        for bit in range(1, dimension+1):
            value = 1 << bit
            for _ in range(rotation):
                value = square(value, degree, taps)
            row.append(value)
        images.append(row)
    ranks = [rank(images[i]+images[j]) for i in range(len(images))
             for j in range(i+1, len(images))]
    assert len(ranks) == 28 and set(ranks) == {2*dimension}
    return min(ranks)


def main():
    fixture = json.loads(N41.read_text())
    columns41 = {int(k): int(v) for k, v in fixture["mask_columns"].items()}
    columns131 = {int(a): int(b) for a, b in
                  (line.split() for line in N131.read_text().splitlines())}
    assert len(columns41) == 32 and len(columns131) == 131307
    p41, p131 = pairs(columns41, SEEDS41), pairs(columns131, SEEDS131)
    c41, c131 = sum(map(len, p41.values())), sum(map(len, p131.values()))
    assert [len(p41[s]) for s in SEEDS41] == [10, 8, 8, 9]
    assert [len(p131[s]) for s in SEEDS131] == [33191, 33002, 32776, 32937]
    rank41 = disjoint_rotated_subspaces(41, 6, (0, 3), tuple(range(0, 40, 5)))
    rank131 = disjoint_rotated_subspaces(131, 18, (0, 1, 2, 13),
                                         tuple(range(0, 128, 16)))
    record = {"status": "EXACT_AFFINE_FOUR_SEED_SOURCE_CENSUS",
              "candidate_id": None,
              "n41": {"seeds": SEEDS41, "per_seed_unordered_pairs":
                      {str(s): len(p41[s]) for s in SEEDS41},
                      "unordered_pairs_per_slot": c41,
                      "signed_pair_states_ceiling_per_slot": 4*c41,
                      "labeled_eight_slot_tuple_ceiling": str((4*c41)**8),
                      "mean_ceiling_numerator": str((4*c41)**8),
                      "mean_ceiling_denominator": str(R41),
                      "factor_base_B_eight_windows": 8*2*len(columns41),
                      "rotated_subspace_pair_rank": rank41,
                      "folded_columns_K": len(set(columns41.values()))},
              "n131": {"seeds": SEEDS131, "per_seed_unordered_pairs":
                       {str(s): len(p131[s]) for s in SEEDS131},
                       "unordered_pairs_per_slot": c131,
                       "signed_pair_states_ceiling_per_slot": 4*c131,
                       "labeled_eight_slot_tuple_ceiling": str((4*c131)**8),
                       "mean_ceiling_numerator": str((4*c131)**8),
                       "mean_ceiling_denominator": str(R131),
                       "factor_base_B_eight_windows": 8*2*len(columns131),
                       "rotated_subspace_pair_rank": rank131,
                       "folded_columns_K": len(set(columns131.values()))},
              "source_sha256": {"support.py": sha(__file__),
                                "n41_fixture": sha(N41), "n131_support": sha(N131)}}
    with (HERE / "support_result.json").open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"n41_pairs": c41, "n131_pairs": c131,
                      "n41_mean_ceiling": (4*c41)**8/R41,
                      "n131_mean_ceiling": (4*c131)**8/R131}))


if __name__ == "__main__":
    main()
