#!/usr/bin/env python3
"""Exact target-conditioned lookup for the matched fixed-sum N41 controls."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
INPUT = GOAL / "n131_w18_four_pairs/native_join/native_input.txt"
ROW = GOAL / "n41_two_free_pair_compact_lookup_20261009/public_search_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("positive", "negative"):
        raise SystemExit("usage: ./sage -python exact_baseline.py positive|negative")
    case = sys.argv[1]
    out = HERE / case / "exact_result.json"
    if out.exists():
        raise FileExistsError(out)
    frozen = json.loads((HERE / "baseline_protocol.json").read_text())
    core = json.loads((HERE / "protocol.json").read_text())
    assert frozen["sha256"]["source"] == sha(__file__)
    assert frozen["sha256"]["core_protocol"] == sha(HERE / "protocol.json")
    assert frozen["sha256"]["input"] == sha(INPUT)
    assert core["status"] == "FROZEN"
    sums = core[f"{case}_sum_masks"]
    binary = PolynomialRing(GF(2), "t")
    t = binary.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(binary([(int(value) >> i) & 1 for i in range(41)]))

    def encode(value):
        return sum(int(c) << i for i, c in enumerate(value.polynomial().list()))

    def point(coords):
        return curve(decode(coords[0]), decode(coords[1]))

    def seed(mask, rotation):
        value = sum((field(t**(i + 1)) for i in range(6) if mask >> i & 1),
                    field.zero())
        for _ in range(rotation):
            value = value**2
        return value

    def half_trace(value):
        result = field.zero()
        for _ in range(21):
            result += value
            value = value**4
        return result

    lines = INPUT.read_text().splitlines()
    position = 1
    slots = []
    for slot in range(8):
        count = int(lines[position]); position += 1
        values = [list(map(int, lines[position + j].split())) for j in range(count)]
        position += count
        slots.append(values)
    assert position == len(lines)
    source_row = json.loads(ROW.read_text())["row"]
    prefix_columns = {int(leaf["column"]) for leaf in source_row[:4]}
    assert len(prefix_columns) == 4
    residual = point(core["residual"])
    target = point(core["target_q"])
    started = time.monotonic_ns()
    groups = []
    leaf_build_ns = 0
    pair_build_ns = 0
    for index, pair in enumerate((2, 3)):
        stage = time.monotonic_ns()
        leaves = []
        for x, y, column, mask, branch, sign in slots[2 * pair]:
            assert branch == 0
            h = half_trace(seed(mask, core["rotations"][pair]))
            subgroup = point((x, y))
            matches = [raw for raw in curve.lift_x(1 + 1 / h, all=True)
                       if 4 * raw == subgroup]
            assert len(matches) == 1
            leaves.append((mask, column, matches[0], subgroup))
        assert len(leaves) == 64
        leaf_build_ns += time.monotonic_ns() - stage
        stage = time.monotonic_ns()
        bucket = {}
        for i, (a, ca, pa, qa) in enumerate(leaves):
            for b, cb, pb, qb in leaves[i + 1:]:
                if a ^ b == sums[index] and ca != cb:
                    bucket.setdefault(pa + pb, []).append(
                        ((a, b), (ca, cb), (qa, qb)))
        assert len(bucket) == core["exact_pair_domain_sizes"][index][str(sums[index])]
        groups.append(bucket)
        pair_build_ns += time.monotonic_ns() - stage
    stage = time.monotonic_ns()
    group_hits = 0
    column_rejects = 0
    witness = None
    for left_sum, left_entries in groups[0].items():
        needed = residual - left_sum
        if needed not in groups[1]:
            continue
        group_hits += 1
        for masks_left, cols_left, pts_left in left_entries:
            for masks_right, cols_right, pts_right in groups[1][needed]:
                columns = prefix_columns | set(cols_left) | set(cols_right)
                if len(columns) != 8:
                    column_rejects += 1
                    continue
                subgroup_points = list(pts_left) + list(pts_right)
                assert sum((point(x["point"]) for x in source_row[:4]),
                           curve(0)) + sum(subgroup_points, curve(0)) == target
                witness = {
                    "pair_masks": [list(masks_left), list(masks_right)],
                    "pair_columns": [list(cols_left), list(cols_right)],
                    "subgroup_points": [[encode(p[0]), encode(p[1])]
                                        for p in subgroup_points],
                }
                break
            if witness is not None:
                break
        if witness is not None:
            break
    lookup_ns = time.monotonic_ns() - stage
    online_ns = time.monotonic_ns() - started
    status = "VERIFIED_RAW_ROW" if witness else "EXACT_DOMAIN_EMPTY"
    expected = case == "positive"
    assert (witness is not None) == expected
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes = peak if sys.platform == "darwin" else peak * 1024
    assert online_ns < frozen["limits"]["per_case_seconds"] * 10**9
    assert peak_bytes < frozen["limits"]["combined_rss_bytes"]
    result = {
        "case": case, "status": status, "sum_masks": sums,
        "target": core["target_q"], "residual": core["residual"],
        "pair_group_sizes": [len(group) for group in groups],
        "group_hits": group_hits, "column_rejects": column_rejects,
        "witness": witness,
        "leaf_build_ns": leaf_build_ns,
        "pair_build_ns": pair_build_ns, "target_lookup_ns": lookup_ns,
        "interval_overhead_ns": online_ns - leaf_build_ns - pair_build_ns - lookup_ns,
        "online_ns": online_ns, "peak_self_rss_bytes": peak_bytes,
        "baseline_protocol_sha256": sha(HERE / "baseline_protocol.json"),
    }
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case": case, "status": status, "online_ns": online_ns,
                      "pair_group_sizes": result["pair_group_sizes"],
                      "peak_rss_bytes": peak_bytes}), flush=True)


if __name__ == "__main__":
    main()
