#!/usr/bin/env python3
"""Freeze evaluation of extracted equations on fresh exact N41 rows."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "evaluation_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first evaluation protocol")
    extraction = json.loads((HERE / "equations.json").read_text())
    control = json.loads((HERE / "extract_control.json").read_text())
    holdout = json.loads((HERE / "holdout_production.json").read_text())
    if (control["status"] != "EXIT_SUCCESS" or
            extraction["status"] != "EXTRACTED_EIGHT_RREF_EQUATIONS" or
            holdout["status"] != "EXACT_UNSEEN_ROWS_WRITTEN" or
            holdout["rows"] != 50000):
        raise ValueError("frozen extraction or holdout missing")
    protocol = {
        "status": "FROZEN", "kind": "n41_full_xy_cubic_fresh_holdout_evaluation",
        "proposal_id": "Q20261009231000", "candidate_id": None,
        "holdout_rows": 50000, "equations": 8,
        "decision_rule": "Count exact violations for each of eight RREF null equations on all 50000 unseen exact four-column-distinct sums. A violation rejects an equation as universal.",
        "input_sha256": {name: digest(HERE / name) for name in
                         ("protocol.json", "rank.json", "equations.json",
                          "extract_control.json", "holdout.bin",
                          "holdout_production.json", "holdout_protocol.json")},
        "source_sha256": digest(HERE / "evaluate.py"),
        "claim_boundary": "held-out validation of coordinate-identity multiples only; no measured public-target pruning until residual evaluation",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": digest(output)}))


if __name__ == "__main__":
    main()
