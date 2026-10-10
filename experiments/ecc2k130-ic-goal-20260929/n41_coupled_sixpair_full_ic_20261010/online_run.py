#!/usr/bin/env python3
"""Deliver one held-out point after the native IC index and logs are warm."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "online_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_WARM_ONE_TARGET_RUN"
    for name, relative in (("atoms", "online_atoms.txt"), ("logs", "online_logs.txt"),
                           ("worker_source", "online_worker.cpp"),
                           ("worker_binary", "online_worker"),
                           ("factor_logs", "factor_logs.json"),
                           ("workload", "workload.json")):
        assert protocol["source_sha256"][name] == sha(HERE / relative)
    files = [HERE / name for name in ("online_hit.json", "online_native.json",
             "online_stdout.txt", "online_stderr.txt", "online_run.json")]
    assert all(not path.exists() for path in files)
    target = protocol["target"]
    command = [str(HERE / "online_worker"), str(HERE / "online_atoms.txt"),
               str(HERE / "online_logs.txt"), str(HERE / "online_hit.json"),
               str(HERE / "online_native.json"),
               str(protocol["max_accepted_probes"]),
               str(protocol["native_online_cap_seconds"]),
               str(protocol["rng_seed"])]
    started = time.perf_counter_ns()
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, bufsize=1) as process:
        ready = process.stdout.readline()
        if not ready.startswith("READY "):
            raise RuntimeError(f"worker did not reach warm barrier: {ready!r}")
        stdout_rest, stderr = process.communicate(f"{target[0]} {target[1]}\n",
                                                  timeout=protocol["parent_process_cap_seconds"])
        exit_code = process.returncode
    outer_wall_ns = time.perf_counter_ns() - started
    (HERE / "online_stdout.txt").write_text(ready + stdout_rest)
    (HERE / "online_stderr.txt").write_text(stderr)
    if not (HERE / "online_native.json").exists():
        raise RuntimeError(f"worker failed before receipt: exit={exit_code} stderr={stderr}")
    native = json.loads((HERE / "online_native.json").read_text())
    phases = native["exclusive_phase_ns"]
    phase_sum = sum(phases.values())
    assert phase_sum == native["online_ns"]
    assert native["peak_rss_bytes"] < protocol["rss_cap_bytes"]
    assert exit_code == 0 and native["status"] == "VERIFIED_SCALAR"
    assert native["scalar_group_replay_verified"] is True
    receipt = {
        "status": "NATIVE_WARM_ONE_TARGET_SCALAR_VERIFIED_PENDING_INDEPENDENT_SAGE",
        "curve_id": protocol["curve_id"], "target": target,
        "recovered_scalar": native["recovered_scalar"],
        "online_ns": native["online_ns"], "exclusive_phase_ns": phases,
        "phase_sum_matches": phase_sum == native["online_ns"],
        "target_independent_native_setup_ns": native["setup_ns"],
        "outer_process_wall_ns_excluded": outer_wall_ns,
        "accepted_probes": native["accepted_probes"],
        "peak_rss_bytes": native["peak_rss_bytes"], "workers": 1,
        "exit_code": exit_code,
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "protocol": HERE / "online_protocol.json",
            "native_result": HERE / "online_native.json",
            "hit": HERE / "online_hit.json",
            "stdout": HERE / "online_stdout.txt",
            "stderr": HERE / "online_stderr.txt",
        }.items()},
    }
    with (HERE / "online_run.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "scalar": receipt["recovered_scalar"],
                      "online_ns": receipt["online_ns"]}))


if __name__ == "__main__":
    main()
