#!/usr/bin/env python3
"""Evaluate the frozen diagonal-atom circuit on an exact group control."""

import gzip
import json
import resource
import time
from pathlib import Path

import prepare

HERE = Path(__file__).resolve().parent
LOW_TERMS = [0, 1, 2, 13]
method = prepare.load("n131_w14_diagonal_sparse_circuit", HERE / "circuit.py")


def bases(field, source_w):
    return [[prepare.old.method.frob(field, w, rotation) for w in source_w]
            for rotation in prepare.ROTATIONS]


def formula_for(q):
    _, _, columns, field, curve, source_w, _ = prepare.old.source()
    lifts = prepare.old.target_preimages(curve, q)
    target_reciprocals = [field.inv(point[0]) for point in lifts]
    instance = prepare.old.old.old.base.KaratsubaCircuit(131, LOW_TERMS)
    meta = method.build(instance, bases(field, source_w), columns,
                        target_reciprocals)
    return instance, meta, lifts


def compress(source, destination):
    with source.open("rb") as inp, gzip.open(destination, "xb", compresslevel=6) as out:
        while block := inp.read(1 << 20):
            out.write(block)


def main():
    protocol = json.loads((HERE / "protocol_v2.json").read_text())
    control = json.loads((HERE / "control.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_CONSTRUCTED_FORMULA_V2"
    for key in ("prepare", "circuit", "profile", "query", "control"):
        path = HERE / (key + ".json" if key == "control" else key + ".py")
        assert protocol["source_sha256"][key] == prepare.sha(path)
    assert not (HERE / "profile.json").exists()
    started = time.monotonic()
    instance, meta, lifts = formula_for(tuple(control["target_q"]))
    build_s = time.monotonic() - started
    assert tuple(control["raw_sum"]) == lifts[control["target_preimage_index"]]
    formula = Path("/private/tmp/n131_w14_diagonal_sparse_constructed.xcnf")
    if formula.exists():
        raise FileExistsError(formula)
    instance.write(formula)
    initial = {}
    for row, mask in zip(meta["masks"], control["masks"]):
        initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
    for index, wire in enumerate(meta["flags"]):
        initial[wire] = int(index == control["target_preimage_index"])
    for row, value in zip(meta["middle"], control["middle_reciprocals"]):
        initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
    assert len(initial) == meta["primary_variables"]
    assignment = prepare.old.old.old.witness_tools.complete_assignment(instance, initial)
    check = prepare.old.old.old.base.check_xcnf(formula, assignment)
    check_s = time.monotonic() - started - build_s
    raw_bytes, raw_sha = formula.stat().st_size, prepare.sha(formula)
    compress(formula, HERE / "constructed.xcnf.gz")
    formula.unlink()
    elapsed = time.monotonic() - started
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    status = "PASS_FULL_FORMULA_CONSTRUCTED_GROUP_WITNESS"
    if elapsed > protocol["construction_wall_cap_seconds"] or rss > protocol["rss_cap_bytes"]:
        status = "RESOURCE_GATE_EXCEEDED"
    receipt = {"status": status, "curve_id": protocol["curve_id"],
               "candidate_id": None, "control_target_q": control["target_q"],
               "full_xcnf_assignment_check": check,
               "formula": {"variables": instance.next_var - 1,
                           "clauses": len(instance.clauses),
                           "xor_rows": len(instance.xors),
                           "and_gates": instance.and_count,
                           "duplicate_column_clauses": meta["duplicate_column_clauses"],
                           "uncompressed_bytes": raw_bytes,
                           "uncompressed_sha256": raw_sha,
                           "gzip_sha256": prepare.sha(HERE / "constructed.xcnf.gz")},
               "phase_seconds": {"build": build_s, "assignment_check": check_s,
                                 "compress_and_total": elapsed},
               "peak_rss_bytes": rss,
               "protocol_sha256": prepare.sha(HERE / "protocol_v2.json")}
    prepare.save(HERE / "profile.json", receipt)
    print(json.dumps({"status": status, "formula": receipt["formula"],
                      "elapsed_seconds": elapsed, "peak_rss_bytes": rss}))


if __name__ == "__main__":
    main()
