#!/usr/bin/env python3
"""Source-bound transfer check for the literal explicit-pair native method."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "q1448_pair_bloom/n131_transfer_gate.json"
PRIOR_SHA = "81d9383209eadfd8d5499afe76c31e76de9deaa8ed48e22a2abe9db70206ef11"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "transfer_gate.json"
    if output.exists():
        raise FileExistsError("preserve first transfer receipt")
    assert sha(PRIOR) == PRIOR_SHA
    prior = json.loads(PRIOR.read_text())
    search = json.loads((HERE / "native_search.json").read_text())
    assert prior["curve_id"] == "EC1N131Ckb1h136f03e58c98"
    assert search["status"] == "ONLINE_TIME_CAP"
    states = prior["n131_distinct_column_pair_states_per_domain_lower"]
    cap_bytes = 4 * 1024**3
    one_bit_bytes = (states + 7) // 8
    assert states == 34_448_654_064 and one_bit_bytes > cap_bytes
    report = {
        "kind": "n131_literal_explicit_pair_domain_transfer_gate",
        "status": "FAIL_N131_4GIB_EXPLICIT_STATE_MEMORY_GATE",
        "proposal_id": "Q20261008191400",
        "candidate_id": None,
        "run_id": None,
        "curve_id": prior["curve_id"],
        "n131_pair_states_per_domain_lower": states,
        "minimum_one_bit_per_state_bytes": one_bit_bytes,
        "memory_cap_bytes": cap_bytes,
        "one_bit_lower_bound_exceeds_cap_bytes": one_bit_bytes - cap_bytes,
        "pair_states_per_second_needed_for_one_domain_in_600s":
            f"{states/600:.3f}",
        "n41_public_search_residuals": search["residuals"],
        "n41_public_search_online_ns": search["online_ns"],
        "n41_sustained_residuals_per_second_exploratory":
            f"{search['residuals']*1_000_000_000/search['online_ns']:.3f}",
        "source_sha256": {
            "prior_n131_frontier": PRIOR_SHA,
            "n41_native_search": sha(HERE / "native_search.json"),
            "source": sha(Path(__file__)),
        },
        "claim_boundary": "The native source materializes each full exact pair-state list. Even an unrealistically compact one-bit-per-state explicit list for one N131 W18 domain exceeds 4 GiB, before coordinates, witnesses, indexes, the other domains, or target queries. This rejects this literal transfer only. It does not bound a streaming, symbolic, or target-adaptive generator. N41 timing is exploratory and is not used as an isolated N131 speed projection.",
    }
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(report["status"])


if __name__ == "__main__":
    main()
