#!/usr/bin/env python3
"""Build the pinned Lean theorem and verify its source/evidence hashes."""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULE = "experiments/prime-j0-radix943-termination-20261012/Termination.lean"
FILES = [
    "experiments/prime-j0-radix943-termination-20261012/check.py",
    MODULE,
    "experiments/prime-j0-radix943-termination-20261012/lean-toolchain",
    "experiments/prime-j0-radix943-termination-20261012/PROOF.md",
    "experiments/prime-j0-radix943-termination-20261012/RESULT.md",
    "experiments/prime-j0-radix943-termination-20261012/lean-build.txt",
    "experiments/prime-j0-radix943-pareto-20261012/Recoding.lean",
    "experiments/prime-j0-radix943-pareto-20261012/PROTOCOL.md",
    "experiments/prime-j0-secp256k1-native/radix943_screen.py",
    "experiments/prime-j0-secp256k1-native/radix943-screen-result.json",
]


def digest(path):
    return sha256((ROOT / path).read_bytes()).hexdigest()


def build():
    env = dict(os.environ, ELAN_TOOLCHAIN="leanprover/lean4:v4.34.1")
    cmd = ["lean", MODULE]
    result = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    output = result.stdout + result.stderr
    (HERE / "lean-build.txt").write_text(
        f"$ ELAN_TOOLCHAIN={env['ELAN_TOOLCHAIN']} {' '.join(cmd)}\n"
        + output + f"exit_code={result.returncode}\n"
    )
    if result.returncode:
        raise SystemExit(result.returncode)
    assert "'PrimeJ0Radix943Termination.thirteen_steps_terminate' depends on axioms:" in output
    assert "sorryAx" not in output
    print("Lean theorem and axiom audit checked")


def receipt():
    return {
        "schema": 1,
        "status": "lean_termination_implication_checked",
        "toolchain": "leanprover/lean4:v4.34.1",
        "radix": 943,
        "windows": 13,
        "geometric_inequality_left": "651350628440358224124238101989970066222256118655262501573337863827367383247201",
        "geometric_inequality_right": "652266788196859845275623226369043785643589744678153169412500491536255330555747",
        "sha256": {name: digest(name) for name in FILES},
    }


def main():
    if "--proof" in sys.argv:
        build()
    else:
        raw = (json.dumps(receipt(), indent=2, sort_keys=True) + "\n").encode()
        path = HERE / "receipt.json"
        if "--check" in sys.argv:
            assert path.read_bytes() == raw
        else:
            path.write_bytes(raw)
        print(f"receipt_sha256={sha256(raw).hexdigest()}")


if __name__ == "__main__":
    main()
