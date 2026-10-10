#!/usr/bin/env sage -python
"""Independent algebraic and group replay of the native four-atom oracle."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fe_integer(words):
    assert len(words) == 3
    return int(words[0]) | (int(words[1]) << 64) | (int(words[2]) << 128)


def setup(n):
    base = PolynomialRing(GF(2), "t")
    t = base.gen()
    modulus = t**41 + t**3 + 1 if n == 41 else t**131 + t**13 + t**2 + t + 1
    field = GF(2**n, name="t", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(base([(int(value) >> i) & 1 for i in range(n)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def point(pair):
        return curve(decode(pair[0]), decode(pair[1]))

    return field, curve, decode, encode, point


def symbolic_terms():
    ring = PolynomialRing(GF(2), names=("s", "p", "q", "z", "c", "d"))
    s, p, q, z, c, d = ring.gens()
    left = (1 + p**2)*c**2 + p*c + s**2
    right = (1 + q**2)*d**2 + q*d + s**2
    upper = (1 + c**2*d**2)*z**2 + c*d*z + (c+d)**2
    result = left.resultant(right.resultant(upper, d), c)
    return sorted([[int(exp[0]), int(exp[1]), int(exp[2]), int(exp[3])]
                   for exp in result.dict()])


def subspace_polynomial(field, basis):
    ring = PolynomialRing(field, "Q")
    q = ring.gen()
    coefficients = [field.one()]
    for vector in basis:
        value = sum((coefficient * vector**(2**i)
                     for i, coefficient in enumerate(coefficients)), field.zero())
        assert value != 0
        following = [field.zero()] * (len(coefficients) + 1)
        for i, coefficient in enumerate(coefficients):
            following[i] += value * coefficient
            following[i+1] += coefficient**2
        coefficients = following
    polynomial = sum((coefficient * q**(2**i)
                      for i, coefficient in enumerate(coefficients)), ring.zero())
    assert polynomial.degree() == 1 << len(basis)
    return ring, polynomial


def specialize(ring, field, terms, s, p, z):
    q = ring.gen()
    polynomial = ring.zero()
    for es, ep, eq, ez in terms:
        polynomial += s**es * p**ep * z**ez * q**eq
    return polynomial


def audit_field(n, terms, inputs):
    panel = inputs["panels"][str(n)]
    field, curve, decode, encode, point = setup(n)
    s = decode(panel["source_sum_field"])
    basis_w = [field.gen()**i for i in range(1, panel["source_dimension"] + 1)]
    product_basis = [w**2 + s*w for w in basis_w]
    assert product_basis[0] == 0
    basis = product_basis[1:]
    assert len(basis) == panel["source_dimension"] - 1
    ring, subspace = subspace_polynomial(field, basis)
    values = [field.zero()]
    for vector in basis:
        values.extend([value + vector for value in list(values)])
    assert len({encode(value) for value in values}) == len(values)
    atoms = [point(pair) for pair in panel["raw_diagonal_atoms"]]
    assert len(atoms) == 4
    source_columns = panel["folded_columns"]
    assert len(set(source_columns)) == 4
    for atom, mask in zip(atoms, panel["masks"]):
        w = sum((basis_w[i] for i in range(len(basis_w)) if mask >> i & 1),
                field.zero())
        assert atom[0] == 1/w
    total = sum(atoms, curve(0))
    assert [encode(total[0]), encode(total[1])] == panel["raw_four_atom_sum"]
    assert int(4 * total != curve(0)) == 1
    assert int(panel["subgroup_order"]) * (4 * total) == curve(0)
    assert [encode((4*total)[0]), encode((4*total)[1])] == panel["positive_target_projected"]
    assert encode(1/total[0]) == panel["positive_z"]
    products = []
    pair_outputs = []
    for i in (0, 2):
        a, b = panel["masks"][i:i+2]
        assert a ^ b == panel["source_mask_sum"]
        wa = sum((basis_w[j] for j in range(len(basis_w)) if a >> j & 1), field.zero())
        wb = sum((basis_w[j] for j in range(len(basis_w)) if b >> j & 1), field.zero())
        products.append(wa*wb)
        pair = atoms[i] + atoms[i+1]
        assert pair != curve(0) and pair[0] != 0
        pair_outputs.append(1/pair[0])
    assert [encode(value) for value in products] == panel["pair_products"]
    z_positive = decode(panel["positive_z"])
    assert all(((1+p**2)*c**2+p*c+s**2) == 0
               for p, c in zip(products, pair_outputs))
    c, d = pair_outputs
    assert (1+c**2*d**2)*z_positive**2+c*d*z_positive+(c+d)**2 == 0
    cases = {}
    for kind in ("positive", "trace_zero_control"):
        folder = HERE / f"native_run_n{n}_{kind}"
        receipt = json.loads((folder / "receipt.json").read_text())
        native = json.loads((folder / "result.json").read_text())
        assert receipt["status"] == native["status"] == "COMPLETE_ALGEBRAIC_SCAN"
        assert native["processed_product_states"] == len(values)
        assert native["peak_rss_bytes"] < 4 * 1024**3
        assert receipt["source_sha256"]["result"] == sha(folder / "result.json")
        z = decode(panel["positive_z"] if kind == "positive"
                   else panel["trace_zero_control_z"])
        assert int(z.trace()) == 0
        hits = {}
        for item in native["hits"]:
            p = decode(fe_integer(item["p"]))
            assert subspace(p) == 0
            coefficients = [decode(fe_integer(row))
                            for row in item["gcd_coefficients"]]
            gcd = ring(coefficients)
            assert gcd.degree() == item["gcd_degree"]
            direct = specialize(ring, field, terms, s, p, z).gcd(subspace)
            assert direct.monic() == gcd.monic()
            roots = [root for root, _ in gcd.roots()]
            assert all(subspace(root) == 0 for root in roots)
            hits[encode(p)] = sorted(encode(root) for root in roots)
        if kind == "positive":
            assert set(hits) == set(panel["pair_products"])
            assert all(set(panel["pair_products"]) - {p} <= set(qs)
                       for p, qs in hits.items())
        else:
            assert not hits
        sample_indices = [0, 1, 7, 15, 31] if n == 41 else [0, 1, 31, 511, 2047, 8191]
        for index in sample_indices:
            p = values[index]
            direct = specialize(ring, field, terms, s, p, z).gcd(subspace)
            if encode(p) not in hits:
                assert direct.degree() == 0
        cases[kind] = {"processed": native["processed_product_states"],
                       "hit_products": sorted(hits), "hit_q_roots": hits,
                       "sampled_negative_product_indices": sample_indices,
                       "query_ns": native["query_ns"],
                       "peak_rss_bytes": native["peak_rss_bytes"],
                       "source_sha256": {"result": sha(folder / "result.json"),
                                         "receipt": sha(folder / "receipt.json")}}
    if n == 41:
        for kind in cases:
            prior = json.loads((HERE / f"result_n41_{kind}.json").read_text())
            assert prior["status"] == "COMPLETE_ALGEBRAIC_SCAN"
            assert set(cases[kind]["hit_products"]) == {
                row["p"] for row in prior["algebraic_hits"]}
    return {"curve_id": panel["curve_id"],
            "product_space_dimension": len(basis),
            "subspace_polynomial_degree": int(subspace.degree()),
            "source_masks": panel["masks"], "seed_sum_mask": panel["source_mask_sum"],
            "source_products": panel["pair_products"],
            "positive_output_z": panel["positive_z"],
            "cases": cases}


def main():
    protocol = json.loads((HERE / "native_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_NATIVE_FOUR_ATOM_PANEL"
    inputs = json.loads((HERE / "inputs.json").read_text())
    terms_file = HERE / "resultant_terms.json"
    terms = json.loads(terms_file.read_text())["terms_s_p_q_z"]
    assert symbolic_terms() == terms
    panels = {str(n): audit_field(n, terms, inputs) for n in (41, 131)}
    result = {"status": "PASS_INDEPENDENT_SAGE_FOUR_ATOM_NATIVE_ORACLE",
              "candidate_id": None, "target_count": 0,
              "universal_resultant_terms": len(terms),
              "panels": panels,
              "source_sha256": {"script": sha(Path(__file__)),
                                "protocol": sha(HERE / "native_protocol.json"),
                                "inputs": sha(HERE / "inputs.json"),
                                "terms": sha(terms_file),
                                "binary": sha(HERE / "native"),
                                "runtime": sha(HERE / "sage_runtime_info.json")}}
    with (HERE / "sage_audit.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "n41": panels["41"]["cases"]["positive"]["hit_products"],
                      "n131": panels["131"]["cases"]["positive"]["hit_products"]}))


if __name__ == "__main__":
    main()
