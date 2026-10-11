"""Independent Sage rank, S3, and group replay for the W15 family witness."""

import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

from sage.all import GF, PolynomialRing, matrix

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
TABLE = GOAL / "n131_w15_seedwise_fouratom_20261011/table.tsv"
LIFT = GOAL / "n131_w15_coupled_sixpair_20261010/w15_lift.py"
N = 131


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(field, integer):
    return field.from_integer(int(integer))


def bit_row(value, augmented=False):
    return ([1] if augmented else []) + [(int(value) >> i) & 1 for i in range(N)]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    assert protocol["source_sha256"]["table.tsv"] == sha(TABLE)
    assert result["source_protocol_sha256"] == sha(HERE / "protocol.json")
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**N, "z", modulus=t**N + t**13 + t**2 + t + 1)
    first = decode(field, protocol["fixed_first_reciprocal"])
    lookup = {int(c): (int(a), int(b)) for c, a, b in
              (line.split() for line in TABLE.read_text().splitlines())}
    replayed = []
    for row in result["affine_rank_witnesses"] + result["linear_rank_witnesses"]:
        d = decode(field, row["right_reciprocal"])
        z = decode(field, row["output_z"])
        cd = first * d
        assert (1 + cd**2) * z**2 + cd * z + (first + d)**2 == 0
        unrotated = d**(2**(N - 13))
        code = sum(int(bit) << i for i, bit in enumerate(unrotated.polynomial().list()))
        assert lookup[code] == tuple(sorted(row["right_masks"]))
        assert z.trace() == 0
        replayed.append(row)
    linear = matrix(GF(2), [bit_row(row["output_z"]) for row in result["linear_rank_witnesses"]])
    affine = matrix(GF(2), [bit_row(row["output_z"], True) for row in result["affine_rank_witnesses"]])
    assert linear.rank() == result["linear_rank"] == 130
    assert affine.rank() == result["affine_rank"] == 131
    assert result["positive_root"]["output_z"] == protocol["positive_four_atom_reciprocal"]
    lift = load("fixed_seed_family_lift", LIFT)
    _, curve_field, curve, basis_w, basis_u = lift.source()
    group_rows = [result["positive_root"]]
    alternative = next(row for row in result["affine_rank_witnesses"]
                       if row["output_z"] != protocol["positive_four_atom_reciprocal"])
    group_rows.append(alternative)
    group_checks = []
    for row in group_rows:
        masks = [*protocol["fixed_first_masks"], *row["right_masks"]]
        rotations = (26, 26, 39, 39)
        points = [lift.frobenius(curve_field,
                                lift.atom(curve_field, curve, basis_w, basis_u, mask),
                                rotation)
                  for mask, rotation in zip(masks, rotations)]
        matches = 0
        for signs in itertools.product((0, 1), repeat=4):
            signed = [curve.neg(point) if sign else point
                      for point, sign in zip(points, signs)]
            total = curve.add(curve.add(signed[0], signed[1]),
                              curve.add(signed[2], signed[3]))
            if total is not None and total[0] and curve_field.inv(total[0]) == row["output_z"]:
                matches += 1
        assert matches > 0
        group_checks.append({"output_z": row["output_z"],
                             "masks": masks, "sign_assignments": matches})
    receipt = {"status": "PASS_N131_W15_FIXED_SEED_AFFINE_RANK_SAGE_REPLAY",
               "curve_id": protocol["curve_id"], "linear_rank": int(linear.rank()),
               "affine_rank": int(affine.rank()),
               "s3_witness_rows_replayed": len(replayed),
               "group_replay": group_checks,
               "source_sha256": {"protocol.json": sha(HERE / "protocol.json"),
                                 "result.json": sha(HERE / "result.json"),
                                 "table.tsv": sha(TABLE), "w15_lift.py": sha(LIFT),
                                 "sage_runtime_info.json": sha(HERE / "sage_runtime_info.json"),
                                 "verify_sage.py": sha(__file__)}}
    (HERE / "sage_replay.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "linear_rank": receipt["linear_rank"],
                      "affine_rank": receipt["affine_rank"],
                      "group_rows": len(group_checks)}))


if __name__ == "__main__":
    main()
