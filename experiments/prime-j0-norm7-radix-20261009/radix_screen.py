#!/usr/bin/env python3
"""Exact alpha-adic digit, termination, point, and matched-cost screen."""

from collections import Counter
import hashlib
import json
from math import isqrt
from pathlib import Path

from map_verify import BETA, ORDER, P, add, alpha_reference, omega, sha


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
INPUTS = ROOT / "experiments/prime-j0-radix943-word-20261009/inputs.json"
CONTROL = ROOT / "experiments/prime-j0-secp256k1-scalar/width4-result.json"
GENERATOR = (
    int("79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798", 16),
    int("483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8", 16),
)
LAMBDA_TAU = int("ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0", 16)
V = (-238911465918039986966665730306072050094,
     303414439467246543595250775667605759171)
U = (193508920647619669885755136084601127231,
     238911465918039986966665730306072050094)
W = (U[0] - 2 * V[0], U[1] - 2 * V[1])
WIDTHS = (1, 2, 3, 4, 5)


def norm(pair):
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def omega_coeff(pair):
    a, b = pair
    return a + 3 * b, -a - 2 * b


def unit_images(pair):
    value = pair
    out = []
    for _ in range(3):
        out.extend((value, (-value[0], -value[1])))
        value = omega_coeff(value)
    assert value == pair
    return out


def alpha_coeff(pair):
    a, b = pair
    return a - 3 * b, a + 4 * b


def div_alpha(pair):
    a, b = pair
    x, y = 4 * a + 3 * b, -a + b
    assert x % 7 == 0 and y % 7 == 0
    return x // 7, y // 7


def nearest_representative(scalar):
    fw = scalar * V[1] // ORDER
    fv = -(scalar * W[1]) // ORDER
    choices = []
    for i in (fw, fw + 1):
        for j in (fv, fv + 1):
            a = scalar - i * W[0] - j * V[0]
            b = -i * W[1] - j * V[1]
            choices.append((norm((a, b)), max(abs(a), abs(b)), a, b))
    _, _, a, b = min(choices)
    assert (a + b * LAMBDA_TAU - scalar) % ORDER == 0
    return a, b


def hensel_root(width):
    value, modulus = 6, 7
    assert (value * value - 3 * value + 3) % modulus == 0
    for _ in range(1, width):
        next_modulus = 7 * modulus
        choices = [value + digit * modulus for digit in range(7)
                   if ((value + digit * modulus)**2
                       - 3 * (value + digit * modulus) + 3) % next_modulus == 0]
        assert len(choices) == 1
        value, modulus = choices[0], next_modulus
    return value


