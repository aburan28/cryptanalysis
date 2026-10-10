#!/usr/bin/env python3
"""Run corrected frozen queries with file I/O inside the online clock."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SUPPORT = ROOT / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
LEGACY = ROOT / "n131_w14_coupled_fouratom_inverse_20261010/native.cpp"
MIXED = ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


protocol = json.loads((HERE / "query_protocol_v2.json").read_text())
files = {name: HERE / name for name in
         ("stream.cpp", "stream", "stream_v1.cpp", "stream_v1",
          "freeze_query_v2.py", "run_query_v2.py", "compiler_version.txt",
          "prepare_protocol.json", "query_protocol.json", "setup.json",
          "index.bin", "query_failure_v1.json")}
files.update({"support_w14.tsv": SUPPORT, "legacy_native.cpp": LEGACY,
              "mixed_inputs.json": MIXED})
assert protocol["source_sha256"] == {name: sha(path) for name, path in files.items()}

rows = []
for case in protocol["case_order"]:
    output = HERE / f"{case}_v2.json"
    command = [str(HERE / "stream"), "query", str(HERE / "index.bin"),
               str(SUPPORT), str(protocol["target_z"][case]), str(output),
               str(protocol["query_cap_seconds_per_case"]),
               str(protocol["rss_cap_bytes"])]
    start = time.monotonic_ns()
    process = subprocess.run(command, capture_output=True, text=True,
                             timeout=protocol["query_cap_seconds_per_case"] + 5)
    parent_ns = time.monotonic_ns() - start
    stdout = HERE / f"{case}_v2.stdout.txt"
    stderr = HERE / f"{case}_v2.stderr.txt"
    stdout.write_text(process.stdout)
    stderr.write_text(process.stderr)
    if process.returncode:
        raise RuntimeError(f"{case} exit {process.returncode}: {process.stderr}")
    result = json.loads(output.read_text())
    assert result["status"] == "COMPLETE_PACKED_SEED_QUERY"
    rows.append({"case": case, "parent_wall_ns": parent_ns,
                 "exit_code": process.returncode,
                 "result_sha256": sha(output),
                 "stdout_sha256": sha(stdout),
                 "stderr_sha256": sha(stderr),
                 "query_ns": result["query_ns"],
                 "hit_count": len(result["hits"])})
    print(json.dumps({"case": case, "query_s": result["query_ns"]/1e9,
                      "entries": result["left_entries_checked"],
                      "hits": len(result["hits"])}, sort_keys=True), flush=True)
receipt = {"status": "COMPLETE_PACKED_SEED_QUERY_PANEL_V2",
           "protocol_sha256": sha(HERE / "query_protocol_v2.json"),
           "rows": rows}
(HERE / "query_parent_v2.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n")
