#!/usr/bin/env python3
"""Run the frozen paired panel and retain every raw executable result."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010"
SUPPORT = ROOT / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
LEGACY = ROOT / "n131_w14_coupled_fouratom_inverse_20261010/native.cpp"
protocol = json.loads((HERE / "protocol.json").read_text())
files = {name: HERE / name for name in
         ("native.cpp", "native", "baseline.cpp", "baseline", "run.py",
          "compiler_version.txt")}
files.update({"legacy_native.cpp": LEGACY,
              "support_w14.tsv": SUPPORT,
              "mixed_inputs.json": BASE / "inputs.json"})
for n in (41, 131):
    for case in ("positive", "trace_zero_control"):
        name = f"n{n}_{case}.txt"
        files[name] = BASE / name
assert protocol["source_sha256"] == {
    name: hashlib.sha256(path.read_bytes()).hexdigest()
    for name, path in files.items()}

trials = []
counts = {}
for n, case, variant in protocol["run_order"]:
    key = (n, case, variant)
    counts[key] = counts.get(key, 0) + 1
    label = f"n{n}_{case}_{variant}_r{counts[key]}"
    output = HERE / f"{label}.json"
    stdout = HERE / f"{label}.stdout.txt"
    stderr = HERE / f"{label}.stderr.txt"
    binary = HERE / ("baseline" if variant == "baseline" else "native")
    cmd = [str(binary), str(BASE / f"n{n}_{case}.txt"), str(output),
           "-" if n == 41 else str(SUPPORT),
           str(protocol["cap_seconds_per_run"]),
           str(protocol["rss_cap_bytes"])]
    start = time.monotonic_ns()
    process = subprocess.run(cmd, text=True, capture_output=True, timeout=35)
    parent_ns = time.monotonic_ns() - start
    stdout.write_text(process.stdout)
    stderr.write_text(process.stderr)
    if process.returncode != 0:
        raise RuntimeError(f"{label} exited {process.returncode}: {process.stderr}")
    row = json.loads(output.read_text())
    assert row["status"] == "COMPLETE_ALGEBRAIC_SCAN"
    trials.append({"label": label, "field_degree": n, "case": case,
                   "variant": variant, "returncode": process.returncode,
                   "parent_ns": parent_ns,
                   "result": row,
                   "result_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                   "stdout_sha256": hashlib.sha256(stdout.read_bytes()).hexdigest(),
                   "stderr_sha256": hashlib.sha256(stderr.read_bytes()).hexdigest()})
    print(json.dumps({"label": label, "query_ns": row["query_ns"],
                      "setup_ns": row["setup_ns"],
                      "hits": len(row["hits"])}, sort_keys=True), flush=True)

for n in (41, 131):
    for case in ("positive", "trace_zero_control"):
        panel = [t for t in trials if t["field_degree"] == n and t["case"] == case]
        assert len(panel) == 4
        controls = [t["result"] for t in panel]
        assert all(r["hits"] == controls[0]["hits"] for r in controls)
        assert all(r["left_outputs_checked"] == controls[0]["left_outputs_checked"]
                   for r in controls)
        assert len(controls[0]["hits"]) == (1 if case == "positive" else 0)

receipt = {"status": "PASS_PAIRED_TARGET_SPLIT_HALFTRACE_PANEL",
           "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
           "trials": trials}
(HERE / "result.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
