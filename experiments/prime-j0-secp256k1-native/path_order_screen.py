#!/usr/bin/env python3
"""Choose a tau-comb row path on design masks and test it on holdout masks."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import scalar_text
from screen_coset_representatives import N
from tau6_comb_screen import digit_stream
from width6_tau_screen import build_width_six_table

HERE = Path(__file__).resolve().parent
SEEDS = (20261009211, 20261009212)
COUNT = 4096
ROWS = 12
NATIVE_BINARY_SHA256 = "e8ffd24be7ea2c976b9ab8f31cea7d7d1cda0b6fbeb35b7e5b95ba2e1ae411aa"
NATURAL = tuple(range(ROWS))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matched(mask, order):
    result = 0
    index = 0
    while index + 1 < ROWS:
        if mask & (1 << order[index]) and mask & (1 << order[index + 1]):
            result += 1
            index += 2
        else:
            index += 1
    return result


def best_weight_path(weights):
    """Exact weighted Hamiltonian path with lexicographic tie breaking."""
    all_masks = 1 << ROWS
    states = [dict() for _ in range(all_masks)]
    for row in range(ROWS):
        states[1 << row][row] = (0, (row,))
    for mask in range(1, all_masks):
        for last, (score, order) in tuple(states[mask].items()):
            unused = (all_masks - 1) ^ mask
            while unused:
                bit = unused & -unused
                nxt = bit.bit_length() - 1
                proposal = (score + weights[last][nxt], order + (nxt,))
                old = states[mask | bit].get(nxt)
                if old is None or proposal[0] > old[0] or (
                    proposal[0] == old[0] and proposal[1] < old[1]
                ):
                    states[mask | bit][nxt] = proposal
                unused ^= bit
    score, order = sorted(states[-1].values(), key=lambda row: (-row[0], row[1]))[0]
    assert sorted(order) == list(NATURAL)
    return score, order


def run(binary, scalars):
    process = subprocess.run(
        [str(binary), "--scalar-w6-comb13-hex9-path-fixed"],
        input="".join(scalar_text(value) + "\n" for value in scalars),
        capture_output=True, text=True, check=True, timeout=600,
    )
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def masks_for_result(result, table):
    digits = digit_stream(tuple(map(int, result["representative"])), table, 162)
    masks = tuple(sum(1 << row for row in range(ROWS)
                      if row * 13 + column < len(digits)
                      and digits[row * 13 + column] is not None)
                  for column in range(13))
    assert sum(matched(mask, NATURAL) for mask in masks) == result["recoding_work"]["pair_fusions"]
    return masks


def weights_for(records):
    weights = [[0] * ROWS for _ in range(ROWS)]
    for masks, _ in records:
        for mask in masks:
            for left in range(ROWS):
                if not mask & (1 << left):
                    continue
                for right in range(left + 1, ROWS):
                    if mask & (1 << right):
                        weights[left][right] += 1
                        weights[right][left] += 1
    return weights


def summarize(records, order):
    totals = Counter()
    delta = Counter()
    fingerprint = hashlib.sha256()
    for masks, native in records:
        natural = sum(matched(mask, NATURAL) for mask in masks)
        shaped = sum(matched(mask, order) for mask in masks)
        complete = sum(mask.bit_count() // 2 for mask in masks)
        assert natural <= complete and shaped <= complete
        additions = native["nonzero_digits"] + natural
        tau = native["tau_steps"]
        delta[shaped - natural] += 1
        totals.update({"cases": 1, "tau_steps": tau,
                       "natural_fusions": natural, "shaped_fusions": shaped,
                       "complete_fusions": complete,
                       "natural_adds": additions - natural,
                       "shaped_adds": additions - shaped,
                       "complete_adds": additions - complete,
                       "natural_proxy": 5 * tau + 11 * (additions - natural),
                       "shaped_proxy": 5 * tau + 11 * (additions - shaped),
                       "complete_proxy": 5 * tau + 11 * (additions - complete)})
        fingerprint.update(f"{natural},{shaped},{complete},{tau},{additions}\n".encode())
    return {"totals": dict(totals), "fusion_delta_histogram": dict(sorted(delta.items())),
            "per_case_sha256": fingerprint.hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output already exists")
    binary = args.binary.resolve(strict=True)
    if sha(binary) != NATIVE_BINARY_SHA256:
        raise SystemExit("native path binary differs from frozen reference")
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    panels = {}
    for name, seed in zip(("design", "holdout"), SEEDS):
        rng = random.Random(seed)
        scalars = [rng.randrange(N) for _ in range(COUNT)]
        rows = run(binary, scalars)
        panels[name] = {
            "records": [(masks_for_result(row, table), row) for row in rows],
            "scalar_sha256": hashlib.sha256(
                b"".join(value.to_bytes(32, "big") for value in scalars)).hexdigest(),
        }
    weights = weights_for(panels["design"]["records"])
    score, order = best_weight_path(weights)
    summaries = {}
    for name, data in panels.items():
        summaries[name] = summarize(data["records"], order)
        summaries[name]["scalar_sha256"] = data["scalar_sha256"]
    holdout = summaries["holdout"]["totals"]
    improvement = holdout["natural_proxy"] - holdout["shaped_proxy"]
    passes = improvement * 100 >= holdout["natural_proxy"]
    result = {"schema": 1, "status": "screen_passed" if passes else "screen_stopped",
              "design_seed": SEEDS[0], "holdout_seed": SEEDS[1], "count_per_panel": COUNT,
              "natural_order": NATURAL, "selected_order": order,
              "design_edge_weight_sum": score, "design_pair_weights": weights,
              "table_bytes_per_path": 11 * 81 * 81 * 6 * 104,
              "reference_binary_sha256": sha(binary),
              "protocol_sha256": sha(HERE / "PATH_ORDER_PROTOCOL.md"),
              "checker_sha256": sha(Path(__file__)), "panels": summaries}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "selected_order": order,
                      "holdout_improvement_percent":
                      100 * improvement / holdout["natural_proxy"],
                      "design": summaries["design"]["totals"],
                      "holdout": holdout, "receipt_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
