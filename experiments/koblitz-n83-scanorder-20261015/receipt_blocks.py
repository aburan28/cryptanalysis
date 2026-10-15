#!/usr/bin/env python3
"""Reconstruct every archived K600 baseline scan, state by state, from its receipt.

Zero compute beyond Python arithmetic; no timing. Input: the first IC receipt
per point of BL-arm run 38689817618 (`inputs/bl_run_38689817618_ic/`, copied
byte for byte from branch `claude/n83-bl-arm` at 4b8ff92a; digests in the
output) and the retained K600 base in `snapshots/r770`.

What the source fixes (crypto 770f6a69 `koblitz_orbit_dlp_fast_online.rs`,
wide path):

* `build_index128` pushes one state for every (left, right, relative) in
  that loop order; the receipts' `regular_states` is 29,880,000 = 600·600·83,
  so state `i` is left `i // 49,800`, right `(i // 83) % 600`, relative `i % 83`;
* `extract128_timed` scans `states[start..]` then `states[..start]`, with
  `start = query_hash mod S` and `query_hash` the public-point hash below;
* `scan_state128` batch-solves 2n = 166 roots per state and every root
  yields two partner probes (every receipt has 332·(k-1) < probes <= 332·k
  for k = root_calls / 166 states), so a state costs 332 probes and one left
  orbit (49,800 states) costs 16,533,600 probes.

For each point this script recomputes `start` from the point, the number of
states scanned (`root_calls / 166`) and the hit state, and checks the hit
state against the relation's own x-codes (left and right orbit and relative
shift). It then reports where each scan started and ended in left-orbit
blocks, and derives the planted-control start (`inputs/planted_starts.json`):
halfway through B's own hit-free stretch, with the exact probe count the
baseline scan must then report.

It also evaluates one stated model (a heuristic estimate, not a
measurement): each target has Poisson(lambda) four-term representations
Q = ±A ± B ± C ± D with four distinct orbits, lambda = C(99600, 4)/r; each
representation is found at the 12 ordered states (X, Y) with X != Y among
its orbits, so 3 of its hits fall in each of its 4 left-orbit blocks. The
model gives the mean probes of a left-major scan from a uniform start and of
a uniformly random state order, both over the quotient law r/(A·#states).
"""

import base64
import hashlib
import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECEIPTS = HERE / "inputs" / "bl_run_38689817618_ic"
BASE = HERE / "snapshots/r770/experiments/koblitz-single-target-n83-20261006/base_n83_K600.jsonl"
N = 83
MODULUS = (1 << 83) | (1 << 7) | (1 << 4) | (1 << 2) | 1
M128 = (1 << 128) - 1
R = 8569786107849059
LAW = R / (2 * N * 600 * 600 * N)  # r / (A · #states), A = 2n


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def square(a):
    out, i = 0, 0
    while a:
        if a & 1:
            out |= 1 << (2 * i)
        a >>= 1
        i += 1
    for d in range(out.bit_length() - 1, N - 1, -1):
        if out >> d & 1:
            out ^= MODULUS << (d - N)
    return out


def start_of(x, y):
    """B's wide query hash (u128 wrapping arithmetic), as `usize` (low 64 bits)."""
    h = x ^ (((y << 29) | (y >> 99)) & M128) ^ 0x9E3779B97F4A7C15_9E3779B97F4A7C15
    h = ((h ^ (h >> 30)) * 0xBF58476D1CE4E5B9_BF58476D1CE4E5B9) & M128
    h = ((h ^ (h >> 27)) * 0x94D049BB133111EB_94D049BB133111EB) & M128
    h ^= h >> 31
    return h & ((1 << 64) - 1)


def model(lam, samples, seed, columns=600):
    """Mean probes over the law for a left-major scan and a random order."""
    rng = random.Random(seed)
    states, block = columns * columns * N, columns * N
    left_major, uniform = [], []
    for _ in range(samples):
        # Poisson(lam) by inversion in the log domain (lam ~ 478).
        reps, p = 0, math.exp(-lam)
        cdf, u = p, rng.random()
        while u > cdf:
            reps += 1
            p *= lam / reps
            cdf += p
        hits = []
        for _ in range(reps):
            orbits = rng.sample(range(columns), 4)
            for a in orbits:
                for b in orbits:
                    if a != b:
                        hits.append(a * block + b * N + rng.randrange(N))
        s0 = rng.randrange(states)
        left_major.append((min((h - s0) % states for h in hits) + 1) * 2 * 2 * N)
        uniform.append((min(rng.randrange(states) for _ in hits) + 1) * 2 * 2 * N)

    def summary(values):
        mean = sum(values) / len(values)
        sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
        return {"mean_over_law": mean / LAW, "cv": sd / mean}
    return {"left_major_uniform_start": summary(left_major), "uniformly_random_order": summary(uniform),
            "samples": samples, "seed": seed, "lambda": lam}


