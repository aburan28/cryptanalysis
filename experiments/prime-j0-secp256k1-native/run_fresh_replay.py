#!/usr/bin/env python3
"""Retain offline native replay evidence for the held-out Sage panel."""

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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, env=None):
    result = subprocess.run(args, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            check=False)
    return {"command": args, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main():
    destination = HERE / "native-fresh-result.json"
    if destination.exists():
        raise SystemExit("native fresh result exists; refusing overwrite")
    fixture_path = HERE / "fresh-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 256
    assert fixture["script_sha256"] == sha(HERE / "make_fresh_fixture.py")
    source_paths = [
        HERE / "Cargo.toml", HERE / "Cargo.lock", HERE / "src/main.rs",
        HERE / "FRESH_NATIVE_PROTOCOL.md", HERE / "make_fresh_fixture.py",
        Path(__file__).resolve(), HERE / "fresh-runtime-info.json", fixture_path,
        HERE.parent / "prime-j0-secp256k1-scalar" / "result.json",
        HERE.parent / "prime-j0-secp256k1-scalar" / "validate_scalar.py",
        HERE.parent / "prime-j0-cost-aware-chain" / "run.py",
        REPO / "suite/src/ct_bignum.rs",
        REPO / "suite/src/ecc/secp256k1_field.rs",
    ]
    sources = {str(path.relative_to(REPO)): sha(path) for path in source_paths}
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(TARGET)
    build = command(["cargo", "build", "--offline", "--locked", "--release",
                     "--manifest-path", str(HERE / "Cargo.toml")], env)
    binary = TARGET / "release/prime-j0-secp256k1-native-replay"
    replay = None
    if build["exit_code"] == 0:
        replay = command([str(binary), str(fixture_path)], env)
        replay["parsed"] = None
        if replay["exit_code"] == 0:
            try:
                replay["parsed"] = json.loads(replay["stdout"])
            except json.JSONDecodeError:
                pass
    summary = replay and replay["parsed"]
    verified = bool(summary and summary.get("verified") is True and
                    summary.get("cases") == 256 and
                    summary.get("representative_checks") == 256 and
                    summary.get("digit_checks") == 256 and
                    summary.get("seed_checks") == 2304 and
                    summary.get("output_checks") == 256 and
                    summary.get("native_scope") == "variable_time_scalar_input" and
                    summary.get("cpu_speedup_claim") is None)
    result = {
        "schema": 1, "kind": "native-scalar-input-heldout-correctness",
        "verified": verified, "cpu_speedup_claim": None,
        "academic_novelty_claim": None, "host_isolation_receipt": None,
        "architecture": platform.machine(), "operating_system": platform.platform(),
        "compiler": command(["rustc", "--version", "--verbose"]),
        "fixture_input_sha256": fixture["input_sha256"],
        "source_sha256": sources, "build": build,
        "binary_sha256": sha(binary) if build["exit_code"] == 0 else None,
        "replay": replay,
    }
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": verified,
                      "fixture_sha256": sources[str(fixture_path.relative_to(REPO))],
                      "binary_sha256": result["binary_sha256"],
                      "summary": summary}, sort_keys=True))
    if not verified:
        raise SystemExit("native held-out replay failed; see retained receipt")


if __name__ == "__main__":
    main()
