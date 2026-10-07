#!/usr/bin/env python3
"""Exact norm-seven recoding and direct endomorphism-map screen."""

import hashlib
import json
from pathlib import Path
import sys

from sage.all import EllipticCurve, GF


HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "prime-j0-secp256k1-native"
SCALAR = HERE.parent / "prime-j0-secp256k1-scalar"
sys.path.insert(0, str(SCALAR))
import cached_projective as cached  # noqa: E402
import validate_scalar as dense  # noqa: E402


def norm(a, b):
    return a * a + 3 * a * b + 3 * b * b


def multiply_rho(a, b):
    return a - 3 * b, a + 4 * b


def residue_rho2(a, b):
    return ((13 * a + 15 * b) % 49, (-5 * a - 2 * b) % 49)


def digit_table():
    table = {}
    for a in range(-20, 21):
        for b in range(-20, 21):
            if (b - a) % 7 == 0:
                continue
            key = residue_rho2(a, b)
            candidate = (norm(a, b), max(abs(a), abs(b)), a, b)
            if key not in table or candidate < table[key]:
                table[key] = candidate
    assert len(table) == 42
    return {key: (candidate[2], candidate[3])
            for key, candidate in table.items()}


def recode(a, b, table):
    original = a, b
    digits = []
    while a or b:
        if len(digits) >= 256:
            raise ValueError("norm-seven recoder did not terminate")
        before = norm(a, b)
        digit = None
        if (b - a) % 7:
            digit = table[residue_rho2(a, b)]
            a -= digit[0]
            b -= digit[1]
        na, nb = 4 * a + 3 * b, -a + b
        assert na % 7 == nb % 7 == 0
        a, b = na // 7, nb // 7
        assert norm(a, b) < before
        digits.append(digit)
    restored = (0, 0)
    for digit in reversed(digits):
        restored = multiply_rho(*restored)
        if digit is not None:
            restored = restored[0] + digit[0], restored[1] + digit[1]
    assert restored == original
    return digits


def norm7_map(x, y, z, beta, curve_b):
    alpha = 2 - beta
    c = -4 * curve_b / (1 + 3 * beta)
    z2 = z**2
    z6 = z2**2 * z2
    u = x**3
    kernel_c = c * z6
    scaled_b = curve_b * z6
    d = u - kernel_c
    n = d**2 + 18 * kernel_c * d + 12 * (kernel_c + scaled_b) * (u + 2 * kernel_c)
    n_u = 2 * d + 30 * kernel_c + 12 * scaled_b
    m = (n + 3 * u * n_u) * d - 6 * u * n
    return x * n, y * m, alpha * z * d


def main():
    fixture_path = NATIVE / "fixture.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 64
    field = GF(dense.P)
    curve = EllipticCurve(field, [0, 7])
    beta = field(int(fixture["beta_hex"], 16))
    assert beta**3 == 1 and beta != 1
    table = digit_table()
    rows = []
    all_digits = set()
    for case in fixture["cases"]:
        a, b = int(case["short_a_hex"], 16), int(case["short_b_hex"], 16)
        digits = recode(a, b, table)
        all_digits.update(digit for digit in digits if digit is not None)
        base = curve(field(int(case["base_x_hex"], 16)),
                     field(int(case["base_y_hex"], 16)))
        omega_base = curve(beta * base[0], base[1])
        expected = 2 * base - omega_base
        for scale in (field(1), field(2), field(3)):
            jac = base[0] * scale**2, base[1] * scale**3, scale
            actual = dense.affine(curve, norm7_map(*jac, beta, field(7)))
            assert actual == expected
        reference = cached.candidate_cost(case["expected_counts"])
        step_count = len(digits) - 1
        rows.append({
            "index": case["index"], "short_a_hex": case["short_a_hex"],
            "short_b_hex": case["short_b_hex"],
            "rho_digit_length": len(digits),
            "rho_nonzero_digits": sum(digit is not None for digit in digits),
            "rho_steps": step_count,
            "optimistic_step_only_13m4s": 17 * step_count,
            "optimistic_step_only_12m4s": 16 * step_count,
            "tau_width4_full_m_plus_s": reference["m_plus_s_excluding_inversion"],
            "map_checks": 3, "verified": True,
        })
    totals = {key: sum(row[key] for row in rows) for key in (
        "rho_digit_length", "rho_nonzero_digits", "rho_steps",
        "optimistic_step_only_13m4s", "optimistic_step_only_12m4s",
        "tau_width4_full_m_plus_s", "map_checks")}
    result = {
        "schema": 1, "kind": "norm-seven-direct-map-feasibility",
        "verified": True, "case_count": len(rows),
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "digit_table_size": len(table), "distinct_used_digits": len(all_digits),
        "digit_table": [{"residue": list(key), "digit": list(value)}
                        for key, value in sorted(table.items())],
        "totals": totals, "rows": rows,
        "cpu_speedup_claim": None, "academic_novelty_claim": None,
    }
    output = HERE / "result.json"
    if output.exists():
        raise SystemExit("result exists; refusing overwrite")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(rows),
                      "digit_table_size": len(table),
                      "distinct_used_digits": len(all_digits),
                      "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()
