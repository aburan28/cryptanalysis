#!/usr/bin/env python3
"""Retain paired native replay of ordinary and twinned linked-atlas seeds."""

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
PANELS = (("fixture.json", 64), ("linked-fresh-fixture.json", 256),
          ("edge-fixture.json", 30))


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
                        default=HERE / "native-linked-twin-checks.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("linked-twin receipt exists; refusing overwrite")
    env = dict(os.environ, CARGO_TARGET_DIR=str(TARGET))
    runs = []
    failures = []
    build = run(["cargo", "build", "--offline", "--locked", "--release",
                 "--manifest-path", str(HERE / "Cargo.toml")], env=env)
    runs.append(build)
    if build["exit_code"]:
        failures.append("offline release build failed")
    panels = []
    if not failures:
        regression = run([str(BINARY), str(HERE / "fixture.json")])
        runs.append(regression)
        if regression["exit_code"] or '"verified":true' not in regression["stdout"]:
            failures.append("original scalar regression failed")
        for name, count in PANELS:
            pair = []
            for mode in ("linked", "linked-twin"):
                command = [str(BINARY), f"--check-{mode}-fixture",
                           str(HERE / name), str(HERE / "linked-seed-fixture.json")]
                observed = run(command)
                runs.append(observed)
                if observed["exit_code"]:
                    failures.append(f"{mode} replay failed: {name}")
                    break
                try:
                    summary = json.loads(observed["stdout"])
                    if not (summary["verified"] and summary["cases"] == count
                            and summary["seed_checks"] == 9 * count
                            and summary["output_checks"] == count
                            and summary["exceptional_cached_adds"] == 0):
                        failures.append(f"{mode} summary mismatch: {name}")
                    pair.append(summary)
                except (KeyError, ValueError) as error:
                    failures.append(f"{mode} parse error: {name}: {error}")
                    break
            if len(pair) == 2:
                if pair[0]["source_M_plus_S"] - pair[1]["source_M_plus_S"] != 5 * count:
                    failures.append(f"five-unit preparation saving failed: {name}")
                panels.append({"fixture": name, "cases": count,
                               "linked_M_plus_S": pair[0]["source_M_plus_S"],
                               "twin_M_plus_S": pair[1]["source_M_plus_S"]})
        path = HERE / "linked-fresh-fixture.json"
        reference = run([str(BINARY), "--check-benchmark-case", "linked_atlas",
                         str(path), "0"])
        candidate = run([str(BINARY), "--check-benchmark-case", "linked_twin",
                         str(path), "0"])
        runs.extend((reference, candidate))
        if reference["exit_code"] or candidate["exit_code"]:
            failures.append("paired single-case handoff failed")
        else:
            left, right = fields(reference["stdout"]), fields(candidate["stdout"])
            if any(left.get(key) != right.get(key) for key in
                   ("curve", "base_x", "base_y", "scalar", "point")) or \
               right.get("verified") != "1":
                failures.append("paired single-case fields differ")
    artifacts = [HERE / name for name in (
        "Cargo.toml", "Cargo.lock", "src/main.rs", "src/selective.rs",
        "src/mixed_radix.rs", "src/coset.rs",
        "TWIN_ORBIT_SEEDS_PROTOCOL.md", "run_linked_twin_checks.py",
        "fixture.json", "linked-fresh-fixture.json", "edge-fixture.json",
        "linked-seed-fixture.json")]
    artifacts += [REPO / "suite/src/ct_bignum.rs",
                  REPO / "suite/src/ecc/secp256k1_field.rs", BINARY]
    receipt = {"schema": 1, "verified": not failures,
               "cpu_speedup_claim": None, "academic_novelty_claim": None,
               "failures": failures, "panels": panels, "runs": runs,
               "artifacts_sha256": {
                   str(path.relative_to(REPO) if path.is_relative_to(REPO)
                       else path): sha(path) for path in artifacts},
               "compiler": run(["rustc", "--version"])["stdout"].strip(),
               "host": {"system": platform.system(),
                        "machine": platform.machine(),
                        "release": platform.release()}}
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": not failures, "panels": panels,
                      "failures": failures,
                      "receipt_sha256": sha(args.output)}, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
