#!/usr/bin/env python3
"""Bound point-work gains from any two entries in the existing terminal table.

This is a retrospective combinatorial screen. It keeps the frozen four
representatives, twelve full-window digits, and terminal point table fixed.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PRIOR = ROOT / "prime-j0-terminal-split-20261011"
TABLE = ROOT / "prime-j0-fused-orbit-20261011/atlas-r1024-terminal-fused-orbit.bin"


def digest(raw):
    return sha256(raw).hexdigest()


def norm(pair):
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def point_proxy(terms, masks):
    occupied = sum(bool(mask) for mask in masks)
    rotations = sum(mask.bit_count() - 1 + int(mask & 1 == 0)
                    for mask in masks if mask)
    return (11 * (terms - occupied) + 14 * max(occupied - 1, 0)
            + 6 * bool(masks[1]) + 10 * bool(masks[2]) + rotations)


def read_table(raw):
    magic, bound, b_min, b_max, _, pair_count, reserved = struct.unpack_from(
        "<4sHhhIIH", raw)
    assert (magic, bound, reserved) == (b"R103", 149, 0)
    code_base = 20 + 8 * (b_max - b_min + 1)
    entries = []
    for b in range(b_min, b_max + 1):
        a_min, count, offset = struct.unpack_from("<hHI", raw, 20 + 8 * (b - b_min))
        for index in range(count):
            code = struct.unpack_from("<I", raw, code_base + 4 * (offset + index))[0]
            seed, exponent, unit = code >> 5, (code >> 3) & 3, code & 7
            assert exponent < 3 and unit < 6
            if seed:
                entries.append((a_min + index, b, 3 * exponent + unit // 2))
            else:
                assert (a_min + index, b) == (0, 0)
    assert len(entries) == pair_count - 1
    points = np.asarray(entries, dtype=np.int32)
    a_min = min(entry[0] for entry in entries)
    a_max = max(entry[0] for entry in entries)
    labels = np.full((a_max - a_min + 1, b_max - b_min + 1), -1, dtype=np.int8)
    labels[points[:, 0] - a_min, points[:, 1] - b_min] = points[:, 2]
    return points, labels, a_min, b_min


def all_pair_best(path, points, labels, a_min, b_min):
    """Return exact best proxy and a concrete witness from all nonzero pairs."""
    a, b = path["terminal"]
    q_a = a - points[:, 0] - a_min
    q_b = b - points[:, 1] - b_min
    valid = ((q_a >= 0) & (q_a < labels.shape[0]) &
             (q_b >= 0) & (q_b < labels.shape[1]))
    positions = np.flatnonzero(valid)
    q_labels = labels[q_a[positions], q_b[positions]]
    positions = positions[q_labels >= 0]
    q_labels = q_labels[q_labels >= 0]
    if len(positions) == 0:
        return None, 0, 0
    pair_codes = (9 * points[positions, 2].astype(np.int16) +
                  q_labels.astype(np.int16))
    distinct, first = np.unique(pair_codes, return_index=True)
    masks = [0, 0, 0]
    terms = 0
    for _, _, seed, exponent, unit in path["digits"]:
        if seed:
            masks[exponent] |= 1 << (unit // 2)
            terms += 1
    best = None
    for code, first_index in zip(distinct, first):
        left, right = divmod(int(code), 9)
        option_masks = masks.copy()
        option_masks[left // 3] |= 1 << (left % 3)
        option_masks[right // 3] |= 1 << (right % 3)
        proxy = point_proxy(terms + 2, option_masks)
        p = tuple(map(int, points[positions[first_index], :2]))
        q = (a - p[0], b - p[1])
        assert (p[0] + q[0], p[1] + q[1]) == (a, b)
        assert labels[p[0] - a_min, p[1] - b_min] == left
        assert labels[q[0] - a_min, q[1] - b_min] == right
        candidate = (proxy, p, q)
        if best is None or candidate < best:
            best = candidate
    return best, len(distinct), len(positions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        raise SystemExit("refusing to overwrite screen receipt")
    input_raw = (PRIOR / "holdout-inputs.json").read_bytes()
    path_raw = (PRIOR / "holdout-paths.jsonl").read_bytes()
    table_raw = TABLE.read_bytes()
    prior_screen = json.loads((PRIOR / "holdout-screen.json").read_bytes())
    inputs = json.loads(input_raw)
    assert digest(input_raw) == prior_screen["input_sha256"]
    assert digest(path_raw) == prior_screen["certificate_sha256"]
    assert digest(table_raw) == inputs["terminal_sha256"] == prior_screen["terminal_sha256"]
    points, labels, a_min, b_min = read_table(table_raw)
    total_prior = total_bound = improved = witnesses = improved_inside_disk = 0
    eligible_representatives = omitted_corners = distinct_label_sets = exact_pairs = 0
    witness_hash = sha256()
    rows = path_raw.splitlines()[:args.limit]
    for line in rows:
        row = json.loads(line)
        assert row["index"] == witnesses
        old = row["options"][row["selected_option"]]["metrics"]["point_proxy_units"]
        best = (old, None, None, None)
        best_terminal_inside = False
        seen = set()
        for option in row["options"]:
            path = option["path"]
            representative = tuple(path["representative"])
            if representative in seen:
                continue
            seen.add(representative)
            eligible_representatives += 1
            candidate, label_count, pair_count = all_pair_best(
                path, points, labels, a_min, b_min)
            distinct_label_sets += label_count
            exact_pairs += pair_count
            if candidate is not None and candidate[0] < best[0]:
                best = (candidate[0], representative, candidate[1], candidate[2])
                best_terminal_inside = norm(path["terminal"]) < 149 * 149
        # The frozen certificate omits corners where its midpoint rule found
        # no valid split. This screen bounds the retained paths only.
        assert 1 <= len(seen) <= 4
        omitted_corners += 4 - len(seen)
        total_prior += old
        total_bound += best[0]
        if best[0] < old:
            improved += 1
            improved_inside_disk += best_terminal_inside
            witness_hash.update(json.dumps((row["index"], best), separators=(",", ":")).encode())
        witnesses += 1
    if args.limit is None:
        assert witnesses == 4096 and total_prior == 609671
    result = {"schema": 1, "status": "screened",
              "kind": "retrospective-recorded-path-all-terminal-pairs",
              "cases": witnesses, "prior_point_proxy_units": total_prior,
              "all_pair_point_proxy_units": total_bound,
              "point_proxy_units_saved": total_prior - total_bound,
              "improved_cases": improved,
              "improved_with_terminal_inside_disk": improved_inside_disk,
              "representatives": eligible_representatives,
              "omitted_original_corners": omitted_corners,
              "feasible_label_sets_examined": distinct_label_sets,
              "exact_point_pairs_examined": exact_pairs,
              "improved_witnesses_sha256": witness_hash.hexdigest(),
              "input_sha256": digest(input_raw), "path_sha256": digest(path_raw),
              "terminal_table_sha256": digest(table_raw),
              "source_sha256": digest(Path(__file__).read_bytes())}
    if args.output:
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
