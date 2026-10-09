#!/usr/bin/env python3
"""Freeze the corrected four-column rank experiment before execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "protocol_v2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("preserve first corrected protocol")
    old = json.loads((HERE / "protocol.json").read_text())
    first = json.loads((HERE / "result.json").read_text())
    if first["status"] != "FULL_MIXED_CUBIC_RANK" or first["rank"] != 13599:
        raise ValueError("initial unrestricted screen changed")
    inputs = {**old["inputs"], "protocol_v1": str(HERE / "protocol.json"),
              "result_v1": str(HERE / "result.json")}
    decoded = json.loads(Path(inputs["decoded_rows"]).read_text())
    holdout = json.loads(Path(inputs["holdout_rows"]).read_text())
    unique = {tuple(row["pair_state_indices"][-2:])
              for source in (decoded["rows"], holdout["rows"])
              for row in source}
    protocol = {
        "kind": "n41_two_pair_distinct_column_mixed_cubic_rank_v2",
        "status": "FROZEN", "proposal_id": "Q20261009230200",
        "candidate_id": None, "run_id": None,
        "curve_id": old["curve_id"], "public_target_q": old["public_target_q"],
        "pair_rotations": old["pair_rotations"], "target_count": 1,
        "inputs": inputs,
        "input_sha256": {name: sha(Path(path)) for name, path in inputs.items()},
        "source_sha256": {"screen_v1": sha(HERE / "screen.py"),
                          "screen_v2": sha(HERE / "screen_v2.py"),
                          "freeze_v2": sha(Path(__file__))},
        "feature_count": 13599,
        "feature_order": old["feature_order"],
        "unique_source_index_pairs": len(unique),
        "extra_seed": 202610092302,
        "limits": {"wall_seconds": 300, "rss_bytes": 4294967296,
                   "max_extra_draws": 100000, "workers": 1},
        "decision_rule": "Only four-column-distinct source and extra rows enter rank. Full rank is an exact finite witness ruling out every universal equation in the fixed mixed-cubic family on that domain.",
        "claim_boundary": "corrected finite-row rank witness for a fixed N41 two-pair mixed-cubic family; no measured N131 relation or complete IC timing",
    }
    with OUTPUT.open("x") as stream:
        json.dump(protocol, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": protocol["status"],
                      "unique_source_index_pairs": len(unique),
                      "screen_v2_sha256": protocol["source_sha256"]["screen_v2"]}, sort_keys=True))


if __name__ == "__main__":
    main()
