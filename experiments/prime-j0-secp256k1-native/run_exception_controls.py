#!/usr/bin/env python3
"""Retain exceptional cached-add control and full replay regression."""

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


def command(args, env):
    result = subprocess.run(args, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            check=False)
    return {"command": args, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def replay(binary, fixture, env):
    record = command([str(binary), str(fixture)], env)
    record["parsed"] = None
    if record["exit_code"] == 0:
        try:
            record["parsed"] = json.loads(record["stdout"])
        except json.JSONDecodeError:
            pass
    return record


def valid(record, cases):
    summary = record and record["parsed"]
    return bool(summary and record["exit_code"] == 0 and
                summary.get("verified") is True and
                summary.get("cases") == cases and
                summary.get("representative_checks") == cases and
                summary.get("digit_checks") == cases and
                summary.get("seed_checks") == 9 * cases and
                summary.get("output_checks") == cases and
                summary.get("exceptional_cached_adds") == 0 and
                summary.get("native_scope") == "variable_time_scalar_input" and
                summary.get("cpu_speedup_claim") is None)


def main():
    destination = HERE / "native-exception-result.json"
    if destination.exists():
        raise SystemExit("native exception result exists; refusing overwrite")
    panels = [("original", HERE / "fixture.json", 64),
              ("edge", HERE / "edge-fixture.json", 30),
              ("heldout", HERE / "fresh-fixture.json", 256)]
    for _, path, count in panels:
        fixture = json.loads(path.read_text())
        assert fixture["schema"] == 1 and len(fixture["cases"]) == count
    paths = [HERE / "Cargo.toml", HERE / "Cargo.lock", HERE / "src/main.rs",
             HERE / "EXCEPTION_PROTOCOL.md", Path(__file__).resolve(),
             REPO / "suite/src/ct_bignum.rs",
             REPO / "suite/src/ecc/secp256k1_field.rs"]
    paths.extend(path for _, path, _ in panels)
    sources = {str(path.relative_to(REPO)): sha(path) for path in paths}
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(TARGET)
    manifest = str(HERE / "Cargo.toml")
    build = command(["cargo", "build", "--offline", "--locked", "--release",
                     "--manifest-path", manifest], env)
    binary = TARGET / "release/prime-j0-secp256k1-native-replay"
    control = None
    replays = {}
    if build["exit_code"] == 0:
        control = replay(binary, Path("--check-exceptions"), env)
        for name, path, _ in panels:
            replays[name] = replay(binary, path, env)
    verified = (build["exit_code"] == 0 and control and
                control["exit_code"] == 0 and control["parsed"] and
                control["parsed"].get("verified") is True and
                control["parsed"].get("exception_cases") == 24 and
                all(valid(replays.get(name), count) for name, _, count in panels))
    result = {
        "schema": 1, "kind": "native-cached-add-exception-correctness",
        "verified": verified, "cpu_speedup_claim": None,
        "academic_novelty_claim": None, "host_isolation_receipt": None,
        "architecture": platform.machine(), "operating_system": platform.platform(),
        "compiler": command(["rustc", "--version", "--verbose"], env),
        "source_sha256": sources, "control": control, "build": build,
        "binary_sha256": sha(binary) if build["exit_code"] == 0 else None,
        "replays": replays,
    }
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": verified,
                      "binary_sha256": result["binary_sha256"],
                      "control": control and control["parsed"],
                      "replays": {name: item["parsed"] for name, item in replays.items()}},
                     sort_keys=True))
    if not verified:
        raise SystemExit("exception control failed; see retained receipt")


if __name__ == "__main__":
    main()
