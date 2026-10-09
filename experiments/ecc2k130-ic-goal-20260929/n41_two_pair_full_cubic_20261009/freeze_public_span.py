#!/usr/bin/env python3
"""Freeze coordinate-span replay for the public target residuals."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "public_span_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first public-span protocol")
    combined = json.loads((HERE / "combined_coordinate_rank.json").read_text())
    public = json.loads((HERE / "public_residual_probe.json").read_text())
    if (combined["status"] != "COMPLETE_COMBINED_RANK" or
            combined["novel_rank_from_subgroup"] != 0 or
            public["valid_prefix_residuals"] != 8192):
        raise ValueError("combined subgroup or public probe prerequisite changed")
    protocol = {
        "status": "FROZEN", "kind": "n41_full_cubic_public_residual_coordinate_span",
        "proposal_id": "Q20261009231000", "candidate_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "decision_rule": "Build the independent low-pivot coordinate row span of all 80000 training pair sums and append the exact 8192 public residuals in the frozen prefix order. Zero novel rank makes every coordinate-only training null equation vanish on these residuals, so the entire full-cubic training nullspace gives zero rejection for every seed assignment there.",
        "limits": {"workers": 1, "wall_seconds": 180, "rss_bytes": 4294967296},
        "input_sha256": {name: digest(HERE / name) for name in
                         ("protocol.json", "rows.bin", "combined_coordinate_rank.py",
                          "combined_coordinate_rank.json", "public_probe_protocol.json",
                          "public_residual_probe.json", "produce.py")},
        "source_sha256": digest(HERE / "public_coordinate_span.py"),
        "claim_boundary": "exact zero-pruning certificate on 8192 frozen public residuals for the full tested feature family; not a full-prefix-domain proof",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": digest(output)}))


if __name__ == "__main__":
    main()
