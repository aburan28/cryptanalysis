#!/usr/bin/env python3
"""Rebuild the Lean audit and bind a radix-943 Pareto evidence receipt."""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE_COMMIT = "1ed06551d33421d395298b0416e612240ab21cba"
SOURCE_FILES = [
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs",
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
    "experiments/prime-j0-radix943-pareto-20261012/PROTOCOL.md",
    "experiments/prime-j0-radix943-pareto-20261012/holdout.py",
]
EVIDENCE_FILES = [
    "experiments/prime-j0-radix943-pareto-20261012/freeze.py",
    "experiments/prime-j0-radix943-pareto-20261012/Recoding.lean",
    "experiments/prime-j0-radix943-pareto-20261012/PROOF.md",
    "experiments/prime-j0-radix943-pareto-20261012/RESULT.md",
    "experiments/prime-j0-radix943-pareto-20261012/lean-toolchain",
    "experiments/prime-j0-radix943-pareto-20261012/lean-build.txt",
    "experiments/prime-j0-radix943-pareto-20261012/build.txt",
    "experiments/prime-j0-radix943-pareto-20261012/panel-test.txt",
    "experiments/prime-j0-radix943-pareto-20261012/holdout.json",
    "experiments/prime-j0-radix943-pareto-20261012/holdout-candidate.txt",
    "experiments/prime-j0-radix943-pareto-20261012/holdout-reference.txt",
    "experiments/prime-j0-radix943-pareto-20261012/cli-fixture.txt",
    "experiments/prime-j0-radix943-pareto-20261012/screen.py",
    "experiments/prime-j0-radix943-pareto-20261012/screen.json",
    "experiments/prime-j0-radix943-pareto-20261012/verify_cli.py",
    "experiments/prime-j0-radix943-pareto-20261012/verify.json",
    "experiments/prime-j0-pareto-tree-20261012/plans.bin",
    "experiments/prime-j0-pareto-tree-20261012/plans.py",
    "experiments/prime-j0-pareto-tree-20261012/ParetoCost.lean",
    "experiments/prime-j0-gauge-tree-20261012/GaugeTree.lean",
    "experiments/prime-j0-sector-digit-20261010/fresh-inputs.json",
    "experiments/prime-j0-secp256k1-native/radix943-screen-result.json",
    "experiments/prime-j0-secp256k1-native/radix943_screen.py",
    "experiments/prime-j0-secp256k1-native/unit_orbit_windows_screen.py",
    "experiments/prime-j0-secp256k1-native/tau6-comb13-bench-fixture.json",
    "experiments/prime-j0-secp256k1-native/Cargo.toml",
    "experiments/prime-j0-secp256k1-native/Cargo.lock",
    "experiments/prime-j0-secp256k1-native/target/release/eisenstein_fixed",
]
PROOF_MODULES = [
    "experiments/prime-j0-gauge-tree-20261012/GaugeTree.lean",
    "experiments/prime-j0-pareto-tree-20261012/ParetoCost.lean",
    "experiments/prime-j0-radix943-pareto-20261012/Recoding.lean",
]


def digest(path):
    return sha256((ROOT / path).read_bytes()).hexdigest()


def check_source_commit():
    head = subprocess.check_output(
        ["git", "rev-parse", SOURCE_COMMIT], cwd=ROOT, text=True
    ).strip()
    assert head == SOURCE_COMMIT
    subprocess.run(
        ["git", "diff", "--exit-code", SOURCE_COMMIT, "--", *SOURCE_FILES],
        cwd=ROOT, check=True, stdout=subprocess.DEVNULL,
    )


def build_proofs():
    env = dict(os.environ, ELAN_TOOLCHAIN="leanprover/lean4:v4.34.1")
    records = []
    for module in PROOF_MODULES:
        command = ["lean", module]
        result = subprocess.run(command, cwd=ROOT, env=env,
                                text=True, capture_output=True)
        records.append(f"$ ELAN_TOOLCHAIN={env['ELAN_TOOLCHAIN']} {' '.join(command)}\n"
                       + result.stdout + result.stderr
                       + f"exit_code={result.returncode}\n")
        if result.returncode:
            (HERE / "lean-build.txt").write_text("\n".join(records))
            raise SystemExit(result.returncode)
    (HERE / "lean-build.txt").write_text("\n".join(records))
    print("Lean modules=3 status=checked")


def receipt():
    check_source_commit()
    return {
        "schema": 1,
        "status": "verified_points_and_source_model",
        "source_commit_before_holdout": SOURCE_COMMIT,
        "lean_toolchain": "leanprover/lean4:v4.34.1",
        "source_sha256": {path: digest(path) for path in SOURCE_FILES},
        "evidence_sha256": {path: digest(path) for path in EVIDENCE_FILES},
        "design_cases": 4096,
        "holdout_cases": 512,
        "independent_fixture_cases": 129,
        "mode_173_holdout_field_products": 65786,
        "mode_174_holdout_field_products": 60522,
        "mode_174_retained_bytes": 127488664,
        "controlled_cpu_timing": None,
    }


def main():
    if "--proof" in sys.argv:
        build_proofs()
    else:
        data = (json.dumps(receipt(), sort_keys=True, indent=2) + "\n").encode()
        path = HERE / "receipt.json"
        if "--check" in sys.argv:
            assert path.read_bytes() == data
        else:
            path.write_bytes(data)
        print(f"receipt_sha256={sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
