#!/usr/bin/env python3
"""Freeze unpinned prefix sampling against the public N41 point."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "public_probe_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first public probe protocol")
    validation = json.loads((HERE / "holdout_validation.json").read_text())
    if not validation["all_selected_equations_hold"] or validation["checked_rows"] != 50000:
        raise ValueError("fresh exact held-out validation changed")
    protocol = {
        "status": "FROZEN", "kind": "n41_full_xy_cubic_public_residual_probe",
        "proposal_id": "Q20261009231000", "candidate_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "public_target_q": [1458168294740, 1672312028033],
        "prefix_rotations": [0, 10], "residual_count": 8192,
        "random_seed": 20261009231004, "max_draws": 16000,
        "decision_rule": "For exact distinct-column prefix pairs, compute Q-prefix and evaluate the common coordinate factor of the eight shortest null equations. A zero factor makes all eight equations zero for every seed assignment.",
        "input_sha256": {name: digest(HERE / name) for name in
                         ("protocol.json", "equations.json", "holdout_validation.json",
                          "produce.py")},
        "source_sha256": digest(HERE / "public_residual_probe.py"),
        "claim_boundary": "selected eight equations only; sampled public-target residuals, not full-domain proof or end-to-end relation generation",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": digest(output)}))


if __name__ == "__main__":
    main()
