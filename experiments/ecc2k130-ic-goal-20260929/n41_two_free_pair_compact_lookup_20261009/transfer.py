#!/usr/bin/env python3
"""Source-bound N131 W18 transfer check for explicit pair-state vectors."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PRIOR = GOAL / "q1448_pair_bloom/n131_transfer_gate.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "transfer_gate.json"
    if output.exists():
        raise FileExistsError("preserve first transfer receipt")
    protocol = json.loads((HERE / "protocol_v2.json").read_text())
    source = (HERE / "native_compact.cpp").read_text()
    prior = json.loads(PRIOR.read_text())
    assert digest(HERE / "native_compact.cpp") == protocol["source_sha256"]
    assert "std::vector<PairState> out;" in source
    assert "out.push_back({sum, uint8_t(i), uint8_t(j)});" in source
    assert "for (int i = 0; i < 4; ++i) pairs[i] = make_pairs(seeds[i]);" in source
    assert prior["curve_id"] == "EC1N131Ckb1h136f03e58c98"
    states = prior["n131_distinct_column_pair_states_per_domain_lower"]
    assert states == 34_448_654_064
    cap = 4 * 1024**3
    minimum_bytes = (states + 7) // 8
    assert minimum_bytes > cap
    report = {
        "kind": "n41_compact_lookup_explicit_pair_n131_transfer_gate",
        "status": "FAIL_N131_EXPLICIT_PAIR_MEMORY_GATE",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "n131_curve_id": prior["curve_id"],
        "pair_states_per_domain_lower": states,
        "one_bit_per_state_bytes_lower": minimum_bytes,
        "memory_cap_bytes": cap,
        "one_domain_excess_bytes_lower": minimum_bytes - cap,
        "four_domain_one_bit_bytes_lower": 4 * minimum_bytes,
        "one_domain_states_per_second_needed_for_600s_lower":
            (states + 599) // 600,
        "source_path": "native_compact.cpp:make_pairs",
        "source_sha256": digest(HERE / "native_compact.cpp"),
        "prior_frontier_sha256": digest(PRIOR),
        "claim_boundary": "The native source materializes every exact pair state in each of four vectors. Even one bit per distinct-column state exceeds 4 GiB for one N131 W18 domain; actual PairState objects are larger. This rejects the literal source transfer, not symbolic generation or target-adaptive elimination.",
    }
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(report["status"])


if __name__ == "__main__":
    main()
