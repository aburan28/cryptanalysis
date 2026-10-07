#!/usr/bin/env python3
"""Build and retain native selective mixed-atlas replay against Sage."""

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
PANELS = (("fixture.json", 64), ("selective-fixture.json", 256))


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
                        default=HERE / "native-selective-checks.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("native selective receipt exists; refusing overwrite")
    env = dict(os.environ, CARGO_TARGET_DIR=str(TARGET))
    runs = []
    failures = []
    build = run(["cargo", "build", "--offline", "--locked", "--release",
                 "--manifest-path", str(HERE / "Cargo.toml")], env=env)
    runs.append(build)
    if build["exit_code"] != 0:
        failures.append("offline release build failed")
    if not failures:
        baseline = run([str(BINARY), str(HERE / "fixture.json")])
        runs.append(baseline)
        if baseline["exit_code"] != 0 or '"verified":true' not in baseline["stdout"]:
            failures.append("original 64-case baseline regression failed")
        portfolio = run([str(BINARY), "--check-portfolio-fixture",
                         str(HERE / "fixture.json"),
                         str(HERE / "portfolio-seed-fixture.json"),
                         str(HERE / "portfolio-result.json")])
        runs.append(portfolio)
        if portfolio["exit_code"] != 0:
            failures.append("portfolio regression failed")
        scores = json.loads((HERE / "selective-mixed-result.json").read_text())
        expected = {panel["fixture"]: panel for panel in scores["panels"]}
        for name, count in PANELS:
            row = run([str(BINARY), "--check-selective-fixture",
                       str(HERE / name), str(HERE / "selective-seed-fixture.json"),
                       str(HERE / "selective-mixed-result.json")])
            runs.append(row)
            if row["exit_code"] != 0:
                failures.append(f"selective replay failed: {name}")
                continue
            try:
                observed = json.loads(row["stdout"])
                panel = expected[name]
                expected_seed_checks = sum(len(item["built_seed_ids"])
                                           for item in panel["rows"])
                if not (observed["verified"] and observed["cases"] == count
                        and observed["output_checks"] == count
                        and observed["seed_checks"] == expected_seed_checks
                        and observed["selected_M_plus_S"] == panel["selective_total"]
                        and observed["peak_carry_norm"] <= 896):
                    failures.append(f"selective replay summary mismatch: {name}")
            except (KeyError, ValueError) as error:
                failures.append(f"selective replay parse error: {name}: {error}")
        bench = run([str(BINARY), "--check-selective-case",
                     str(HERE / "fixture.json"), "0"])
        runs.append(bench)
        if bench["exit_code"] != 0 or "verified=1" not in bench["stdout"]:
            failures.append("selective one-case handoff failed")
    files = [HERE / name for name in (
        "Cargo.toml", "Cargo.lock", "src/main.rs", "src/selective.rs",
        "SELECTIVE_NATIVE_PROTOCOL.md", "SELECTIVE_MIXED_PROTOCOL.md",
        "selective_mixed_atlas.py",
        "mixed_atlas_screen.py", "selective-mixed-result.json",
        "selective-seed-fixture.json", "selective-runtime-info.json",
        "selective-sage-replay.json", "make_selective_fixture.py",
        "make_selective_seed_fixture.py", "run_selective_native_checks.py",
        "fixture.json", "selective-fixture.json",
        "portfolio-seed-fixture.json", "portfolio-result.json")]
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
                      "selective_cases": sum(count for _, count in PANELS),
                      "failures": failures,
                      "receipt_sha256": sha(args.output)}, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
