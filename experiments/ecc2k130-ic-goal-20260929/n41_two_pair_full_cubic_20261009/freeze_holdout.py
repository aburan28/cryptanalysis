#!/usr/bin/env python3
"""Freeze held-out exact pair-pair row generation."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "holdout_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first held-out protocol")
    prior = json.loads((HERE / "extract_protocol.json").read_text())
    original = json.loads((HERE / "protocol.json").read_text())
    protocol = {
        "status": "FROZEN", "kind": "n41_two_pair_fresh_exact_holdout",
        "proposal_id": original["proposal_id"], "candidate_id": None,
        "random_seed": prior["holdout_seed"],
        "row_count": prior["holdout_rows"], "max_draws": prior["holdout_max_draws"],
        "selection_rule": "draw independent pair-domain indices with the frozen PRNG; skip every training or previous holdout index pair and all repeated-column pairs; accept first 50000 exact sums",
        "input_sha256": {name: digest(HERE / name) for name in
                         ("protocol.json", "extract_protocol.json", "rows.bin",
                          "produce.py")},
        "source_sha256": {name: digest(HERE / name) for name in
                          ("holdout.py", "freeze_holdout.py")},
        "claim_boundary": "fresh exact holdout for candidate equation validation; no inference of target-pruning rate before target residual evaluation",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": digest(output)}))


if __name__ == "__main__":
    main()
