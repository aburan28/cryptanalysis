"""Exact Boolean ANF supports of the two N41 quartic factors."""

import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODULUS = (1 << 41) | (1 << 3) | 1


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mul(a, b):
    output = 0
    while b:
        if b & 1:
            output ^= a
        b >>= 1
        a <<= 1
        if a & (1 << 41):
            a ^= MODULUS
    return output


def rotate(a, exponent):
    for _ in range(exponent):
        a = mul(a, a)
    return a


def powers(a):
    out = [1]
    for _ in range(4):
        out.append(mul(out[-1], a))
    return out


def evaluate(terms, pp, qq):
    output = 0
    for ep, eq, coefficient in terms:
        output ^= mul(coefficient, mul(pp[ep], qq[eq]))
    return output


def main():
    protocol = json.loads((HERE / "boolean_protocol.json").read_text())
    for name, (path, expected) in protocol["source_sha256"].items():
        assert sha(Path(path)) == expected, name
    previous = json.loads((ROOT / "n41_rotated_resultant_boolean_degree_20261010" / "result.json").read_text())
    basis = previous["product_basis"]
    products = [0] * 32
    for mask in range(1, 32):
        low = mask & -mask
        products[mask] = products[mask ^ low] ^ basis[low.bit_length() - 1]
    left = [powers(rotate(p, 10)) for p in products]
    right = [powers(rotate(p, 15)) for p in products]
    cases = {}
    for label in ("n41_positive", "n41_public_target"):
        data = json.loads((HERE / (label + ".json")).read_text())
        factor_rows = []
        for factor in data["factors"]:
            values = [evaluate(factor["terms"], left[index & 31], right[index >> 5])
                      for index in range(1024)]
            zero_indices = [i for i, value in enumerate(values) if value == 0]
            coefficients = values[:]
            for bit in range(10):
                for mask in range(1024):
                    if mask & (1 << bit):
                        coefficients[mask] ^= coefficients[mask ^ (1 << bit)]
            counts = Counter((bin(mask & 31).count("1"), bin(mask >> 5).count("1"))
                             for mask, value in enumerate(coefficients) if value)
            encoded = b"".join(value.to_bytes(6, "little") for value in coefficients)
            factor_rows.append({"zero_count": len(zero_indices), "zero_indices": zero_indices,
                                "boolean_degree": max(sum(pair) for pair in counts),
                                "max_left_degree": max(pair[0] for pair in counts),
                                "max_right_degree": max(pair[1] for pair in counts),
                                "nonzero_coefficients": sum(counts.values()),
                                "bidegree_histogram": {f"{left_degree},{right_degree}": count
                                                       for (left_degree, right_degree), count in sorted(counts.items())},
                                "coefficient_vector_sha256": hashlib.sha256(encoded).hexdigest()})
        union = sorted(set(factor_rows[0]["zero_indices"]) | set(factor_rows[1]["zero_indices"]))
        if label == "n41_positive":
            assert union == previous["cases"]["positive"]["zero_indices"]
        cases[label] = {"z": data["z"], "factors": factor_rows,
                        "union_zero_count": len(union), "union_zero_indices": union}
    result = {"status": "PASS_EXACT_N41_QUARTIC_BOOLEAN_SUPPORT",
              "protocol_sha256": sha(HERE / "boolean_protocol.json"),
              "basis": basis, "cases": cases}
    with (HERE / "boolean_result.json").open("x") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")
    print(json.dumps({name: [(row["boolean_degree"], row["nonzero_coefficients"], row["zero_count"])
                             for row in case["factors"]] for name, case in cases.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
