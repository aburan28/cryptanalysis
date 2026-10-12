#!/usr/bin/env python3
"""Retain field-test, release-replay, and paired fast-inverse handoff evidence."""

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
PANELS = (("fixture.json", 64), ("coset-fixture.json", 256))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def run(command, env=None):
    result = subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                            text=True, check=False)
    return {"command": command, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def fields(output):
    return dict(token.split("=", 1) for token in output.split() if "=" in token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=HERE / "native-fastinv-checks.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("fast-inverse receipt exists; refusing overwrite")
    env = dict(os.environ, CARGO_TARGET_DIR=str(TARGET))
    runs = []
    failures = []
    field = run(["cargo", "test", "--offline", "--locked",
                 "--manifest-path", str(HERE / "Cargo.toml"),
                 "inversion_chain_matches_ladder_and_field_identity"], env=env)
    runs.append(field)
    if field["exit_code"] or "1 passed" not in field["stdout"]:
        failures.append("field inversion test failed")
    build = run(["cargo", "build", "--offline", "--locked", "--release",
                 "--manifest-path", str(HERE / "Cargo.toml")], env=env)
    runs.append(build)
    if build["exit_code"]:
        failures.append("offline release build failed")
    if not failures:
        for name, count in PANELS:
            replay = run([str(BINARY), "--check-coset-fastinv-fixture",
                          str(HERE / name)])
            runs.append(replay)
            try:
                observed = json.loads(replay["stdout"])
                if not (replay["exit_code"] == 0 and observed["verified"]
                        and observed["cases"] == count
                        and observed["fast_inverse_checks"] == count
                        and observed["scalar_output_checks"] == count):
                    failures.append(f"scalar replay failed: {name}")
            except (KeyError, ValueError) as error:
                failures.append(f"scalar replay parse failed: {name}: {error}")
        scores = json.loads((HERE / "coset-result.json").read_bytes())
        fresh = next(panel for panel in scores["panels"]
                     if panel["fixture"] == "coset-fixture.json")
        for arm in range(4):
            index = next(row["index"] for row in fresh["rows"]
                         if row["selected_path_index"] == arm)
            left = run([str(BINARY), "--check-coset-case",
                        str(HERE / "coset-fixture.json"), str(index)])
            right = run([str(BINARY), "--check-coset-fastinv-case",
                         str(HERE / "coset-fixture.json"), str(index)])
            runs.extend((left, right))
            if left["exit_code"] or right["exit_code"]:
                failures.append(f"paired case failed: {index}")
                continue
            a, b = fields(left["stdout"]), fields(right["stdout"])
            if any(a.get(key) != b.get(key) for key in
                   ("curve", "base_x", "base_y", "scalar", "point",
                    "choice", "source_M_plus_S")) or b.get("verified") != "1":
                failures.append(f"paired case mismatch: {index}")
    artifacts = [HERE / name for name in (
        "Cargo.toml", "Cargo.lock", "src/main.rs", "src/coset.rs",
        "src/mixed_radix.rs", "src/selective.rs",
        "FAST_INVERSION_PROTOCOL.md", "run_fastinv_native_checks.py",
        "fixture.json", "coset-fixture.json", "coset-result.json")]
    artifacts += [REPO / "suite/src/ct_bignum.rs",
                  REPO / "suite/src/ecc/secp256k1_field.rs", BINARY]
    receipt = {"schema": 1, "verified": not failures,
               "cpu_speedup_claim": None, "failures": failures,
               "artifacts_sha256": {
                   str(path.relative_to(REPO) if path.is_relative_to(REPO)
                       else path): sha(path) for path in artifacts},
               "runs": runs,
               "compiler": run(["rustc", "--version"])["stdout"].strip(),
               "host": {"system": platform.system(),
                        "machine": platform.machine(),
                        "release": platform.release()}}
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": not failures,
                      "scalar_cases": sum(count for _, count in PANELS),
                      "failures": failures,
                      "receipt_sha256": sha(args.output)}, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
