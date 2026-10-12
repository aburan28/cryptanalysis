#!/usr/bin/env python3
"""Freeze and run an N83 packed-index capacity diagnostic on one public point."""

import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import time


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCE = PARENT / "packed_index_e1_sparse26_cachedxy_cpu_20261011"
INPUTS = PARENT / "adaptive_all_orientations_20261004" / "inputs"
SOURCE_SHA256 = "8a57c4d994c47344d7093c1103bfadc80e48f666e49f346bf729b80404132b05"
PARENT_WORKLOAD_ID = "981ac530e67e"
STATE_CAP = 29_900_000
RSS_CAP_MIB = 5_500
MODE = "packed_sparse26_compact16_cachedxy"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def save(name, value):
    (HERE / name).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def checked_inputs(binary):
    parent = json.loads((SOURCE / "stage_manifest.json").read_text())
    workload = json.loads((SOURCE / "workload.json").read_text())
    assert parent["workload_id"] == PARENT_WORKLOAD_ID
    assert parent["target_count"] == workload["target_count"] == 1
    assert parent["target_poly_xy"] == workload["target_poly_xy"]
    assert digest(SOURCE / "native_packed_index.rs") == SOURCE_SHA256
    assert digest(INPUTS / "n83_x_representatives.bin") == parent["representatives_file_sha256"]
    assert binary.is_file()
    return parent, workload


def prepare(binary):
    parent, workload = checked_inputs(binary)
    workload["index_state_law"]["count"] = STATE_CAP
    workload_id = hashlib.sha256(canonical(workload)).hexdigest()[:12]
    save("workload.json", workload)
    protocol = {
        "kind": "n83_e1_sparse26_capacity_protocol",
        "proposal_id": "Q2026101131",
        "candidate_id": None,
        "curve_id": parent["curve_id"],
        "workload_id": workload_id,
        "parent_workload_id": PARENT_WORKLOAD_ID,
        "public_target_poly_xy": parent["target_poly_xy"],
        "pair_state_cap": STATE_CAP,
        "peak_rss_cap_mib": RSS_CAP_MIB,
        "index_mode": MODE,
        "measurement_boundary": "target clock starts after index and cached-coordinate construction",
        "source_sha256": SOURCE_SHA256,
        "binary_sha256": digest(binary),
        "bridge_sha256": digest(INPUTS / "n83_onb_poly_bridge.json"),
        "representatives_sha256": digest(INPUTS / "n83_x_representatives.bin"),
        "parent_stage_manifest_sha256": digest(SOURCE / "stage_manifest.json"),
        "parent_protocol_sha256": digest(SOURCE / "protocol.json"),
        "runner_sha256": digest(HERE / "capacity_probe.py"),
        "resource_accounting": "index preparation, online target, memory, and raw failure retained separately",
    }
    save("protocol.json", protocol)
    manifest = dict(parent)
    manifest.update({
        "kind": "n83_e1_sparse26_capacity_input",
        "stage_id": "n83_e1_sparse26_capacity_20261011",
        "proposal_id": protocol["proposal_id"],
        "workload_id": workload_id,
        "pair_state_cap": STATE_CAP,
        "peak_rss_cap_mib": RSS_CAP_MIB,
        "stage_protocol_sha256": digest(HERE / "protocol.json"),
    })
    save("stage_manifest.json", manifest)
    print(json.dumps({"workload_id": workload_id,
                      "source_sha256": SOURCE_SHA256,
                      "binary_sha256": protocol["binary_sha256"],
                      "state_cap": STATE_CAP,
                      "rss_cap_mib": RSS_CAP_MIB}, sort_keys=True))


def run(binary):
    parent, _ = checked_inputs(binary)
    protocol = json.loads((HERE / "protocol.json").read_text())
    manifest = json.loads((HERE / "stage_manifest.json").read_text())
    workload = json.loads((HERE / "workload.json").read_text())
    assert protocol["binary_sha256"] == digest(binary)
    assert protocol["source_sha256"] == SOURCE_SHA256
    assert protocol["bridge_sha256"] == digest(INPUTS / "n83_onb_poly_bridge.json")
    assert protocol["representatives_sha256"] == digest(INPUTS / "n83_x_representatives.bin")
    assert protocol["parent_stage_manifest_sha256"] == digest(SOURCE / "stage_manifest.json")
    assert protocol["parent_protocol_sha256"] == digest(SOURCE / "protocol.json")
    assert protocol["runner_sha256"] == digest(HERE / "capacity_probe.py")
    assert manifest["stage_protocol_sha256"] == digest(HERE / "protocol.json")
    assert manifest["workload_id"] == protocol["workload_id"]
    assert manifest["pair_state_cap"] == workload["index_state_law"]["count"] == STATE_CAP
    assert manifest["peak_rss_cap_mib"] == RSS_CAP_MIB
    assert manifest["target_poly_xy"] == parent["target_poly_xy"]
    output = HERE / "run_sparse26_cachedxy_29900000.json"
    if output.exists() or (HERE / "run_record.json").exists():
        raise RuntimeError("capacity run already exists; preserve its first receipt")
    command = [str(binary), str(HERE / "stage_manifest.json"),
               str(INPUTS / "n83_onb_poly_bridge.json"),
               str(INPUTS / "n83_x_representatives.bin"),
               str(STATE_CAP), str(RSS_CAP_MIB), MODE, str(output)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=1_800)
        code = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
        status = "completed" if code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        code, status = None, "timeout"
        stdout = (exc.stdout or b"").decode(errors="replace")
        stderr = (exc.stderr or b"").decode(errors="replace")
    elapsed = time.perf_counter_ns() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (HERE / "run.stdout.txt").write_text(stdout)
    (HERE / "run.stderr.txt").write_text(stderr)
    result = {
        "kind": "n83_e1_sparse26_capacity_run",
        "workload_id": protocol["workload_id"],
        "status": status,
        "exit_code": code,
        "command": command,
        "outer_elapsed_ns": elapsed,
        "child_user_cpu_ns": round((after.ru_utime - before.ru_utime) * 1e9),
        "child_system_cpu_ns": round((after.ru_stime - before.ru_stime) * 1e9),
        "output_sha256": digest(output) if output.exists() else None,
        "protocol_sha256": digest(HERE / "protocol.json"),
        "stage_manifest_sha256": digest(HERE / "stage_manifest.json"),
        "binary_sha256": digest(binary),
        "host_isolation_receipt": None,
    }
    if output.exists():
        raw = json.loads(output.read_text())
        assert raw["native_source_sha256"] == SOURCE_SHA256
        assert raw["workload_id"] == protocol["workload_id"]
        assert raw["limits"]["pair_state_cap"] == STATE_CAP
        result.update(native_status=raw["status"],
                      index_states=raw["index_pair_states_examined"],
                      peak_rss_bytes=raw["peak_rss_bytes"])
    save("run_record.json", result)
    print(json.dumps({"status": status,
                      "native_status": result.get("native_status"),
                      "index_states": result.get("index_states"),
                      "peak_rss_bytes": result.get("peak_rss_bytes")}, sort_keys=True))
    if code != 0:
        raise RuntimeError("capacity producer did not complete; preserve raw status")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run"))
    parser.add_argument("--binary", required=True, type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.binary.resolve(strict=True))
    else:
        run(args.binary.resolve(strict=True))
