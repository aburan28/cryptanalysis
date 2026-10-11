"""Independent sparse GF(2) multiplication proof of the quartic identity."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010" / "resultant.json"
ZERO = (0, 0, 0, 0, 0)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_exponents(left, right):
    return tuple(a + b for a, b in zip(left, right))


def product(left, right):
    output = set()
    for a in left:
        for b in right:
            exponent = add_exponents(a, b)
            if exponent in output:
                output.remove(exponent)
            else:
                output.add(exponent)
    return output


def powers(base):
    output = [{ZERO}]
    for _ in range(8):
        output.append(product(output[-1], base))
    return output


def main():
    protocol = json.loads((HERE / "symbolic_audit_protocol.json").read_text())
    for label, (path, expected) in protocol["source_sha256"].items():
        assert sha(Path(path)) == expected, label
    terms = json.loads(SOURCE.read_text())["terms"]
    result = json.loads((HERE / "symbolic_result.json").read_text())
    b_powers = powers({(1, 0, 0, 0, 0), (0, 2, 0, 0, 0), (0, 1, 0, 0, 0)})
    z_powers = powers({(0, 0, 2, 0, 0), (0, 0, 1, 0, 0)})
    expanded = set()
    for ea, eb, ep, eq, ez in terms:
        fixed = (ea, 0, 0, ep, eq)
        for b_term in b_powers[eb]:
            for z_term in z_powers[ez]:
                exponent = add_exponents(fixed, add_exponents(b_term, z_term))
                if exponent in expanded:
                    expanded.remove(exponent)
                else:
                    expanded.add(exponent)
    factors = [set(map(tuple, item["terms"])) for item in result["factors"]]
    rebuilt = product(factors[0], factors[1])
    assert len(expanded) == result["substituted_resultant_term_count"] == 1452
    assert rebuilt == expanded
    assert len(factors[0]) == 114 and len(factors[1]) == 138
    assert all(max(term[3] for term in factor) == 4 and
               max(term[4] for term in factor) == 4 for factor in factors)
    output = {
        "status": "PASS_INDEPENDENT_GF2_QUARTIC_PRODUCT_IDENTITY",
        "audit_protocol_sha256": sha(HERE / "symbolic_audit_protocol.json"),
        "symbolic_result_sha256": sha(HERE / "symbolic_result.json"),
        "expanded_terms": len(expanded),
        "factor_terms": [len(item) for item in factors],
        "rebuilt_terms": len(rebuilt),
    }
    with (HERE / "symbolic_audit_result.json").open("x") as handle:
        json.dump(output, handle, sort_keys=True, indent=2)
        handle.write("\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
