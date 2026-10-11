#!/usr/bin/env sage -python
"""One-GCD inverse for a proposed affine-plane four-atom output."""

import hashlib
import json
import resource
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n131_w14_coupled_fouratom_inverse_20261010"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def setup_field(n):
    base = PolynomialRing(GF(2), "t")
    t = base.gen()
    modulus = t**41 + t**3 + 1 if n == 41 else t**131 + t**13 + t**2 + t + 1
    field = GF(2**n, name="t", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(base([(int(value) >> i) & 1 for i in range(n)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    return field, curve, decode, encode


def subspace_coefficients(field, s, dimension):
    coefficients = [field.one()]
    vectors = []
    for i in range(1, dimension + 1):
        w = field.gen()**i
        vector = w*w + s*w
        value = field.zero()
        power = vector
        for coefficient in coefficients:
            value += coefficient * power
            power = power*power
        if value == 0:
            assert vector == 0 and not vectors
            continue
        updated = [field.zero()] * (len(coefficients) + 1)
        for j, coefficient in enumerate(coefficients):
            updated[j] += value * coefficient
            updated[j + 1] += coefficient*coefficient
        coefficients = updated
        vectors.append(vector)
    assert len(vectors) == dimension - 1
    return coefficients


def trace_split_roots(polynomial, field):
    """Split a squarefree polynomial known to divide a subspace polynomial."""
    if polynomial.degree() <= 0:
        return []
    if polynomial.degree() == 1:
        return [polynomial[0] / polynomial[1]]
    if polynomial.degree() == 2 and polynomial[1] != 0:
        scale = polynomial[1] / polynomial[2]
        value = (polynomial[0] / polynomial[2]) / (scale*scale)
        assert field.degree() & 1 and value.trace() == 0
        root = field.zero()
        term = value
        for _ in range((field.degree() + 1) // 2):
            root += term
            term = (term*term)*(term*term)
        assert root*root + root == value
        result = [scale*root, scale*(root + 1)]
        assert all(polynomial(item) == 0 for item in result)
        return result
    P = polynomial.parent().gen()
    multiplier = field.one()
    for _ in range(field.degree()):
        power = (multiplier * P) % polynomial
        trace = polynomial.parent().zero()
        for _ in range(field.degree()):
            trace = (trace + power) % polynomial
            power = (power * power) % polynomial
        left = polynomial.gcd(trace)
        if 0 < left.degree() < polynomial.degree():
            return (trace_split_roots(left, field) +
                    trace_split_roots(polynomial // left, field))
        multiplier *= field.gen()
    raise AssertionError("trace basis did not separate distinct roots")


def query(field, coefficients, s, c, z, terms):
    start = time.perf_counter_ns()
    ps = [field.one()]
    pc = [field.one()]
    pz = [field.one()]
    for _ in range(16):
        ps.append(ps[-1] * s)
        pc.append(pc[-1] * c)
    for _ in range(8):
        pz.append(pz[-1] * z)
    h_coefficients = [field.zero()] * 17
    for es, ec, ep, ez in terms:
        h_coefficients[ep] += ps[es] * pc[ec] * pz[ez]
    polynomial = PolynomialRing(field, "P")
    P = polynomial.gen()
    h = polynomial(h_coefficients)
    specialize_end = time.perf_counter_ns()
    if h == 0:
        return {"status": "ZERO_SPECIALIZATION", "specialization_ns": specialize_end - start}
    if h.degree() == 0:
        return {"status": "NO_ALGEBRAIC_ROOT", "specialization_ns": specialize_end - start,
                "subspace_reduce_ns": 0, "gcd_ns": 0, "roots_ns": 0, "gcd_degree": 0,
                "roots": [], "h_degree": 0}
    power = P % h
    remainder = polynomial.zero()
    for coefficient in coefficients:
        remainder += coefficient * power
        power = (power*power) % h
    reduce_end = time.perf_counter_ns()
    common = h.gcd(remainder)
    gcd_end = time.perf_counter_ns()
    roots = trace_split_roots(common, field)
    roots_end = time.perf_counter_ns()
    return {
        "status": "COMPLETE_ALGEBRAIC_GCD",
        "h_degree": int(h.degree()),
        "gcd_degree": int(common.degree()),
        "roots": roots,
        "specialization_ns": specialize_end - start,
        "subspace_reduce_ns": reduce_end - specialize_end,
        "gcd_ns": gcd_end - reduce_end,
        "roots_ns": roots_end - gcd_end,
    }


def panel_case(n, dimension, case, panel, terms):
    field, curve, decode, encode = setup_field(n)
    masks = panel["masks"]
    seed_mask = masks[0] ^ masks[1]
    offset_mask = masks[0] ^ masks[2]
    assert masks[1] ^ masks[3] == offset_mask
    assert seed_mask != 0 and offset_mask not in (0, seed_mask)
    assert len(set(masks)) == 4 and len(set(panel["folded_columns"])) == 4
    s = decode(sum(((seed_mask >> i) & 1) << (i + 1) for i in range(dimension)))
    c = decode(sum(((offset_mask >> i) & 1) << (i + 1) for i in range(dimension)))
    delta = c*c + s*c
    assert decode(panel["pair_products"][0]) + delta == decode(panel["pair_products"][1])
    coefficients = subspace_coefficients(field, s, dimension)
    z = decode(panel["positive_z"] if case == "positive" else panel["trace_zero_control_z"])
    result = query(field, coefficients, s, c, z, terms)
    roots = result.pop("roots", [])
    result["roots_p"] = [encode(value) for value in roots]
    result.update({"field_degree": n, "source_dimension": dimension,
                   "case": case, "seed_mask": seed_mask, "offset_mask": offset_mask,
                   "seed_sum_field": encode(s), "offset_field": encode(c),
                   "delta_field": encode(delta), "output_z": encode(z),
                   "product_space_dimension": dimension - 1})
    if case == "positive":
        assert result["status"] == "COMPLETE_ALGEBRAIC_GCD"
        assert panel["pair_products"][0] in result["roots_p"]
        assert panel["pair_products"][1] in result["roots_p"]
        atoms = [curve(decode(x), decode(y)) for x, y in panel["raw_diagonal_atoms"]]
        total = sum(atoms, curve(0))
        assert [encode(total[0]), encode(total[1])] == panel["raw_four_atom_sum"]
        assert 1 / total[0] == z
        assert int(panel["subgroup_order"]) * (4 * total) == curve(0)
        result["raw_group_replay"] = True
    else:
        result["raw_group_replay"] = None
    result["query_total_ns"] = sum(result[k] for k in (
        "specialization_ns", "subspace_reduce_ns", "gcd_ns", "roots_ns"))
    result["peak_process_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return result


def main():
    protocol = json.loads((HERE / "oracle_protocol_v3.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_ORACLE_QUERIES"
    for name, path in {"script": Path(__file__),
                       "specialization": HERE / "resultant.json",
                       "controls": PARENT / "inputs.json",
                       "runtime": HERE / "sage_runtime_info.json"}.items():
        assert protocol["source_sha256"][name] == digest(path), name
    terms = json.loads((HERE / "resultant.json").read_text())["terms_s_c_p_z"]
    controls = json.loads((PARENT / "inputs.json").read_text())["panels"]
    rows = []
    for n, dimension in ((41, 6), (131, 14), (131, 18)):
        for case in ("positive", "trace_zero_control"):
            rows.append(panel_case(n, dimension, case, controls[str(n)], terms))
    result = {"status": "PASS_AFFINE_PLANE_ONE_GCD_CONTROLS",
              "candidate_id": None, "target_count": 0, "rows": rows,
              "source_sha256": {"script": digest(__file__),
                                "protocol": digest(HERE / "oracle_protocol_v3.json"),
                                "specialization": digest(HERE / "resultant.json"),
                                "controls": digest(PARENT / "inputs.json"),
                                "runtime": digest(HERE / "sage_runtime_info.json")}}
    with (HERE / "oracle_result_v3.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "rows": [{k: row[k] for k in (
        "field_degree", "source_dimension", "case", "h_degree", "gcd_degree",
        "query_total_ns")} for row in rows]}))


if __name__ == "__main__":
    main()
