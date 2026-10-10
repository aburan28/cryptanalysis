#!/usr/bin/env python3
"""Monitored parent for the frozen packed setup and proposed-output scans."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MIXED = ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
SUPPORT = ROOT / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
LEGACY = ROOT / "n131_w14_coupled_fouratom_inverse_20261010/native.cpp"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


sources = {"stream.cpp": HERE / "stream.cpp", "stream": HERE / "stream",
           "freeze.py": HERE / "freeze.py", "run.py": Path(__file__),
           "compiler_version.txt": HERE / "compiler_version.txt",
           "support_w14.tsv": SUPPORT, "legacy_native.cpp": LEGACY,
           "mixed_inputs.json": MIXED}
if len(sys.argv) != 2 or sys.argv[1] not in ("prepare", "query"):
    raise SystemExit("usage: run.py prepare|query")
action = sys.argv[1]
protocol_path = HERE / f"{action}_protocol.json"
protocol = json.loads(protocol_path.read_text())
if action == "prepare":
    assert protocol["source_sha256"] == {
        name: sha(path) for name, path in sources.items()}
    command = [str(HERE / "stream"), "prepare", str(SUPPORT),
               str(HERE / "index.bin"), str(HERE / "setup.json"),
               str(protocol["seed_first"]), str(protocol["seed_last"]),
               str(protocol["setup_cap_seconds"]), str(protocol["rss_cap_bytes"])]
    start = time.monotonic_ns()
    process = subprocess.run(command, capture_output=True, text=True,
                             timeout=protocol["setup_cap_seconds"] + 5)
    parent_ns = time.monotonic_ns() - start
    (HERE / "prepare.stdout.txt").write_text(process.stdout)
    (HERE / "prepare.stderr.txt").write_text(process.stderr)
    if process.returncode:
        raise RuntimeError(f"prepare exit {process.returncode}: {process.stderr}")
    setup = json.loads((HERE / "setup.json").read_text())
    assert setup["status"] == "COMPLETE_PACKED_SEED_PREPARE"
    parent = {"status": "COMPLETE_PACKED_SEED_PREPARE_PARENT",
              "parent_wall_ns": parent_ns,
              "exit_code": process.returncode,
              "protocol_sha256": sha(protocol_path),
              "index_sha256": sha(HERE / "index.bin"),
              "setup_sha256": sha(HERE / "setup.json"),
              "stdout_sha256": sha(HERE / "prepare.stdout.txt"),
              "stderr_sha256": sha(HERE / "prepare.stderr.txt")}
    (HERE / "prepare_parent.json").write_text(
        json.dumps(parent, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"parent_s": parent_ns/1e9,
                      "setup": setup}, sort_keys=True), flush=True)
else:
    assert protocol["source_sha256"] == {
        **{name: sha(path) for name, path in sources.items()},
        "prepare_protocol.json": sha(HERE / "prepare_protocol.json"),
        "setup.json": sha(HERE / "setup.json"),
        "index.bin": sha(HERE / "index.bin")}
    rows = []
    for case in protocol["case_order"]:
        output = HERE / f"{case}.json"
        command = [str(HERE / "stream"), "query", str(HERE / "index.bin"),
                   str(SUPPORT), str(protocol["target_z"][case]), str(output),
                   str(protocol["query_cap_seconds_per_case"]),
                   str(protocol["rss_cap_bytes"])]
        start = time.monotonic_ns()
        process = subprocess.run(command, capture_output=True, text=True,
                                 timeout=protocol["query_cap_seconds_per_case"] + 5)
        parent_ns = time.monotonic_ns() - start
        stdout = HERE / f"{case}.stdout.txt"
        stderr = HERE / f"{case}.stderr.txt"
        stdout.write_text(process.stdout)
        stderr.write_text(process.stderr)
        if process.returncode:
            raise RuntimeError(f"{case} exit {process.returncode}: {process.stderr}")
        row = json.loads(output.read_text())
        assert row["status"] == "COMPLETE_PACKED_SEED_QUERY"
        rows.append({"case": case, "parent_wall_ns": parent_ns,
                     "exit_code": process.returncode,
                     "result_sha256": sha(output),
                     "stdout_sha256": sha(stdout),
                     "stderr_sha256": sha(stderr),
                     "query_ns": row["query_ns"],
                     "hit_count": len(row["hits"])})
        print(json.dumps({"case": case,
                          "query_s": row["query_ns"]/1e9,
                          "entries": row["left_entries_checked"],
                          "hits": len(row["hits"])}, sort_keys=True), flush=True)
    receipt = {"status": "COMPLETE_PACKED_SEED_QUERY_PANEL",
               "protocol_sha256": sha(protocol_path), "rows": rows}
    (HERE / "query_parent.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
