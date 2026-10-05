#!/usr/bin/env python3
"""Score the orbit-pair point policy on previously used design scalars."""

import hashlib
import json
from pathlib import Path
import struct

from make_tau_pair_fused import catalog, generate, index, pack, validate
from make_tau_tail_gate import canonical_cost
from screen_tau_tail_double import ENDO_LAMBDA, sample_tail


ROOT = Path(__file__).resolve().parent


def main():
    reps, _recipes, words, _even, _odd = catalog()
    costs, actions, old_costs = generate(reps, words)
    reached, _paths, max_pairs = validate(costs, actions, reps)
    codes, gate, _offsets, _lengths, _dictionary = pack(costs, actions, reps)
    fixture_path = ROOT / "tail-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    rows = []
    sources = [Path(__file__).resolve(), ROOT / "make_tau_pair_fused.py",
               ROOT / "make_tau_tail_double.py", ROOT / "make_tau_tail_gate.py",
               ROOT / "screen_tau_tail_double.py", ROOT / "run.py", fixture_path]
    for case in (fixture["cases"][0], fixture["cases"][4]):
        scalar_path = ROOT / case["scalar_file"]
        raw = scalar_path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == case["scalar_file_sha256"]
        sources.append(scalar_path)
        scalars = struct.unpack(f"<{len(raw)//8}Q", raw)
        curve = case["curve"]["name"]
        old_total = fused_total = wins = losses = 0
        for scalar in scalars:
            a, b, phase = sample_tail(scalar, case["curve"]["order"],
                                      case["curve"]["order"] - ENDO_LAMBDA[curve])
            pos = index(a, b, phase)
            canonical = canonical_cost(a, b, phase)
            old = min(canonical, old_costs[pos])
            new = min(canonical, costs[pos])
            old_total += old
            fused_total += new
            wins += new < old
            losses += new > old
        assert losses == 0
        rows.append({"curve": curve, "scalars": len(scalars),
                     "old_two_digit_tail_weight": old_total,
                     "fused_pair_tail_weight": fused_total,
                     "saved_weight": old_total - fused_total,
                     "winning_scalars": wins, "losing_scalars": losses})
    report = {"schema": 1, "status": "design_data_operation_screen_only",
              "cpu_timing_claim": None, "target_independent_setup_charged": False,
              "point_orbits": len(reps), "raw_pair_choices": 3025,
              "unique_contributions": len(words), "bounded_states": len(costs),
              "reachable_states": reached, "max_tail_pairs": max_pairs,
              "states_cheaper_than_unfused": sum(a < b for a, b in zip(costs, old_costs)),
              "states_more_expensive_than_unfused": sum(a > b for a, b in zip(costs, old_costs)),
              "packed_state_bytes": len(codes), "gate_bytes": len(gate),
              "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in sources},
              "results": rows}
    output = ROOT / "tail-pair-fused-screen.json"
    data = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text() != data:
        raise ValueError(f"design screen changed: {output}")
    output.write_text(data)
    print(json.dumps({"status": report["status"], "point_orbits": len(reps),
                      "saved_weight": sum(row["saved_weight"] for row in rows)}, sort_keys=True))


if __name__ == "__main__":
    main()
