#!/usr/bin/env sage -python
"""Freeze and measure exact W15 support for the N131 six-pair geometry."""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
HELPER = HERE.parent.parent / "koblitz-s5-invariant-20260924/lowpoly_w23_geometry.cpp"
PARAMS = Path("/Volumes/SSD990/crypto/docs/ic/params/ecc2k130-fixed.json")
BINARY = HERE / "export_w15_support"
RSS_CAP = 4 * 1024**3
WALL_CAP = 120.0


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def source_paths():
    return {"source": HERE / "export_w15_support.cpp",
            "binary": BINARY,
            "helper": HELPER,
            "official_params": PARAMS,
            "runner": HERE / "support_run.py",
            "checked_sage_runtime": HERE / "sage_runtime_info.json"}


def save(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def freeze():
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    record = {
        "status": "FROZEN_BEFORE_W15_SIX_PAIR_SUPPORT_ENUMERATION",
        "candidate_id": None,
        "curve_id": "EC1N131Ckb1heb5f1998f20b",
        "field_degree": 131,
        "source_dimension": 15,
        "summands": 12,
        "rotations": [0, 13, 26, 39, 52, 65],
        "target_q": [2309658012506412099988466246134815930289,
                     1578526100003023531340803776621036465818],
        "workers": 1,
        "wall_cap_seconds": WALL_CAP,
        "rss_cap_bytes": RSS_CAP,
        "compile_command": "c++ -O3 -std=c++17 -Wall -Wextra export_w15_support.cpp -o export_w15_support",
        "source_sha256": {name: sha(path) for name, path in source_paths().items()},
    }
    save(HERE / "support_protocol.json", record)
    print(json.dumps({"status": record["status"], "source_dimension": 15}))


def run():
    protocol = json.loads((HERE / "support_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_W15_SIX_PAIR_SUPPORT_ENUMERATION"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in source_paths().items()}
    command = [str(BINARY), str(HERE / "support_w15.tsv"), str(HERE / "support_receipt.json")]
    started = time.monotonic()
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    stop_reason = None
    with (HERE / "native.stdout.txt").open("xb") as stdout, \
         (HERE / "native.stderr.txt").open("xb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        process = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                peak_rss = max(peak_rss, parent.memory_info().rss + process.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak_rss >= RSS_CAP:
                stop_reason = "RSS_CAP"
            elif time.monotonic() - started >= WALL_CAP:
                stop_reason = "WALL_CAP"
            if stop_reason:
                child.terminate()
                break
            time.sleep(.001)
        child.wait(timeout=5)
    elapsed = time.monotonic() - started
    status = ("COMPLETE" if child.returncode == 0 and stop_reason is None else
              "OOM" if stop_reason == "RSS_CAP" else
              "CENSORED_TIME" if stop_reason == "WALL_CAP" else "PRODUCER_FAILURE")
    source = json.loads((HERE / "support_receipt.json").read_text()) if status == "COMPLETE" else None
    receipt = {
        "status": status,
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "command": command,
        "wall_seconds": elapsed,
        "sampled_peak_combined_rss_bytes": peak_rss,
        "stop_reason": stop_reason,
        "exit_code": child.returncode,
        "native_result": source,
        "source_sha256": {
            "protocol": sha(HERE / "support_protocol.json"),
            "stdout": sha(HERE / "native.stdout.txt"),
            "stderr": sha(HERE / "native.stderr.txt"),
            "support": sha(HERE / "support_w15.tsv") if source else None,
            "native_receipt": sha(HERE / "support_receipt.json") if source else None,
        },
    }
    save(HERE / "parent_receipt.json", receipt)
    print(json.dumps({"status": status, "wall_seconds": elapsed,
                      "rational_masks": source["rational_masks"] if source else None,
                      "B": source["actual_subgroup_factor_base_points_B"] if source else None}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "run"))
    mode = parser.parse_args().mode
    freeze() if mode == "freeze" else run()
