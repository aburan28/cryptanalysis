"""Independent bit-field replay of the split and archived degree-eight hit."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010"
N = 131
MODULUS = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def combine(limbs):
    assert len(limbs) == 3
    return sum(int(limb) << (64 * index) for index, limb in enumerate(limbs))


def mul(a, b):
    output = 0
    while b:
        if b & 1:
            output ^= a
        b >>= 1
        a <<= 1
        if a & (1 << N):
            a ^= MODULUS
    return output


def powers(a):
    output = [1]
    for _ in range(8):
        output.append(mul(output[-1], a))
    return output


def inverse(a):
    assert a
    result, exponent, base = 1, (1 << N) - 2, a
    while exponent:
        if exponent & 1:
            result = mul(result, base)
        base = mul(base, base)
        exponent >>= 1
    assert mul(a, result) == 1
    return result


def evaluate_h(terms, a, b, p, q, z):
    ap, bp, pp, qp, zp = map(powers, (a, b, p, q, z))
    output = 0
    for ea, eb, ep, eq, ez in terms:
        output ^= mul(mul(mul(ap[ea], bp[eb]), pp[ep]), mul(qp[eq], zp[ez]))
    return output


def evaluate_factor(terms, p, q):
    pp, qp = powers(p), powers(q)
    output = 0
    for ep, eq, coefficient in terms:
        output ^= mul(coefficient, mul(pp[ep], qp[eq]))
    return output


def main():
    protocol = json.loads((HERE / "split_audit_protocol.json").read_text())
    for name, (path, expected) in protocol["source_sha256"].items():
        assert sha(Path(path)) == expected, name
    split = json.loads((HERE / "split_n131_positive.json").read_text())
    legacy = json.loads((SOURCE / "native_n131_positive.json").read_text())
    control = json.loads((SOURCE / "control_result.json").read_text())["n131"]
    factors = json.loads((HERE / "n131_positive.json").read_text())["factors"]
    terms = json.loads((SOURCE / "resultant.json").read_text())["terms"]
    receipt = json.loads((HERE / "split_receipt.json").read_text())
    assert receipt["exit_code"] == 0 and receipt["native_result_sha256"] == sha(HERE / "split_n131_positive.json")
    assert split["status"] == "COMPLETE_FACTORED_SCAN"
    assert legacy["status"] == "COMPLETE_ALGEBRAIC_SCAN"
    assert split["processed_product_states"] == legacy["processed_product_states"] == 16384
    assert len(split["hits"]) == len(legacy["hits"]) == 1
    hit, old = split["hits"][0], legacy["hits"][0]
    p = combine(hit["p"])
    assert p == combine(old["p"]) == control["rotated_pair_products"][0]
    assert hit["factor"] in (0, 1)

    def root(row):
        assert row["gcd_degree"] == 1
        coefficients = list(map(combine, row["gcd_coefficients"]))
        return mul(coefficients[0], inverse(coefficients[1]))

    q = root(hit)
    assert q == root(old) == control["rotated_pair_products"][1]
    a, b = control["rotated_seed_coordinates"]
    z = control["four_atom_reciprocal_output"]
    factor_values = [evaluate_factor(item["terms"], p, q) for item in factors]
    assert factor_values[hit["factor"]] == 0
    assert mul(factor_values[0], factor_values[1]) == evaluate_h(terms, a, b, p, q, z) == 0
    output = {"status": "PASS_INDEPENDENT_SPLIT_NATIVE_ROOT_REPLAY",
              "protocol_sha256": sha(HERE / "split_audit_protocol.json"),
              "product_p": p, "product_q": q, "hit_factor": hit["factor"],
              "factor_values": factor_values,
              "split_query_ns": split["query_ns"], "legacy_query_ns": legacy["query_ns"],
              "split_peak_rss_bytes": split["peak_rss_bytes"]}
    with (HERE / "split_audit_result.json").open("x") as out:
        json.dump(output, out, sort_keys=True, indent=2)
        out.write("\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
