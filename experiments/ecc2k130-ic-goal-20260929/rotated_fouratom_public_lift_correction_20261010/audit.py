"""Independent integer-field and curve replay of corrected public lifts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field(n):
    modulus = ((1 << 41) | (1 << 3) | 1) if n == 41 else \
              ((1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1)

    def mul(a, b):
        output = 0
        while b:
            if b & 1:
                output ^= a
            b >>= 1
            a <<= 1
            if a & (1 << n):
                a ^= modulus
        return output

    def inverse(a):
        assert a
        result, base, exponent = 1, a, (1 << n) - 2
        while exponent:
            if exponent & 1:
                result = mul(result, base)
            base = mul(base, base)
            exponent >>= 1
        assert mul(a, result) == 1
        return result

    def trace(a):
        result = 0
        for _ in range(n):
            result ^= a
            a = mul(a, a)
        assert result in (0, 1)
        return result

    return mul, inverse, trace


def curve_arithmetic(mul, inverse):
    def on_curve(point):
        if point is None:
            return True
        x, y = point
        return mul(y, y) ^ mul(x, y) == mul(mul(x, x), x) ^ 1

    def add(p, q):
        if p is None:
            return q
        if q is None:
            return p
        x, y = p
        X, Y = q
        if x == X:
            if y != Y or x == 0:
                return None
            lam = x ^ mul(y, inverse(x))
            x3 = mul(lam, lam) ^ lam
            y3 = mul(x, x) ^ mul(lam ^ 1, x3)
        else:
            lam = mul(y ^ Y, inverse(x ^ X))
            x3 = mul(lam, lam) ^ lam ^ x ^ X
            y3 = mul(lam, x ^ x3) ^ x3 ^ y
        return x3, y3

    return on_curve, add


def main():
    protocol = json.loads((HERE / "audit_protocol.json").read_text())
    for name, (path, digest) in protocol["source_sha256"].items():
        assert sha(Path(path)) == digest, name
    result = json.loads((HERE / "result.json").read_text())
    original = json.loads((ROOT / "rotated_fouratom_factorization_20261010" /
                           "torsion_result.json").read_text())
    archived131 = json.loads((ROOT / "n131_fixed_seed_eight_pair_circuit_20261010" /
                              "target_preimages.json").read_text())
    audit = {}
    for label, n in (("n41", 41), ("n131", 131)):
        mul, inverse, trace = field(n)
        on_curve, add = curve_arithmetic(mul, inverse)
        case = result[label]
        q = tuple(case["public_target"])
        assert on_curve(q)
        rows = case["preimages"]
        assert len(rows) == 4
        for row in rows:
            point = tuple(row["point"])
            x, y = point
            assert on_curve(point) and x not in (0, 1)
            assert add(add(point, point), add(point, point)) == q
            assert row["z_h_reciprocal_x"] == inverse(x)
            assert row["z_transformed_reciprocal_x_plus_one"] == inverse(x ^ 1)
            assert row["trace_z_h"] == trace(inverse(x))
            assert len(row["factor_degrees_and_terms"]) == (2 if row["trace_z_h"] == 0 else 1)
        for first, second in ((0, 1), (2, 3)):
            p, t2 = tuple(rows[first]["point"]), tuple(rows[second]["point"])
            assert add(p, (0, 1)) == t2
            assert t2[0] == inverse(p[0])
            assert rows[second]["z_h_reciprocal_x"] == inverse(rows[first]["z_h_reciprocal_x"])
            assert rows[second]["z_transformed_reciprocal_x_plus_one"] == \
                   (rows[first]["z_transformed_reciprocal_x_plus_one"] ^ 1)
        if n == 131:
            for row, archived in zip(rows, archived131["preimages"]):
                assert row["point"] == archived["point"]
                assert row["z_transformed_reciprocal_x_plus_one"] == archived["reciprocal_x_z"]
                old = next(item for item in original[label]
                           if item["label"] == "public_raw_lift_" + str(row["index"]))
                assert old["z"] == row["z_transformed_reciprocal_x_plus_one"]
                assert old["z"] != row["z_h_reciprocal_x"]
        audit[label] = {"preimage_count": 4,
                        "trace_zero_indices": [r["index"] for r in rows if r["trace_z_h"] == 0],
                        "trace_one_indices": [r["index"] for r in rows if r["trace_z_h"] == 1],
                        "fourfold_projection_checks": 4,
                        "two_torsion_pair_checks": 2}
    old41 = {item["label"]: item for item in original["n41"]}
    assert old41["public_subgroup_plus_t2"]["z"] == old41["public_subgroup"]["z"] ^ 1
    assert old41["known_block_plus_t2"]["z"] == old41["known_block"]["z"] ^ 1
    output = {"status": "PASS_INDEPENDENT_RECIPROCAL_X_LIFT_CORRECTION",
              "audit_protocol_sha256": sha(HERE / "audit_protocol.json"),
              "result_sha256": sha(HERE / "result.json"),
              "cases": audit,
              "prior_n131_public_lift_coordinate_mismatches": 4,
              "prior_n41_plus_t2_labels_were_field_xor_controls": 2}
    with (HERE / "audit_result.json").open("x") as handle:
        json.dump(output, handle, sort_keys=True, indent=2)
        handle.write("\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
