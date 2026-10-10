#!/usr/bin/env python3
"""Independent checked-Sage audit of invariant rows and pair recovery."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix, vector

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w14_polynomial_pair_inverse_20261010"
N, D = 131, 14
FULL = (1 << N) - 1


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def main():
    output = HERE / "sage_audit.json"
    if output.exists():
        raise FileExistsError(output)
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    result = json.loads((HERE / "result.json").read_text())
    inputs = json.loads((SOURCE / "inputs.json").read_text())
    assert result["status"] == "COMPLETE_HIGH_PREFIX_PANEL"
    assert result["sha256"]["inputs"] == sha(SOURCE / "inputs.json")
    polynomial = PolynomialRing(GF(2), "t")
    t = polynomial.gen()
    field = GF(2**N, name="t", modulus=t**131+t**13+t**2+t+1)
    alpha = field.gen()
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(polynomial([(int(value) >> i) & 1 for i in range(N)]))

    def half_trace(value):
        total = field.zero()
        for _ in range((N+1)//2):
            total += value
            value = value**4
        return total

    u2 = [half_trace(alpha**(i+1))**2 for i in range(D)]
    product_basis = [alpha**degree for degree in range(2, 2*D+1)]
    checked_masks = {}
    for b in result["panel"]:
        variable_support = 0
        for j in range(b):
            basis = alpha**j
            square = basis**2
            variable_support |= encode(square)
            delta_a = square+basis
            for product in product_basis:
                variable_support |= encode(delta_a*product)
        invariant = FULL ^ variable_support
        assert invariant == result["invariant_masks"][str(b)]
        for j in range(b):
            perturbation = 1 << j
            delta = decode(perturbation)
            assert encode(delta**2) & invariant == 0
            for product in product_basis:
                assert encode((delta**2+delta)*product) & invariant == 0
        checked_masks[str(b)] = invariant.bit_length()

    selected = []
    for b in (0, 24, 31, 34, 35, 36, 48):
        invariant = result["invariant_masks"][str(b)]
        positions = [i for i in range(N) if invariant >> i & 1]
        for kind, index in (("positive", 0), ("positive", 1),
                            ("uniform_field", 0)):
            item = inputs["positives"][index] if kind == "positive" else inputs["controls"][index]
            z = item["z"] & (FULL ^ ((1 << b) - 1))
            z_element = decode(z)
            columns = [encode(value) & invariant for value in u2]
            columns += [encode((z_element**2+z_element)*product) & invariant
                        for product in product_basis]
            right = encode(z_element**2) & invariant
            block = matrix(GF(2), len(positions), 41,
                           lambda i, j: (columns[j] >> positions[i]) & 1)
            rhs = vector(GF(2), [(right >> i) & 1 for i in positions])
            rank = block.rank()
            consistent = matrix(GF(2), len(positions), 42,
                                lambda i, j: block[i,j] if j < 41 else rhs[i]).rank() == rank
            row = next(row for row in result["rows"] if
                       row["free_low_bits"] == b and row["kind"] == kind and
                       row["index"] == index)
            assert row["projected_rank"] == rank
            assert row["nullity"] == 41-rank
            assert (row["status"] == "INCONSISTENT_HIGH") == (not consistent)
            selected.append({"free_low_bits": b, "kind": kind,
                             "index": index, "rank": rank,
                             "consistent": bool(consistent)})

    group_checked = 0
    for index, item in enumerate(inputs["positives"]):
        leaves = [curve(decode(x), decode(y)) for x, y in item["raw_leaves"]]
        assert all(point != curve(0) for point in leaves)
        total = leaves[0]+leaves[1]
        assert [encode(total[0]), encode(total[1])] == item["raw_sum"]
        assert encode(1/(total[0]+1)) == item["z"]
        for mask, point in zip(item["masks"], leaves):
            w = sum((alpha**(i+1) for i in range(D) if mask >> i & 1),
                    field.zero())
            assert point[0] == 1+1/half_trace(w)
        for b in result["panel"]:
            row = next(row for row in result["rows"] if
                       row["free_low_bits"] == b and row["kind"] == "positive" and
                       row["index"] == index)
            if row["status"] != "RANK_FALLBACK":
                assert sorted(item["masks"]) in row["pairs"]
        group_checked += 1

    receipt = {"status": "PASS_SAGE_HIGH_PREFIX_AUDIT",
               "curve_id": "EC1N131Ckb1heb5f1998f20b",
               "invariant_masks_recomputed": len(checked_masks),
               "projected_rank_cases": selected,
               "positive_raw_groups_replayed": group_checked,
               "sha256": {"source": sha(Path(__file__)),
                          "runtime": sha(HERE / "sage_runtime_info.json"),
                          "result": sha(HERE / "result.json"),
                          "inputs": sha(SOURCE / "inputs.json")}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "invariant_masks_recomputed": len(checked_masks),
                      "projected_rank_cases": len(selected),
                      "positive_raw_groups_replayed": group_checked},
                     sort_keys=True))


if __name__ == "__main__":
    main()
