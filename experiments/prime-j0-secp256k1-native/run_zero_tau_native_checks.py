#!/usr/bin/env python3
"""Retain build and raw native zero-tau-rule replay evidence."""

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
          ("zero-tau-fixture.json", "zero-tau-seed-fixture.json", 256))


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
                        default=HERE / "native-zero-tau-checks.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("native zero-tau receipt exists; refusing overwrite")
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
        scores = json.loads((HERE / "zero-tau-result.json").read_text())
        expected = {panel["fixture"]: panel for panel in scores["panels"]}
        for name, seed_name, count in PANELS:
            actions = run([str(BINARY), "--check-zero-tau-actions",
                           str(HERE / name),
                           str(HERE / "zero-tau-action-fingerprints.json")])
            runs.append(actions)
            if actions["exit_code"] != 0:
                failures.append(f"action fingerprint replay failed: {name}")
            replay = run([str(BINARY), "--check-zero-tau-fixture",
                          str(HERE / name), str(HERE / seed_name),
                          str(HERE / "zero-tau-result.json")])
            runs.append(replay)
            if replay["exit_code"] != 0:
                failures.append(f"zero-tau replay failed: {name}")
                continue
            try:
                observed = json.loads(replay["stdout"])
                panel = expected[name]
                if not (observed["verified"] and observed["cases"] == count
                        and observed["output_checks"] == count
                        and observed["zero_tau_choices"] == panel["zero_tau_choices"]
                        and observed["selected_M_plus_S"] == panel["selected_total"]
                        and observed["seed_checks"] >= 9 * panel["zero_tau_choices"]
                        and observed["exceptional_cached_adds"] == 0):
                    failures.append(f"zero-tau summary mismatch: {name}")
            except (KeyError, ValueError) as error:
                failures.append(f"zero-tau parse error: {name}: {error}")
        fresh = expected["zero-tau-fixture.json"]
        for arm in ("selective", "zero_tau"):
            index = next(row["index"] for row in fresh["rows"] if row["selected"] == arm)
            reference = run([str(BINARY), "--check-mixed-radix-case",
                             str(HERE / "zero-tau-fixture.json"), str(index)])
            candidate = run([str(BINARY), "--check-zero-tau-case",
                             str(HERE / "zero-tau-fixture.json"), str(index)])
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
        "src/mixed_radix.rs", "ZERO_TAU_RULE_PROTOCOL.md",
        "ZERO_TAU_NATIVE_PROTOCOL.md", "screen_radix_policy.py",
        "zero_tau_rule.py", "make_zero_tau_fixture.py",
        "make_zero_tau_seed_fixture.py",
        "make_zero_tau_action_fingerprints.py",
        "zero-tau-action-fingerprints.json",
        "run_zero_tau_native_checks.py", "fixture.json",
        "zero-tau-fixture.json", "zero-tau-result.json",
        "zero-tau-runtime-info.json", "zero-tau-sage-replay.json",
        "selective-seed-fixture.json", "zero-tau-seed-fixture.json")]
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
                      "zero_tau_cases": sum(count for _, _, count in PANELS),
                      "failures": failures,
                      "receipt_sha256": sha(args.output)}, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
