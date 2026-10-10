#!/usr/bin/env python3
"""Freeze the exact W18 bilinear partial-output diagnostic before running it."""

import json

import run


def main():
    path = run.HERE / "protocol.json"
    if path.exists():
        raise FileExistsError("preserve first protocol")
    row = {"proposal_id": run.PROPOSAL_ID, "candidate_id": None,
           "curve_id": "EC1N131Ckb1h136f03e58c98",
           "field_modulus_exponents": [0, 1, 2, 13, 131],
           "pair_seed_space": "span(t^1,...,t^18)",
           "coordinate": "z=phi(raw pair sum)",
           "unknown_output_bits": run.K,
           "control_law": "first independently replayed positive pair; first saved uniform field control",
           "cases": ["pinned_positive", "positive_partial", "field_control_partial"],
           "solver_workers": 1, "solver_cap_seconds": run.SOLVER_CAP_SECONDS,
           "parent_cap_seconds_per_case": run.PARENT_CAP_SECONDS,
           "rss_cap_bytes": run.RSS_CAP_BYTES,
           "source_sha256": {str(p): run.sha(p) for p in run.source_paths()}}
    path.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
    print(run.sha(path))


if __name__ == "__main__":
    main()
