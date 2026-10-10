#!/usr/bin/env sage -python
"""Matched native W14 same-seed four-atom inverse correctness and cost panel."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

import psutil

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n131_w14_coupled_fouratom_inverse_20261010"
BUILD = ["c++", "-O3", "-std=c++17", "-DNDEBUG", "-Wall", "-Wextra"]
RUN_ORDER = [
    ("baseline", "positive", 1), ("batch", "positive", 1),
    ("batch", "control", 1), ("baseline", "control", 1),
    ("baseline", "control", 2), ("batch", "control", 2),
    ("batch", "positive", 2), ("baseline", "positive", 2),
]
RSS_CAP = 4 * 1024**3
PARENT_CAP = 120
INTERNAL_CAP = 118


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    with Path(path).open("x") as sink:
        json.dump(value, sink, indent=2, sort_keys=True)
        sink.write("\n")


def sources():
    paths = {"runner": Path(__file__),
             "runtime": HERE / "sage_runtime_info.json",
             "baseline_source": HERE / "baseline.cpp",
             "batch_source": HERE / "batch.cpp",
             "terms_header": HERE / "resultant_terms.hpp",
             "baseline_binary": HERE / "baseline",
             "batch_binary": HERE / "batch",
             "prior_source": PRIOR / "native.cpp",
             "prior_header": PRIOR / "resultant_terms.hpp",
             "prior_sage_audit": PRIOR / "sage_audit.json",
             "prior_positive": PRIOR / "native_run_n131_positive" / "result.json",
             "prior_control": PRIOR / "native_run_n131_trace_zero_control" / "result.json"}
    for case in ("positive", "trace_zero_control"):
        paths[f"n131_input_{case}"] = PRIOR / f"native_n131_{case}.txt"
        paths[f"n41_input_{case}"] = PRIOR / f"native_n41_{case}.txt"
    for case in ("positive", "control"):
        for variant in ("baseline", "batch"):
            paths[f"n41_{variant}_{case}"] = HERE / f"n41_{variant}_{case}.json"
    return paths


def core(value):
    return {name: value[name] for name in
            ("status", "field_degree", "source_dimension", "seed_sum",
             "output_z", "total_product_states", "processed_product_states", "hits")}


def freeze():
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    assert sha(HERE / "baseline.cpp") == sha(PRIOR / "native.cpp")
    assert sha(HERE / "resultant_terms.hpp") == sha(PRIOR / "resultant_terms.hpp")
    for case in ("positive", "control"):
        first = json.loads((HERE / f"n41_baseline_{case}.json").read_text())
        second = json.loads((HERE / f"n41_batch_{case}.json").read_text())
        assert core(first) == core(second)
        assert first["status"] == "COMPLETE_ALGEBRAIC_SCAN"
        assert len(first["hits"]) == (2 if case == "positive" else 0)
        assert second["field_inverse_calls"] == 1
    assert json.loads((PRIOR / "sage_audit.json").read_text())["status"].startswith("PASS")
    compiler = subprocess.run(["c++", "--version"], check=True,
                              capture_output=True, text=True).stdout.splitlines()[0]
    record = {
        "status": "FROZEN_BEFORE_MATCHED_N131_FOUR_ATOM_BATCH_INVERSION_PANEL",
        "candidate_id": None, "curve_id": "EC1N131Ckb1heb5f1998f20b",
        "target_law": "fixed-seed constructed four-atom output and independent trace-zero control",
        "source_dimension": 14, "product_states": 8192,
        "workers": 1, "parent_cap_seconds_per_run": PARENT_CAP,
        "internal_cap_seconds_per_run": INTERNAL_CAP,
        "rss_cap_bytes": RSS_CAP,
        "build_command_baseline": [*BUILD, "baseline.cpp", "-o", "baseline"],
        "build_command_batch": [*BUILD, "batch.cpp", "-o", "batch"],
        "compiler_version_first_line": compiler,
        "run_order": [{"variant": variant, "case": case, "repetition": repetition}
                      for variant, case, repetition in RUN_ORDER],
        "source_sha256": {name: sha(path) for name, path in sources().items()},
    }
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"], "run_count": len(RUN_ORDER)}))


def run_all():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_MATCHED_N131_FOUR_ATOM_BATCH_INVERSION_PANEL"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    folder = HERE / "runs"
    folder.mkdir(exist_ok=False)
    rows = []
    for variant, case, repetition in RUN_ORDER:
        label = f"{variant}_{case}_r{repetition}"
        run_dir = folder / label
        run_dir.mkdir()
        source = PRIOR / f"native_n131_{'positive' if case == 'positive' else 'trace_zero_control'}.txt"
        binary = HERE / variant
        result_path = run_dir / "producer.json"
        stdout_path = run_dir / "stdout.txt"
        stderr_path = run_dir / "stderr.txt"
        command = [str(binary), str(source), str(result_path), str(INTERNAL_CAP),
                   str(RSS_CAP)]
        started = time.monotonic_ns()
        peak_rss = 0
        stop_reason = None
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                     start_new_session=True)
            process = psutil.Process(child.pid)
            while child.poll() is None:
                try:
                    peak_rss = max(peak_rss, process.memory_info().rss)
                except psutil.NoSuchProcess:
                    pass
                if peak_rss >= RSS_CAP:
                    stop_reason = "RSS_CAP"
                elif time.monotonic_ns() - started >= PARENT_CAP * 10**9:
                    stop_reason = "PARENT_WALL_CAP"
                if stop_reason:
                    child.terminate()
                    break
                time.sleep(.05)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                stop_reason = (stop_reason or "DRAIN_TIMEOUT") + "_KILLED"
        wall_ns = time.monotonic_ns() - started
        producer = json.loads(result_path.read_text()) if result_path.exists() else None
        if stop_reason or child.returncode != 0 or producer is None:
            status = "OOM" if stop_reason == "RSS_CAP" else "PRODUCER_FAILURE_OR_CAP"
        else:
            status = producer["status"]
        receipt = {
            "status": status, "candidate_id": None, "field_degree": 131,
            "variant": variant, "case": case, "repetition": repetition,
            "command": command, "exit_code": child.returncode,
            "stop_reason": stop_reason, "parent_wall_ns": wall_ns,
            "sampled_peak_rss_bytes": peak_rss,
            "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                              "input": sha(source), "binary": sha(binary),
                              "stdout": sha(stdout_path), "stderr": sha(stderr_path),
                              "producer": sha(result_path) if result_path.exists() else None},
        }
        save(run_dir / "receipt.json", receipt)
        rows.append({"label": label, "status": status,
                     "query_ns": producer["query_ns"] if producer else None,
                     "hits": len(producer["hits"]) if producer else None,
                     "wall_ns": wall_ns})
        print(json.dumps(rows[-1]), flush=True)
    for case in ("positive", "control"):
        prior_label = "positive" if case == "positive" else "trace_zero_control"
        reference = json.loads((PRIOR / f"native_run_n131_{prior_label}" /
                                "result.json").read_text())
        for variant in ("baseline", "batch"):
            for repetition in (1, 2):
                label = f"{variant}_{case}_r{repetition}"
                result = json.loads((folder / label / "producer.json").read_text())
                assert core(result) == core(reference)
                assert result["status"] == "COMPLETE_ALGEBRAIC_SCAN"
                if variant == "batch":
                    assert result["evaluated_product_states"] == 8192
                    assert result["nonconstant_resultants"] > 0
                    assert result["field_inverse_calls"] == 1
    save(HERE / "result.json", {
        "status": "PASS_MATCHED_N131_FOUR_ATOM_BATCH_INVERSION_PANEL",
        "candidate_id": None, "field_degree": 131,
        "run_order": rows,
        "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                          "prior_sage_audit": sha(PRIOR / "sage_audit.json")},
    })
    print(json.dumps({"status": "PASS_MATCHED_N131_FOUR_ATOM_BATCH_INVERSION_PANEL",
                      "run_count": len(rows)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "run"))
    {"freeze": freeze, "run": run_all}[parser.parse_args().mode]()
