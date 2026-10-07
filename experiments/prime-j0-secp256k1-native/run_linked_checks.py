#!/usr/bin/env python3
"""Retain native linked-atlas correctness against frozen Sage fixtures."""

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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command):
    result = subprocess.run(command, cwd=REPO, capture_output=True,
                            text=True, check=False)
    return {"command": command, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=HERE / "native-linked-checks.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("native linked receipt exists; refusing overwrite")
    paths = [HERE / name for name in (
        "Cargo.toml", "Cargo.lock", "src/main.rs",
        "LINKED_ATLAS_PROTOCOL.md", "linked_atlas.py",
        "linked-atlas-result.json", "linked-seed-fixture.json",
        "alternate-seed-fixture.json",
        "linked-runtime-info.json", "fixture.json",
        "edge-fixture.json", "linked-fresh-fixture.json", "bench-workload.json",
        "run_linked_checks.py")]
    paths += [REPO / "suite/src/ct_bignum.rs",
              REPO / "suite/src/ecc/secp256k1_field.rs", BINARY]
    artifacts = {str(path.relative_to(REPO) if path.is_relative_to(REPO)
                     else path): sha(path) for path in paths}
    score = json.loads((HERE / "linked-atlas-result.json").read_text())
    expected_cost = {panel["fixture"]: panel["candidate_total"]
                     for panel in score["panels"]}
    runs = []
    baseline = run([str(BINARY), str(HERE / "fixture.json")])
    runs.append(baseline)
    assert baseline["exit_code"] == 0
    assert json.loads(baseline["stdout"])["verified"] is True
    old_joint = run([str(BINARY), "--check-alternate-fixture",
                     str(HERE / "fixture.json"),
                     str(HERE / "alternate-seed-fixture.json")])
    runs.append(old_joint)
    assert old_joint["exit_code"] == 0, old_joint["stderr"]
    assert json.loads(old_joint["stdout"])["source_M_plus_S"] == 88313
    for filename, count in (("fixture.json", 64),
                            ("edge-fixture.json", 30),
                            ("linked-fresh-fixture.json", 256)):
        row = run([str(BINARY), "--check-linked-fixture",
                   str(HERE / filename),
                   str(HERE / "linked-seed-fixture.json")])
        runs.append(row)
        assert row["exit_code"] == 0, row["stderr"]
        result = json.loads(row["stdout"])
        assert result["verified"] and result["cases"] == count
        assert result["seed_checks"] == 9 * count
        assert result["output_checks"] == count
        if filename in expected_cost:
            assert result["source_M_plus_S"] == expected_cost[filename]
    bench = run([str(BINARY), "--check-benchmark-case", "linked_atlas",
                 str(HERE / "fixture.json"), "0"])
    runs.append(bench)
    assert bench["exit_code"] == 0, bench["stderr"]
    assert "verified=1" in bench["stdout"]
    rustc = run(["rustc", "--version"])
    receipt = {"schema": 1, "verified": True,
               "cpu_speedup_claim": None,
               "artifacts_sha256": artifacts, "runs": runs,
               "compiler": rustc["stdout"].strip(),
               "host": {"system": platform.system(),
                        "machine": platform.machine(),
                        "release": platform.release()}}
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "linked_cases": 350,
                      "linked_seed_checks": 3150,
                      "receipt_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
