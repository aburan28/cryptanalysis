#!/usr/bin/env python3
"""Predeclared prefix screen on the three frozen ordinary rank-eight streams.

Stop after each stream's first charged target if that single attempt already
exceeds half the compiled control's complete rank-eight wall time. Because all
remaining costs are nonnegative, the current pipeline cannot meet the 2x
collection goal on that stream. This is an early-stop lower bound, not a
fabricated complete cost per relation.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, default=HERE / "compiled_control_results.json")
    p.add_argument("--out", type=Path, default=HERE / "matched_prefix_results.json")
    p.add_argument("--timeout", type=float, default=60.0)
    args = p.parse_args()
    runs = json.loads(args.baseline.read_text())["runs"]
    seeds = sorted({r["seed"] for r in runs})
    records = []
    for seed in seeds:
        matched = [r for r in runs if r["seed"] == seed]
        assert len(matched) == 2 and len({tuple(r["targets"]) for r in matched}) == 1
        ceiling = min(r["driver_wall_ns_including_startup"] for r in matched) / 2e9
        path = args.out.with_name(f"matched_prefix_{seed}.json")
        subprocess.run([sys.executable, str(HERE / "probe_large.py"),
                        "--seed", str(seed), "--target-index", "0",
                        "--timeout", str(args.timeout), "--out", str(path)],
                       check=True)
        outcome = json.loads(path.read_text())
        first = outcome["stages"][0]
        assert first["target_scalar"] == matched[0]["targets"][0]
        assert first["target_point"] == matched[0]["attempts"][0]["target_point"]
        wall = outcome["charged_wall_seconds"]
        record = {
            "seed": seed, "first_target_scalar": first["target_scalar"],
            "first_target_point": first["target_point"],
            "first_target_compiled_outcome": matched[0]["attempts"][0]["status"],
            "first_target_homogeneous_outcome": outcome["status"],
            "first_target_independent_verified_rows": outcome["independent_verified_relations"],
            "first_target_wall_seconds": wall,
            "compiled_rank_eight_wall_seconds_fastest_repeat": 2 * ceiling,
            "max_candidate_rank_eight_wall_seconds_for_2x": ceiling,
            "single_target_lower_bound_exceeds_2x_budget": wall > ceiling,
            "attempts_run": 1, "full_rank_eight_wall_seconds": None,
            "full_rank_eight_seconds_per_new_row": None,
            "receipt": path.name,
        }
        records.append(record)
        args.out.write_text(json.dumps({
            "schema": "homogeneous-fraction-matched-prefix.v1",
            "resource_limit_seconds_per_target": args.timeout,
            "stop_rule": "first target exceeds half of fastest compiled control's "
                         "full rank-eight wall time on the identical stream",
            "status": "early_stopped_cannot_meet_2x" if all(
                r["single_target_lower_bound_exceeds_2x_budget"] for r in records)
                else "continue_needed",
            "runs": records,
        }, indent=2) + "\n")
        print(json.dumps(record), flush=True)
        if not record["single_target_lower_bound_exceeds_2x_budget"]:
            raise RuntimeError("bound is inconclusive: run the full matched rank-eight sequence")


if __name__ == "__main__":
    main()
