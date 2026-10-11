#!/usr/bin/env sage -python
"""Capped unpinned ECC2K-130 public-point search with product coordinates."""

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
OLD = PARENT / "n131_w15_two_fixed_seeds_public_20261010"
SOURCE = PARENT / "n131_w15_coupled_sixpair_20261010"
RAW = Path("/private/tmp/n131_w15_product_coordinates_public_20261011.xcnf")
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
CAP = 600.0
RSS_CAP = 4 * 1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1",
         "--random=20261010", "--maxconfl=20000000"]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("product_coordinate_public_old", OLD / "run.py")
new = load("product_coordinate_public_new", HERE / "circuit.py")


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


def checked():
    protocol = json.loads((HERE / "public_protocol.json").read_text())
    paths = {"public": Path(__file__), "new_circuit": HERE / "circuit.py",
             "preflight_result": HERE / "result.json",
             "control_v2": HERE / "control_v2.py",
             "control_result": HERE / "control_result.json",
             "control_protocol": HERE / "control_protocol_v2.json",
             "old_run": OLD / "run.py", "old_circuit": OLD / "circuit.py",
             "published_input": SOURCE / "query_protocol.json",
             "support": SOURCE / "support_w15.tsv",
             "runtime": HERE / "sage_runtime_info.json", "solver": SOLVER}
    assert protocol["status"] == "FROZEN_PRODUCT_COORDINATE_PUBLIC_QUERY"
    assert protocol["source_sha256"] == {key: sha(path) for key, path in paths.items()}
    assert protocol["target_q"] == json.loads(paths["published_input"].read_text())["target_q"]
    assert json.loads(paths["control_result"].read_text())["status"] == \
        "PASS_PRODUCT_COORDINATE_COMPLETE_CONSTRUCTED_CONTROL"
    return protocol


def main():
    protocol = checked()
    if RAW.exists() or (HERE / "public_result.json").exists():
        raise FileExistsError("public query already exists")
    started = time.monotonic()
    previous = old.base.run.method
    old.base.run.method = new
    try:
        circuit, meta, raw = old.base.run.formula_for(tuple(protocol["target_q"]))
    finally:
        old.base.run.method = previous
    _, field = old.raw_preimages(protocol["target_q"])
    traces = [(field.inv(point[0]) & 1) ^
              ((field.inv(point[0]) >> 129) & 1) for point in raw]
    assert traces == protocol["raw_preimage_traces"]
    for index, value in enumerate(traces):
        if value:
            circuit.clauses.append(f"-{meta['flags'][index]} 0")
    for row in meta["middle"]:
        circuit.clauses.extend((f"-{row[0]} {row[129]} 0",
                                f"{row[0]} -{row[129]} 0"))
    circuit.write(RAW)
    try:
        form = {"variables": circuit.next_var-1,
                "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
                "and_gates": circuit.and_count, "raw_bytes": RAW.stat().st_size,
                "raw_sha256": sha(RAW)}
        control_form = json.loads((HERE / "control_result.json").read_text())["formula"]
        assert form["and_gates"] == control_form["and_gates"] == 72641
        assert form["clauses"] == control_form["clauses"] == 363985
        build_seconds = time.monotonic()-started
        assert build_seconds < CAP-30
        with (HERE / "system.xcnf.gz").open("xb") as out, RAW.open("rb") as source:
            with gzip.GzipFile(fileobj=out, mode="wb", compresslevel=6) as packed:
                for block in iter(lambda: source.read(1 << 20), b""):
                    packed.write(block)
        form["gzip_sha256"] = sha(HERE / "system.xcnf.gz")
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
                    peak = max(peak, parent.memory_info().rss + process.memory_info().rss)
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
        log = (HERE / "solver.stdout.txt").read_text(errors="replace")
        lines = log.splitlines()
        sat_lines = [line for line in lines if line.startswith("s ")]
        model_lines = [line for line in lines if line.startswith("v ")]
        if any(line.strip() == "s SATISFIABLE" for line in sat_lines):
            status = "MODEL_REQUIRES_INDEPENDENT_REPLAY"
        elif peak >= RSS_CAP:
            status = "CENSORED_RSS"
        else:
            status = "CENSORED_TIME" if stop or not sat_lines else "SOLVER_TERMINAL_OTHER"
        receipt = {"status": status, "candidate_id": None,
                   "curve_id": protocol["curve_id"], "target_count": 1,
                   "target_q": protocol["target_q"], "formula": form,
                   "build_seconds": build_seconds,
                   "solver_seconds": search_seconds,
                   "construction_plus_search_seconds": time.monotonic()-started,
                   "sampled_peak_combined_rss_bytes": peak,
                   "solver_command": command, "solver_returncode": child.returncode,
                   "stop_reason": stop, "solver_status_lines": sat_lines,
                   "model_line_count": len(model_lines),
                   "solver_stdout_sha256": sha(HERE / "solver.stdout.txt"),
                   "solver_stderr_sha256": sha(HERE / "solver.stderr.txt"),
                   "source_sha256": protocol["source_sha256"]}
        save(HERE / "public_result.json", receipt)
        print(json.dumps({key: receipt[key] for key in (
            "status", "build_seconds", "solver_seconds",
            "construction_plus_search_seconds", "sampled_peak_combined_rss_bytes",
            "model_line_count")}))
    finally:
        RAW.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
