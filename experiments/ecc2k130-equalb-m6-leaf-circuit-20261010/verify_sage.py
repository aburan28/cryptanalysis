#!/usr/bin/env sage -python
"""Replay source leaves and planted six-summand circuit in checked Sage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import sys
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

import build_formula as circuit
import field as ref


HERE = Path(__file__).resolve().parent
INPUT = ref.EQUAL / "runs/R1/point16/public_points.json"
PREFIX = ref.EQUAL / "runs/R1/base_prefixes.json"
ORDER = ZZ("680564733841876926932320129493409985129")


def peak_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def bits(value: int, length: int) -> list[int]:
    return [(value >> j) & 1 for j in range(length)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite verification receipt")
    started = time.perf_counter()
    runtime = json.loads(args.runtime_info.read_text())
    if runtime.get("status") != "verified":
        raise ValueError("checked Sage runtime did not verify")
    public = json.loads(INPUT.read_text())
    prefix = json.loads(PREFIX.read_text())
    if (public["base_prefixes_sha256"] != ref.sha(PREFIX)
            or prefix["source"]["actual_usable_points_B"] != 11743888):
        raise ValueError("frozen source-base receipts changed")

    f2 = GF(2)
    ring = PolynomialRing(f2, "t")
    t = ring.gen()
    modulus = t**131 + t**13 + t**2 + t + 1
    if not modulus.is_irreducible():
        raise ArithmeticError("field modulus changed")
    field = GF(2**131, "t", modulus=modulus)
    powers = [field.gen()**bit for bit in range(131)]
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def from_int(value):
        return sum((powers[bit] for bit in range(int(value).bit_length())
                    if int(value) & (1 << bit)), field.zero())

    def to_int(value):
        return sum(int(bit) << j for j, bit in
                   enumerate(value.polynomial().list()))

    def halftrace(value):
        result = field.zero()
        for _ in range(66):
            result += value
            value = value**4
        return result

    checked = {}
    planted = {}
    for policy in ("w24_source", "normal4_source"):
        basis = ref.words(policy)
        controls = public["point_controls"][policy]
        members = []
        for row in controls:
            mask = (int(row["mask"]) if policy == "w24_source"
                    else int(row["normal_mask_decimal"]))
            if (policy == "normal4_source" and mask.bit_count() != 4) or (
                    policy == "w24_source" and mask > prefix["source"][
                        "last_selected_mask"]):
                raise ArithmeticError("sample selector outside exact base")
            w_int = ref.parameter(basis, mask)
            w = from_int(w_int)
            u = halftrace(w)
            if u*u + u != w or w.trace() != 0 or (1/w).trace() != 0:
                raise ArithmeticError("Sage source-parameter equation failed")
            x = 1 + 1/u
            y = x*halftrace(x + 1/(x*x))
            raw = curve([x, y])
            projected = 4*raw
            if (to_int(x) != ref.leaf_x(basis, mask)
                    or [to_int(projected[0]), to_int(projected[1])]
                    != row["source"] or ORDER*projected != curve(0)):
                raise ArithmeticError("independent projected point mismatch")
            members.append((mask, raw, w))
        checked[policy] = len(members)

        selected = sorted(members[:6], key=lambda item: item[0])
        raw_points = [point for _, point, _ in selected]
        query = sum(raw_points, curve(0))
        if query.is_zero() or not query[0]:
            raise ArithmeticError("degenerate planted six-summand query")
        current = -query
        chain = []
        for point in raw_points[:5]:
            current += point
            if current.is_zero():
                raise ArithmeticError("degenerate S3 intermediate")
            chain.append(to_int(current[0]))
        if current != -raw_points[5] or chain[-1] != to_int(raw_points[5][0]):
            raise ArithmeticError("planted group-sum chain failed")

        prog, roots, leaves, _ = circuit.build_ir(policy, "m6", to_int(query[0]))
        assignments = {("one", 0): 1}
        for bit, value in enumerate(bits(to_int(query[0]), 131)):
            assignments[("target", bit)] = value
        for index, ((mask, point, w), leaf) in enumerate(zip(selected, leaves)):
            inverse = 1/w
            for name, value, width in (
                    ("s", mask, len(basis)), ("x", to_int(point[0]), 131),
                    ("z", to_int(inverse), 131)):
                for bit, b in enumerate(bits(value, width)):
                    assignments[("%s%d" % (name, index), bit)] = b
        for index, value in enumerate(chain):
            for bit, b in enumerate(bits(value, 131)):
                assignments[("t%d" % index, bit)] = b
        if any(prog.evaluate(assignments, roots)):
            raise ArithmeticError("valid group chain fails the Boolean circuit")
        altered = dict(assignments)
        altered[("x0", 0)] ^= 1
        if not any(prog.evaluate(altered, roots)):
            raise ArithmeticError("mutated leaf x was accepted")
        altered = dict(assignments)
        altered[("z0", 0)] ^= 1
        if not any(prog.evaluate(altered, roots)):
            raise ArithmeticError("mutated reciprocal witness was accepted")
        planted[policy] = {
            "source_query": [to_int(query[0]), to_int(query[1])],
            "selectors": [str(mask) for mask, _, _ in selected],
            "raw_leaf_x": [to_int(point[0]) for point in raw_points],
            "chain_x": chain,
            "planted_summands": 6,
            "positive_boolean_replay": True,
            "negative_leaf_x_rejected": True,
            "negative_reciprocal_witness_rejected": True,
        }
    receipt = {
        "schema": "ecc2k130-equalb-leaf-sage-verification-v1",
        "status": "PASS_SAGE_POINT_AND_BOOLEAN_REPLAY",
        "candidate_id": None,
        "source_curve_id": "EC1N131Ckb1h136f03e58c98",
        "point_control_counts": checked,
        "planted": planted,
        "runtime_info_sha256": ref.sha(args.runtime_info),
        "source_hashes": {name: ref.sha(HERE / name)
                          for name in ("field.py", "build_formula.py",
                                       "verify_sage.py")},
        "input_public_sha256": ref.sha(INPUT),
        "wall_seconds": time.perf_counter() - started,
        "peak_rss_bytes": peak_bytes(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "point_control_counts", "wall_seconds",
                       "peak_rss_bytes")}, sort_keys=True))


if __name__ == "__main__":
    main()
