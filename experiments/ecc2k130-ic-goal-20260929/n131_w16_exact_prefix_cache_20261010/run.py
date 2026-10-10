#!/usr/bin/env sage -python
"""Freeze and replay the byte-identical W16 source-prefix cache."""

import argparse
import gzip
import hashlib
import importlib.util
import json
import pickle
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n131_w16_fivepair_sat_gate_20261010"
WIDTH = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010"
CACHE = HERE / "source_prefix.pickle.gz"
R = 680564733841876926932320129493409985129
RSS_CAP = 4 * 1024**3


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("exact_prefix_previous_w16", OLD / "fivepair_run.py")
method = load("exact_prefix_method", HERE / "core.py")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(name, row):
    with (HERE / name).open("x") as stream:
        json.dump(row, stream, sort_keys=True, indent=2)
        stream.write("\n")


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


def sources():
    return {"runner": HERE / "run.py", "core": HERE / "core.py",
            "original_runner": OLD / "fivepair_run.py",
            "original_method": OLD / "fivepair_circuit.py",
            "original_control": OLD / "fivepair_control_result.json",
            "original_input": OLD / "fivepair_input.json",
            "width_support": WIDTH / "support_w16.tsv",
            "width_audit": WIDTH / "audit_result.json",
            "runtime": HERE / "sage_runtime_info.json"}


