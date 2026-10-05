#!/usr/bin/env python3
"""Run the frozen full W3 S3 root kernel only after its sampled gate passes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import time

from run_n83_w3_pair_root_probe import CRYPTO_COMMIT, PROTOCOL, SOURCE, save, sha


def main(sample_dir: Path, out: Path, binary: Path, crypto_checkout: Path) -> None:
    sample_dir, out = sample_dir.resolve(), out.resolve()
    binary, crypto_checkout = binary.resolve(), crypto_checkout.resolve()
    protocol = json.loads(PROTOCOL.read_text())
    sampled = json.loads((sample_dir / "left64.json").read_text())
    replay = json.loads((sample_dir / "left64_sage_replay.json").read_text())
    receipt = json.loads((sample_dir / "receipt.json").read_text())
    assert receipt["status"] == "PRODUCER_COMPLETE_PENDING_INDEPENDENT_REPLAY"
    assert replay["status"] == "PASS" and replay["sampled_group_sum_roots_checked"] == 64
    assert replay["result_sha256"] == sha(sample_dir / "left64.json")
    assert sampled["s3_roots_found"] == sampled["s3_calls"]
    assert sampled["left_limit"] == 64 and sampled["s3_calls"] == 64 * 539 * 83
    projected_seconds = (
        int(sampled["root_kernel_wall_ns_exploratory"]) / 1e9 * 539 / 64
    )
    assert projected_seconds < 240, projected_seconds
    assert sha(sample_dir / "input.json") == protocol["input_sha256"]
    assert not (out / "started.json").exists()
    assert not (out / "left539.json").exists()
    assert binary.is_file() and os.access(binary, os.X_OK)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=crypto_checkout, text=True
    ).strip()
    assert commit == CRYPTO_COMMIT
    assert sha(crypto_checkout / "examples/n83_w3_pair_root_probe.rs") == sha(SOURCE)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sample_dir / "input.json", out / "input.json")
    shutil.copy2(binary, out / "solver_binary")
    assert sha(out / "solver_binary") == sha(sample_dir / "solver_binary")
    started = {
        "kind": "n83_w3_pair_root_full_start",
        "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(PROTOCOL),
        "input_sha256": sha(out / "input.json"),
        "sample_receipt_sha256": sha(sample_dir / "receipt.json"),
        "sample_replay_sha256": sha(sample_dir / "left64_sage_replay.json"),
        "sample_result_sha256": sha(sample_dir / "left64.json"),
        "projected_full_kernel_seconds_exploratory": projected_seconds,
        "probe_source_sha256": sha(SOURCE),
        "runner_source_sha256": sha(Path(__file__)),
        "crypto_source_commit": commit,
        "crypto_cargo_lock_sha256": sha(crypto_checkout / "Cargo.lock"),
        "solver_binary_sha256": sha(out / "solver_binary"),
        "architecture": platform.machine(),
        "os": platform.platform(),
        "wall_limit_seconds": protocol["per_run_external_wall_limit_seconds"],
    }
    save(out / "started.json", started)

    destination = out / "left539.json"
    command = [str(out / "solver_binary"), str(out / "input.json"), "539", str(destination)]
    begin = time.perf_counter_ns()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=protocol["per_run_external_wall_limit_seconds"], check=False,
        )
        status = "complete" if completed.returncode == 0 else "error"
        exit_code = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as error:
        status, exit_code = "timeout", None
        stdout = error.stdout.decode(errors="replace") if error.stdout else ""
        stderr = error.stderr.decode(errors="replace") if error.stderr else ""
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (out / "left539.stdout.txt").write_text(stdout)
    (out / "left539.stderr.txt").write_text(stderr)
    outcome = {
        "left_limit": 539,
        "status": status,
        "exit_code": exit_code,
        "external_wall_ns": time.perf_counter_ns() - begin,
        "child_user_seconds": after.ru_utime - before.ru_utime,
        "child_system_seconds": after.ru_stime - before.ru_stime,
        "children_peak_rss_highwater": after.ru_maxrss,
        "children_peak_rss_unit": "bytes" if platform.system() == "Darwin" else "kilobytes",
        "kernel_result_sha256": sha(destination) if destination.exists() else None,
        "stdout_sha256": sha(out / "left539.stdout.txt"),
        "stderr_sha256": sha(out / "left539.stderr.txt"),
    }
    if status == "complete":
        result = json.loads(destination.read_text())
        assert result["left_limit"] == 539
        assert result["s3_calls"] == 539 * 539 * 83
        assert result["s3_roots_found"] == result["s3_calls"]
    save(out / "receipt.json", {
        "schema_version": 1,
        "kind": "n83_w3_pair_root_full_execution",
        "status": "PRODUCER_COMPLETE_PENDING_INDEPENDENT_REPLAY" if status == "complete" else "INCOMPLETE",
        "started_sha256": sha(out / "started.json"),
        "outcome": outcome,
        "claim_boundary": protocol["claim_boundary"],
    })
    print(json.dumps(outcome, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sample_dir", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("binary", type=Path)
    parser.add_argument("crypto_checkout", type=Path)
    args = parser.parse_args()
    main(args.sample_dir, args.out, args.binary, args.crypto_checkout)
