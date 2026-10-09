#!/usr/bin/env python3
"""Independent installed-Sage replay of the complete N41 occupancy census."""

from __future__ import annotations

import hashlib
import json
import math
import resource
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "protocol.json"
GEOMETRY = HERE / "geometry_snapshot.json"
RESULT = HERE / "result.json"
AUDIT = HERE / "audit.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    if AUDIT.exists():
        raise FileExistsError("preserve first independent Sage audit")
    protocol = json.loads(PROTOCOL.read_text())
    result = json.loads(RESULT.read_text())
    record = json.loads(GEOMETRY.read_text())
    if (result["status"] != "COMPLETE_EXACT_OCCUPANCY_AND_TARGET_CENSUS" or
            protocol["geometry_sha256"] != sha(GEOMETRY) or
            protocol["run_source_sha256"] != sha(HERE / "run.py") or
            protocol["audit_source_sha256"] != sha(Path(__file__)) or
            result["input_sha256"]["protocol"] != sha(PROTOCOL) or
            result["input_sha256"]["geometry"] != sha(GEOMETRY) or
            result["input_sha256"]["runner"] != sha(HERE / "run.py") or
            result["process_peak_rss_bytes"] > protocol["process_rss_cap_bytes"]):
        raise ValueError("frozen result identity or resource gate failed")
    n41 = record["n41"]
    if (n41["curve_id"] != protocol["curve_id"] or
            n41["public_target_q"] != result["public_target_q"] or
            result["pair_rotations"] != protocol["pair_rotations"]):
        raise ValueError("curve, target, or pair policy changed")

    start = time.monotonic_ns()
    polynomial = PolynomialRing(GF(2), "t")
    t = polynomial.gen()
    field = GF(2**41, "t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value: int):
        return field(polynomial([(value >> bit) & 1 for bit in range(41)]))

    def point(row):
        return curve(decode(row[0]), decode(row[1]))

    sources = [n41["point_rows_by_unique_rotation"][str(rotation)]
               for rotation in protocol["pair_rotations"]]
    points = [[point(row) for row in source] for source in sources]
    domains = []
    for source, group_points in zip(sources, points):
        states = []
        for i in range(len(source)):
            for j in range(i + 1, len(source)):
                if source[i][2] == source[j][2]:
                    continue
                states.append((group_points[i] + group_points[j],
                               (1 << source[i][2]) | (1 << source[j][2]), i, j))
        if len(states) != 1956:
            raise ValueError("Sage reconstructed pair-domain size changed")
        domains.append(states)
    target = curve(decode(protocol["public_target_q"][0]),
                   decode(protocol["public_target_q"][1]))
    if protocol["subgroup_order"] * target != curve(0):
        raise ValueError("Sage public target subgroup check failed")

    suffix = {}
    counts = {"suffix_valid_assignments": 0, "suffix_distinct_group_sums": 0,
              "suffix_duplicate_assignments": 0, "prefix_valid_assignments": 0,
              "prefix_residual_support_hits": 0, "prefixes_with_valid_completions": 0,
              "eight_column_relations": 0}
    for i, left in enumerate(domains[2]):
        for j, right in enumerate(domains[3]):
            if left[1] & right[1]:
                continue
            key = left[0] + right[0]
            packed = i | (j << 11)
            prior = suffix.get(key)
            if prior is None:
                suffix[key] = packed
            elif isinstance(prior, int):
                suffix[key] = [prior, packed]
                counts["suffix_duplicate_assignments"] += 1
            else:
                prior.append(packed)
                counts["suffix_duplicate_assignments"] += 1
            counts["suffix_valid_assignments"] += 1
        if time.monotonic_ns() - start > protocol["audit_wall_cap_seconds"] * 1_000_000_000:
            raise TimeoutError("independent Sage suffix census exceeded frozen cap")
    counts["suffix_distinct_group_sums"] = len(suffix)

    audited_witnesses = []
    for i, left in enumerate(domains[0]):
        for j, right in enumerate(domains[1]):
            if left[1] & right[1]:
                continue
            counts["prefix_valid_assignments"] += 1
            prefix_mask = left[1] | right[1]
            residual = target - left[0] - right[0]
            found = suffix.get(residual)
            if found is None:
                continue
            counts["prefix_residual_support_hits"] += 1
            valid = False
            for packed in ([found] if isinstance(found, int) else found):
                k, l = packed & 2047, packed >> 11
                if prefix_mask & (domains[2][k][1] | domains[3][l][1]):
                    continue
                valid = True
                counts["eight_column_relations"] += 1
                if len(audited_witnesses) < protocol["max_saved_witnesses"]:
                    audited_witnesses.append([i, j, k, l])
            if valid:
                counts["prefixes_with_valid_completions"] += 1
        if time.monotonic_ns() - start > protocol["audit_wall_cap_seconds"] * 1_000_000_000:
            raise TimeoutError("independent Sage target census exceeded frozen cap")
    if counts != result["counts"]:
        raise ValueError("independent Sage occupancy or target census differs")
    if audited_witnesses != [w["pair_state_indices"] for w in result["saved_witnesses"]]:
        raise ValueError("saved witness order differs from independent Sage census")
    for witness in result["saved_witnesses"]:
        states = [domains[d][index] for d, index in
                  enumerate(witness["pair_state_indices"])]
        if sum((state[0] for state in states), curve(0)) != target:
            raise ValueError("Sage group replay of saved relation failed")
        columns = [column for pair in witness["columns"] for column in pair]
        if len(set(columns)) != 8:
            raise ValueError("saved row repeats a folded column")
        if witness["point_indices"] != [[state[2], state[3]] for state in states]:
            raise ValueError("saved row point indices differ")

    n131 = record["n131"]
    b = n131["per_slot_usable_points_B"]
    r = int(n131["subgroup_order"])
    d = math.comb(b, 2)
    bound = result["n131_fixed_prefix_bound"]
    if (bound["pair_state_upper_without_column_filter"] != d or
            bound["two_free_pair_assignment_upper"] != d * d or
            bound["uniform_nonidentity_target_hit_probability_upper"] !=
            {"numerator": d * d, "denominator": r - 1} or
            bound["fixed_prefix_probes_for_half_success_lower_by_union_bound"] !=
            ((r - 1) + 2 * d * d - 1) // (2 * d * d)):
        raise ValueError("N131 fixed-prefix union bound differs")

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    receipt = {
        "kind": "n41_two_free_pair_occupancy_independent_sage_audit",
        "status": "PASS_FULL_EXACT_RECOUNT_AND_GROUP_REPLAY",
        "curve_id": n41["curve_id"],
        "public_target_q": protocol["public_target_q"],
        "pair_domain_sizes": [len(domain) for domain in domains],
        "counts": counts,
        "replayed_saved_relations": len(result["saved_witnesses"]),
        "n131_bound_checked": True,
        "audit_wall_ns": time.monotonic_ns() - start,
        "audit_peak_rss_bytes": peak,
        "input_sha256": {"protocol": sha(PROTOCOL), "geometry": sha(GEOMETRY),
                         "result": sha(RESULT), "audit_source": sha(Path(__file__))},
    }
    with AUDIT.open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "counts": counts,
                      "audit_wall_ns": receipt["audit_wall_ns"]}, sort_keys=True))


if __name__ == "__main__":
    main()