def freeze():
    original = json.loads((OLD / "fivepair_control_result.json").read_text())
    input_row = json.loads((OLD / "fivepair_input.json").read_text())
    assert original["status"] == "PASS_FULL_XCNF_AND_GROUP_FIVE_PAIR_CONTROL"
    assert input_row["status"] == "PASS_EXACT_CONSTRUCTED_W15_FIVE_PAIR_RESIDUAL"
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    row = {"status": "FROZEN_BEFORE_BYTE_IDENTICAL_W16_PREFIX_CACHE",
           "candidate_id": None, "curve_id": input_row["curve_id"],
           "target_law": "constructed signed-prefix exact residual control",
           "target_q": input_row["residual_target_q"],
           "fixed_first_pair_columns": input_row["first_pair_columns"],
           "expected_formula_sha256": original["formula"]["sha256"],
           "expected_formula_profile": {key: original["formula"][key] for key in
                                        ("variables", "cnf_clauses", "native_xor_rows")},
           "workers": 1, "source_precompute_cap_seconds": 120,
           "target_formula_cap_seconds": 60,
           "rss_cap_bytes": RSS_CAP,
           "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save("protocol.json", row)
    print(json.dumps({"status": row["status"]}))


def frozen():
    row = json.loads((HERE / "protocol.json").read_text())
    assert row["status"] == "FROZEN_BEFORE_BYTE_IDENTICAL_W16_PREFIX_CACHE"
    assert row["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    return row


def precompute():
    protocol = frozen()
    assert not CACHE.exists()
    started = time.monotonic_ns()
    columns, _, _, _, _ = old.experiment.run.source()
    circuit = old.experiment.run.base.KaratsubaCircuit(131, old.experiment.run.LOW_TERMS)
    state = method.prepare(circuit, columns)
    built = time.monotonic_ns()-started
    with gzip.open(CACHE, "xb", compresslevel=6) as stream:
        pickle.dump((circuit, state), stream, protocol=5)
    wall = time.monotonic_ns()-started
    peak = peak_rss()
    status = "PASS_W16_EXACT_SOURCE_PREFIX_CACHE"
    if wall > protocol["source_precompute_cap_seconds"]*10**9:
        status = "CENSORED_TIME"
    if peak > RSS_CAP:
        status = "CENSORED_MEMORY"
    row = {"status": status, "candidate_id": None,
           "source_prefix_sha256": sha(CACHE),
           "source_prefix_bytes": CACHE.stat().st_size,
           "variables": circuit.next_var-1,
           "cnf_clauses": len(circuit.clauses),
           "native_xor_rows": len(circuit.xors),
           "build_ns": built, "build_and_archive_ns": wall,
           "peak_rss_bytes": peak,
           "protocol_sha256": sha(HERE / "protocol.json"),
           "source_sha256": protocol["source_sha256"]}
    save("cache_result.json", row)
    print(json.dumps({"status": status, "build_seconds": built/1e9,
                      "clauses": row["cnf_clauses"], "cache_bytes": row["source_prefix_bytes"]}))
    if status != "PASS_W16_EXACT_SOURCE_PREFIX_CACHE":
        raise SystemExit(1)


def load_cache():
    cache = json.loads((HERE / "cache_result.json").read_text())
    assert cache["status"] == "PASS_W16_EXACT_SOURCE_PREFIX_CACHE"
    assert cache["source_prefix_sha256"] == sha(CACHE)
    with gzip.open(CACHE, "rb") as stream:
        circuit, state = pickle.load(stream)
        assert not stream.read(1)
    assert circuit.next_var-1 == cache["variables"]
    assert len(circuit.clauses) == cache["cnf_clauses"]
    return circuit, state


def compare():
    protocol = frozen()
    setup_started = time.monotonic_ns()
    circuit, state = load_cache()
    _, field, curve, source_w, _ = old.experiment.run.source()
    bases = old.experiment.run.bases(field, source_w)[2:]
    rotations = old.experiment.run.prior.ROTATIONS[2:]
    setup_ns = time.monotonic_ns()-setup_started
    started = time.monotonic_ns()
    raw_targets = old.experiment.run.prior.prior.old.target_preimages(
        curve, tuple(protocol["target_q"]))
    target_reciprocals = [field.inv(point[0]) for point in raw_targets]
    preimage_ns = time.monotonic_ns()-started
    meta = method.finish(circuit, state, field, bases, target_reciprocals,
                         rotations, old.experiment.run.prior.prior.old.method.frob,
                         protocol["fixed_first_pair_columns"])
    finish_ns = time.monotonic_ns()-started-preimage_ns
    formula = HERE / "control.xcnf"
    circuit.write(formula)
    write_ns = time.monotonic_ns()-started-preimage_ns-finish_ns
    digest = sha(formula)
    check_ns = time.monotonic_ns()-started-preimage_ns-finish_ns-write_ns
    total_ns = time.monotonic_ns()-started
    profile = {"variables": circuit.next_var-1,
               "cnf_clauses": len(circuit.clauses),
               "native_xor_rows": len(circuit.xors),
               "bytes": formula.stat().st_size, "sha256": digest}
    original = json.loads((OLD / "fivepair_control_result.json").read_text())
    assert profile == {key: original["formula"][key] for key in profile}
    assert digest == protocol["expected_formula_sha256"]
    assert total_ns <= protocol["target_formula_cap_seconds"]*10**9
    peak = peak_rss()
    assert peak <= RSS_CAP
    formula.unlink()
    row = {"status": "PASS_BYTE_IDENTICAL_W16_FORMULA_FROM_PREFIX_CACHE",
           "candidate_id": None, "formula": profile,
           "fixed_first_pair_columns": protocol["fixed_first_pair_columns"],
           "target_q": protocol["target_q"],
           "phase_ns": {"target_independent_cache_load_and_source": setup_ns,
                        "target_preimages": preimage_ns,
                        "target_suffix": finish_ns,
                        "formula_write": write_ns,
                        "formula_hash_check": check_ns,
                        "target_formula_total": total_ns},
           "peak_rss_bytes": peak,
           "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                             "cache_result": sha(HERE / "cache_result.json"),
                             "original_control": sha(OLD / "fivepair_control_result.json")},
           "meta": {key: meta[key] for key in
                    ("bilinear_pair_ands", "target_linear_ands",
                     "seed_equality_rows", "fixed_column_clauses")}}
    save("compare_result.json", row)
    print(json.dumps({"status": row["status"],
                      "target_formula_seconds": total_ns/1e9,
                      "target_suffix_seconds": finish_ns/1e9,
                      "peak_rss_bytes": peak}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "precompute", "compare"))
    {"freeze": freeze, "precompute": precompute,
     "compare": compare}[parser.parse_args().mode]()
