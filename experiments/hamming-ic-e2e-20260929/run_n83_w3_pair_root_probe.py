#!/usr/bin/env python3
"""Run the frozen wide S3 kernel probe with bounded, retained outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import time


ROOT = Path(__file__).resolve().parent
PROTOCOL = ROOT / "n83_w3_pair_root_probe_protocol.json"
SOURCE = ROOT / "n83_w3_pair_root_probe.rs"
CRYPTO_COMMIT = "ea8892a530505a07ca1274f614cdba3b16f96c5c"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def decoded(value):
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""


def main(out, binary, crypto_checkout):
    out = out.resolve()
    binary = binary.resolve()
    crypto_checkout = crypto_checkout.resolve()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["curve_id"] == "EC1N83Ckb1h2bcb59d56ad6"
    assert protocol["left_limits"] == [16, 64]
    assert sha(out / "input.json") == protocol["input_sha256"]
    assert not (out / "started.json").exists()
    assert not (out / "left16.json").exists()
    assert not (out / "left64.json").exists()
    assert binary.is_file() and os.access(binary, os.X_OK)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=crypto_checkout, text=True
    ).strip()
    assert commit == CRYPTO_COMMIT
    assert sha(crypto_checkout / "examples/n83_w3_pair_root_probe.rs") == sha(SOURCE)
    snapshot = out / "solver_binary"
    shutil.copy2(binary, snapshot)
    assert sha(snapshot) == sha(binary)
    started = {
        "kind": "n83_w3_pair_root_probe_start",
        "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(PROTOCOL),
        "input_sha256": sha(out / "input.json"),
        "probe_source_sha256": sha(SOURCE),
        "runner_source_sha256": sha(Path(__file__)),
        "crypto_source_commit": commit,
        "crypto_cargo_lock_sha256": sha(crypto_checkout / "Cargo.lock"),
        "solver_binary_sha256": sha(snapshot),
        "architecture": platform.machine(),
        "os": platform.platform(),
        "wall_limit_seconds_per_run": protocol["per_run_external_wall_limit_seconds"],
    }
    save(out / "started.json", started)

    outcomes = []
    for left_limit in protocol["left_limits"]:
        destination = out / f"left{left_limit}.json"
        command = [str(snapshot), str(out / "input.json"), str(left_limit), str(destination)]
        begin = time.perf_counter_ns()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True,
                timeout=protocol["per_run_external_wall_limit_seconds"],
                check=False,
            )
            status = "complete" if completed.returncode == 0 else "error"
            exit_code = completed.returncode
            stdout, stderr = completed.stdout, completed.stderr
        except subprocess.TimeoutExpired as error:
            status, exit_code = "timeout", None
            stdout = decoded(error.stdout)
            stderr = decoded(error.stderr)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        (out / f"left{left_limit}.stdout.txt").write_text(stdout)
        (out / f"left{left_limit}.stderr.txt").write_text(stderr)
        result = {
            "left_limit": left_limit,
            "status": status,
            "exit_code": exit_code,
            "external_wall_ns": time.perf_counter_ns() - begin,
            "child_user_seconds": after.ru_utime - before.ru_utime,
            "child_system_seconds": after.ru_stime - before.ru_stime,
            "children_peak_rss_highwater": after.ru_maxrss,
            "children_peak_rss_unit": "bytes" if platform.system() == "Darwin" else "kilobytes",
            "kernel_result_sha256": sha(destination) if destination.exists() else None,
            "stdout_sha256": sha(out / f"left{left_limit}.stdout.txt"),
            "stderr_sha256": sha(out / f"left{left_limit}.stderr.txt"),
        }
        outcomes.append(result)
        save(out / "progress.json", {"outcomes": outcomes})
        if status != "complete":
            break
        kernel = json.loads(destination.read_text())
        assert kernel["left_limit"] == left_limit
        assert kernel["s3_calls"] == left_limit * 539 * 83
    receipt = {
        "schema_version": 1,
        "kind": "n83_w3_pair_root_kernel_probe_execution",
        "status": "PRODUCER_COMPLETE_PENDING_INDEPENDENT_REPLAY"
        if len(outcomes) == len(protocol["left_limits"])
        and all(item["status"] == "complete" for item in outcomes)
        else "INCOMPLETE",
        "started_sha256": sha(out / "started.json"),
        "outcomes": outcomes,
        "claim_boundary": protocol["claim_boundary"],
    }
    save(out / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "outcomes": outcomes}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("binary", type=Path)
    parser.add_argument("crypto_checkout", type=Path)
    args = parser.parse_args()
    main(args.out, args.binary, args.crypto_checkout)
