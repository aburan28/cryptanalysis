"""Independent binary-field replay of the single-branch norm on public blocks."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LIFT = ROOT / "rotated_fouratom_public_lift_correction_20261010" / "lift_result.json"
RESULTANT = ROOT / "n131_w15_rotated_fouratom_inverse_20261010" / "resultant.json"
CONTROLS = ROOT / "n131_w15_rotated_fouratom_inverse_20261010" / "control_result.json"
NORM = HERE / "norm_result.json"


def multiply(x, y, n, modulus):
    out = 0
    while y:
        if y & 1:
            out ^= x
        y >>= 1
        x <<= 1
        if x >> n:
            x ^= modulus
    return out


def power(x, k, n, modulus):
    out = 1
    while k:
        if k & 1:
            out = multiply(out, x, n, modulus)
        x = multiply(x, x, n, modulus)
        k >>= 1
    return out


def frobenius(x, turns, n, modulus):
    for _ in range(turns):
        x = multiply(x, x, n, modulus)
    return x


def half_trace(x, n, modulus):
    assert n & 1
    out = 0
    term = x
    for _ in range((n + 1) // 2):
        out ^= term
        term = frobenius(term, 2, n, modulus)
    assert multiply(out, out, n, modulus) ^ out == x
    return out


def evaluate(terms, values, n, modulus):
    cache = [{0: 1} for _ in values]
    for term in terms:
        for axis, exponent in enumerate(term):
            if exponent not in cache[axis]:
                cache[axis][exponent] = power(values[axis], exponent, n, modulus)
    out = 0
    for term in terms:
        product = 1
        for axis, exponent in enumerate(term):
            product = multiply(product, cache[axis][exponent], n, modulus)
        out ^= product
    return out


def encoded_mask(mask):
    return sum(1 << (i + 1) for i in range(mask.bit_length()) if mask >> i & 1)


def check_norm(a, b, P, Q, z, n, modulus, norm, resultant, expected_zero=True):
    s = a ^ b
    branch_rhs = z ^ s
    w_branch = half_trace(branch_rhs, n, modulus)
    A = evaluate(norm["A_terms"], (a, s, z, P, Q), n, modulus)
    B = evaluate(norm["B_terms"], (a, s, z, P, Q), n, modulus)
    h_direct = evaluate(resultant, (a, b, P, Q, z), n, modulus)
    norm_value = multiply(A, A ^ B, n, modulus) ^ multiply(branch_rhs, multiply(B, B, n, modulus), n, modulus)
    f0 = A ^ multiply(w_branch, B, n, modulus)
    f1 = f0 ^ B
    assert h_direct == norm_value == multiply(f0, f1, n, modulus)
    assert (h_direct == 0) == expected_zero
    existential_witness = w_branch if f0 == 0 else (w_branch ^ 1 if f1 == 0 else None)
    assert (existential_witness is not None) == expected_zero
    if existential_witness is not None:
        assert multiply(existential_witness, existential_witness, n, modulus) ^ existential_witness == branch_rhs
        assert A ^ multiply(existential_witness, B, n, modulus) == 0
    return {"a": a, "b": b, "P": P, "Q": Q, "z": z,
            "branch_rhs": branch_rhs, "branch_root": w_branch,
            "A": A, "B": B, "factor_values": [f0, f1],
            "existential_branch_witness": existential_witness,
            "zero_factor_count": int(f0 == 0) + int(f1 == 0),
            "direct_resultant": h_direct}


def main():
    lift = json.loads(LIFT.read_text())
    norm = json.loads(NORM.read_text())
    resultant = json.loads(RESULTANT.read_text())["terms"]
    n = 41
    modulus = (1 << n) | (1 << 3) | 1
    rotations = (0, 5, 10, 15, 20, 25)
    masks = lift["masks"]
    rows = []
    for block in range(3):
        i = 4 * block
        m = masks[i:i + 4]
        seed0, seed1 = m[0] ^ m[1], m[2] ^ m[3]
        assert [seed0, seed1] == lift["seed_sums"][2 * block:2 * block + 2]
        w = list(map(encoded_mask, m))
        r0, r1 = rotations[2 * block:2 * block + 2]
        a = frobenius(w[0] ^ w[1], r0, n, modulus)
        b = frobenius(w[2] ^ w[3], r1, n, modulus)
        P = frobenius(multiply(w[0], w[1], n, modulus), r0, n, modulus)
        Q = frobenius(multiply(w[2], w[3], n, modulus), r1, n, modulus)
        z = lift["four_atom_blocks"][block]["z_h_reciprocal_x"]
        row = check_norm(a, b, P, Q, z, n, modulus, norm, resultant)
        row.update({"block": block, "masks": m, "rotations": [r0, r1]})
        rows.append(row)
    control = json.loads(CONTROLS.read_text())["n131"]
    n131 = 131
    mod131 = (1 << n131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
    a, b = control["rotated_seed_coordinates"]
    P, Q = control["rotated_pair_products"]
    z = control["four_atom_reciprocal_output"]
    n131_row = check_norm(a, b, P, Q, z, n131, mod131, norm, resultant)
    n131_row["source"] = "archived_constructed_four_atom_control"
    rejection_rows = [
        check_norm(row["a"], row["b"], row["P"] ^ 1, row["Q"], row["z"],
                   41, modulus, norm, resultant, expected_zero=False)
        for row in rows
    ]
    rejection_rows.append(check_norm(a, b, P ^ 1, Q, z, n131, mod131,
                                     norm, resultant, expected_zero=False))
    result = {"status": "PASS_N41_PUBLIC_THREE_BLOCK_NORM_REPLAY",
              "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "target": [1458168294740, 1672312028033],
              "raw_lift_index": lift["raw_preimage_index"],
              "blocks": rows,
              "n131_control": n131_row,
              "one_bit_product_perturbation_controls": rejection_rows,
              "input_sha256": {"norm_result.json": hashlib.sha256(NORM.read_bytes()).hexdigest(),
                               "lift_result.json": hashlib.sha256(LIFT.read_bytes()).hexdigest(),
                               "control_result.json": hashlib.sha256(CONTROLS.read_bytes()).hexdigest(),
                               "resultant.json": hashlib.sha256(RESULTANT.read_bytes()).hexdigest()}}
    (HERE / "audit_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "zero_factor_counts": [row["zero_factor_count"] for row in rows],
                      "n131_zero_factor_count": n131_row["zero_factor_count"],
                      "rejection_count": len(rejection_rows)}, sort_keys=True))


if __name__ == "__main__":
    main()
