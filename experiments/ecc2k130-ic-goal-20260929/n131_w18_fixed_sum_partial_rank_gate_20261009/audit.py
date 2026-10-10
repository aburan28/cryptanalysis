#!/usr/bin/env sage -python
"""Independent low-pivot rank replay with Sage arithmetic and group checks."""

import hashlib
import json
import random
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PROBE = GOAL / "n131_w18_full_width_pair_oracle/probe.json"
CONTROLS = GOAL / "n131_w18_partial_output_linear_gate.json"
N = 131
MODULUS = (1 << N) | (1 << 13) | (1 << 2) | (1 << 1) | 1


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mul(left, right):
    """Carryless shift/reduce, independent of the producer's field class."""
    result = 0
    while right:
        if right & 1:
            result ^= left
        right >>= 1
        left <<= 1
        if left & (1 << N):
            left ^= MODULUS
    return result


def half_trace(value):
    output = 0
    term = value
    for _ in range((N + 1) // 2):
        output ^= term
        term = mul(mul(term, term), mul(term, term))
    return output


def insert_low(pivots, value):
    while value:
        bit = (value & -value).bit_length() - 1
        if bit not in pivots:
            pivots[bit] = value
            return True
        value ^= pivots[bit]
    return False


def group_inputs():
    source = json.loads(PROBE.read_text())
    if source["status"] != "PASS" or source["verified_queries"] != 128:
        raise ValueError("saved pair source changed")
    groups = {}
    representatives = {}
    for query in source["queries"]:
        if query.get("z") is None:
            continue
        for witness in query["matching_witnesses"]:
            mask = witness["w_masks"][0] ^ witness["w_masks"][1]
            groups.setdefault(mask, set()).add(query["z"])
            representatives.setdefault(mask, query)
    return {mask: sorted(values) for mask, values in sorted(groups.items())}, representatives


def image_basis(seed_sum):
    pivots = {}
    for bit in range(1, 19):
        w = 1 << bit
        insert_low(pivots, mul(w, w) ^ mul(seed_sum, w))
    if len(pivots) != 17:
        raise ValueError("independent image rank differs")
    return list(pivots.values())


def blocks_for(image):
    blocks = []
    for bit in range(N):
        e = 1 << bit
        square = mul(e, e)
        blocks.append([square] + [mul(square ^ e, value) for value in image])
    return blocks


def base_for(blocks, bits):
    basis = {}
    insert_low(basis, 1)
    for bit in bits:
        for value in blocks[bit]:
            insert_low(basis, value)
    return basis


def greedy(blocks):
    bits = []
    basis = base_for(blocks, ())
    ranks = []
    for _ in range(48):
        best = None
        for bit in range(N):
            if bit in bits:
                continue
            trial = basis.copy()
            for value in blocks[bit]:
                insert_low(trial, value)
            option = (len(trial), bit, trial)
            if best is None or option[:2] < best[:2]:
                best = option
        rank, bit, basis = best
        bits.append(bit)
        ranks.append(rank)
    return bits, ranks


def pass_gate(h_square, image, bits, base, z):
    mask = sum(1 << bit for bit in bits)
    fixed = z & ~mask
    square = mul(fixed, fixed)
    basis = base.copy()
    for value in image:
        insert_low(basis, mul(square ^ fixed, value))
    residual = square ^ h_square
    while residual:
        bit = (residual & -residual).bit_length() - 1
        if bit not in basis:
            return False
        residual ^= basis[bit]
    return True


def sage_checks(representatives):
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**N, name="t", modulus=t**N + t**13 + t**2 + t + 1)

    def elem(value):
        return field(ring([(value >> bit) & 1 for bit in range(N)]))

    def integer(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    rng = random.Random(20261009192000)
    for _ in range(64):
        left, right = rng.getrandbits(N), rng.getrandbits(N)
        if integer(elem(left) * elem(right)) != mul(left, right):
            raise ValueError("independent field multiplication differs from Sage")
    for bit in range(1, 19):
        if integer(elem(half_trace(1 << bit))) != integer(
                sum((elem(1 << bit) ** (2 ** (2*j)) for j in range((N + 1)//2)), field(0))):
            raise ValueError("independent half-trace differs from Sage")
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    for seed_sum, query in representatives.items():
        point1, point2 = [curve(elem(x), elem(y)) for x, y in query["raw_points"]]
        total = point1 + point2
        if total.is_zero() or [integer(total[0]), integer(total[1])] != query["raw_sum"]:
            raise ValueError(f"Sage raw pair addition differs for sum {seed_sum}")
        if elem(query["z"]) != 1 / (total[0] + 1):
            raise ValueError(f"Sage phi differs for sum {seed_sum}")
    return {"field_products_checked": 64, "half_traces_checked": 18,
            "raw_pair_sums_checked": len(representatives)}


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve first independent audit")
    start = time.monotonic_ns()
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    if protocol["source_sha256"] != {path: sha(path) for path in protocol["source_sha256"]}:
        raise ValueError("frozen source or input changed")
    if (result["status"] != "COMPLETE_FIXED_SUM_PARTIAL_RANK_PANEL" or
            result["source_sha256"] != protocol["source_sha256"] or
            result["protocol_sha256"] != sha(HERE / "protocol.json") or
            result["seed_sum_count"] != 32 or result["control_count_per_sum"] != 64):
        raise ValueError("saved run receipt differs")
    if (sum(result[key] for key in ("image_build_ns", "greedy_selection_ns",
                                   "gate_evaluation_ns", "interval_overhead_ns")) !=
            result["charged_structural_ns"] or
            result["charged_structural_ns"] > protocol["time_cap_ns"] or
            result["peak_rss_bytes"] > protocol["rss_cap_bytes"]):
        raise ValueError("measured stage accounting or cap differs")
    groups, representatives = group_inputs()
    controls = json.loads(CONTROLS.read_text())["uniform_field_controls"]
    if list(groups) != [row["seed_sum_mask"] for row in result["rows"]] or len(controls) != 64:
        raise ValueError("input population differs")
    half_squares = [mul(h, h) for h in (half_trace(1 << bit) for bit in range(1, 19))]
    totals = {key: 0 for key in ("low_40", "greedy_40", "low_48", "greedy_48")}
    positive_count = 0
    for row in result["rows"]:
        mask = row["seed_sum_mask"]
        if row["positive_z"] != groups[mask] or row["image_rank"] != 17:
            raise ValueError("saved positive row differs")
        seed_sum = sum(((mask >> bit) & 1) << (bit + 1) for bit in range(18))
        image = image_basis(seed_sum)
        blocks = blocks_for(image)
        chosen, ranks = greedy(blocks)
        if chosen != row["greedy_bits_48"] or ranks != row["greedy_base_ranks"]:
            raise ValueError(f"greedy selected bits differ for sum {mask}")
        h_square = 0
        for bit in range(18):
            if (mask >> bit) & 1:
                h_square ^= half_squares[bit]
        for policy in ("low", "greedy"):
            for k in (40, 48):
                key = f"{policy}_{k}"
                bits = list(range(k)) if policy == "low" else chosen[:k]
                base = base_for(blocks, bits)
                saved = row["policies"][key]
                if saved["base_rank"] != len(base):
                    raise ValueError(f"base rank differs for sum {mask}, {key}")
                actual_positive = [pass_gate(h_square, image, bits, base, z)
                                   for z in groups[mask]]
                actual_controls = [pass_gate(h_square, image, bits, base, z)
                                   for z in controls]
                if (not all(actual_positive) or saved["positive_pass"] != actual_positive or
                        saved["control_pass"] != actual_controls or
                        saved["control_pass_count"] != sum(actual_controls)):
                    raise ValueError(f"gate decisions differ for sum {mask}, {key}")
                totals[key] += sum(actual_controls)
        positive_count += len(groups[mask])
    if totals != result["totals"]:
        raise ValueError("aggregated control decisions differ")
    sage = sage_checks(representatives)
    receipt = {"status": "PASS_INDEPENDENT_LOW_PIVOT_AND_SAGE_AUDIT",
               "proposal_id": result["proposal_id"], "candidate_id": None,
               "protocol_sha256": sha(HERE / "protocol.json"),
               "independent_source_sha256": sha(__file__),
               "positive_output_count": positive_count,
               "control_decision_totals": totals,
               "sage_checks": sage, "audit_wall_ns": time.monotonic_ns() - start}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "positive_output_count", "control_decision_totals",
                       "sage_checks", "audit_wall_ns")}, sort_keys=True))


if __name__ == "__main__":
    main()
