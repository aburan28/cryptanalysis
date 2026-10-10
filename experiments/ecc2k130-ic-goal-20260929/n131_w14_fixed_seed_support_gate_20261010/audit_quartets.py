#!/usr/bin/env python3
"""Independent combinatorial replay of N41 quartets and selected N131 seeds."""

import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
W14 = GOAL / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
SCREEN = GOAL / "n41_n131_diagonal_atom_20261010/screen.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_pairs(mapping, seed):
    return [(a, a ^ seed) for a in sorted(mapping)
            if a < a ^ seed and (a ^ seed) in mapping and
            mapping[a] != mapping[a ^ seed]]


def direct_compatible(mapping, seed):
    pairs = source_pairs(mapping, seed)
    count = 0
    for (a, b), (c, d) in itertools.combinations(pairs, 2):
        if len({mapping[a], mapping[b], mapping[c], mapping[d]}) == 4:
            count += 1
    return len(pairs), count


def main():
    result = json.loads((HERE / "quartet_result.json").read_text())
    assert result["status"] == "COMPLETE"
    screen = json.loads(SCREEN.read_text())
    n41 = {int(row["mask"]): int(row["source_column"])
           for row in screen["slots"][0]}
    n41_quartets = sum(
        (a ^ b ^ c ^ d) == 0 and
        len({n41[a], n41[b], n41[c], n41[d]}) == 4
        for a, b, c, d in itertools.combinations(sorted(n41), 4))
    assert n41_quartets == result["n41"][
        "xor_zero_distinct_column_quartets"] == 540
    fixed_pairs, fixed_compatible = direct_compatible(n41, 1)
    assert (fixed_pairs, fixed_compatible) == (8, 28)
    group = json.loads((HERE / "support_n41_v2.json").read_text())
    assert 16 * n41_quartets == group["all_seed_distinct_group_outputs"]
    assert 16 * fixed_compatible == group["fixed_seed_support"][
        "distinct_group_outputs"]

    w14 = {int(a): int(b) for a, b in
           (line.split() for line in W14.read_text().splitlines())}
    samples = {}
    for seed in (1, 8191, 16383):
        pairs, compatible = direct_compatible(w14, seed)
        assert pairs == result["n131"]["pair_counts_by_seed"][seed]
        assert compatible == result["n131"][
            "compatible_pair_pairs_by_seed"][seed]
        samples[str(seed)] = {"pairs": pairs,
                              "compatible_pair_pairs": compatible}
    assert sum(result["n131"]["compatible_pair_pairs_by_seed"]) == (
        3 * result["n131"]["xor_zero_distinct_column_quartets"])
    assert result["n131"]["variable_seed_fouratom_group_support_upper"] == (
        16 * result["n131"]["xor_zero_distinct_column_quartets"])
    audit = {
        "status": "PASS_INDEPENDENT_QUARTET_COUNT_AUDIT",
        "n41_quartets": n41_quartets,
        "n41_fixed_seed_pairs": fixed_pairs,
        "n41_fixed_seed_compatible": fixed_compatible,
        "n131_sampled_seed_counts": samples,
        "source_sha256": {
            "script": sha(Path(__file__)),
            "w14_support": sha(W14),
            "n41_screen": sha(SCREEN),
            "quartet_result": sha(HERE / "quartet_result.json"),
            "n41_sage_replay": sha(HERE / "support_n41_v2.json"),
        },
    }
    with (HERE / "audit.json").open("x") as out:
        json.dump(audit, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": audit["status"],
                      "n41_quartets": n41_quartets,
                      "n131_sampled_seed_counts": samples}))


if __name__ == "__main__":
    main()
