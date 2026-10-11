"""Freeze and bound the native N41 six-pair public-point group join."""

import hashlib
import json
import psutil
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n41_w7_entropy_cubic_20261011/w8"
CAP = 120
RSS = 4 * 1024**3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def source_paths():
    return {"runner": HERE / "run.py", "native_source": HERE / "join.cpp",
            "native_binary": HERE / "join", "input": HERE / "join_input.tsv",
            "preparer": HERE / "prepare_sage.py",
            "preparation_protocol": HERE / "prepare_protocol.json",
            "preparation_result": HERE / "prepare_result.json",
            "runtime": HERE / "sage_runtime_info.json",
            "geometry": BASE / "geometry.json", "fixture": BASE / "fixture.json"}


def freeze():
    prepared = json.loads((HERE / "prepare_result.json").read_text())
    assert prepared["status"] == "PASS_N41_W8_SIX_PAIR_LIST_PREPARATION"
    assert prepared["input_sha256"] == sha(HERE / "join_input.tsv")
    protocol = json.loads((HERE / "prepare_protocol.json").read_text())
    assert protocol["join_wall_cap_seconds"] == CAP
    assert protocol["combined_rss_cap_bytes"] == RSS
    compiler = subprocess.check_output(["/usr/bin/clang++", "--version"], text=True)
    record = {"status": "FROZEN_N41_W8_SIX_PAIR_NATIVE_JOIN",
              "candidate_id": None, "curve_id": protocol["curve_id"],
              "public_target_transported": protocol["public_target_transported"],
              "raw_target_preimages": protocol["raw_target_preimages"],
              "seed_mask": protocol["seed_mask"], "rotations": protocol["rotations"],
              "eligible_pair_edges": prepared["edge_count"],
              "signed_pair_states_per_slot": prepared["state_count_per_slot"],
              "worker_count": 1, "parent_wall_cap_seconds": CAP,
              "combined_rss_cap_bytes": RSS,
              "compiler": compiler.splitlines()[0],
              "compile_command": "/usr/bin/clang++ -O3 -std=c++17 -Wall -Wextra -pedantic join.cpp -o join",
              "source_sha256": {name: sha(path) for name, path in source_paths().items()}}
    save(HERE / "protocol.json", record)
    print(record["status"])


def query():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_N41_W8_SIX_PAIR_NATIVE_JOIN"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in source_paths().items()}
    outpath, errpath = HERE / "join.stdout.txt", HERE / "join.stderr.txt"
    assert not outpath.exists() and not errpath.exists()
    parent = psutil.Process()
    started = time.monotonic()
    peak = 0
    stop = None
    with outpath.open("x") as stdout, errpath.open("x") as stderr:
        child = subprocess.Popen([str(HERE / "join"), str(HERE / "join_input.tsv")],
                                 stdout=stdout, stderr=stderr)
        process = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                combined = parent.memory_info().rss + process.memory_info().rss
            except psutil.NoSuchProcess:
                combined = parent.memory_info().rss
            peak = max(peak, combined)
            if combined > RSS:
                stop = "RSS_CAP"
                child.kill()
                break
            if time.monotonic() - started > CAP:
                stop = "WALL_CAP"
                child.kill()
                break
            time.sleep(0.05)
        exit_code = child.wait()
    wall = time.monotonic() - started
    lines = outpath.read_text().splitlines()
    hits = [line for line in lines if line.startswith("HIT ")]
    if stop:
        status = "CENSORED_TIME" if stop == "WALL_CAP" else "CENSORED_RSS"
    elif exit_code != 0 or not lines or lines[0].split()[0] != "CHECK_PASS":
        status = "PRODUCER_FAILURE"
    elif len(hits) == 1:
        status = "HIT_PENDING_SAGE_REPLAY"
    elif any(line.startswith("MISS_COMPLETE ") for line in lines):
        status = "COMPLETE_RESTRICTED_SOURCE_MISS"
    else:
        status = "PRODUCER_FAILURE"
    result = {"status": status, "candidate_id": None,
              "target_count": 1, "curve_id": protocol["curve_id"],
              "public_target_transported": protocol["public_target_transported"],
              "raw_target_preimages": protocol["raw_target_preimages"],
              "worker_count": 1, "wall_seconds_exploratory": wall,
              "parent_wall_cap_seconds": CAP, "combined_peak_rss_bytes_sampled": peak,
              "stop_reason": stop, "exit_code": exit_code,
              "preflight_group_checks_passed": bool(lines and lines[0].startswith("CHECK_PASS 128 ")),
              "phase_lines": [line for line in lines if line.startswith(("LEFT_DONE", "RIGHT_DONE", "TARGET_DONE"))],
              "hit_lines": hits, "stdout_sha256": sha(outpath),
              "stderr_sha256": sha(errpath),
              "protocol_sha256": sha(HERE / "protocol.json"),
              "parent_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    save(HERE / "query_result.json", result)
    print(json.dumps({"status": status, "wall_seconds": wall, "peak_rss": peak,
                      "hit_lines": hits}), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "query"):
        raise SystemExit("usage: run.py freeze|query")
    {"freeze": freeze, "query": query}[sys.argv[1]]()
