#!/usr/bin/env sage -python
"""Independent Sage replay of the coupled-seed N41 W6 public relation."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SCREEN = HERE.parent / "n41_n131_diagonal_atom_20261010/screen.json"
R = 549756390943


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "w6_protocol.json").read_text())
    export = json.loads((HERE / "w6_export.json").read_text())
    screen = json.loads(SCREEN.read_text())
    native = json.loads((HERE / "w6_result.json").read_text())
    hit = json.loads((HERE / "w6_hit.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    assert protocol["status"] == "FROZEN_BEFORE_N41_W6_PUBLIC_QUERY"
    assert protocol["source_sha256"]["input"] == sha(HERE / "w6_input.txt")
    assert protocol["source_sha256"]["binary"] == sha(HERE / "join_w6")
    assert export["source_sha256"]["screen"] == sha(SCREEN)
    assert native["status"] == "FOUND_PENDING_SAGE_REPLAY"
    assert hit["status"] == "NATIVE_RELATION_PENDING_SAGE"
    assert len(hit["masks"]) == len(hit["signs"]) == len(hit["columns"]) == 12
    assert len(set(hit["columns"])) == 12
    assert hit["seed_sums"][2] == hit["seed_sums"][3]
    assert hit["seed_sums"][4] == hit["seed_sums"][5]

    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)

    def decode(value):
        return field(ring([(int(value) >> i) & 1 for i in range(41)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def point(pair):
        return curve(decode(pair[0]), decode(pair[1]))

    def key(value):
        return [encode(value[0]), encode(value[1])]

    def frob(value):
        return curve(value[0]**2, value[1]**2)

    def orbit_key(value):
        reps = []
        current = value
        for _ in range(41):
            reps.extend((tuple(key(current)), tuple(key(-current))))
            current = frob(current)
        return min(reps)

    q = point(protocol["public_target_q"])
    assert q != zero and R * q == zero
    raw_by_mask = {row["mask"]: row for row in screen["raw_audit"]}
    selected = []
    canonicals = []
    source_identities = []
    for block, rotation in enumerate(protocol["paired_rotations"]):
        for local in range(2):
            i = 2 * block + local
            mask, sign, column = hit["masks"][i], hit["signs"][i], hit["columns"][i]
            choices = [row for row in screen["slots"][block]
                       if row["mask"] == mask and row["sign"] == sign]
            assert len(choices) == 1
            row = choices[0]
            assert row["rotation"] == rotation and row["source_column"] == column
            leaf = point(row["point"])
            assert R * leaf == zero and leaf != zero
            source = raw_by_mask[mask]
            assert decode(source["w"]) == sum(
                (field.gen()**(j + 1) for j in range(6) if mask >> j & 1),
                field.zero())
            assert decode(source["u"])**2 + decode(source["u"]) == decode(source["w"])
            raw_atom = point(source["raw_pair_point"])
            assert raw_atom[0] == 1 / decode(source["w"])
            projected = 4 * raw_atom
            assert key(projected) == source["subgroup_atom"]
            for _ in range(rotation):
                projected = frob(projected)
            assert leaf == projected or leaf == -projected
            selected.append(leaf)
            canonicals.append(orbit_key(leaf))
            source_identities.append({"mask": mask, "rotation": rotation,
                                      "sign": sign, "column": column,
                                      "point": key(leaf)})
    assert len(set(canonicals)) == 12
    seeds = [hit["masks"][2*i] ^ hit["masks"][2*i+1] for i in range(6)]
    assert seeds == hit["seed_sums"]
    total = sum(selected, zero)
    assert total == q and key(total) == hit["raw_sum"]
    receipt = {
        "status": "PASS_INDEPENDENT_SAGE_W6_COUPLED_SEED_PUBLIC_RELATION",
        "curve_id": protocol["curve_id"], "public_target_q": key(q),
        "summands": 12, "actual_factor_base_points_B": 384,
        "folded_columns_K": 26, "distinct_relation_columns": 12,
        "paired_rotations": protocol["paired_rotations"],
        "seed_sums": seeds, "replayed_sum": key(total),
        "source_points": source_identities,
        "source_sha256": {"script": sha(Path(__file__)),
                          "protocol": sha(HERE / "w6_protocol.json"),
                          "screen": sha(SCREEN), "input": sha(HERE / "w6_input.txt"),
                          "native_result": sha(HERE / "w6_result.json"),
                          "native_hit": sha(HERE / "w6_hit.json"),
                          "runtime": sha(HERE / "sage_runtime_info.json")},
    }
    with (HERE / "w6_sage_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "seed_sums": seeds,
                      "replayed_sum": receipt["replayed_sum"]}))


if __name__ == "__main__":
    main()
