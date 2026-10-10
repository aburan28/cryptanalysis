#!/usr/bin/env python3
"""Freeze the W18 fixed-sum partial-output panel before measuring it."""

import json

import run


def main():
    path = run.HERE / "protocol.json"
    if path.exists():
        raise FileExistsError("preserve first frozen protocol")
    protocol = {"proposal_id": run.PROPOSAL_ID, "candidate_id": None,
                "curve_id": "EC1N131Ckb1h136f03e58c98",
                "field_modulus_exponents": [0, 1, 2, 13, 131],
                "seed_space": "span(t^1,...,t^18)",
                "positive_law": "all distinct nonexceptional outputs grouped by 32 nonzero seed sums in saved pair oracle",
                "control_law": "same 64 frozen balanced-trace field controls per sum",
                "partial_output_free_bit_counts": list(run.K_VALUES),
                "policies": ["low contiguous", "greedy rank-minimizing monomial coordinate bits"],
                "greedy_tie_break": "smallest field bit index",
                "target_count": 0, "time_cap_ns": run.TIME_CAP_NS,
                "rss_cap_bytes": run.RSS_CAP_BYTES,
                "source_sha256": {str(p): run.sha(p) for p in run.source_paths()}}
    path.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(run.sha(path))


if __name__ == "__main__":
    main()
