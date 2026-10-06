#!/usr/bin/env python3
"""Screen periodic 3-adic pair actions as a low-work online recoder."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct

from make_tau_pair_fused import ZERO, catalog, decode
from run import representatives
from screen_global_pair_search import (bounded, canonical_step, index, lattice_norm,
                                       quotient, reconstruct, score, tail_oracle)
from screen_tau_tail_double import ENDO_LAMBDA


ROOT = Path(__file__).resolve().parent
MODULI = (3, 9, 27, 81)


def centered(value, modulus):
    return (value + modulus // 2) % modulus - modulus // 2


def reference_plan(start, words_by_point, actions, reps):
    a, b = start
    words = []
    while a or b:
        assert len(words) < 128
        word = actions[index(a, b)] if bounded(a, b) else None
        if word is None:
            (a, b), word = canonical_step(a, b, words_by_point)
        else:
            da, db = decode(word, reps)
            a, b = quotient(a, b, da, db)
        words.append(word)
    assert reconstruct(words, reps) == start
    return tuple(words)


def periodic_plan(start, modulus, words_by_point, actions, reps):
    a, b = start
    words = []
    lookups = misses = 0
    while a or b:
        if len(words) == 128:
            return None, lookups, misses
        if bounded(a, b) and actions[index(a, b)] is not None:
            word = actions[index(a, b)]
        else:
            ra, rb = centered(a, modulus), centered(b, modulus)
            assert bounded(ra, rb)
            word = actions[index(ra, rb)]
            lookups += 1
            if word is None:
                misses += 1
                (a, b), word = canonical_step(a, b, words_by_point)
                words.append(word)
                continue
        da, db = decode(word, reps)
        a, b = quotient(a, b, da, db)
        words.append(word)
    assert reconstruct(words, reps) == start
    return tuple(words), lookups, misses


def main(args):
    reps, _, words_by_point, _, _ = catalog()
    options = [(a, b, word) for (a, b), word in words_by_point.items()]
    options.sort(key=lambda item: (lattice_norm(item[0], item[1]), item[2]))
    costs, actions = tail_oracle(options)
    assert sum(action is not None for action in actions) == 15043
    fixture = json.loads((ROOT / "tail-pair-fused-inputs.json").read_text())
    raw_rows = []
    sources = [Path(__file__), ROOT / "make_tau_pair_fused.py",
               ROOT / "screen_global_pair_search.py", ROOT / "run.py",
               ROOT / "make_tau_tail_double.py", ROOT / "screen_tau_tail_double.py",
               ROOT / "tail-pair-fused-inputs.json"]
    for case in (fixture["cases"][0], fixture["cases"][4]):
        scalar_path = ROOT / case["scalar_file"]
        raw = scalar_path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == case["scalar_file_sha256"]
        sources.append(scalar_path)
        scalars = struct.unpack(f"<{len(raw)//8}Q", raw)[:args.samples]
        curve = case["curve"]["name"]
        order = case["curve"]["order"]
        tau_lambda = (1 - (order - ENDO_LAMBDA[curve])) % order
        for scalar_index, scalar in enumerate(scalars):
            _, a, b = min(representatives(order, order - ENDO_LAMBDA[curve], scalar),
                          key=lambda row: row[0])
            assert (a + b * tau_lambda - scalar) % order == 0
            baseline = reference_plan((a, b), words_by_point, actions, reps)
            baseline_score = score(baseline)
            for modulus in MODULI:
                candidate, lookups, misses = periodic_plan((a, b), modulus,
                                                             words_by_point, actions, reps)
                candidate_score = None if candidate is None else score(candidate)
                chosen = (candidate if candidate is not None and
                          candidate_score < baseline_score else baseline)
                raw_rows.append((curve, scalar_index, scalar, modulus,
                                 baseline_score, candidate_score, score(chosen),
                                 len(baseline), None if candidate is None else len(candidate),
                                 sum(word != ZERO for word in baseline),
                                 None if candidate is None else
                                 sum(word != ZERO for word in candidate),
                                 lookups, misses, candidate is not None))
    raw_path = ROOT / "periodic-pair-atlas-raw.csv"
    with raw_path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("curve", "scalar_index", "scalar", "modulus",
                         "baseline_score", "candidate_score", "gated_score",
                         "baseline_pairs", "candidate_pairs", "baseline_adds",
                         "candidate_adds", "atlas_lookups", "atlas_misses",
                         "terminated"))
        writer.writerows(raw_rows)
    summaries = []
    for curve in ("glv-j0-32", "j0-56"):
        for modulus in MODULI:
            rows = [row for row in raw_rows if row[0] == curve and row[3] == modulus]
            old = sum(row[4] for row in rows)
            direct = sum(row[5] for row in rows if row[5] is not None)
            gated = sum(row[6] for row in rows)
            summaries.append({"curve": curve, "modulus": modulus,
                              "scalars": len(rows), "baseline_score": old,
                              "direct_score": direct if all(row[13] for row in rows) else None,
                              "gated_score": gated, "gated_saved_score": old - gated,
                              "direct_worse_scalars": sum(row[5] is not None and row[5] > row[4]
                                                          for row in rows),
                              "direct_improved_scalars": sum(row[5] is not None and row[5] < row[4]
                                                             for row in rows),
                              "nonterminating_scalars": sum(not row[13] for row in rows),
                              "atlas_lookups": sum(row[11] for row in rows),
                              "atlas_misses": sum(row[12] for row in rows)})
    result = {"schema": 1, "status": "retrospective_design_data_periodic_pair_atlas_screen",
              "cpu_timing_claim": None, "academic_novelty_claim": None,
              "sample_per_curve": args.samples, "moduli": list(MODULI),
              "tail_reached_states": 15043,
              "atlas_reached_entries": {
                  str(modulus): sum(actions[index(a, b)] is not None
                                    for a in range(-(modulus // 2), modulus // 2 + 1)
                                    for b in range(-(modulus // 2), modulus // 2 + 1))
                  for modulus in MODULI},
              "raw_csv": raw_path.name,
              "raw_csv_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
              "source_sha256": {str(path.relative_to(ROOT)):
                                hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in sources},
              "summaries": summaries}
    output = ROOT / "periodic-pair-atlas-screen.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "summaries": [{key: summary[key] for key in
                                     ("curve", "modulus", "gated_saved_score",
                                      "direct_worse_scalars", "atlas_lookups",
                                      "atlas_misses", "nonterminating_scalars")}
                                    for summary in summaries]}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=512)
    main(parser.parse_args())
