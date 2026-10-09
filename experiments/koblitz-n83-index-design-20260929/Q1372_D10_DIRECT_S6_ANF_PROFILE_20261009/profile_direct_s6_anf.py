#!/usr/bin/env python3
"""Bounded direct-S6 Boolean ANF profile for Q1105 d10-c000.

The five planted masks are read only for a numerical formula audit.  The ANF
system is built from the full exact Q1104 d10 valid-mask truth table, the five
frozen Frobenius shifts, and the raw cofactor-preimage target x-coordinate.
No planted mask is inserted into the generated equations.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import resource
import sys
import time
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
N83 = HERE.parent
ROOT = N83.parents[1]
RUN = Path(os.environ.get(
    "Q1372_RUN_DIR",
    str(HERE / "runs/q1372_d10_c000_direct_s6_anf_profile_20261009"),
))
Q1104 = N83 / "runs/q1104_seed_subspace_d10_d11_20261003"
Q1105 = N83 / "runs/q1105_planted_pdp5_cofactor_controls_20261003"
CONTROL_PATH = Q1105 / "controls.json"
Q1104_RESULT = Q1104 / "d10_stage_result.json"
Q1104_KEYS = Q1104 / "d10_canonical_orbit_keys.bin"
PAIR = ROOT / "experiments/koblitz-polynomial-w-pair-20260925"
S5 = ROOT / "experiments/koblitz-s5-invariant-20260924"
CURVE_PATH = PAIR / "n83_toy_curve.json"
FORMULA_PATH = S5 / "s6_compact.json"
RUNTIME_PATH = RUN / "sage_runtime_info.json"
RESULT_PATH = RUN / "profile_result.json"
PROTOCOL_PATH = RUN / "protocol.json"

N = 83
D = 10
MASK_COUNT = 1 << D
FIELD_MASK = (1 << N) - 1
MODULUS = (1 << 83) | (1 << 7) | (1 << 4) | (1 << 2) | 1
MAX_TERMS_PER_FIELD_POLY = 100_000
MAX_TOTAL_PAIR_PRODUCTS = 25_000_000
MAX_RSS_BYTES = 1 << 30
CHECK_EVERY_PAIRS = 16_384


class ProfileCap(RuntimeError):
    def __init__(self, reason: str, detail: dict):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def peak_rss_bytes() -> int:
    raw = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return raw if sys.platform == "darwin" else raw * 1024


def gf_square(a: int) -> int:
    spread = 0
    bit = 0
    while a:
        if a & 1:
            spread |= 1 << (2 * bit)
        a >>= 1
        bit += 1
    for degree in range(164, 82, -1):
        if (spread >> degree) & 1:
            spread ^= MODULUS << (degree - 83)
    return spread & FIELD_MASK


@lru_cache(maxsize=262_144)
def gf_mul(a: int, b: int) -> int:
    result = 0
    while b:
        if b & 1:
            result ^= a
        b >>= 1
        a <<= 1
        if a >> N:
            a ^= MODULUS
    return result & FIELD_MASK


def frobenius(value: int, shift: int) -> int:
    for _ in range(shift):
        value = gf_square(value)
    return value


class FieldANF:
    """Sparse Boolean ANF whose coefficients lie in GF(2^83).

    A dictionary maps a square-free Boolean monomial bitmask to its field
    coefficient.  Multiplication uses OR on monomial masks, which implements
    x_i^2=x_i, and exact XOR on field coefficients.
    """

    def __init__(self, term_cap: int, pair_budget: int):
        self.term_cap = term_cap
        self.pair_budget = pair_budget
        self.pair_products = 0
        self.max_terms = 0
        self.max_degree = 0
        self.max_rss = peak_rss_bytes()
        self.events: list[dict] = []

    def observe(self, name: str, value: dict[int, int]) -> dict[int, int]:
        size = len(value)
        self.max_terms = max(self.max_terms, size)
        if value:
            self.max_degree = max(
                self.max_degree,
                max(monomial.bit_count() for monomial in value),
            )
        current_rss = peak_rss_bytes()
        self.max_rss = max(self.max_rss, current_rss)
        if size > self.term_cap:
            raise ProfileCap("field_polynomial_term_cap", {
                "operation": name,
                "observed_terms": size,
                "term_cap": self.term_cap,
            })
        if current_rss > MAX_RSS_BYTES:
            raise ProfileCap("process_rss_cap", {
                "operation": name,
                "peak_rss_bytes": current_rss,
                "rss_cap_bytes": MAX_RSS_BYTES,
            })
        self.events.append({
            "operation": name,
            "terms": size,
            "max_degree": max((m.bit_count() for m in value), default=0),
            "pair_products_total": self.pair_products,
        })
        return value

    @staticmethod
    def one() -> dict[int, int]:
        return {0: 1}

    @staticmethod
    def constant(value: int) -> dict[int, int]:
        return {0: value} if value else {}

    def add(self, a: dict[int, int], b: dict[int, int], name: str) -> dict[int, int]:
        out = a.copy()
        for monomial, coefficient in b.items():
            combined = out.get(monomial, 0) ^ coefficient
            if combined:
                out[monomial] = combined
            else:
                out.pop(monomial, None)
        return self.observe(name, out)

    def square(self, a: dict[int, int], name: str) -> dict[int, int]:
        out: dict[int, int] = {}
        for monomial, coefficient in a.items():
            squared = gf_square(coefficient)
            if squared:
                out[monomial] = squared
        return self.observe(name, out)

    def multiply(self, a: dict[int, int], b: dict[int, int], name: str) -> dict[int, int]:
        if not a or not b:
            return self.observe(name, {})
        planned = len(a) * len(b)
        remaining = self.pair_budget - self.pair_products
        if planned > remaining:
            raise ProfileCap("pair_product_budget", {
                "operation": name,
                "left_terms": len(a),
                "right_terms": len(b),
                "planned_pair_products": planned,
                "remaining_pair_budget": remaining,
            })
        out: dict[int, int] = {}
        done = 0
        for monomial_a, coefficient_a in a.items():
            for monomial_b, coefficient_b in b.items():
                monomial = monomial_a | monomial_b
                coefficient = gf_mul(coefficient_a, coefficient_b)
                if coefficient:
                    combined = out.get(monomial, 0) ^ coefficient
                    if combined:
                        out[monomial] = combined
                    else:
                        out.pop(monomial, None)
                done += 1
                if done % CHECK_EVERY_PAIRS == 0:
                    rss = peak_rss_bytes()
                    self.max_rss = max(self.max_rss, rss)
                    if len(out) > self.term_cap:
                        raise ProfileCap("field_polynomial_term_cap", {
                            "operation": name,
                            "observed_terms": len(out),
                            "term_cap": self.term_cap,
                            "pair_products_in_operation": done,
                        })
                    if rss > MAX_RSS_BYTES:
                        raise ProfileCap("process_rss_cap", {
                            "operation": name,
                            "peak_rss_bytes": rss,
                            "rss_cap_bytes": MAX_RSS_BYTES,
                            "pair_products_in_operation": done,
                        })
        self.pair_products += done
        return self.observe(name, out)

    def power(self, a: dict[int, int], exponent: int, name: str) -> dict[int, int]:
        if exponent == 0:
            return self.one()
        out = self.one()
        base = a
        step = 0
        while exponent:
            if exponent & 1:
                out = self.multiply(out, base, f"{name}.mul{step}")
            exponent >>= 1
            step += 1
            if exponent:
                base = self.multiply(base, base, f"{name}.sq{step}")
        return out


def mobius_field(values: list[int]) -> list[int]:
    out = values[:]
    for bit in range(D):
        flag = 1 << bit
        for mask in range(MASK_COUNT):
            if mask & flag:
                out[mask] ^= out[mask ^ flag]
    return out


def mobius_bool(values: list[int]) -> list[int]:
    return mobius_field(values)


def embed_mask(mask: int, block: int) -> int:
    return mask << (block * D)


def field_eval_horner(field, variables: list[int], terms: tuple[tuple[int, ...], ...], order: tuple[int, ...]) -> int:
    cache: dict[tuple[tuple[tuple[int, ...], ...], int], int] = {}
    power_cache: dict[tuple[int, int], int] = {}

    def power(index: int, exponent: int) -> int:
        key = (index, exponent)
        if key not in power_cache:
            if exponent == 0:
                power_cache[key] = 1
            elif exponent == 1:
                power_cache[key] = variables[index]
            elif exponent % 2 == 0:
                half = power(index, exponent // 2)
                power_cache[key] = field.mul(half, half)
            else:
                power_cache[key] = field.mul(power(index, exponent - 1), variables[index])
        return power_cache[key]

    def recurse(rows: tuple[tuple[int, ...], ...], depth: int) -> int:
        key = (rows, depth)
        if key in cache:
            return cache[key]
        if depth == len(order):
            if rows != (tuple(0 for _ in variables),):
                raise ValueError("S6 Horner recursion did not reach the constant monomial")
            return 1
        index = order[depth]
        groups: dict[int, list[tuple[int, ...]]] = {}
        for row in rows:
            stripped = list(row)
            exponent = stripped[index]
            stripped[index] = 0
            groups.setdefault(exponent, []).append(tuple(stripped))
        exponents = sorted(groups, reverse=True)
        top = exponents[0]
        value = recurse(tuple(sorted(groups[top])), depth + 1)
        previous = top
        for exponent in exponents[1:]:
            value = field.mul(value, power(index, previous - exponent)) ^ recurse(
                tuple(sorted(groups[exponent])), depth + 1
            )
            previous = exponent
        if previous:
            value = field.mul(value, power(index, previous))
        cache[key] = value
        return value

    return recurse(tuple(sorted(terms)), 0)


def build_numeric_s6(field, masks: list[int], shifts: list[int], target_x: int, terms, order) -> int:
    us = []
    for mask, shift in zip(masks, shifts):
        x = q1111.coordinate(GAMMA[:D], mask)
        u = field.inv(x ^ 1)
        us.append(frobenius(u, shift))
    target_u = field.inv(target_x ^ 1)
    ws = [gf_square(u) ^ u for u in us] + [gf_square(target_u) ^ target_u]
    elementary = [1] + [0] * 6
    for index, w in enumerate(ws):
        for degree in range(index + 1, 0, -1):
            elementary[degree] ^= field.mul(elementary[degree - 1], w)
    total_u = target_u
    for u in us:
        total_u ^= u
    variables = [gf_square(elementary[index]) for index in (2, 3, 4, 5)]
    variables.extend((elementary[6], gf_square(total_u)))
    return field_eval_horner(field, variables, terms, order)


def profile_horner(anf: FieldANF, variables: list[dict[int, int]], terms: tuple[tuple[int, ...], ...], order: tuple[int, ...]) -> dict[int, int]:
    cache: dict[tuple[tuple[tuple[int, ...], ...], int], dict[int, int]] = {}
    power_cache: dict[tuple[int, int], dict[int, int]] = {}

    def power(index: int, exponent: int) -> dict[int, int]:
        key = (index, exponent)
        if key not in power_cache:
            if exponent == 0:
                power_cache[key] = anf.one()
            elif exponent == 1:
                power_cache[key] = variables[index]
            elif exponent % 2 == 0:
                half = power(index, exponent // 2)
                power_cache[key] = anf.multiply(half, half, f"s6.power_v{index}_e{exponent}")
            else:
                power_cache[key] = anf.multiply(
                    power(index, exponent - 1), variables[index],
                    f"s6.power_v{index}_e{exponent}",
                )
        return power_cache[key]

    def recurse(rows: tuple[tuple[int, ...], ...], depth: int) -> dict[int, int]:
        key = (rows, depth)
        if key in cache:
            return cache[key]
        if depth == len(order):
            if rows != (tuple(0 for _ in variables),):
                raise ValueError("S6 Horner recursion did not reach the constant monomial")
            return anf.one()
        index = order[depth]
        groups: dict[int, list[tuple[int, ...]]] = {}
        for row in rows:
            stripped = list(row)
            exponent = stripped[index]
            stripped[index] = 0
            groups.setdefault(exponent, []).append(tuple(stripped))
        exponents = sorted(groups, reverse=True)
        top = exponents[0]
        value = recurse(tuple(sorted(groups[top])), depth + 1)
        previous = top
        for exponent in exponents[1:]:
            value = anf.add(
                anf.multiply(value, power(index, previous - exponent),
                             f"s6.horner_v{index}_gap{previous-exponent}"),
                recurse(tuple(sorted(groups[exponent])), depth + 1),
                f"s6.horner_v{index}_add",
            )
            previous = exponent
        if previous:
            value = anf.multiply(value, power(index, previous),
                                 f"s6.horner_v{index}_tail{previous}")
        cache[key] = value
        return value

    return recurse(tuple(sorted(terms)), 0)


def source_hashes() -> dict[str, str]:
    paths = {
        "profile_script": Path(__file__).resolve(),
        "q1111_seed_lookup_source": N83 / "q1111_onb_seed_table_s6_planted_solver.py",
        "q1105_controls": CONTROL_PATH,
        "q1104_d10_result": Q1104_RESULT,
        "q1104_d10_keys": Q1104_KEYS,
        "generated_basis_header": N83 / "runs/q1070_m31_pilot/source_snapshot/ecc2k130/runner/generated/eccF83.h",
        "curve_record": CURVE_PATH,
        "s6_formula": FORMULA_PATH,
        "s6_formula_loader": S5 / "s6_sat.py",
        "runtime_info": RUNTIME_PATH,
    }
    return {name: sha(path) for name, path in paths.items()}


def main() -> int:
    global q1111, GAMMA
    runtime = json.loads(RUNTIME_PATH.read_text())
    if runtime.get("status") != "verified":
        raise RuntimeError("checked Sage runtime receipt is not verified")
    if RESULT_PATH.exists() or PROTOCOL_PATH.exists():
        raise FileExistsError("Q1372 output already exists; preserve prior run")

    sys.path.insert(0, str(N83))
    sys.path.insert(0, str(PAIR))
    sys.path.insert(0, str(S5))
    q1111 = importlib.import_module("q1111_onb_seed_table_s6_planted_solver")
    s6_sat = importlib.import_module("s6_sat")
    controls = json.loads(CONTROL_PATH.read_text())
    control = next(row for row in controls["controls"] if row["control_id"] == "d10-c000")
    if control["dimension"] != D or control["summand_count"] != 5:
        raise ValueError("frozen planted control dimensions changed")
    terms = s6_sat.formula_terms("compact")
    order = s6_sat.ORDERS["compact"]

    low_terms = [0, 2, 4, 7]
    field = q1111.Field(N, low_terms)
    curve = q1111.Curve(field, 0)
    GAMMA = q1111.parse_gamma_to_polynomial()
    if len(GAMMA) != N:
        raise ValueError("ONB basis vector count is incorrect")

    binary = q1111.GF(2)
    conversion = q1111.matrix(binary, N, N, lambda i, j: (GAMMA[j] >> i) & 1)
    if not conversion.is_invertible():
        raise ValueError("ONB conversion matrix is singular")
    inverse_basis = conversion.inverse()
    cycle = q1111.coordinate_cycle()
    key_bytes = Q1104_KEYS.read_bytes()
    if len(key_bytes) % 21:
        raise ValueError("Q1104 key file width is malformed")
    base_keys = [int.from_bytes(key_bytes[i:i + 21], "little")
                 for i in range(0, len(key_bytes), 21)]
    if base_keys != sorted(set(base_keys)) or len(base_keys) != 474:
        raise ValueError("Q1104 exact d10 key set failed canonical checks")
    base_key_set = set(base_keys)

    valid_masks = []
    for mask in range(1, MASK_COUNT):
        x = q1111.coordinate(GAMMA[:D], mask)
        lifts = q1111.points_with_x(curve, x)
        if not lifts:
            continue
        projected = curve.mul(4, lifts[0])
        if projected is None:
            continue
        key = q1111.signed_frobenius_key(projected, inverse_basis, binary, cycle)
        if key not in base_key_set:
            raise ValueError(f"valid seed mask {mask} is absent from Q1104 d10")
        valid_masks.append(mask)
    if len(valid_masks) != 493:
        raise ValueError(f"expected 493 exact valid masks, found {len(valid_masks)}")

    # Numerical audit is isolated from ANF generation: these masks are never
    # inserted into the substitution table or the resulting equations.
    planted_masks = [int(row["seed_coordinates"]) for row in control["terms"]]
    query_shifts = [int(row["query_shift"]) for row in control["terms"]]
    canonical_shifts = [int(row["canonical_transform_shift"])
                        for row in control["terms"]]
    shifts = [(canonical + query) % N
              for canonical, query in zip(canonical_shifts, query_shifts)]
    signs = [int(row["canonical_transform_sign"]) * int(row["query_sign"])
             for row in control["terms"]]
    if any(mask not in valid_masks for mask in planted_masks):
        raise ValueError("planted mask is absent from the exact valid seed domain")
    target_raw = q1111.onb_raw_to_polynomial(int(control["unprojected_planted_sum"][0]), GAMMA)
    numeric_s6 = build_numeric_s6(field, planted_masks, shifts, target_raw, terms, order)

    build_started = time.perf_counter_ns()
    seed_x = [q1111.coordinate(GAMMA[:D], mask) for mask in range(MASK_COUNT)]
    valid_set = set(valid_masks)
    seed_u = [field.inv(x ^ 1) if mask in valid_set else 0
               for mask, x in enumerate(seed_x)]
    if seed_x[0] != 0 or any(seed_x[mask] == 1 for mask in valid_masks):
        raise ValueError("seed table contains an exceptional x coordinate")

    valid_truth = [1 if mask in valid_set else 0 for mask in range(MASK_COUNT)]
    valid_coefficients = mobius_bool(valid_truth)
    valid_monomials = [mask for mask, coefficient in enumerate(valid_coefficients) if coefficient]
    validity_polynomials = []
    for block in range(5):
        validity_polynomials.append({embed_mask(m, block): 1 for m in valid_monomials})

    summand_polynomials = []
    summand_term_counts = []
    for block, shift in enumerate(shifts):
        values = [frobenius(value, shift) if mask in valid_set else 0
                  for mask, value in enumerate(seed_u)]
        coefficients = mobius_field(values)
        polynomial = {
            embed_mask(mask, block): coefficient
            for mask, coefficient in enumerate(coefficients) if coefficient
        }
        summand_polynomials.append(polynomial)
        summand_term_counts.append(len(polynomial))

    anf = FieldANF(MAX_TERMS_PER_FIELD_POLY, MAX_TOTAL_PAIR_PRODUCTS)
    cap = None
    final_equation = None
    invariant_variables: list[dict[int, int]] = []
    elementary: list[dict[int, int]] = []
    ws: list[dict[int, int]] = []
    try:
        one = anf.one()
        target_u = field.inv(target_raw ^ 1)
        target_w = gf_square(target_u) ^ target_u
        elementary = [one] + [{} for _ in range(6)]
        ws = [anf.add(anf.square(u, f"w{index}.square"), u, f"w{index}.add_u")
              for index, u in enumerate(summand_polynomials)]
        ws.append(anf.constant(target_w))

        for index, w in enumerate(ws):
            for degree in range(index + 1, 0, -1):
                product = anf.multiply(elementary[degree - 1], w,
                                       f"elementary_e{degree}_step{index+1}")
                elementary[degree] = anf.add(elementary[degree], product,
                                             f"elementary_e{degree}_accumulate{index+1}")

        total_u = anf.constant(target_u)
        for index, u in enumerate(summand_polynomials):
            total_u = anf.add(total_u, u, f"sum_u_add{index+1}")

        invariant_variables = [
            anf.square(elementary[index], f"invariant_e{index}_square")
            for index in (2, 3, 4, 5)
        ]
        invariant_variables.extend((elementary[6], anf.square(total_u, "invariant_sum_u_square")))
        final_equation = profile_horner(anf, invariant_variables, terms, order)
    except ProfileCap as exc:
        cap = {"reason": exc.reason, **exc.detail}

    all_hashes = source_hashes()
    protocol = {
        "kind": "n83_q1372_direct_s6_boolean_anf_profile_protocol",
        "proposal_id": "Q1372",
        "candidate_id": None,
        "workload_id": None,
        "run_id": None,
        "curve_id": "EC1N83Ckb1h876c2921cb64",
        "control_id": "d10-c000",
        "equation_architecture": "direct S6 after exact seed-mask substitution, fixed five query Frobenius shifts, and a raw cofactor-preimage target x",
        "unknowns": {"seed_blocks": 5, "bits_per_seed": D, "boolean_variables": 5 * D},
        "validity": "exact Q1104 d10 usable seed-mask truth table; one Boolean validity equation per summand",
        "s6_formula": {"path": str(FORMULA_PATH), "monomials": len(terms), "variable_order": list(order)},
        "canonical_frobenius_shifts": canonical_shifts,
        "query_frobenius_shifts": query_shifts,
        "combined_frobenius_shifts": shifts,
        "combined_signs_for_numeric_control_audit": signs,
        "target_semantics": "raw unprojected planted sum x-coordinate; planted summand masks are withheld from equation construction",
        "limits": {
            "max_terms_per_field_anf": MAX_TERMS_PER_FIELD_POLY,
            "max_total_pair_products": MAX_TOTAL_PAIR_PRODUCTS,
            "max_process_rss_bytes": MAX_RSS_BYTES,
        },
        "inputs_sha256": all_hashes,
        "numeric_formula_audit": {
            "s6_value_zero": numeric_s6 == 0,
            "planted_masks_used_only_for_audit": True,
            "planted_masks_inserted_into_equations": False,
        },
    }
    PROTOCOL_PATH.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")

    validity_counts = []
    for equation in validity_polynomials:
        equation[0] = equation.get(0, 0) ^ 1
        if not equation[0]:
            equation.pop(0, None)
        validity_counts.append({
            "terms": len(equation),
            "max_degree": max((m.bit_count() for m in equation), default=0),
        })

    if final_equation is not None:
        coefficient_bit_terms = sum(coefficient.bit_count()
                                    for coefficient in final_equation.values())
        final_equation_profile = {
            "complete": True,
            "field_monomials": len(final_equation),
            "boolean_equation_terms_sum_over_83_coordinates": coefficient_bit_terms,
            "maximum_boolean_degree": max((m.bit_count() for m in final_equation), default=0),
            "nonzero_equation_coordinates": [
                bit for bit in range(N)
                if any((coefficient >> bit) & 1 for coefficient in final_equation.values())
            ],
        }
        status = "profile_complete"
    else:
        coefficient_bit_terms = None
        final_equation_profile = {"complete": False}
        status = f"capped_{cap['reason']}"

    result = {
        "kind": "n83_q1372_direct_s6_boolean_anf_profile_result",
        "proposal_id": "Q1372",
        "candidate_id": None,
        "workload_id": None,
        "run_id": None,
        "status": status,
        "curve_id": "EC1N83Ckb1h876c2921cb64",
        "control_id": "d10-c000",
        "runtime_info_sha256": sha(RUNTIME_PATH),
        "protocol_sha256": sha(PROTOCOL_PATH),
        "source_hashes_sha256": all_hashes,
        "timing": {"anf_build_wall_ns": time.perf_counter_ns() - build_started},
        "control_audit": {
            "valid_mask_count": len(valid_masks),
            "planted_mask_count": len(planted_masks),
            "planted_masks_withheld_from_equation_construction": True,
            "planted_masks_used_for_numeric_formula_audit_only": True,
            "canonical_frobenius_shifts": canonical_shifts,
            "query_frobenius_shifts": query_shifts,
            "combined_frobenius_shifts": shifts,
            "combined_signs_ignored_by_x_only_s6_encoding": signs,
            "numeric_s6_value_zero": numeric_s6 == 0,
        },
        "variables": {"seed_variables": 5 * D, "validity_equations": 5, "s6_coordinate_equations": N},
        "validity_equation_profile": validity_counts,
        "seed_to_u_anf_terms_per_summand": summand_term_counts,
        "s6_invariant_field_anf_terms": [len(poly) for poly in invariant_variables],
        "elementary_symmetric_field_anf_terms": [len(poly) for poly in elementary],
        "summand_w_field_anf_terms": [len(poly) for poly in ws[:-1]],
        "s6_equation_profile": final_equation_profile,
        "limits": protocol["limits"],
        "resource": {
            "pair_products_completed": anf.pair_products,
            "pair_products_in_capped_operation": (
                cap.get("pair_products_in_operation", 0) if cap else 0
            ),
            "maximum_field_anf_terms_observed": anf.max_terms,
            "maximum_anf_degree_observed": anf.max_degree,
            "peak_rss_bytes": max(anf.max_rss, peak_rss_bytes()),
            "event_count": len(anf.events),
            "completed_operation_events": anf.events,
        },
        "cap": cap,
        "solver_invoked": False,
        "interpretation": "A profile or cap outcome on one planted correctness control; it does not measure natural relation yield or a discrete-log speedup.",
    }
    RESULT_PATH.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({
        "status": status,
        "numeric_s6_value_zero": numeric_s6 == 0,
        "valid_mask_count": len(valid_masks),
        "seed_to_u_anf_terms_per_summand": summand_term_counts,
        "summand_w_field_anf_terms": [len(poly) for poly in ws[:-1]],
        "s6_invariant_field_anf_terms": [len(poly) for poly in invariant_variables],
        "pair_products_completed": anf.pair_products,
        "max_terms": anf.max_terms,
        "max_degree": anf.max_degree,
        "peak_rss_bytes": max(anf.max_rss, peak_rss_bytes()),
        "cap": cap,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