def main():
    base = json.loads(BASE.read_text().splitlines()[0])
    reps = [int(p[0]) for p in base["factor_base_representatives"]]
    columns = len(reps)
    orbit = {}
    for left, x in enumerate(reps):
        value = x
        for shift in range(N):
            orbit[value] = (left, shift)
            value = square(value)
    states, block = columns * columns * N, columns * N
    per_state = 2 * 2 * N
    rows, planted = [], {}
    for path in sorted(RECEIPTS.glob("*.stdout.txt")):
        point_id = path.name.split(".")[0]
        line = next(l for l in path.read_text().splitlines() if l.startswith("raw_b64="))
        raw = json.loads(base64.b64decode(line[len("raw_b64="):]))
        record, summary = raw["records"][0], raw["records"][1]
        assert summary["regular_states"] == states, "state count differs from 600*600*83"
        x, y = (int(v) for v in record["target"])
        probes, root_calls = record["probes"], record["root_calls"]
        assert root_calls % (2 * N) == 0
        scanned = root_calls // (2 * N)
        # Every root call yields two partners; the scan stops inside the hit state.
        assert per_state * (scanned - 1) < probes <= per_state * scanned
        s0 = start_of(x, y) % states
        hit = (s0 + scanned - 1) % states
        left, rest = divmod(hit, block)
        right, relative = divmod(rest, N)
        code_left, shift_left = orbit[int(record["x_codes"][0])]
        code_right, shift_right = orbit[int(record["x_codes"][1])]
        consistent = (code_left == left and code_right == right and (shift_right - shift_left) % N == relative)
        start_left, start_offset = divmod(s0, block)
        crossed = (hit // block - start_left) % columns
        skip = (scanned - 1) // 2
        planted[point_id] = {"start_override": (s0 + skip) % states, "baseline_start": s0,
                             "skipped_states": skip, "expected_probes": probes - per_state * skip,
                             "baseline_probes": probes, "hit_state": hit,
                             "relation_point_indices": record["point_indices"],
                             "recovered_scalar": record["recovered_scalar"]}
        rows.append({
            "point_id": point_id, "probes": probes, "probes_over_law": probes / LAW,
            "states_scanned": scanned, "start_state": s0, "hit_state": hit,
            "start_left_orbit": start_left, "start_offset_in_block": start_offset,
            "states_left_in_start_block": block - start_offset,
            "hit_left_orbit": left, "hit_right_orbit": right, "hit_relative": relative,
            "hit_state_matches_relation_x_codes": consistent,
            "left_blocks_entered_after_start": crossed,
            "hit_offset_in_block": hit % block,
            "hit_free_states_before_hit": scanned - 1,
            "homogeneous_law_tail_probability": math.exp(-(scanned - 1) * per_state / LAW),
            "receipt_sha256": sha256(path),
        })
    fresh = [r for r in rows if r["point_id"] != "q0"]
    crossed = [r for r in fresh if r["left_blocks_entered_after_start"] > 0]
    lam = math.comb(columns * 2 * N, 4) / R
    out = {
        "source": {"run": "38689817618 (BL arm, branch claude/n83-bl-arm @ 4b8ff92a)",
                   "base_sha256": sha256(BASE), "producer": "crypto 770f6a69 koblitz_orbit_dlp_fast_online.rs + ic_log_cache.patch"},
        "exact": {"states": states, "states_per_left_block": block, "probes_per_state": per_state,
                  "probes_per_left_block": block * per_state, "law_probes": LAW,
                  "law_states": LAW / per_state},
        "rows": rows,
        "fresh_summary": {
            "points": len(fresh),
            "all_hit_states_match_relations": all(r["hit_state_matches_relation_x_codes"] for r in rows),
            "mean_probes": sum(r["probes"] for r in fresh) / len(fresh),
            "mean_over_law": sum(r["probes"] for r in fresh) / len(fresh) / LAW,
            "points_whose_hit_is_past_the_start_block": len(crossed),
            "points_with_a_whole_empty_block": sum(r["left_blocks_entered_after_start"] >= 2 for r in fresh),
            "tail_points_over_14M": [r["point_id"] for r in fresh if r["probes"] > 14_000_000],
        },
        "model": model(lam, 2000, 20261015, columns),
        "model_note": "heuristic estimate: Poisson four-term representations, 12 ordered states per representation, 3 per left block",
    }
    (HERE / "analysis").mkdir(exist_ok=True)
    (HERE / "analysis" / "receipt_blocks.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    (HERE / "inputs" / "planted_starts.json").write_text(json.dumps(
        {"schema": 1, "rule": "start_override = baseline_start + floor((states_scanned - 1) / 2) mod S; "
                              "expected_probes = baseline_probes - 332 * skipped_states (exact: no state in "
                              "[baseline_start, hit_state) has a lifted hit)",
         "source": "receipt_blocks.py over inputs/bl_run_38689817618_ic", "points": planted},
        indent=1, sort_keys=True) + "\n")
    print(json.dumps(out["fresh_summary"], sort_keys=True))
    print(json.dumps(out["model"], sort_keys=True))


if __name__ == "__main__":
    main()
