#!/usr/bin/env python3
"""Independent Sage evaluation of the Q1105 planted direct-S6 equation."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
N83 = HERE.parent
ROOT = N83.parents[1]
PAIR = ROOT / "experiments/koblitz-polynomial-w-pair-20260925"
S5 = ROOT / "experiments/koblitz-s5-invariant-20260924"
RUN = Path(sys.argv[1]).resolve()
CONTROL_PATH = N83 / "runs/q1105_planted_pdp5_cofactor_controls_20261003/controls.json"
Q1105_REPLAY = N83 / "runs/q1105_planted_pdp5_cofactor_controls_20261003/independent_sage_replay.json"
PROFILE_RESULT = RUN / "profile_result.json"
PROTOCOL = RUN / "protocol.json"
RUNTIME = RUN / "sage_runtime_info_replay.json"
OUTPUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else RUN / "independent_numeric_replay.json"
HEADER = N83 / "runs/q1070_m31_pilot/source_snapshot/ecc2k130/runner/generated/eccF83.h"
FORMULA_PATH = S5 / "s6_compact.json"

N = 83
RING_BITS = 2 * N + 1
RING_MASK = (1 << RING_BITS) - 1
FIELD_MASK = (1 << N) - 1


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_gamma() -> list[int]:
    source = HEADER.read_text()
    block = source.split("GAMMA_TO_PB[83][3] = {", 1)[1].split("};", 1)[0]
    rows = re.findall(
        r"\{\s*(0x[0-9a-f]+)ull,\s*(0x[0-9a-f]+)ull,\s*(0x[0-9a-f]+)ull\s*\}",
        block,
    )
    if len(rows) != N:
        raise ValueError("generated ONB conversion header is incomplete")
    values = []
    for low, high, upper in rows:
        value = int(low, 16) | (int(high, 16) << 64)
        if int(upper, 16) != 0 or value > FIELD_MASK:
            raise ValueError("generated ONB conversion entry is out of range")
        values.append(value)
    return values


def from_bits(field, generator, bits: int):
    value = field(0)
    while bits:
        low = bits & -bits
        value += generator ** (low.bit_length() - 1)
        bits ^= low
    return value


def from_onb_raw(field, generator, gamma: list[int], raw: int):
    if not 0 <= raw <= RING_MASK:
        raise ValueError("raw ONB value is outside the 167-bit encoding")
    normalized = raw ^ RING_MASK if (raw & 1) else raw
    if normalized & 1:
        raise ValueError("ONB normalization did not clear parity")
    coords = (normalized >> 1) & FIELD_MASK
    bits = 0
    while coords:
        low = coords & -coords
        bits ^= gamma[low.bit_length() - 1]
        coords ^= low
    return from_bits(field, generator, bits)


def coordinate(gamma: list[int], mask: int) -> int:
    value = 0
    while mask:
        low = mask & -mask
        value ^= gamma[low.bit_length() - 1]
        mask ^= low
    return value


def compact_terms(formula: dict) -> list[tuple[int, ...]]:
    terms = []
    for row in formula["coefficient_nonzero_exponents_e2_e3_e4_e5_e6_s"]:
        terms.append(tuple(
            row[index] // 2 if index in (0, 1, 2, 3, 5) else row[index]
            for index in range(6)
        ))
    if len(set(terms)) != 49:
        raise ValueError("compact S6 formula term count changed")
    return terms


def main() -> int:
    runtime = json.loads(RUNTIME.read_text())
    if runtime.get("status") != "verified":
        raise RuntimeError("checked Sage replay runtime receipt is not verified")
    if OUTPUT.exists():
        raise FileExistsError("independent replay already exists")

    controls = json.loads(CONTROL_PATH.read_text())
    control = next(row for row in controls["controls"] if row["control_id"] == "d10-c000")
    q1105 = json.loads(Q1105_REPLAY.read_text())
    q1105_control = next(row for row in q1105["controls"]
                         if row["control_id"] == "d10-c000")
    if q1105.get("status") != "pass" or not q1105_control.get("raw_seed_sum_verified"):
        raise ValueError("independent Q1105 group replay is not a passing control")

    binary = GF(2)
    ring = PolynomialRing(binary, "t")
    t = ring.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    if not modulus.is_irreducible():
        raise ValueError("frozen GF(2^83) modulus is not irreducible")
    field = GF(2**83, name="z", modulus=modulus)
    z = field.gen()
    gamma = parse_gamma()
    s6 = json.loads(FORMULA_PATH.read_text())
    terms = compact_terms(s6)

    planted = []
    for term in control["terms"]:
        mask = int(term["seed_coordinates"])
        seed_x = from_bits(field, z, coordinate(gamma[:10], mask))
        u = (seed_x + 1) ** (-1)
        shift = (int(term["canonical_transform_shift"])
                 + int(term["query_shift"])) % N
        planted.append((u ** (1 << shift), mask, shift))

    target_x = from_onb_raw(field, z, gamma,
                            int(control["unprojected_planted_sum"][0]))
    target_u = (target_x + 1) ** (-1)
    target_w = target_u**2 + target_u
    ws = [u**2 + u for u, _, _ in planted]
    ws.append(target_u**2 + target_u)
    elementary = [field(1)] + [field(0)] * 6
    for index, w in enumerate(ws):
        for degree in range(index + 1, 0, -1):
            elementary[degree] += elementary[degree - 1] * w
    total_u = target_u + sum((u for u, _, _ in planted), field(0))
    variables = [elementary[index]**2 for index in (2, 3, 4, 5)]
    variables.extend((elementary[6], total_u**2))

    s6_value = field(0)
    for exponents in terms:
        monomial = field(1)
        for value, exponent in zip(variables, exponents):
            if exponent:
                monomial *= value**exponent
        s6_value += monomial

    result = {
        "kind": "n83_q1372_independent_numeric_s6_replay",
        "proposal_id": "Q1372",
        "candidate_id": None,
        "workload_id": None,
        "run_id": None,
        "curve_id": "EC1N83Ckb1h876c2921cb64",
        "control_id": "d10-c000",
        "status": "pass" if s6_value == 0 else "producer_formula_mismatch",
        "s6_value_polynomial_basis_integer": int(sum(
            int(coefficient) << index
            for index, coefficient in enumerate(s6_value.polynomial().list())
        )),
        "target_w_nonzero": bool(target_w),
        "s6_term_count": len(terms),
        "seed_masks_used_only_as_independent_control_input": True,
        "combined_frobenius_shifts": [shift for _, _, shift in planted],
        "signs_do_not_change_the_x_coordinate": True,
        "q1105_independent_group_replay_status": q1105.get("status"),
        "profile_result_status": json.loads(PROFILE_RESULT.read_text())["status"],
        "inputs_sha256": {
            "q1105_controls": sha(CONTROL_PATH),
            "q1105_independent_group_replay": sha(Q1105_REPLAY),
            "s6_formula": sha(FORMULA_PATH),
            "generated_basis_header": sha(HEADER),
            "profile_result": sha(PROFILE_RESULT),
            "profile_protocol": sha(PROTOCOL),
            "runtime_info": sha(RUNTIME),
        },
    }
    OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "status", "s6_value_polynomial_basis_integer", "s6_term_count",
        "combined_frobenius_shifts", "q1105_independent_group_replay_status",
    )}, sort_keys=True))
    return 0 if s6_value == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
