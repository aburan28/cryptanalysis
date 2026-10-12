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
            actions = run([str(BINARY), "--check-mixed-radix-actions",
                           str(HERE / name),
                           str(HERE / "mixed-radix-action-fingerprints.json")])
            runs.append(actions)
            if actions["exit_code"] != 0:
                failures.append(f"action fingerprint replay failed: {name}")
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
        for index, arm in ((0, "selective"), (1, "radix_two")):
            reference = run([str(BINARY), "--check-selective-case",
                             str(HERE / "mixed-radix-fixture.json"), str(index)])
            candidate = run([str(BINARY), "--check-mixed-radix-case",
                             str(HERE / "mixed-radix-fixture.json"), str(index)])
            runs.extend((reference, candidate))
            if (reference["exit_code"] != 0 or candidate["exit_code"] != 0
                    or "verified=1" not in reference["stdout"]
                    or f"arm={arm}" not in candidate["stdout"]
                    or "verified=1" not in candidate["stdout"]):
                failures.append(f"paired one-case handoff failed: {index}")
            else:
                def fields(output):
                    return dict(token.split("=", 1) for token in output.split()
                                if "=" in token)
                left = fields(reference["stdout"])
                right = fields(candidate["stdout"])
                if any(left[key] != right[key] for key in
                       ("curve", "base_x", "base_y", "scalar", "point")):
                    failures.append(f"paired one-case fields differ: {index}")
    files = [HERE / name for name in (
        "Cargo.toml", "Cargo.lock", "src/main.rs", "src/selective.rs",
        "src/mixed_radix.rs", "MIXED_RADIX_NATIVE_PROTOCOL.md",
        "MIXED_RADIX_SCALAR_PROTOCOL.md", "mixed_radix_scalar.py",
        "make_mixed_radix_action_fingerprints.py",
        "make_mixed_radix_manifest.py",
        "mixed-radix-action-fingerprints.json",
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
