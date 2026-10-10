#!/usr/bin/env python3
"""Run the frozen one-target rho reference and retain its complete outcome."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "rho_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_SAME_POINT_RHO"
    assert protocol["source_sha256"]["input"] == sha(HERE / "rho_input.txt")
    assert protocol["source_sha256"]["binary"] == sha(HERE / "rho_r3")
    outputs = [HERE / name for name in ("rho_native.json", "rho_stdout.txt",
               "rho_stderr.txt", "rho_run.json")]
    assert all(not path.exists() for path in outputs)
    command = [str(HERE / "rho_r3"), str(HERE / "rho_input.txt"),
               str(HERE / "rho_native.json")]
    start = time.perf_counter_ns()
    try:
        completed = subprocess.run(command, text=True, capture_output=True,
                                   timeout=130, check=False)
        elapsed = time.perf_counter_ns() - start
        status = "COMPLETED"
        stdout, stderr = completed.stdout, completed.stderr
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as error:
        elapsed = time.perf_counter_ns() - start
        status = "PARENT_TIMEOUT"
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        exit_code = None
    (HERE / "rho_stdout.txt").write_text(stdout)
    (HERE / "rho_stderr.txt").write_text(stderr)
    native = json.loads((HERE / "rho_native.json").read_text()) if (HERE / "rho_native.json").exists() else None
    if native is not None:
        phases = native["exclusive_stage_phase_ns"]
        assert sum(phases.values()) == native["rho_online_wall_ns"]
        assert native["target"] == protocol["target"]
    receipt = {
        "status": native["status"] if native is not None else status,
        "curve_id": protocol["curve_id"], "target": protocol["target"],
        "target_count": 1, "workers": 1, "exit_code": exit_code,
        "rho_online_ns": native["rho_online_wall_ns"] if native is not None else None,
        "exclusive_phase_ns": native["exclusive_stage_phase_ns"] if native is not None else None,
        "recovered_scalar": native["recovered_scalar"] if native is not None else None,
        "outer_process_wall_ns_excluded": elapsed,
        "peak_rss_bytes": native["peak_rss_bytes"] if native is not None else None,
        "walk_steps": native["walk_steps"] if native is not None else None,
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "protocol": HERE / "rho_protocol.json",
            "stdout": HERE / "rho_stdout.txt", "stderr": HERE / "rho_stderr.txt",
        }.items()},
    }
    if native is not None:
        receipt["source_sha256"]["native"] = sha(HERE / "rho_native.json")
    with (HERE / "rho_run.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "rho_online_ns": receipt["rho_online_ns"],
                      "walk_steps": receipt["walk_steps"]}))


if __name__ == "__main__":
    main()