def build_digit_set(width):
    modulus = 7**width
    lam = hensel_root(width)
    assert (lam * lam - 3 * lam + 3) % modulus == 0 and lam % 7 == 6
    residue = lambda pair: (pair[0] + lam * pair[1]) % modulus
    radius = (modulus + 2) // 3
    b_bound = isqrt(4 * radius // 3) + 2
    a_bound = isqrt(radius) + (3 * b_bound + 1) // 2 + 2
    best = [None] * modulus
    for b in range(-b_bound, b_bound + 1):
        for a in range(-a_bound, a_bound + 1):
            value = norm((a, b))
            if value > radius:
                continue
            slot = residue((a, b))
            if slot % 7 == 0:
                continue
            candidate = (value, a, b)
            if best[slot] is None or candidate < best[slot]:
                best[slot] = candidate
    assert all(best[slot] is not None for slot in range(modulus) if slot % 7)
    digits = [None] * modulus
    seeds = []
    for slot in range(modulus):
        if slot % 7 == 0 or digits[slot] is not None:
            continue
        seed = best[slot][1:]
        images = unit_images(seed)
        orbit_slots = [residue(image) for image in images]
        assert len(set(orbit_slots)) == 6 and min(orbit_slots) == slot
        for image_slot, image in zip(orbit_slots, images):
            assert digits[image_slot] is None
            assert best[image_slot][0] == norm(image)
            digits[image_slot] = image
        seeds.append(seed)
    assert len(seeds) == 7**(width - 1)
    assert all(digits[slot] is not None for slot in range(modulus) if slot % 7)
    max_norm = max(norm(digit) for digit in seeds)
    assert max_norm <= radius
    return lam, digits, seeds, max_norm


def step(pair, lam, digits):
    modulus = len(digits)
    slot = (pair[0] + lam * pair[1]) % modulus
    digit = (0, 0) if slot % 7 == 0 else digits[slot]
    return div_alpha((pair[0] - digit[0], pair[1] - digit[1])), digit


def recode(pair, lam, digits, cap=500):
    current = pair
    expansion = []
    while current != (0, 0) and len(expansion) < cap:
        current, digit = step(current, lam, digits)
        expansion.append(digit)
    assert current == (0, 0), (pair, len(expansion))
    reconstructed = (0, 0)
    for digit in reversed(expansion):
        reconstructed = alpha_coeff(reconstructed)
        reconstructed = reconstructed[0] + digit[0], reconstructed[1] + digit[1]
    assert reconstructed == pair
    return expansion


def audit_small_states(lam, digits, max_norm):
    b_bound = isqrt(4 * max_norm // 3) + 2
    a_bound = isqrt(max_norm) + (3 * b_bound + 1) // 2 + 2
    good = {(0, 0)}
    checked = 0
    for b in range(-b_bound, b_bound + 1):
        for a in range(-a_bound, a_bound + 1):
            origin = a, b
            if norm(origin) > max_norm:
                continue
            checked += 1
            path = []
            seen = set()
            current = origin
            while current not in good:
                assert current not in seen, (origin, current)
                assert norm(current) <= max_norm, (origin, current)
                seen.add(current)
                path.append(current)
                current, _ = step(current, lam, digits)
            good.update(path)
    return checked


def neg(point):
    return None if point is None else (point[0], -point[1] % P)


def scalar_mul(scalar, point):
    if scalar < 0:
        return scalar_mul(-scalar, neg(point))
    out = None
    base = point
    while scalar:
        if scalar & 1:
            out = add(out, base)
        base = add(base, base)
        scalar >>= 1
    return out


def point_for_digit(digit, tau_generator, cache):
    if digit not in cache:
        a, b = digit
        cache[digit] = add(scalar_mul(a, GENERATOR), scalar_mul(b, tau_generator))
    return cache[digit]


def replay_points(expansions, scalars):
    tau_generator = add(GENERATOR, neg(omega(GENERATOR)))
    cache = {(0, 0): None}
    digest = hashlib.sha256()
    for index in range(128):
        point = None
        for digit in reversed(expansions[index]):
            point = add(alpha_reference(point), point_for_digit(digit, tau_generator, cache))
        expected = scalar_mul(scalars[index] % ORDER, GENERATOR)
        assert point == expected, index
        digest.update(("identity" if point is None else
                       f"{point[0]:064x}:{point[1]:064x}").encode())
    return len(cache), digest.hexdigest()


def screen_width(width, pairs, scalars, control):
    lam, digits, seeds, max_norm = build_digit_set(width)
    small_states = audit_small_states(lam, digits, max_norm)
    expansions = [recode(pair, lam, digits) for pair in pairs]
    cached_digits, point_sha = replay_points(expansions, scalars)
    lengths = [len(value) for value in expansions]
    weights = [sum(digit != (0, 0) for digit in value) for value in expansions]
    # A matched evaluation-only lower bound: free unit actions, free table
    # construction, and a free first nonzero add favor the candidate.
    matched = []
    for case in control["cases"]:
        pair = int(case["short_a_hex"], 16), int(case["short_b_hex"], 16)
        assert (pair[0] + pair[1] * LAMBDA_TAU - int(case["scalar_hex"], 16)) % ORDER == 0
        expansion = recode(pair, lam, digits)
        maps = max(len(expansion) - 1, 0)
        adds = max(sum(digit != (0, 0) for digit in expansion) - 1, 0)
        lower_bound = 12 * maps + 11 * adds
        reference = case["arms"]["width4_paired"]["generic_cost"]["m_plus_s"]
        matched.append({"case": case["scalar_index"], "base": case["base_index"],
                        "alpha_maps": maps, "alpha_adds": adds,
                        "alpha_evaluation_lower_bound": lower_bound,
                        "width4_paired_m_plus_s": reference,
                        "map_break_even_m_plus_s":
                            (reference - 11 * adds) / maps if maps else None})
    return {"width": width, "residue_count": 7**width, "hensel_root": lam,
            "unit_seed_orbits": len(seeds), "max_digit_norm": max_norm,
            "audited_small_states": small_states, "input_cases": len(scalars),
            "all_integer_pairs_reconstructed": True, "point_replays": 128,
            "cached_digit_points": cached_digits, "point_output_sha256": point_sha,
            "lengths": dict(sorted(Counter(lengths).items())),
            "nonzero_weights": dict(sorted(Counter(weights).items())),
            "total_map_steps": sum(max(value - 1, 0) for value in lengths),
            "total_nonzero_adds": sum(max(value - 1, 0) for value in weights),
            "matched_control": {
                "cases": len(matched),
                "candidate_lower_bound_sum": sum(row["alpha_evaluation_lower_bound"] for row in matched),
                "reference_sum": sum(row["width4_paired_m_plus_s"] for row in matched),
                "candidate_below_reference_cases": sum(
                    row["alpha_evaluation_lower_bound"] < row["width4_paired_m_plus_s"]
                    for row in matched),
                "maximum_map_break_even_m_plus_s": max(
                    row["map_break_even_m_plus_s"] for row in matched
                    if row["map_break_even_m_plus_s"] is not None),
                "rows": matched,
            }}


def main():
    data = json.loads(INPUTS.read_text())
    scalars = [int(value, 16) for value in data["scalars_hex"]]
    assert len(scalars) == 519
    assert hashlib.sha256(b"".join(value.to_bytes(32, "big") for value in scalars)).hexdigest() == data["scalar_sha256"]
    pairs = [nearest_representative(value) for value in scalars]
    control = json.loads(CONTROL.read_text())
    assert control["verified"] and len(control["cases"]) == 128
    result = {"schema": 1, "status": "running", "input_sha256": sha(INPUTS),
              "control_sha256": sha(CONTROL), "protocol_sha256": sha(HERE / "PROTOCOL.md"),
              "map_receipt_sha256": sha(HERE / "map-result.json"),
              "source_sha256": sha(Path(__file__)),
              "cpu_speedup_claim": None, "academic_priority_claim": None,
              "widths": []}
    for width in WIDTHS:
        row = screen_width(width, pairs, scalars, control)
        result["widths"].append(row)
        print(f"width={width} seeds={row['unit_seed_orbits']} "
              f"maps={row['total_map_steps']} adds={row['total_nonzero_adds']} "
              f"paired_lower={row['matched_control']['candidate_lower_bound_sum']} "
              f"paired_control={row['matched_control']['reference_sum']}", flush=True)
    result["status"] = "passed"
    (HERE / "radix-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
