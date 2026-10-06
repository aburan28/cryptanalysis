#!/usr/bin/env python3
"""Retrospective exact-cost radix-minus-27 block-action shortest-path screen."""

import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct

from make_tau3_fused import UNREACHABLE, build, tau
from make_tau3_sparse import build_candidate
from run import representatives


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "compact-pos-inputs.json"
COMPACT_PANEL = ROOT / "compact-pos-panel.json"
SPARSE_RECEIPT = ROOT / "tau3-sparse-native-design.json"
INF = 10**9


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pattern_coeff(pattern, digits):
    if not pattern:
        return 0, 0
    position = (pattern - 1) // 18
    a, b = digits[(pattern - 1) % 18]
    for _ in range(position):
        a, b = tau(a, b)
    return a, b


def action_pool():
    digits, _, _, orbit_id, orbit_unit, representatives_by_id = build()
    pool = defaultdict(list)
    for u in range(55):
        for v in range(55):
            index = 55 * u + v
            identity = orbit_id[index]
            if identity == UNREACHABLE:
                continue
            a, b = pattern_coeff(u, digits)
            c, d = pattern_coeff(v, digits)
            for _ in range(3):
                c, d = tau(c, d)
            correction = (a + c, b + d)
            action = (identity << 3) | orbit_unit[index]
            pool[(correction[0] % 27, correction[1] % 27)].append(
                (correction, action))
    assert len(pool) == 729
    assert sum(map(len, pool.values())) == 2053
    assert Counter(map(len, pool.values())) == {1: 397, 3: 222, 9: 110}
    singles = {i for i, (u, v) in enumerate(representatives_by_id)
               if (u == 0) != (v == 0)}
    assert len(singles) == 18
    return pool, singles


def shortest_path_solver(pool, singles, hot_sets):
    @lru_cache(maxsize=None)
    def solve(a, b, block):
        if not (a or b):
            return 0, None
        if block >= len(hot_sets):
            return INF, None
        best = (INF, None)
        best_rank = (INF, INF, INF, INF, INF)
        for correction, action in pool[(a % 27, b % 27)]:
            identity = action >> 3
            charge = (0 if identity == 0 else 1 if identity in singles or
                      identity in hot_sets[block] else 2)
            next_a = (correction[0] - a) // 27
            next_b = (correction[1] - b) // 27
            tail, _ = solve(next_a, next_b, block + 1)
            rank = (charge + tail, abs(correction[0]) + abs(correction[1]),
                    action, correction[0], correction[1])
            if rank < best_rank:
                best_rank = rank
                best = (charge + tail, (correction, action, next_a, next_b, charge))
        return best

    return solve


def replay(solve, a, b, blocks, hot_sets, singles):
    original = a, b
    total = 0
    cold = 0
    used = 0
    reconstruction = (0, 0)
    power = 1
    while a or b:
        if used >= blocks:
            return None
        optimum, choice = solve(a, b, used)
        assert optimum < INF and choice is not None
        correction, action, next_a, next_b, charge = choice
        assert (correction[0] - a) % 27 == (correction[1] - b) % 27 == 0
        assert (next_a, next_b) == ((correction[0] - a) // 27,
                                    (correction[1] - b) // 27)
        assert charge + solve(next_a, next_b, used + 1)[0] == optimum
        identity = action >> 3
        assert charge == (0 if identity == 0 else 1 if identity in singles or
                          identity in hot_sets[used] else 2)
        total += charge
        cold += charge == 2
        reconstruction = (reconstruction[0] + power * correction[0],
                          reconstruction[1] + power * correction[1])
        power *= -27
        a, b = next_a, next_b
        used += 1
    assert reconstruction == original
    return total, cold, used


def screen():
    pool, singles = action_pool()
    records, hot_arrays, _, _ = build_candidate()
    fixture = json.loads(FIXTURE.read_text())
    compact_panel = json.loads(COMPACT_PANEL.read_text())
    sparse_receipt = json.loads(SPARSE_RECEIPT.read_text())
    compact_rows = {(row["case_id"], row["mode"]): row for row in compact_panel["rows"]}
    sparse_rows = {(row["case_id"], row["mode"]): row for row in sparse_receipt["rows"]}
    rows = []
    for record in records:
        curve = record["curve"]
        offsets, hot_ids, _ = hot_arrays[curve]
        hot_sets = [set(hot_ids[offsets[block]:offsets[block + 1]])
                    for block in range(record["blocks"])]
        solve = shortest_path_solver(pool, singles, hot_sets)
        for case in fixture["cases"]:
            if case["curve"]["name"] != curve:
                continue
            order = case["curve"]["order"]
            old = compact_rows[(case["id"], "pos-compact")]["fields"]
            eigenvalue = (order - int(old["endo_lambda"])) % order
            content = (ROOT / case["scalar_file"]).read_bytes()
            assert hashlib.sha256(content).hexdigest() == case["scalar_file_sha256"]
            total = cold = max_blocks = fallback = count = 0
            for (scalar,) in struct.iter_unpack("<Q", content):
                _, a, b = min(representatives(order, eigenvalue, scalar),
                              key=lambda item: item[0])
                result = replay(solve, a, b, record["blocks"], hot_sets, singles)
                if result is None:
                    fallback += 1
                    continue
                additions, cold_pairs, blocks = result
                total += additions
                cold += cold_pairs
                max_blocks = max(max_blocks, blocks)
                count += 1
            baseline = int(sparse_rows[(case["id"], "tau3-sparse-pos")]["fields"]["adds"])
            assert count == case["scalars"] and fallback == 0 and total <= baseline
            rows.append({"case_id": case["id"], "curve": curve,
                         "scalar_file_sha256": case["scalar_file_sha256"],
                         "scalars": count, "fallbacks": fallback,
                         "prepared_blocks": record["blocks"],
                         "maximum_used_blocks": max_blocks,
                         "optimal_additions": total, "optimal_cold_pairs": cold,
                         "native_sparse_additions": baseline,
                         "native_compact_additions": int(old["adds"]),
                         "cached_dp_states_at_case_end": solve.cache_info().currsize})
    assert len(rows) == 8
    return {"schema": 1, "status": "retrospective_radix27_shortest_path_screen",
            "cpu_timing_claim": None, "novelty_claim": None,
            "alphabet": "2053 valid two-half tau actions; 729 coefficient residues modulo 27",
            "objective": "minimum charged mixed additions within the frozen sparse point table and block bound",
            "ties": "correction L1, action code, signed correction coefficients",
            "fixture_sha256": sha256(FIXTURE),
            "compact_panel_sha256": sha256(COMPACT_PANEL),
            "sparse_receipt_sha256": sha256(SPARSE_RECEIPT),
            "sparse_header_sha256": sha256(ROOT.parents[1] / "src/generated/tau3_sparse.h"),
            "source_sha256": sha256(Path(__file__)),
            "residue_option_multiplicity": {"1": 397, "3": 222, "9": 110},
            "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = screen()
    content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output.exists() and args.output.read_text() != content:
        raise ValueError("frozen report differs from recomputed screen")
    args.output.write_text(content)
    print(json.dumps({"status": report["status"],
                      "rows": [{key: row[key] for key in
                                ("case_id", "optimal_additions", "native_sparse_additions")}
                               for row in report["rows"]]}, sort_keys=True))


if __name__ == "__main__":
    main()
