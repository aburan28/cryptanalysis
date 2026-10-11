#!/usr/bin/env python3
"""Exhaust higher-arity shifted S3 chains against small-field group sums."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "shifted_sat_protocol.json"
WALL_LIMIT_SECONDS = 900


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def rank_bits(columns: list[int]) -> int:
    pivots = {}
    for column in columns:
        value = column
        while value:
            bit = value.bit_length() - 1
            if bit not in pivots:
                pivots[bit] = value
                break
            value ^= pivots[bit]
    return len(pivots)


def main(degree: int, arity: int, out: Path) -> None:
    out = out.resolve()
    runtime = out / "sage_runtime_info.json"
    if not out.is_dir() or not runtime.is_file():
        raise FileNotFoundError("save checked Sage runtime before small-field control")
    if (out / "report.json").exists() or (out / "started.json").exists():
        raise FileExistsError("small-field output is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    if degree not in protocol["small_field_degrees"] or arity not in (7, 8):
        raise ValueError("outside frozen small-field grid")
    started = time.perf_counter_ns()
    save(out / "started.json", {
        "kind": "small_shifted_s3_control_start", "degree": degree,
        "arity": arity, "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(runtime),
    })
    field = GF(2**degree, "w")
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    identity = curve(0)
    elements = list(field)

    def word(value) -> int:
        return sum(int(coefficient) << index for index, coefficient in
                   enumerate(value.polynomial().list()))

    def s3(a, b, c):
        e2 = a * b + a * c + b * c
        return e2**2 + a * b * c + field(1)

    normal = None
    for candidate in sorted((value for value in elements if value != 0), key=word):
        conjugates = [candidate]
        for _ in range(1, degree):
            conjugates.append(conjugates[-1]**2)
        if rank_bits([word(value) for value in conjugates]) == degree:
            normal = candidate
            break
    assert normal is not None
    conjugates = [normal]
    for _ in range(1, degree):
        conjugates.append(conjugates[-1]**2)
    assert conjugates[-1]**2 == normal
    lifts = {x: tuple(curve.lift_x(x, all=True)) for x in elements}
    slots = []
    for slot in range(arity):
        a, b = conjugates[slot % degree], conjugates[(slot + 1) % degree]
        assert a != b
        choices = tuple(sorted((x for x in (a, b, a + b) if x != 0 and lifts[x]),
                               key=word))
        assert len(choices) == len(set(choices))
        slots.append(choices)
    total_tuples = 1
    for choices in slots:
        total_tuples *= len(choices)
    assert total_tuples <= 100000
    roots = {(a, b): frozenset(c for c in elements if s3(a, b, c) == 0)
             for a, b in itertools.product(elements, repeat=2)}
    counters = {
        "factor_x_tuples": 0,
        "chain_and_group_pairs": 0,
        "chain_spurious_pairs": 0,
        "chain_missed_pairs": 0,
        "regular_chain_missed_pairs": 0,
        "exceptional_only_missed_pairs": 0,
        "tuples_with_identity_intermediate": 0,
        "tuples_with_nonempty_chain": 0,
    }
    examples = []
    for cursor, xs in enumerate(itertools.product(*slots), 1):
        chain = roots[xs[0], xs[1]]
        for x in xs[2:]:
            chain = frozenset(target for middle in chain
                              for target in roots[middle, x])
        # Keep both regular and exceptional prefix histories for each point.
        states = {(point, True) for point in lifts[xs[0]]}
        had_identity_intermediate = False
        for position, x in enumerate(xs[1:], 1):
            next_states = set()
            for point, regular in states:
                for factor in lifts[x]:
                    total = point + factor
                    next_regular = regular and not (
                        position < arity - 1 and total == identity)
                    if not next_regular:
                        had_identity_intermediate = True
                    next_states.add((total, next_regular))
            states = next_states
        actual = {point[0] for point, _ in states if point != identity}
        regular = {point[0] for point, ok in states
                   if point != identity and ok}
        extra, missing = chain - actual, actual - chain
        regular_missing = regular - chain
        assert not (missing - regular) or had_identity_intermediate
        counters["factor_x_tuples"] += 1
        counters["chain_and_group_pairs"] += len(chain & actual)
        counters["chain_spurious_pairs"] += len(extra)
        counters["chain_missed_pairs"] += len(missing)
        counters["regular_chain_missed_pairs"] += len(regular_missing)
        counters["exceptional_only_missed_pairs"] += len(missing - regular)
        counters["tuples_with_identity_intermediate"] += int(had_identity_intermediate)
        counters["tuples_with_nonempty_chain"] += int(bool(chain))
        if (extra or missing) and len(examples) < 8:
            examples.append({
                "factor_x": [word(x) for x in xs],
                "spurious_target_x": sorted(word(x) for x in extra),
                "missed_target_x": sorted(word(x) for x in missing),
                "regular_missed_target_x": sorted(word(x) for x in regular_missing),
                "identity_intermediate_possible": had_identity_intermediate,
            })
        if cursor % 128 == 0 and (time.perf_counter_ns() - started) / 1e9 > WALL_LIMIT_SECONDS:
            save(out / "progress.json", {"status": "BUDGET", "processed_tuples": cursor,
                                         "total_tuples": total_tuples, "counters": counters})
            raise TimeoutError("small-field frozen wall cap exceeded")
    assert counters["factor_x_tuples"] == total_tuples
    regular_pass = (total_tuples > 0 and counters["chain_spurious_pairs"] == 0 and
                    counters["regular_chain_missed_pairs"] == 0)
    report = {
        "schema_version": 1, "kind": "small_shifted_s3_chain_equivalence",
        "status": ("VACUOUS_NO_RATIONAL_TUPLES" if total_tuples == 0 else
                   "PASS_REGULAR" if regular_pass else "COUNTEREXAMPLE_REGULAR"),
        "degree": degree, "arity": arity,
        "field_modulus": str(field.modulus()),
        "normal_element_polynomial_bits": word(normal),
        "curve_order": int(curve.cardinality()),
        "slot_rational_x_counts": [len(choices) for choices in slots],
        "empty_slot_indices": [index for index, choices in enumerate(slots)
                               if not choices],
        "counters": counters, "first_mismatches": examples,
        "full_locus_equivalence": (None if total_tuples == 0 else
                                   not counters["chain_spurious_pairs"] and
                                   not counters["chain_missed_pairs"]),
        "protocol_sha256": sha(PROTOCOL), "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(runtime),
        "wall_ms_exploratory": (time.perf_counter_ns() - started) / 1e6,
        "claim_boundary": "Exhaustive fixed small-field shifted-slot x tuple control. "
        "Identity-intermediate misses are retained; this is not N83 coverage.",
    }
    save(out / "report.json", report)
    print(json.dumps({"degree": degree, "arity": arity,
                      "status": report["status"], "counters": counters}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("degree", type=int)
    parser.add_argument("arity", type=int)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    main(args.degree, args.arity, args.out)
