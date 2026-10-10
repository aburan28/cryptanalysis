#!/usr/bin/env python3
"""Run the frozen fresh point through warmed IC and same-point rho."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_FRESH_ONE_TARGET_PAIR"
    for name, path in {
        "fixture": HERE / "fixture.json", "rho_input": HERE / "rho_input.txt",
        "atoms": ROOT / "online_atoms.txt", "logs": ROOT / "online_logs.txt",
        "ic_worker_source": ROOT / "online_worker.cpp",
        "ic_worker_binary": ROOT / "online_worker",
        "rho_source": ROOT.parent / "n41_signed_frobenius_rho_r3.cpp",
        "rho_binary": ROOT / "rho_r3", "factor_logs": ROOT / "factor_logs.json",
        "factor_audit": ROOT / "sage_audit.json",
        "sage_runtime": ROOT / "sage_runtime_info.json",
    }.items():
        assert protocol["source_sha256"][name] == sha(path), name
    assert all(not (HERE / name).exists() for name in (
        "ic_hit.json", "ic_native.json", "ic_stdout.txt", "ic_stderr.txt",
        "ic_run.json", "rho_native.json", "rho_stdout.txt", "rho_stderr.txt",
        "rho_run.json"))
    target = protocol["target"]
    command = [str(ROOT / "online_worker"), str(ROOT / "online_atoms.txt"),
               str(ROOT / "online_logs.txt"), str(HERE / "ic_hit.json"),
               str(HERE / "ic_native.json"),
               str(protocol["ic_max_accepted_probes"]),
               str(protocol["ic_online_cap_seconds"]), str(protocol["ic_rng_seed"])]
    start = time.perf_counter_ns()
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, bufsize=1) as process:
        ready = process.stdout.readline()
        if not ready.startswith("READY "):
            raise RuntimeError(f"IC warm setup failed: {ready!r}")
        rest, stderr = process.communicate(f"{target[0]} {target[1]}\n", timeout=30)
        exit_code = process.returncode
    elapsed = time.perf_counter_ns() - start
    (HERE / "ic_stdout.txt").write_text(ready + rest)
    (HERE / "ic_stderr.txt").write_text(stderr)
    native = json.loads((HERE / "ic_native.json").read_text())
    assert sum(native["exclusive_phase_ns"].values()) == native["online_ns"]
    save(HERE / "ic_run.json", {
        "status": native["status"], "target": target, "workers": 1,
        "exit_code": exit_code, "outer_process_wall_ns_excluded": elapsed,
        "online_ns": native["online_ns"], "accepted_probes": native["accepted_probes"],
        "recovered_scalar": native["recovered_scalar"],
        "source_sha256": {name: sha(path) for name, path in {
            "runner": __file__, "protocol": HERE / "protocol.json",
            "native": HERE / "ic_native.json", "hit": HERE / "ic_hit.json",
            "stdout": HERE / "ic_stdout.txt", "stderr": HERE / "ic_stderr.txt",
        }.items()},
    })
    print(json.dumps({"method": "IC", "status": native["status"],
                      "online_ns": native["online_ns"],
                      "accepted_probes": native["accepted_probes"]}), flush=True)
    rho_command = [str(ROOT / "rho_r3"), str(HERE / "rho_input.txt"),
                   str(HERE / "rho_native.json")]
    start = time.perf_counter_ns()
    try:
        completed = subprocess.run(rho_command, text=True, capture_output=True,
                                   timeout=protocol["parent_cap_seconds"], check=False)
        rho_elapsed = time.perf_counter_ns() - start
        rho_status, rho_stdout, rho_stderr, rho_exit = (
            "COMPLETED", completed.stdout, completed.stderr, completed.returncode)
    except subprocess.TimeoutExpired as error:
        rho_elapsed = time.perf_counter_ns() - start
        rho_status, rho_exit = "PARENT_TIMEOUT", None
        rho_stdout, rho_stderr = error.stdout or "", error.stderr or ""
        if isinstance(rho_stdout, bytes):
            rho_stdout = rho_stdout.decode(errors="replace")
        if isinstance(rho_stderr, bytes):
            rho_stderr = rho_stderr.decode(errors="replace")
    (HERE / "rho_stdout.txt").write_text(rho_stdout)
    (HERE / "rho_stderr.txt").write_text(rho_stderr)
    rho = json.loads((HERE / "rho_native.json").read_text()) if (HERE / "rho_native.json").exists() else None
    if rho is not None:
        assert rho["target"] == target
        assert sum(rho["exclusive_stage_phase_ns"].values()) == rho["rho_online_wall_ns"]
    save(HERE / "rho_run.json", {
        "status": rho["status"] if rho is not None else rho_status,
        "target": target, "workers": 1, "exit_code": rho_exit,
        "outer_process_wall_ns_excluded": rho_elapsed,
        "online_ns": rho["rho_online_wall_ns"] if rho is not None else None,
        "walk_steps": rho["walk_steps"] if rho is not None else None,
        "recovered_scalar": rho["recovered_scalar"] if rho is not None else None,
        "source_sha256": {name: sha(path) for name, path in {
            "runner": __file__, "protocol": HERE / "protocol.json",
            "stdout": HERE / "rho_stdout.txt", "stderr": HERE / "rho_stderr.txt",
            **({"native": HERE / "rho_native.json"} if rho is not None else {}),
        }.items()},
    })
    print(json.dumps({"method": "rho", "status": rho["status"] if rho is not None else rho_status,
                      "online_ns": rho["rho_online_wall_ns"] if rho is not None else None,
                      "walk_steps": rho["walk_steps"] if rho is not None else None}))


if __name__ == "__main__":
    main()
