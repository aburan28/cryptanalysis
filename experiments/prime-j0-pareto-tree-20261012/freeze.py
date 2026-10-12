#!/usr/bin/env python3
"""Bind the exact stage artifacts and local release replay by SHA-256."""

from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

ARTIFACTS = {
    "protocol": "experiments/prime-j0-pareto-tree-20261012/PROTOCOL.md",
    "result": "experiments/prime-j0-pareto-tree-20261012/RESULT.md",
    "proof": "experiments/prime-j0-pareto-tree-20261012/PROOF.md",
    "plan_generator": "experiments/prime-j0-pareto-tree-20261012/plans.py",
    "plan_table": "experiments/prime-j0-pareto-tree-20261012/plans.bin",
    "plan_screen": "experiments/prime-j0-pareto-tree-20261012/screen.json",
    "lean_source": "experiments/prime-j0-pareto-tree-20261012/ParetoCost.lean",
    "lean_build": "experiments/prime-j0-pareto-tree-20261012/lean-build.txt",
    "panel_test": "experiments/prime-j0-pareto-tree-20261012/panel-test.txt",
    "build_log": "experiments/prime-j0-pareto-tree-20261012/build.txt",
    "cli_replay": "experiments/prime-j0-pareto-tree-20261012/cli-fixture.txt",
    "cli_verifier": "experiments/prime-j0-pareto-tree-20261012/verify_cli.py",
    "receipt_generator": "experiments/prime-j0-pareto-tree-20261012/freeze.py",
    "kernel_source": "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
    "cli_source": "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs",
    "frozen_panel": "experiments/prime-j0-sector-digit-20261010/fresh-inputs.json",
    "independent_fixture": "experiments/prime-j0-secp256k1-native/tau6-comb13-bench-fixture.json",
    "inherited_tree_proof": "experiments/prime-j0-gauge-tree-20261012/GaugeTree.lean",
    "release_binary": "experiments/prime-j0-secp256k1-native/target/release/eisenstein_fixed",
}


def main():
    records = {}
    for label, relative in sorted(ARTIFACTS.items()):
        path = ROOT / relative
        data = path.read_bytes()
        records[label] = {"path": relative, "size": len(data),
                          "sha256": sha256(data).hexdigest()}
    receipt = {"schema": 1, "status": "verified_stage",
               "base_commit": "f8dcc6721b6886b7b3de396b3c6288649518b214",
               "format": 173, "artifacts": records}
    (HERE / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(f"bound {len(records)} artifacts")


if __name__ == "__main__":
    main()
