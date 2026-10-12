#!/usr/bin/env python3
"""Retain build, four-stream replay, and native coset output evidence."""

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
                        default=HERE / "native-coset-checks.json")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("native coset receipt exists; refusing overwrite")
    runs = []
    failures = []
    env = dict(os.environ, CARGO_TARGET_DIR=str(TARGET))
    build = run(["cargo", "build", "--offline", "--locked", "--release",
                 "--manifest-path", str(HERE / "Cargo.toml")], env=env)
    runs.append(build)
    if build["exit_code"] != 0:
        failures.append("offline release build failed")
    if not failures:
        regression = run([str(BINARY), str(HERE / "fixture.json")])
        runs.append(regression)
        if regression["exit_code"] != 0 or '"verified":true' not in regression["stdout"]:
            failures.append("original native regression failed")
        scores = json.loads((HERE / "coset-result.json").read_bytes())
        expected = {panel["fixture"]: panel for panel in scores["panels"]}
        frozen = json.loads((HERE / "coset-fingerprints.json").read_bytes())
        fingerprints = {panel["fixture"]: panel for panel in frozen["panels"]}
        for name, count in PANELS:
            if expected[name]["fixture_sha256"] != sha(HERE / name) or \
               fingerprints[name]["fixture_sha256"] != sha(HERE / name):
                failures.append(f"fixture hash mismatch: {name}")
            streams = run([str(BINARY), "--check-coset-streams", str(HERE / name),
                           str(HERE / "coset-fingerprints.json")])
            runs.append(streams)
            if streams["exit_code"] != 0:
                failures.append(f"four action streams failed: {name}")
            replay = run([str(BINARY), "--check-coset-fixture", str(HERE / name),
                          str(HERE / "coset-seed-fixture.json"),
                          str(HERE / "coset-result.json")])
            runs.append(replay)
            if replay["exit_code"] != 0:
                failures.append(f"point replay failed: {name}")
                continue
            try:
                observed = json.loads(replay["stdout"])
                panel = expected[name]
                histogram = [sum(row["selected_path_index"] == arm
                                 for row in panel["rows"]) for arm in range(4)]
                if not (observed["verified"] and observed["cases"] == count
                        and observed["output_checks"] == count
                        and observed["choices"] == histogram
                        and observed["selected_M_plus_S"] == panel["selected_total"]
                        and observed["exceptional_cached_adds"] == 0):
                    failures.append(f"native summary mismatch: {name}")
            except (KeyError, ValueError) as error:
                failures.append(f"native parse error: {name}: {error}")
        fresh = expected["coset-fixture.json"]
        for arm in range(4):
            index = next(row["index"] for row in fresh["rows"]
                         if row["selected_path_index"] == arm)
            reference = run([str(BINARY), "--check-zero-tau-case",
                             str(HERE / "coset-fixture.json"), str(index)])
            candidate = run([str(BINARY), "--check-coset-case",
                             str(HERE / "coset-fixture.json"), str(index)])
            runs.extend((reference, candidate))
            if reference["exit_code"] or candidate["exit_code"]:
                failures.append(f"paired case failed: {index}")
                continue
            left, right = fields(reference["stdout"]), fields(candidate["stdout"])
            if any(left.get(key) != right.get(key) for key in
                   ("curve", "base_x", "base_y", "scalar", "point")) or \
               right.get("choice") != str(arm) or right.get("verified") != "1":
                failures.append(f"paired case mismatch: {index}")
    files = [HERE / name for name in (
        "Cargo.toml", "Cargo.lock", "src/main.rs", "src/selective.rs",
        "src/mixed_radix.rs", "src/coset.rs", "COSET_SELECTOR_PROTOCOL.md",
        "screen_coset_representatives.py", "coset_selector.py",
        "make_coset_fixture.py", "make_coset_seed_fixture.py",
        "make_coset_fingerprints.py", "run_coset_native_checks.py",
        "fixture.json", "coset-fixture.json", "coset-result.json",
        "coset-runtime-info.json", "coset-sage-replay.json",
        "coset-seed-fixture.json", "coset-fingerprints.json")]
    files += [REPO / "suite/src/ct_bignum.rs",
              REPO / "suite/src/ecc/secp256k1_field.rs", BINARY]
    artifacts = {str(path.relative_to(REPO) if path.is_relative_to(REPO)
                     else path): sha(path) for path in files}
    compiler = run(["rustc", "--version"])["stdout"].strip()
    receipt = {"schema": 1, "verified": not failures,
               "cpu_speedup_claim": None, "failures": failures,
               "artifacts_sha256": artifacts, "runs": runs,
               "compiler": compiler,
               "host": {"system": platform.system(),
                        "machine": platform.machine(),
                        "release": platform.release()}}
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": not failures,
                      "coset_cases": sum(count for _, count in PANELS),
                      "failures": failures,
                      "receipt_sha256": sha(args.output)}, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
