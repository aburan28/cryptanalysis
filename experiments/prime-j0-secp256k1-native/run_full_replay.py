#!/usr/bin/env python3
"""Build the native scalar-input replay offline and retain both case panels."""

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
    return bool(record and record["exit_code"] == 0 and summary and
                summary.get("verified") is True and
                summary.get("cases") == cases and
                summary.get("representative_checks") == cases and
                summary.get("digit_checks") == cases and
                summary.get("seed_checks") == 9 * cases and
                summary.get("output_checks") == cases and
                summary.get("native_scope") == "variable_time_scalar_input" and
                summary.get("cpu_speedup_claim") is None)


def main():
    destination = HERE / "native-full-result.json"
    if destination.exists():
        raise SystemExit("native full result exists; refusing overwrite")
    original_path = HERE / "fixture.json"
    edge_path = HERE / "edge-fixture.json"
    original = json.loads(original_path.read_text())
    edge = json.loads(edge_path.read_text())
    assert len(original["cases"]) == 64 and len(edge["cases"]) == 30
    assert original["script_sha256"] == sha(HERE / "make_fixture.py")
    assert edge["script_sha256"] == sha(HERE / "make_edge_fixture.py")
    scalar_result = json.loads((HERE.parent / "prime-j0-secp256k1-scalar" /
                                "result.json").read_text())
    assert scalar_result["subgroup_order_hex"] == \
        "fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141"
    assert scalar_result["lambda_tau_hex"] == \
        "ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0"
    assert scalar_result["lattice_basis"] == [
        ["193508920647619669885755136084601127231",
         "238911465918039986966665730306072050094"],
        ["-238911465918039986966665730306072050094",
         "303414439467246543595250775667605759171"]]
    source_paths = [
        HERE / "Cargo.toml", HERE / "Cargo.lock", HERE / "src/main.rs",
        HERE / "FULL_NATIVE_PROTOCOL.md", Path(__file__).resolve(),
        HERE / "runtime-info.json", HERE / "edge-runtime-info.json",
        original_path, edge_path,
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
    original_replay = edge_replay = None
    if build["exit_code"] == 0:
        original_replay = replay(binary, original_path, env)
        edge_replay = replay(binary, edge_path, env)
    verified = valid(original_replay, 64) and valid(edge_replay, 30)
    compiler = command(["rustc", "--version", "--verbose"])
    result = {
        "schema": 1, "kind": "native-variable-time-scalar-input-correctness",
        "verified": verified, "cpu_speedup_claim": None,
        "academic_novelty_claim": None, "host_isolation_receipt": None,
        "architecture": platform.machine(), "operating_system": platform.platform(),
        "compiler": compiler, "source_sha256": sources,
        "build": build, "binary_sha256": sha(binary) if build["exit_code"] == 0 else None,
        "original_replay": original_replay, "edge_replay": edge_replay,
    }
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": verified,
                      "binary_sha256": result["binary_sha256"],
                      "original": original_replay and original_replay["parsed"],
                      "edge": edge_replay and edge_replay["parsed"]}, sort_keys=True))
    if not verified:
        raise SystemExit("native scalar-input replay failed; see retained receipt")


if __name__ == "__main__":
    main()
