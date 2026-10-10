#!/usr/bin/env python3
"""Run same-output native controls with and without exact source filtering."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

here = Path(__file__).resolve().parent
legacy = here.parent / "n131_w14_coupled_fouratom_inverse_20261010"
support = here.parent / "n131_w14_ten_source_gate_20261009" / "support_w14.tsv"
protocol = json.loads((here / "protocol_filtered.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_FILTERED_COMPARISON"
files = {
    "native_filtered.cpp": here / "native_filtered.cpp",
    "native_filtered": here / "native_filtered",
    "native.cpp": here / "native.cpp",
    "native": here / "native",
    "legacy_native.cpp": legacy / "native.cpp",
    "legacy_native": legacy / "native",
    "support_w14.tsv": support,
    "n131_positive.txt": legacy / "native_n131_positive.txt",
    "n131_trace_zero_control.txt": legacy / "native_n131_trace_zero_control.txt",
    "run_filtered.py": here / "run_filtered.py",
}
assert protocol["source_sha256"] == {
    name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()
}
rows = []
for case, variant in protocol["run_order"]:
    name = f"v2_n131_{case}_{variant}"
    input_path = legacy / f"native_n131_{case}.txt"
    executable = (legacy / "native" if variant == "legacy" else
                  here / ("native" if variant == "pair_join" else "native_filtered"))
    result_path = here / f"{name}.json"
    command = [str(executable), str(input_path), str(result_path)]
    if variant == "filtered_pair_join":
        command.append(str(support))
    command.extend([str(protocol["cap_seconds_per_run"]), str(protocol["rss_cap_bytes"])])
    started = time.monotonic_ns()
    try:
        process = subprocess.run(command, capture_output=True, text=True,
                                 timeout=protocol["cap_seconds_per_run"] + 5)
        status = "PROCESS_OK" if process.returncode == 0 else "PROCESS_FAILURE"
        returncode = process.returncode
        stdout, stderr = process.stdout, process.stderr
    except subprocess.TimeoutExpired as exc:
        status = "PARENT_TIMEOUT"
        returncode = None
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    parent_ns = time.monotonic_ns() - started
    (here / f"{name}.stdout.txt").write_text(stdout)
    (here / f"{name}.stderr.txt").write_text(stderr)
    native = json.loads(result_path.read_text()) if result_path.exists() else None
    rows.append({"name": name, "case": case, "variant": variant,
                 "status": status, "returncode": returncode,
                 "parent_ns": parent_ns, "native": native,
                 "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                 "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()})
    (here / "result_filtered.json").write_text(json.dumps({"rows": rows,
        "protocol_sha256": hashlib.sha256((here / "protocol_filtered.json").read_bytes()).hexdigest()},
        indent=2, sort_keys=True)+"\n")
    print(json.dumps({"name": name, "status": status,
        "native_status": native["status"] if native else None,
        "query_s": native["query_ns"]/1e9 if native else None,
        "setup_s": native["setup_ns"]/1e9 if native else None,
        "hit_count": len(native["hits"]) if native else None}, sort_keys=True), flush=True)
