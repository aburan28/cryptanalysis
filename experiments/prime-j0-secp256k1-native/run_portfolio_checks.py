#!/usr/bin/env python3
"""Retain native bounded-carry portfolio replay against Sage fixtures."""

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
PANELS = (("fixture.json", 64), ("edge-fixture.json", 30),
          ("linked-fresh-fixture.json", 256), ("portfolio-fixture.json", 256))


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
                        default=HERE / "native-portfolio-checks.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("portfolio receipt exists; refusing overwrite")
    files = [HERE / name for name in (
        "Cargo.toml", "Cargo.lock", "src/main.rs",
        "PORTFOLIO_PROTOCOL.md", "atlas_portfolio.py",
        "portfolio-result.json", "portfolio-seed-fixture.json",
        "portfolio-runtime-info.json", "make_portfolio_fixture.py",
        "make_portfolio_seed_fixture.py", "run_portfolio_checks.py",
        "fixture.json", "edge-fixture.json",
        "linked-fresh-fixture.json", "portfolio-fixture.json")]
    files += [REPO / "suite/src/ct_bignum.rs",
              REPO / "suite/src/ecc/secp256k1_field.rs", BINARY]
    artifacts = {str(path.relative_to(REPO) if path.is_relative_to(REPO)
                     else path): sha(path) for path in files}
    scores = json.loads((HERE / "portfolio-result.json").read_text())
    expected = {panel["fixture"]: panel for panel in scores["panels"]}
    runs = []
    baseline = run([str(BINARY), str(HERE / "fixture.json")])
    runs.append(baseline)
    assert baseline["exit_code"] == 0, baseline["stderr"]
    assert json.loads(baseline["stdout"])["verified"] is True
    for name, count in PANELS:
        row = run([str(BINARY), "--check-portfolio-fixture",
                   str(HERE / name), str(HERE / "portfolio-seed-fixture.json"),
                   str(HERE / "portfolio-result.json")])
        runs.append(row)
        assert row["exit_code"] == 0, row["stderr"]
        result = json.loads(row["stdout"])
        assert result["verified"] and result["cases"] == count
        assert result["digit_stream_checks"] == 3 * count
        assert result["seed_checks"] == 9 * count
        assert result["output_checks"] == count
        assert result["peak_carry_norm"] <= 896
        if name in expected:
            panel = expected[name]
            assert result["selected_M_plus_S"] == panel["selected_total"]
            assert result["choices"] == [panel["choice_counts"][key]
                                         for key in ("original", "two_orbit",
                                                     "three_orbit")]
            assert result["active_carry_steps"] == panel["active_steps"]
    bench = run([str(BINARY), "--check-benchmark-case", "portfolio",
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
    print(json.dumps({"verified": True,
                      "portfolio_cases": sum(count for _, count in PANELS),
                      "receipt_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
