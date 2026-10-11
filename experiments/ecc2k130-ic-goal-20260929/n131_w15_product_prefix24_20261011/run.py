#!/usr/bin/env sage -python
"""Complete-control and public-point gates for exact W15 prefix support."""

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
PREVIOUS = PARENT / "n131_w15_product_coordinates_20261011"
PAIR_ROOTS = PARENT / "n131_w15_pair_output_prefix_gate_20261010" / "pair_roots.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RAW = Path("/private/tmp/n131_w15_product_prefix24_20261011.xcnf")
CAP = 600.0
RSS_CAP = 4 * 1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1",
         "--random=20261010", "--maxconfl=20000000"]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load("prefix24_previous_control", PREVIOUS / "control_v2.py")
gate = load("prefix24_gate", HERE / "prefix_gate.py")


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    with path.open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def sources():
    return {"runner": Path(__file__), "gate": HERE / "prefix_gate.py",
            "projection": HERE / "projection.json",
            "projection_protocol": HERE / "projection_protocol.json",
            "pair_roots": PAIR_ROOTS,
            "previous_circuit": PREVIOUS / "circuit.py",
            "previous_control_source": PREVIOUS / "control_v2.py",
            "previous_control": PREVIOUS / "control_result.json",
            "previous_public": PREVIOUS / "public_result.json",
            "previous_public_protocol": PREVIOUS / "public_protocol.json",
            "two_seed_protocol": PARENT / "n131_w15_two_fixed_seeds_public_20261010" / "protocol.json",
            "runtime": HERE / "sage_runtime_info.json", "solver": SOLVER}


