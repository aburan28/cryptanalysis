#!/usr/bin/env python3
"""Replay the prior carry-aware selector on the same new holdout panel."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prime-j0-carry-aware-v2-20261011/screen.py"
SPEC = importlib.util.spec_from_file_location("swap_carry_comparison", SOURCE)
carry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(carry)


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    cover_raw, assignments, seeds = carry.load_cover()
    canonical, nodes, _, _ = carry.dual.parent.full_classes()
    node_index, providers = carry.offer_index(seeds, canonical, nodes)
    options = carry.make_options(canonical, node_index, providers)
    input_raw = (HERE / "holdout-inputs.json").read_bytes()
    scalars = [int(value, 16) for value in
               json.loads(input_raw)["scalars_hex"]]
    assert len(scalars) == 4096
    counts = {"priority_active": 0, "carry_active": 0,
              "priority_rho_terms": 0, "carry_rho_terms": 0,
              "offers_examined": 0, "terminal_fallbacks": 0}
    for scalar in scalars:
        fixed, selected, examined, _, fallback = carry.replay(
            scalar, assignments, seeds, canonical, node_index, options, 2)
        counts["priority_active"] += fixed[2] != 0
        counts["carry_active"] += selected[2] != 0
        counts["priority_rho_terms"] += fixed[2]
        counts["carry_rho_terms"] += selected[2]
        counts["offers_examined"] += examined
        counts["terminal_fallbacks"] += fallback
    screen = json.loads((HERE / "holdout-screen.json").read_bytes())
    assert counts["priority_active"] == screen["priority"]["active_rho"]
    assert counts["priority_rho_terms"] == screen["priority"]["rho_terms"]
    result = {"schema": 1, "status": "retrospective_same_panel_diagnostic",
              "cases": len(scalars), "beam_width": 2,
              "counts": counts,
              "swapped_fixed_active": screen["swapped"]["active_rho"],
              "swapped_fixed_rho_terms": screen["swapped"]["rho_terms"],
              "input_sha256": digest(input_raw),
              "old_cover_sha256": digest(cover_raw),
              "swapped_cover_sha256": screen["swapped_cover_sha256"],
              "prior_selector_sha256": digest(SOURCE.read_bytes()),
              "source_sha256": digest(Path(__file__).read_bytes())}
    (HERE / "comparison.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
