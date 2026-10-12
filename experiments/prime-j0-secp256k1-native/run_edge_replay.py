#!/usr/bin/env python3
"""Retain a source-bound native replay of edge and original scalar cases."""

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


def replay_record(binary, fixture, environment):
    executed = command([str(binary), str(fixture)], environment)
    parsed = None
    if executed.returncode == 0:
        try:
            parsed = json.loads(executed.stdout)
        except json.JSONDecodeError:
            pass
    return {
        "command": [str(binary), str(fixture)],
        "exit_code": executed.returncode,
        "stdout": executed.stdout,
        "stderr": executed.stderr,
        "parsed": parsed,
    }


def valid(record, cases, seeds):
    summary = record and record["parsed"]
    return bool(record and record["exit_code"] == 0 and summary and
                summary.get("verified") is True and
                summary.get("cases") == cases and
                summary.get("seed_checks") == seeds and
                summary.get("output_checks") == cases and
                summary.get("native_scope") == "point_path_only" and
                summary.get("cpu_speedup_claim") is None)


def main():
    destination = HERE / "native-edge-result.json"
    if destination.exists():
        raise SystemExit("native edge result exists; refusing overwrite")
    edge_path = HERE / "edge-fixture.json"
    original_path = HERE / "fixture.json"
    edge = json.loads(edge_path.read_text())
    original = json.loads(original_path.read_text())
    assert edge["schema"] == original["schema"] == 1
    assert len(edge["cases"]) == 30 and len(original["cases"]) == 64
    assert sha(HERE / "make_edge_fixture.py") == edge["script_sha256"]
    assert sha(HERE / "make_fixture.py") == original["script_sha256"]
    source_paths = [
        HERE / "Cargo.toml", HERE / "Cargo.lock", HERE / "src/main.rs",
        HERE / "EDGE_PROTOCOL.md", HERE / "make_edge_fixture.py",
        Path(__file__).resolve(), HERE / "edge-runtime-info.json",
        edge_path, original_path,
        REPO / "suite/src/ct_bignum.rs",
        REPO / "suite/src/ecc/secp256k1_field.rs",
    ]
    source_hashes = {str(path.relative_to(REPO)): sha(path)
                     for path in source_paths}
    environment = os.environ.copy()
    environment["CARGO_TARGET_DIR"] = str(TARGET)
    build_args = ["cargo", "build", "--offline", "--locked", "--release",
                  "--manifest-path", str(HERE / "Cargo.toml")]
    build = command(build_args, environment)
    binary = TARGET / "release/prime-j0-secp256k1-native-replay"
    edge_replay = original_replay = None
    if build.returncode == 0:
        edge_replay = replay_record(binary, edge_path, environment)
        original_replay = replay_record(binary, original_path, environment)
    verified = valid(edge_replay, 30, 270) and valid(original_replay, 64, 576)
    compiler = command(["rustc", "--version", "--verbose"])
    result = {
        "schema": 1, "kind": "native-point-path-edge-correctness",
        "verified": verified, "cpu_speedup_claim": None,
        "academic_novelty_claim": None, "host_isolation_receipt": None,
        "architecture": platform.machine(),
        "operating_system": platform.platform(),
        "compiler": compiler.stdout.strip(),
        "edge_input_sha256": edge["input_sha256"],
        "source_sha256": source_hashes,
        "build_command": build_args,
        "build_exit_code": build.returncode,
        "build_stdout": build.stdout, "build_stderr": build.stderr,
        "binary_sha256": sha(binary) if build.returncode == 0 else None,
        "edge_replay": edge_replay,
        "original_replay": original_replay,
    }
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": verified,
                      "binary_sha256": result["binary_sha256"],
                      "edge_summary": edge_replay and edge_replay["parsed"],
                      "original_summary": original_replay and original_replay["parsed"]},
                     sort_keys=True))
    if not verified:
        raise SystemExit("native edge replay failed; see retained receipt")


if __name__ == "__main__":
    main()