def checked():
    protocol = json.loads((HERE / "run_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_N131_W15_PREFIX24_PUBLIC_GATE"
    assert protocol["source_sha256"] == {key: sha(path) for key, path in sources().items()}
    assert json.loads((HERE / "projection.json").read_text())["status"] == \
        "PASS_EXACT_W15_PREFIX24_PROJECTION"
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    return protocol


def formula(q):
    previous = prior.old.base.run.method
    prior.old.base.run.method = prior.new
    try:
        circuit, meta, raw = prior.old.base.run.formula_for(tuple(q))
    finally:
        prior.old.base.run.method = previous
    _, field = prior.old.raw_preimages(q)
    traces = [(field.inv(point[0]) & 1) ^
              ((field.inv(point[0]) >> 129) & 1) for point in raw]
    for index, value in enumerate(traces):
        if value:
            circuit.clauses.append(f"-{meta['flags'][index]} 0")
    for row in meta["middle"]:
        circuit.clauses.extend((f"-{row[0]} {row[129]} 0",
                                f"{row[0]} -{row[129]} 0"))
    graphs = gate.load_graphs()
    source_clauses = []
    wires = []
    for i, item in enumerate(graphs):
        encoded, clauses = gate.emit(circuit, meta["middle"][i], item)
        wires.append(encoded)
        source_clauses.append(clauses)
    assert source_clauses == [33084, 33457]
    return circuit, meta, raw, traces, graphs, wires


def profile(circuit):
    return {"variables": circuit.next_var-1, "clauses": len(circuit.clauses),
            "xor_rows": len(circuit.xors), "and_gates": circuit.and_count,
            "raw_bytes": RAW.stat().st_size, "raw_sha256": sha(RAW)}


def compress(destination):
    with destination.open("xb") as out, RAW.open("rb") as source:
        with gzip.GzipFile(fileobj=out, mode="wb", compresslevel=6) as packed:
            for block in iter(lambda: source.read(1 << 20), b""):
                packed.write(block)
    return sha(destination)


def control():
    protocol = checked()
    assert not RAW.exists() and not (HERE / "control_result.json").exists()
    _, _, _, _, inp = prior.old.base.run.source()
    started = time.monotonic()
    circuit, meta, raw, traces, graphs, wires = formula(inp["target_q"])
    assert traces == protocol["constructed_raw_preimage_traces"]
    selected = inp["target_preimage_index"]
    assert list(raw[selected]) == inp["raw_sum"]
    circuit.write(RAW)
    try:
        masks, initial = prior.assignment_for(circuit, meta, inp, selected)
        for i, (item, encoded) in enumerate(zip(graphs, wires)):
            initial.update(gate.assignment(
                item, encoded, inp["middle_reciprocals"][i]))
        completed = prior.old.base.run.witness_tools.complete_assignment(
            circuit, initial)
        check = prior.old.base.run.base.check_xcnf(RAW, completed)
        group = prior.old.lift.lift(masks, inp["middle_reciprocals"],
                                    tuple(inp["target_q"]), selected)
        assert group["status"] == "GROUP_LIFT_FOUND"
        form = profile(circuit)
        form["gzip_sha256"] = compress(HERE / "control.xcnf.gz")
        record = {"status": "PASS_PREFIX24_COMPLETE_CONSTRUCTED_CONTROL",
                  "curve_id": protocol["curve_id"], "candidate_id": None,
                  "target_count": 0, "target_q": inp["target_q"],
                  "formula": form, "xcnf_check": check,
                  "group_lift": group, "canonical_masks": masks,
                  "source_clauses": [33084, 33457],
                  "elapsed_seconds": time.monotonic()-started,
                  "source_sha256": protocol["source_sha256"]}
        save(HERE / "control_result.json", record)
        print(json.dumps({"status": record["status"],
                          "formula": form, "group_lift": group["status"]}))
    finally:
        RAW.unlink(missing_ok=True)


def query():
    protocol = checked()
    control_record = json.loads((HERE / "control_result.json").read_text())
    assert control_record["status"] == "PASS_PREFIX24_COMPLETE_CONSTRUCTED_CONTROL"
    assert not RAW.exists() and not (HERE / "public_result.json").exists()
    started = time.monotonic()
    circuit, meta, raw, traces, graphs, wires = formula(protocol["target_q"])
    assert traces == protocol["public_raw_preimage_traces"]
    circuit.write(RAW)
    try:
        form = profile(circuit)
        assert form["clauses"] == control_record["formula"]["clauses"]
        assert form["and_gates"] == control_record["formula"]["and_gates"]
        build_seconds = time.monotonic()-started
        assert build_seconds < CAP-30
        form["gzip_sha256"] = compress(HERE / "system.xcnf.gz")
        parent = psutil.Process()
        peak = parent.memory_info().rss
        command = [str(SOLVER), *FLAGS,
                   f"--maxtime={max(1, int(CAP-build_seconds-8))}", str(RAW)]
        with (HERE / "solver.stdout.txt").open("x") as stdout, \
             (HERE / "solver.stderr.txt").open("x") as stderr:
            child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                     start_new_session=True)
            process = psutil.Process(child.pid)
            search_started = time.monotonic()
            stop = None
            while child.poll() is None:
                try:
                    peak = max(peak, parent.memory_info().rss+process.memory_info().rss)
                except psutil.NoSuchProcess:
                    pass
                if peak >= RSS_CAP:
                    stop = "RSS_CAP"
                elif time.monotonic()-started >= CAP-2:
                    stop = "PARENT_WALL_CAP"
                if stop:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait()
                    break
                time.sleep(0.2)
            search_seconds = time.monotonic()-search_started
        lines = (HERE / "solver.stdout.txt").read_text(errors="replace").splitlines()
        statuses = [line for line in lines if line.startswith("s ")]
        models = [line for line in lines if line.startswith("v ")]
        if "s SATISFIABLE" in statuses:
            status = "MODEL_REQUIRES_INDEPENDENT_REPLAY"
        elif peak >= RSS_CAP:
            status = "CENSORED_RSS"
        elif not statuses:
            status = "CENSORED_TIME"
        else:
            status = "SOLVER_TERMINAL_OTHER"
        record = {"status": status, "curve_id": protocol["curve_id"],
                  "candidate_id": None, "target_count": 1,
                  "target_q": protocol["target_q"], "formula": form,
                  "build_seconds": build_seconds, "solver_seconds": search_seconds,
                  "construction_plus_search_seconds": time.monotonic()-started,
                  "sampled_peak_combined_rss_bytes": peak,
                  "solver_command": command, "solver_returncode": child.returncode,
                  "stop_reason": stop, "solver_status_lines": statuses,
                  "model_line_count": len(models),
                  "solver_stdout_sha256": sha(HERE / "solver.stdout.txt"),
                  "solver_stderr_sha256": sha(HERE / "solver.stderr.txt"),
                  "source_sha256": protocol["source_sha256"]}
        save(HERE / "public_result.json", record)
        print(json.dumps({key: record[key] for key in (
            "status", "build_seconds", "solver_seconds",
            "construction_plus_search_seconds", "sampled_peak_combined_rss_bytes",
            "model_line_count")}))
    finally:
        RAW.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("control", "query"))
    args = parser.parse_args()
    (control if args.mode == "control" else query)()
