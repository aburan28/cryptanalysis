"""Run each frozen algebraic inverse once and preserve exact terminal rows."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


protocol = json.loads((HERE / "native_protocol.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_NATIVE_ROTATED_FOUR_ATOM_SCANS"
assert protocol["source_sha256"] == {name: sha(HERE / name) for name in
    ("native.cpp", "native", "rotated_terms.hpp", "resultant.json",
     "control_result.json", "run_native.py", "prepare_native.py")}
assert protocol["input_sha256"] == {name: sha(HERE / name)
                                    for name in protocol["input_sha256"]}
for label in ("n41_positive", "n41_field_control", "n131_positive", "n131_field_control"):
    input_path = HERE / f"input_{label}.txt"
    output_path = HERE / f"native_{label}.json"
    receipt_path = HERE / f"receipt_{label}.json"
    assert not output_path.exists() and not receipt_path.exists()
    command = [str(HERE / "native"), str(input_path), str(output_path),
               str(protocol["native_query_cap_seconds_each"]), str(protocol["rss_cap_bytes"])]
    started = time.perf_counter_ns()
    try:
        run = subprocess.run(command, capture_output=True, text=True,
                             timeout=protocol["parent_cap_seconds_each"])
        parent_wall_ns = time.perf_counter_ns() - started
        status = "PROCESS_EXIT" if run.returncode else "PROCESS_COMPLETE"
        stdout, stderr, exit_code = run.stdout, run.stderr, run.returncode
    except subprocess.TimeoutExpired as error:
        parent_wall_ns = time.perf_counter_ns() - started
        status = "PARENT_TIMEOUT"
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        exit_code = None
    receipt = {"status": status, "label": label,
               "input_sha256": sha(input_path), "binary_sha256": sha(HERE / "native"),
               "protocol_sha256": sha(HERE / "native_protocol.json"),
               "command": command, "exit_code": exit_code,
               "parent_wall_ns": parent_wall_ns,
               "stdout": stdout, "stderr": stderr,
               "result_sha256": sha(output_path) if output_path.exists() else None}
    with receipt_path.open("x") as output:
        json.dump(receipt, output, sort_keys=True, indent=2)
        output.write("\n")
    print(label, status, stdout.strip(), stderr.strip())
    if status != "PROCESS_COMPLETE":
        break
