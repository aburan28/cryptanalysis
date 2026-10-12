#!/usr/bin/env python3
"""Deterministic coordinate-ascent screen of affine W_11 cosets."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from sweep import CODEGEN, D, HERE, KEY_BYTES, N, OUT, PAIR, scan, sha

sys.path[:0] = [str(CODEGEN), str(PAIR)]
import curves  # noqa: E402
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402

MAX_ROUNDS = 4


def main() -> None:
    started = time.perf_counter_ns()
    original_path = OUT / "sweep.json"
    original = json.loads(original_path.read_text())
    assert json.loads((OUT / "sage_runtime_info.json").read_text())["status"] == "verified"
    assert json.loads((OUT / "independent_sage_replay.json").read_text())["status"] == "PASS"
    assert not (OUT / "improve.json").exists()
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    incumbent = original["winner"]
    rounds = []
    evaluated = {row["offset_onb_coordinates"]: row for row in original["rows"]}
    for round_number in range(1, MAX_ROUNDS + 1):
        offset = incumbent["offset_onb_coordinates"]
        neighbors = []
        before_count = len(evaluated)
        for bit in range(D, N):
            candidate_offset = offset ^ (1 << bit)
            if candidate_offset in evaluated:
                row = evaluated[candidate_offset]
            else:
                row, _ = scan(candidate_offset, onb, curve, orbit)
                evaluated[candidate_offset] = row
            neighbors.append(row)
        candidate = max(neighbors, key=lambda row: (row["folded_columns_K"], -row["offset_onb_coordinates"]))
        rounds.append({"round": round_number, "incumbent_offset": offset,
                       "incumbent_K": incumbent["folded_columns_K"],
                       "best_neighbor_offset": candidate["offset_onb_coordinates"],
                       "best_neighbor_K": candidate["folded_columns_K"],
                       "new_evaluations": len(evaluated) - before_count})
        print(json.dumps(rounds[-1]), flush=True)
        if candidate["folded_columns_K"] <= incumbent["folded_columns_K"]:
            break
        incumbent = candidate
    _, keys = scan(incumbent["offset_onb_coordinates"], onb, curve, orbit)
    assert len(keys) == incumbent["folded_columns_K"]
    path = OUT / "improved_canonical_keys.bin"
    path.write_bytes(b"".join(key.to_bytes(KEY_BYTES, "little") for key in keys))
    winner = dict(incumbent)
    winner["canonical_keys_file"] = path.name
    winner["canonical_keys_sha256"] = sha(path)
    winner["canonical_keys_bytes"] = path.stat().st_size
    output = {
        "kind": "n83_affine_w11_coordinate_ascent_factor_base_geometry",
        "status": "completed_base_geometry_stage",
        "curve_id": original["curve_id"],
        "candidate_id": None,
        "workload_id": None,
        "run_id": None,
        "selection_rule": "best K among all 72 one-coordinate toggles at each step; smallest offset wins ties; stop at no strict gain or four rounds",
        "initial_sweep_sha256": sha(original_path),
        "max_rounds": MAX_ROUNDS,
        "rounds": rounds,
        "distinct_evaluated_offsets": len(evaluated),
        "evaluated_rows": [evaluated[key] for key in sorted(evaluated)],
        "winner": winner,
        "wall_ns": time.perf_counter_ns() - started,
        "source_sha256": {"improve": sha(Path(__file__)), "sweep": sha(HERE / "sweep.py"),
                          "field": sha(CODEGEN / "field.py"), "curve": sha(CODEGEN / "curves.py"),
                          "orbit_key": sha(PAIR / "orbit_key.py")},
        "natural_relation_yield": None,
        "one_target_online_ms": None,
    }
    (OUT / "improve.json").write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
