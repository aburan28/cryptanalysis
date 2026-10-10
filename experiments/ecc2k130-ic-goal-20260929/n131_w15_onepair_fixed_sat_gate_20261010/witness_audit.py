#!/usr/bin/env sage -python
"""Check the known complete W15 assignment against both pinned XCNFs."""

import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
W15 = BASE / "n131_w15_coupled_sixpair_20261010"
ORIGINAL = BASE / "n131_w14_coupled_sixpair_sat_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    experiment = load("w15_pin_witness_experiment", W15 / "experiment.py")
    control = json.loads((ORIGINAL / "control.json").read_text())
    mask_protocol = json.loads((HERE / "protocol.json").read_text())
    point_protocol = json.loads((HERE / "point_protocol.json").read_text())
    circuit, meta, _ = experiment.run.formula_for(tuple(control["target_q"]))
    assert circuit.next_var - 1 == 121787
    assert meta["masks"][0] == list(range(1, 16))
    assert meta["masks"][1] == list(range(16, 31))
    assert meta["middle"][0] == point_protocol["first_pair_output_wire_ids"]
    initial = {}
    for row, mask in zip(meta["masks"], control["masks"]):
        initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
    for index, wire in enumerate(meta["flags"]):
        initial[wire] = int(index == control["target_preimage_index"])
    for row, value in zip(meta["middle"], control["middle_reciprocals"]):
        initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
    assert len(initial) == meta["primary_variables"]
    assignment = experiment.run.witness_tools.complete_assignment(circuit, initial)
    for literal in mask_protocol["pin_literals"] + point_protocol[
            "additional_pin_literals"]:
        assert assignment[abs(literal)] == int(literal > 0)
    checked = {}
    for label, source in (("masks", HERE / "pinned.xcnf.gz"),
                          ("masks_and_point", HERE / "point_pinned.xcnf.gz")):
        temp = Path(f"/private/tmp/w15_pin_witness_{label}_{os.getpid()}.xcnf")
        try:
            with gzip.open(source, "rb") as inp, temp.open("xb") as out:
                shutil.copyfileobj(inp, out)
            checked[label] = experiment.run.base.check_xcnf(temp, assignment)
        finally:
            temp.unlink(missing_ok=True)
    assert checked["masks"] == {"cnf_clauses": 436755, "xor_rows": 43272}
    assert checked["masks_and_point"] == {"cnf_clauses": 436886, "xor_rows": 43272}
    receipt = {
        "status": "PASS_COMPLETE_W15_WITNESS_BOTH_PINNED_FORMULAS",
        "target_q": control["target_q"],
        "pinned_masks": control["masks"][:2],
        "first_pair_reciprocal": control["middle_reciprocals"][0],
        "full_assignment_variables": len(assignment),
        "checked": checked,
        "source_sha256": {"script": sha(__file__),
                          "mask_protocol": sha(HERE / "protocol.json"),
                          "point_protocol": sha(HERE / "point_protocol.json"),
                          "mask_formula_gzip": sha(HERE / "pinned.xcnf.gz"),
                          "point_formula_gzip": sha(HERE / "point_pinned.xcnf.gz"),
                          "original_control": sha(ORIGINAL / "control.json"),
                          "w15_experiment": sha(W15 / "experiment.py"),
                          "runtime": sha(HERE / "sage_runtime_info.json")},
    }
    with (HERE / "witness_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "checked": checked}))


if __name__ == "__main__":
    main()
