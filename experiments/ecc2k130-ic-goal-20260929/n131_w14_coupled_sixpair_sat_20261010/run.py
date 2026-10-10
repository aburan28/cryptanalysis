#!/usr/bin/env python3
"""Frozen N131 W14 six-pair control with coupled seed sums."""

import argparse
import gzip
import hashlib
import importlib.util
import json
import resource
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE
PAIR = HERE.parent / "n131_w14_diagonal_pair_inverse_20261010"
LOW_TERMS = [0, 1, 2, 13]
R = 680564733841876926932320129493409985129


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load("n131_w14_coupled_sixpair_preparation", HERE / "prepare.py")
method = load("n131_w14_coupled_sixpair_circuit", HERE / "circuit.py")
base = prior.prior.old.old.old.base
witness_tools = prior.prior.old.old.old.witness_tools


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sources():
    return {"run": Path(__file__), "circuit": HERE / "circuit.py",
            "sage_runtime_info": HERE / "sage_runtime_info.json",
            "prepare": HERE / "prepare.py",
            "control": HERE / "control.json",
            "sage_audit": HERE / "sage_audit.json",
            "sparse_prepare": prior.SPARSE / "prepare.py",
            "source_support": HERE.parent / "n131_w14_ten_source_gate_20261009/support_w14.tsv",
            "pair_inputs": PAIR / "inputs.json",
            "pair_sage_audit": PAIR / "sage_audit.json",
            "base": Path(base.__file__),
            "witness": Path(witness_tools.__file__)}


def source():
    _, _, columns, field, curve, source_w, _ = prior.prior.old.source()
    control = json.loads((HERE / "control.json").read_text())
    audit = json.loads((HERE / "sage_audit.json").read_text())
    assert audit["status"] == "PASS_INDEPENDENT_SAGE_N131_COUPLED_SIXPAIR_GROUP_REPLAY"
    assert control["curve_id"] == audit["curve_id"]
    assert len(columns) == 8220 and len(set(columns.values())) == 8160
    return columns, field, curve, source_w, control


def bases(field, source_w):
    return [[prior.prior.old.method.frob(field, w, rotation) for w in source_w]
            for rotation in prior.ROTATIONS]


def formula_for(q):
    columns, field, curve, source_w, _ = source()
    lifts = prior.prior.old.target_preimages(curve, q)
    target_reciprocals = [field.inv(point[0]) for point in lifts]
    circuit = base.KaratsubaCircuit(131, LOW_TERMS)
    meta = method.build(circuit, field, bases(field, source_w), columns,
                        target_reciprocals, prior.ROTATIONS,
                        prior.prior.old.method.frob)
    return circuit, meta, lifts


def pair_identity_check(field, source_w):
    panel = json.loads((PAIR / "inputs.json").read_text())
    assert panel["status"] == "FROZEN"
    checked = 0
    for case in panel["cases"]:
        if case["kind"] != "positive":
            continue
        a = prior.prior.old.coordinate(source_w, case["a"])
        b = prior.prior.old.coordinate(source_w, case["b"])
        z = case["z"]
        p = field.mul(a, b)
        pz = field.mul(p, z)
        square = lambda x: field.mul(x, x)
        assert square(a ^ b) ^ square(z) ^ pz ^ square(pz) == 0
        checked += 1
    assert checked == 32
    return checked


def freeze():
    _, field, _, source_w, control = source()
    checks = pair_identity_check(field, source_w)
    record = {"status": "FROZEN_BEFORE_COUPLED_SIXPAIR_CONSTRUCTED_FORMULA",
              "candidate_id": None, "curve_id": control["curve_id"],
              "actual_projected_factor_base_B": 98640,
              "folded_columns_K": 8160,
              "summands": 12, "rotations": prior.ROTATIONS,
              "shared_seed_pair_indices": [[2,3],[4,5]],
              "pair_identity_checks": checks,
              "construction_wall_cap_seconds": 120,
              "rss_cap_bytes": 4*1024**3,
              "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"],
                      "pair_identity_checks": checks}))


def compress(source, destination):
    with source.open("rb") as inp, gzip.open(destination, "xb", compresslevel=6) as out:
        while block := inp.read(1 << 20):
            out.write(block)


def profile():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_COUPLED_SIXPAIR_CONSTRUCTED_FORMULA"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    _, _, _, _, control = source()
    started = time.monotonic()
    circuit, meta, lifts = formula_for(tuple(control["target_q"]))
    build_seconds = time.monotonic() - started
    assert tuple(control["raw_sum"]) == lifts[control["target_preimage_index"]]
    formula = Path("/private/tmp/n131_w14_coupled_sixpair_constructed.xcnf")
    if formula.exists():
        raise FileExistsError(formula)
    circuit.write(formula)
    initial = {}
    for row, mask in zip(meta["masks"], control["masks"]):
        initial.update({wire: mask >> i & 1 for i, wire in enumerate(row)})
    for i, wire in enumerate(meta["flags"]):
        initial[wire] = int(i == control["target_preimage_index"])
    for row, value in zip(meta["middle"], control["middle_reciprocals"]):
        initial.update({wire: value >> i & 1 for i, wire in enumerate(row)})
    assert len(initial) == meta["primary_variables"]
    assignment = witness_tools.complete_assignment(circuit, initial)
    check = base.check_xcnf(formula, assignment)
    check_seconds = time.monotonic() - started - build_seconds
    raw_bytes, raw_sha = formula.stat().st_size, sha(formula)
    compress(formula, HERE / "constructed.xcnf.gz")
    formula.unlink()
    elapsed = time.monotonic() - started
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    status = "PASS_FULL_COUPLED_SIXPAIR_FORMULA_CONSTRUCTED_GROUP_WITNESS"
    if elapsed > protocol["construction_wall_cap_seconds"] or rss > protocol["rss_cap_bytes"]:
        status = "RESOURCE_GATE_EXCEEDED"
    result = {"status": status, "candidate_id": None,
              "curve_id": protocol["curve_id"], "control_target_q": control["target_q"],
              "full_xcnf_assignment_check": check,
              "formula": {"variables": circuit.next_var-1,
                          "clauses": len(circuit.clauses),
                          "xor_rows": len(circuit.xors),
                          "and_gates": circuit.and_count,
                          "bilinear_pair_ands": meta["bilinear_pair_ands"],
                          "target_linear_ands": meta["target_linear_ands"],
                          "seed_equality_rows": meta["seed_equality_rows"],
                          "duplicate_column_clauses": meta["duplicate_column_clauses"],
                          "uncompressed_bytes": raw_bytes,
                          "uncompressed_sha256": raw_sha,
                          "gzip_sha256": sha(HERE / "constructed.xcnf.gz")},
              "phase_seconds": {"build": build_seconds,
                                "assignment_check": check_seconds,
                                "total": elapsed},
              "peak_rss_bytes": rss,
              "protocol_sha256": sha(HERE / "protocol.json")}
    save(HERE / "profile.json", result)
    print(json.dumps({"status": status, "formula": result["formula"],
                      "total_seconds": elapsed, "peak_rss_bytes": rss}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "profile"))
    {"freeze": freeze, "profile": profile}[parser.parse_args().mode]()
