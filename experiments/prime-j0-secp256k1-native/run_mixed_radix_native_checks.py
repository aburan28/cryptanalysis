#!/usr/bin/env python3
"""Retain build and raw native mixed-radix replay evidence."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
TARGET = Path(os.environ.get("CA_NATIVE_TARGET_DIR",
                             "/private/tmp/cryptanalysis-native-target"))
BINARY = TARGET / "release/prime-j0-secp256k1-native-replay"
PANELS = (("fixture.json", "selective-seed-fixture.json", 64),
          ("mixed-radix-fixture.json", "mixed-radix-seed-fixture.json", 256))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def run(command, env=None):
    result = subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                            text=True, check=False)
    return {"command": command, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=HERE / "native-mixed-radix-checks.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("native mixed-radix receipt exists; refusing overwrite")
    env = dict(os.environ, CARGO_TARGET_DIR=str(TARGET))
    runs = []
    failures = []
    build = run(["cargo", "build", "--offline", "--locked", "--release",
                 "--manifest-path", str(HERE / "Cargo.toml")], env=env)
    runs.append(build)
    if build["exit_code"] != 0:
        failures.append("offline release build failed")
    if not failures:
        control = run([str(BINARY), str(HERE / "fixture.json")])
        runs.append(control)
        if control["exit_code"] != 0 or '"verified":true' not in control["stdout"]:
            failures.append("original native 64-case regression failed")
        scores = json.loads((HERE / "mixed-radix-scalar-result.json").read_text())
        expected = {panel["fixture"]: panel for panel in scores["panels"]}
        for name, seed_name, count in PANELS:
            replay = run([str(BINARY), "--check-mixed-radix-fixture",
                          str(HERE / name), str(HERE / seed_name),
                          str(HERE / "mixed-radix-scalar-result.json")])
            runs.append(replay)
            if replay["exit_code"] != 0:
                failures.append(f"mixed-radix replay failed: {name}")
                continue
            try:
                observed = json.loads(replay["stdout"])
                panel = expected[name]
                if not (observed["verified"] and observed["cases"] == count
                        and observed["output_checks"] == count
                        and observed["radix_two_choices"] == panel["radix_two_choices"]
                        and observed["selected_M_plus_S"] == panel["selected_total"]
                        and observed["seed_checks"] >= 9 * panel["radix_two_choices"]):
                    failures.append(f"mixed-radix summary mismatch: {name}")
            except (KeyError, ValueError) as error:
                failures.append(f"mixed-radix parse error: {name}: {error}")
    files = [HERE / name for name in (
        "Cargo.toml", "Cargo.lock", "src/main.rs", "src/selective.rs",
        "src/mixed_radix.rs", "MIXED_RADIX_NATIVE_PROTOCOL.md",
        "MIXED_RADIX_SCALAR_PROTOCOL.md", "mixed_radix_scalar.py",
        "make_mixed_radix_fixture.py", "make_mixed_radix_seed_fixture.py",
        "run_mixed_radix_native_checks.py", "fixture.json",
        "mixed-radix-fixture.json", "mixed-radix-scalar-result.json",
        "mixed-radix-runtime-info.json", "mixed-radix-sage-replay.json",
        "selective-seed-fixture.json", "mixed-radix-seed-fixture.json")]
    files += [REPO / "suite/src/ct_bignum.rs",
              REPO / "suite/src/ecc/secp256k1_field.rs", BINARY]
    artifacts = {str(path.relative_to(REPO) if path.is_relative_to(REPO)
                     else path): sha(path) for path in files}
    rustc = run(["rustc", "--version"])
    receipt = {"schema": 1, "verified": not failures,
               "cpu_speedup_claim": None, "failures": failures,
               "artifacts_sha256": artifacts, "runs": runs,
               "compiler": rustc["stdout"].strip(),
               "host": {"system": platform.system(),
                        "machine": platform.machine(),
                        "release": platform.release()}}
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": not failures,
                      "mixed_radix_cases": sum(count for _, _, count in PANELS),
                      "failures": failures,
                      "receipt_sha256": sha(args.output)}, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
