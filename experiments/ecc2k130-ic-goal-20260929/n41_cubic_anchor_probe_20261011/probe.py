"""Bounded one-leaf conditioning screen for the frozen N41 public cubic query."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE.parent / "n41_transport_cubic_s8_20261011"
sys.path.insert(0, str(UPSTREAM))
import run as prior  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def inputs():
    fixture = prior.fixture()
    source = sorted(map(int, fixture["mask_columns"]))
    assert len(source) == 32
    return fixture, source


def freeze():
    fixture, source = inputs()
    record = {
        "status": "FROZEN_BEFORE_N41_ANCHOR_SCREEN",
        "candidate_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "public_point": fixture["public_target_original"],
        "target_preimages": fixture["raw_target_reciprocals"],
        "source_masks": source,
        "control_anchor": fixture["known_masks"][0],
        "public_screen_anchors": source[:8],
        "control_cap_seconds": 30,
        "screen_cap_seconds_each": 5,
        "parent_margin_seconds": 2,
        "rss_cap_bytes": 4 * 1024**3,
        "workers": 1,
        "source_sha256": {"probe.py": sha(__file__),
                          "upstream_run.py": sha(UPSTREAM / "run.py"),
                          "upstream_circuit.py": sha(UPSTREAM / "circuit.py"),
                          "upstream_fixture.json": sha(UPSTREAM / "fixture.json"),
                          "solver": sha(prior.SOLVER)},
    }
    save_new(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"], "screen_anchors": source[:8]}))


def checked_protocol():
    record = json.loads((HERE / "protocol.json").read_text())
    assert record["source_sha256"] == {
        "probe.py": sha(__file__),
        "upstream_run.py": sha(UPSTREAM / "run.py"),
        "upstream_circuit.py": sha(UPSTREAM / "circuit.py"),
        "upstream_fixture.json": sha(UPSTREAM / "fixture.json"),
        "solver": sha(prior.SOLVER),
    }
    assert record["status"] == "FROZEN_BEFORE_N41_ANCHOR_SCREEN"
    return record


def run_case(label, anchor, cap, protocol):
    beginning = time.monotonic()
    circuit, metadata, construction = prior.build(protocol["target_preimages"])
    assert len(metadata["masks"][0]) == 6
    for bit, wire in enumerate(metadata["masks"][0]):
        circuit.clauses.append(f"{wire if anchor >> bit & 1 else -wire} 0")
    formula = HERE / f"{label}.xcnf"
    circuit.write(formula)
    formula_sha = sha(formula)
    variables = circuit.next_var - 1
    clauses = len(circuit.clauses)
    xors = len(circuit.xors)
    del circuit
    out = HERE / f"{label}.stdout.txt"
    err = HERE / f"{label}.stderr.txt"
    argv = [str(prior.SOLVER), "--threads=1", "--xor=0", "--printsol=1",
            "--random=20261011", f"--maxtime={cap}", str(formula)]
    solver_start = time.monotonic()
    with out.open("xb") as stdout, err.open("xb") as stderr:
        process = subprocess.Popen(argv, stdout=stdout, stderr=stderr)
        worker, parent = psutil.Process(process.pid), psutil.Process()
        peak, stop_reason = 0, None
        while process.poll() is None:
            try:
                rss = worker.memory_info().rss + parent.memory_info().rss
            except psutil.NoSuchProcess:
                rss = parent.memory_info().rss
            peak = max(peak, rss)
            if rss > protocol["rss_cap_bytes"]:
                stop_reason = "RSS_CAP"
            elif time.monotonic() - solver_start > cap + protocol["parent_margin_seconds"]:
                stop_reason = "PARENT_CAP"
            if stop_reason:
                process.kill()
                break
            time.sleep(0.05)
        returncode = process.wait()
    solver_seconds = time.monotonic() - solver_start
    output = out.read_bytes()
    if b"s SATISFIABLE" in output:
        status = "SAT_PENDING_GROUP_REPLAY"
    elif b"s UNSATISFIABLE" in output:
        status = "UNSAT_ANCHORED_FORMULA"
    elif stop_reason == "RSS_CAP":
        status = "RESOURCE_GATE_EXCEEDED"
    else:
        status = "BOUNDED_UNKNOWN"
    record = {"label": label, "anchor": anchor, "status": status,
              "stop_reason": stop_reason, "returncode": returncode,
              "formula_sha256": formula_sha, "formula_bytes": formula.stat().st_size,
              "variables": variables, "clauses": clauses, "xor_rows": xors,
              "construction_seconds": construction,
              "solver_seconds": solver_seconds,
              "wall_seconds": time.monotonic() - beginning,
              "peak_combined_rss_bytes": peak,
              "stdout_sha256": sha(out), "stderr_sha256": sha(err),
              "solver_argv": argv[:-1] + ["<bound-formula-path>"]}
    save_new(HERE / f"{label}.result.json", record)
    print(json.dumps({"label": label, "anchor": anchor, "status": status,
                      "solver_seconds": solver_seconds}), flush=True)
    return record


def run():
    protocol = checked_protocol()
    assert not any(HERE.glob("*.result.json"))
    result = [run_case("control", protocol["control_anchor"],
                       protocol["control_cap_seconds"], protocol)]
    if result[-1]["status"] != "SAT_PENDING_GROUP_REPLAY":
        save_new(HERE / "screen_result.json", {
            "status": "STOP_AFTER_CONTROL", "cases": result,
            "protocol_sha256": sha(HERE / "protocol.json")})
        return
    for index, anchor in enumerate(protocol["public_screen_anchors"]):
        result.append(run_case(f"public_{index:02d}", anchor,
                               protocol["screen_cap_seconds_each"], protocol))
        if result[-1]["status"] == "SAT_PENDING_GROUP_REPLAY":
            break
    save_new(HERE / "screen_result.json", {
        "status": "SCREEN_COMPLETE", "cases": result,
        "protocol_sha256": sha(HERE / "protocol.json")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "run"))
    mode = parser.parse_args().mode
    freeze() if mode == "freeze" else run()
