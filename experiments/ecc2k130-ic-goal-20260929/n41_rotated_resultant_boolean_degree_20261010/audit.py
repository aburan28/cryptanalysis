"""Independent tensor assembly of the N41 Boolean resultant coefficients."""

import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010"
MODULUS = (1 << 41) | (1 << 3) | 1


def multiply(a, b):
    raw = 0
    for bit in range(41):
        if (b >> bit) & 1:
            raw ^= a << bit
    for bit in range(80, 40, -1):
        if (raw >> bit) & 1:
            raw ^= MODULUS << (bit - 41)
    return raw


def power(a, exponent):
    out = 1
    while exponent:
        if exponent & 1:
            out = multiply(out, a)
        a = multiply(a, a)
        exponent >>= 1
    return out


def anf_of_univariate_power(linear_basis, exponent):
    values = []
    for mask in range(32):
        value = 0
        for bit, basis_element in enumerate(linear_basis):
            if (mask >> bit) & 1:
                value ^= basis_element
        values.append(power(value, exponent))
    for bit in range(5):
        for mask in range(32):
            if mask & (1 << bit):
                values[mask] ^= values[mask ^ (1 << bit)]
    return values


def main():
    protocol = json.loads((HERE / "audit_protocol.json").read_text())
    for label, (path, expected) in protocol["source_sha256"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, label
    result = json.loads((HERE / "result.json").read_text())
    control = json.loads((PARENT / "control_result.json").read_text())["n41"]
    terms = json.loads((PARENT / "resultant.json").read_text())["terms"]
    r0, r1 = control["pair_rotations"]
    seed = control["seed_mask"] << 1
    a = power(seed, 1 << r0)
    b = power(seed, 1 << r1)
    assert [a, b] == control["rotated_seed_coordinates"]
    basis = result["product_basis"]
    left = [power(x, 1 << r0) for x in basis]
    right = [power(x, 1 << r1) for x in basis]
    left_anf = [anf_of_univariate_power(left, exponent) for exponent in range(9)]
    right_anf = [anf_of_univariate_power(right, exponent) for exponent in range(9)]
    cases = {}
    for label, case in result["cases"].items():
        z = case["z"]
        coeffs = [0] * 1024
        for ea, eb, ep, eq, ez in terms:
            scalar = multiply(multiply(power(a, ea), power(b, eb)), power(z, ez))
            for i, pcoef in enumerate(left_anf[ep]):
                if pcoef:
                    lhs = multiply(scalar, pcoef)
                    for j, qcoef in enumerate(right_anf[eq]):
                        if qcoef:
                            coeffs[i | (j << 5)] ^= multiply(lhs, qcoef)
        encoded = b"".join(v.to_bytes(6, "little") for v in coeffs)
        digest = hashlib.sha256(encoded).hexdigest()
        assert digest == case["coefficient_vector_sha256"], label
        counts = Counter(bin(index).count("1") for index, value in enumerate(coeffs) if value)
        assert dict(sorted(counts.items())) == {int(k): v for k, v in case["nonzero_coefficients_by_degree"].items()}
        cases[label] = {"coefficient_vector_sha256": digest,
                        "nonzero_coefficient_count": sum(counts.values()),
                        "boolean_degree": max(counts)}
    output = {"status": "PASS_INDEPENDENT_TENSOR_ANF_AUDIT",
              "audit_protocol_sha256": hashlib.sha256((HERE / "audit_protocol.json").read_bytes()).hexdigest(),
              "result_sha256": hashlib.sha256((HERE / "result.json").read_bytes()).hexdigest(),
              "cases": cases}
    (HERE / "audit_result.json").write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
