#!/usr/bin/env python3
"""Build the native point path offline and retain an auditable replay receipt."""

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
    return subprocess.run(args, cwd=REPO, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=False)


def main():
    destination = HERE / "native-replay-result.json"
    if destination.exists():
        raise SystemExit("native replay result exists; refusing overwrite")
    fixture_path = HERE / "fixture.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 64
    assert sha(HERE / "make_fixture.py") == fixture["script_sha256"]
    source_result = (HERE.parent / "prime-j0-secp256k1-scalar" /
                     "cached-projective-result.json")
    assert sha(source_result) == fixture["source_result_sha256"]
    source_paths = [
        HERE / "Cargo.toml", HERE / "Cargo.lock", HERE / "src/main.rs",
        HERE / "make_fixture.py", Path(__file__).resolve(),
        REPO / "suite/src/ct_bignum.rs",
        REPO / "suite/src/ecc/secp256k1_field.rs",
        fixture_path, HERE / "runtime-info.json",
    ]
    sources = {str(path.relative_to(REPO)): sha(path) for path in source_paths}
    environment = os.environ.copy()
    environment["CARGO_TARGET_DIR"] = str(TARGET)
    build_args = ["cargo", "build", "--offline", "--locked", "--release",
                  "--manifest-path", str(HERE / "Cargo.toml")]
    build = command(build_args, environment)
    binary = TARGET / "release/prime-j0-secp256k1-native-replay"
    replay = None
    parsed = None
    if build.returncode == 0:
        replay = command([str(binary), str(fixture_path)], environment)
        if replay.returncode == 0:
            parsed = json.loads(replay.stdout)
    verified = bool(parsed and parsed.get("verified") and
                    parsed.get("cases") == 64 and
                    parsed.get("seed_checks") == 576 and
                    parsed.get("output_checks") == 64 and
                    parsed.get("native_scope") == "point_path_only")
    compiler = command(["rustc", "--version", "--verbose"])
    result = {
        "schema": 1, "kind": "native-256-bit-point-path-correctness",
        "verified": verified, "cpu_speedup_claim": None,
        "academic_novelty_claim": None,
        "host_isolation_receipt": None,
        "architecture": platform.machine(),
        "operating_system": platform.platform(),
        "compiler": compiler.stdout.strip(),
        "fixture_input_sha256": fixture["input_sha256"],
        "fixture_sha256": sha(fixture_path),
        "source_sha256": sources,
        "build_command": build_args,
        "build_exit_code": build.returncode,
        "build_stdout": build.stdout,
        "build_stderr": build.stderr,
        "binary_sha256": sha(binary) if build.returncode == 0 else None,
        "replay_exit_code": replay.returncode if replay else None,
        "replay_stdout": replay.stdout if replay else None,
        "replay_stderr": replay.stderr if replay else None,
        "replay_summary": parsed,
    }
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": verified,
                      "binary_sha256": result["binary_sha256"],
                      "fixture_sha256": result["fixture_sha256"],
                      "replay_summary": parsed}, sort_keys=True))
    if not verified:
        raise SystemExit("native replay failed; see retained receipt")


if __name__ == "__main__":
    main()
