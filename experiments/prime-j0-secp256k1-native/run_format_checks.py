#!/usr/bin/env python3
"""Retain paired correctness of the native projective and affine formats."""

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


def fields(stdout):
    return dict(word.split("=", 1) for word in stdout.strip().split(" ")
                if "=" in word)


def main():
    destination = HERE / "native-format-checks.json"
    if destination.exists():
        raise SystemExit("native format result exists; refusing overwrite")
    panels = [("original", HERE / "fixture.json", 64),
              ("edge", HERE / "edge-fixture.json", 30),
              ("heldout", HERE / "fresh-fixture.json", 256)]
    source_paths = [
        HERE / "Cargo.toml", HERE / "Cargo.lock", HERE / "src/main.rs",
        HERE / "FORMAT_PROTOCOL.md", HERE / "make_bench_workload.py",
        Path(__file__).resolve(),
        REPO / "suite/src/ct_bignum.rs",
        REPO / "suite/src/ecc/secp256k1_field.rs",
    ] + [path for _, path, _ in panels]
    sources = {str(path.relative_to(REPO)): sha(path) for path in source_paths}
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(TARGET)
    build = command(["cargo", "build", "--offline", "--locked", "--release",
                     "--manifest-path", str(HERE / "Cargo.toml")], env)
    binary = TARGET / "release/prime-j0-secp256k1-native-replay"
    rows = []
    if build["exit_code"] == 0:
        for panel_name, path, count in panels:
            fixture = json.loads(path.read_text())
            assert fixture["schema"] == 1 and len(fixture["cases"]) == count
            for index, case in enumerate(fixture["cases"]):
                expected_point = ("identity" if case.get("expected_identity") else
                                  case["expected_x_hex"] + ":" + case["expected_y_hex"])
                for mode in ("cached_projective", "all_affine"):
                    raw = command([str(binary), "--check-benchmark-case", mode,
                                   str(path), str(index)], env)
                    observed = fields(raw["stdout"])
                    checked = (raw["exit_code"] == 0 and
                               observed.get("verified") == "1" and
                               observed.get("curve") == "secp256k1" and
                               observed.get("base_x") == case["base_x_hex"] and
                               observed.get("base_y") == case["base_y_hex"] and
                               observed.get("scalar") == case["scalar_hex"] and
                               observed.get("point") == expected_point and
                               observed.get("mode") == mode and
                               "online_ms" not in observed)
                    rows.append({"panel": panel_name, "index": index,
                                 "mode": mode, "verified": checked, "raw": raw})
    verified = bool(build["exit_code"] == 0 and len(rows) == 700 and
                    all(row["verified"] for row in rows))
    result = {
        "schema": 1, "kind": "native-seed-format-correctness",
        "verified": verified, "cpu_speedup_claim": None,
        "academic_novelty_claim": None, "host_isolation_receipt": None,
        "architecture": platform.machine(), "operating_system": platform.platform(),
        "compiler": command(["rustc", "--version", "--verbose"], env),
        "source_sha256": sources, "build": build,
        "binary_sha256": sha(binary) if build["exit_code"] == 0 else None,
        "rows": rows,
    }
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    failures = [{"panel": row["panel"], "index": row["index"],
                 "mode": row["mode"], "stderr": row["raw"]["stderr"]}
                for row in rows if not row["verified"]]
    print(json.dumps({"verified": verified, "checks": len(rows),
                      "failures": failures[:10],
                      "binary_sha256": result["binary_sha256"]}, sort_keys=True))
    if not verified:
        raise SystemExit("native format checks failed; see retained receipt")


if __name__ == "__main__":
    main()
