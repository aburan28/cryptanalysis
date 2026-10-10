#!/usr/bin/env python3
"""Run the frozen A1 relation-collector AB/BA panel with immutable receipts."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
ORDER = (("primary", False), ("primary", True),
         ("disjoint", True), ("disjoint", False))
CRYPTO_REVISION = "8ab924b935923df9faac25915ed7d9849974de0b"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    export = HERE / "inputs/export.json"
    index = HERE / "inputs/index.bin"
    source = HERE / "collector/src/main.rs"
    for stream, enabled in ORDER:
        workload = HERE / f"inputs/{stream}.json"
        data = json.loads(workload.read_text())
        assert data["pair_index_orbits"] == 735_000
        assert data["index_record_bytes"] == 12
        assert data["base_export_sha256"] == digest(export)
        assert data["index_binary_sha256"] == digest(index)
        name = f"{stream}_{'on' if enabled else 'off'}"
        receipt = HERE / f"results/{name}.json"
        assert not receipt.exists(), f"refusing to overwrite {receipt}"
        env = os.environ.copy()
        env["A1_CONJUGATE_BLOOM"] = "1" if enabled else "0"
        command = [str(binary), str(export), str(index), str(workload)]
        started = time.monotonic_ns()
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       env=env, timeout=600, check=False)
            stdout, stderr = completed.stdout, completed.stderr
            code = completed.returncode
            launch_status = "completed" if code == 0 else "error"
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or b"").decode(errors="replace")
            stderr = (exc.stderr or b"").decode(errors="replace")
            code = None
            launch_status = "timeout"
        outer_ns = time.monotonic_ns() - started
        lines = [line for line in stdout.splitlines() if line.strip()]
        raw = json.loads(lines[0]) if code == 0 and len(lines) == 1 else None
        item = {"schema_version": 1, "name": name, "launch_status": launch_status,
                "exit_code": code, "raw_result": raw,
                "stdout": stdout, "stderr": stderr,
                "outer_wall_ns": outer_ns, "cpu_isolation": "unverified",
                "crypto_source_revision": CRYPTO_REVISION,
                "binary_sha256": digest(binary), "collector_source_sha256": digest(source),
                "manifest_sha256": digest(HERE / "collector/Cargo.toml"),
                "lock_sha256": digest(HERE / "collector/Cargo.lock"),
                "protocol_sha256": digest(HERE / "PROTOCOL.md"),
                "runner_sha256": digest(Path(__file__)),
                "export_sha256": digest(export), "index_sha256": digest(index),
                "workload_sha256": digest(workload),
                "filter_enabled": enabled,
                "timing_boundary": "in-process relation collection after index, base, and optional Bloom preparation"}
        with receipt.open("x") as output:
            json.dump(item, output, sort_keys=True, indent=2)
            output.write("\n")
        print(json.dumps({"name": name, "status": raw["status"] if raw else launch_status,
                          "queries": raw["query_count"] if raw else None}), flush=True)


if __name__ == "__main__":
    main()
