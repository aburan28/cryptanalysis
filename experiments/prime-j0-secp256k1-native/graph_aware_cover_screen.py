#!/usr/bin/env python3
"""Score all nine Eisenstein representatives with the frozen graph33 atlas."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import scalar_text
from hex9_cover_screen import hex_choices, score_pair
from radius2_graph_screen import matching_atlas
from radius3_balanced_screen import sha
from screen_coset_representatives import N
from tau6_comb13_sparse_screen import SPARSE_TOP_ORBITS
from tau6_comb_screen import digit_stream
from width6_tau_screen import build_width_six_table


HERE = Path(__file__).resolve().parent
GRAPH33 = tuple(tuple(edge) for edge in json.loads(
    (HERE / "radius3-balanced-screen-result.json").read_text())["edges"]["g33"])
ATLAS = matching_atlas(GRAPH33)
SEEDS = {"design": 20261009411, "holdout": 20261009412}
COUNT = 2048
BASELINE_SHA256 = "a7a43630b2435daee293d9888b76527d345c56dec21bac500a8e91f5712b35e8"


def active_masks(digits):
    masks = [0] * 13
    for index, digit in enumerate(digits):
        if digit is not None and index // 13 < 12:
            masks[index % 13] |= 1 << (index // 13)
    return masks


def representatives(scalar, table, selected):
    attempts = []
    for rank, (_, _, a, b) in enumerate(hex_choices(scalar)):
        result = score_pair(a, b, table, selected)
        if result is None:
            continue
        digits = digit_stream((a, b), table, 162)
        fusion_count = sum(len(ATLAS[mask]) for mask in active_masks(digits))
        matched_proxy = result["field_product_proxy"] - 11 * fusion_count
        assert matched_proxy == 5 * result["tau_steps"] + 11 * (
            result["mixed_additions"] - fusion_count)
        attempts.append({**result, "rank": rank, "fusions": fusion_count,
                         "matched_proxy": matched_proxy})
    assert attempts and attempts[0]["rank"] == 0
    baseline = min(attempts, key=lambda x: (x["field_product_proxy"], x["rank"]))
    candidate = min(attempts, key=lambda x: (x["matched_proxy"], x["rank"]))
    return baseline, candidate, len(attempts)


def native_check(binary, scalars, expected):
    process = subprocess.run(
        [str(binary), "--scalar-w6-comb13-hex9-graph33-fixed"],
        input="".join(scalar_text(scalar) + "\n" for scalar in scalars),
        text=True, capture_output=True, check=True, timeout=900,
    )
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(expected)
    for index, (row, (baseline, _, valid)) in enumerate(zip(rows, expected)):
        assert list(map(int, row["representative"])) == baseline["representative"], index
        assert row["tau_steps"] == baseline["tau_steps"], index
        assert row["nonzero_digits"] == baseline["mixed_additions"] - baseline["fusions"], index
        work = row["recoding_work"]
        assert work["top_repaired"] == baseline["top_repaired"], index
        assert work["pair_fusions"] == baseline["fusions"], index
        assert work["coset_rank"] == baseline["rank"], index
        assert work["valid_representatives"] == valid, index
        assert work["attempted_representatives"] == 9, index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", choices=SEEDS, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output exists")
    binary = args.binary.resolve(strict=True)
    if sha(binary) != BASELINE_SHA256:
        raise SystemExit("baseline binary differs from protocol")
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    selected = set(SPARSE_TOP_ORBITS)
    atlas_hash = hashlib.sha256(json.dumps(ATLAS).encode()).hexdigest()
    parent = json.loads((HERE / "radius3-balanced-screen-result.json").read_text())
    assert atlas_hash == parent["atlas_sha256"]["g33"]

    rng = random.Random(SEEDS[args.panel])
    scalars = [rng.randrange(N) for _ in range(COUNT)]
    input_hash = hashlib.sha256(b"".join(
        value.to_bytes(32, "big") for value in scalars)).hexdigest()
    rows = []
    native_expected = []
    totals = Counter()
    deltas = Counter()
    for index, scalar in enumerate(scalars):
        baseline, candidate, valid = representatives(scalar, table, selected)
        improvement = baseline["matched_proxy"] - candidate["matched_proxy"]
        assert improvement >= 0, index
        totals.update({"cases": 1, "baseline_proxy": baseline["matched_proxy"],
                       "candidate_proxy": candidate["matched_proxy"],
                       "baseline_fusions": baseline["fusions"],
                       "candidate_fusions": candidate["fusions"],
                       "baseline_mixed_additions": baseline["mixed_additions"] - baseline["fusions"],
                       "candidate_mixed_additions": candidate["mixed_additions"] - candidate["fusions"],
                       "baseline_tau_steps": baseline["tau_steps"],
                       "candidate_tau_steps": candidate["tau_steps"],
                       "rank_changes": int(baseline["rank"] != candidate["rank"]),
                       "top_repairs_baseline": int(baseline["top_repaired"]),
                       "top_repairs_candidate": int(candidate["top_repaired"])})
        deltas[improvement] += 1
        rows.append({"index": index, "baseline_rank": baseline["rank"],
                     "candidate_rank": candidate["rank"], "valid": valid,
                     "baseline_proxy": baseline["matched_proxy"],
                     "candidate_proxy": candidate["matched_proxy"],
                     "baseline_fusions": baseline["fusions"],
                     "candidate_fusions": candidate["fusions"]})
        if index < 128:
            native_expected.append((baseline, candidate, valid))
        if index == 127:
            native_check(binary, scalars[:128], native_expected)
    gain = totals["baseline_proxy"] - totals["candidate_proxy"]
    passed = gain * 100 >= totals["baseline_proxy"]
    result = {"schema": 1, "panel": args.panel, "status": "screen_passed" if passed else "screen_stopped",
              "seed": SEEDS[args.panel], "count": COUNT, "input_sha256": input_hash,
              "baseline_binary_sha256": sha(binary), "protocol_sha256": sha(HERE / "GRAPH_AWARE_COVER_PROTOCOL.md"),
              "screen_sha256": sha(Path(__file__)), "parent_screen_sha256": sha(HERE / "radius3-balanced-screen-result.json"),
              "atlas_sha256": atlas_hash, "totals": dict(totals), "delta_counts": dict(sorted(deltas.items())),
              "gain_percent": 100 * gain / totals["baseline_proxy"], "native_baseline_checks": 128,
              "rows": rows}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "panel": args.panel,
                      "gain_percent": result["gain_percent"], "totals": dict(totals),
                      "receipt_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
