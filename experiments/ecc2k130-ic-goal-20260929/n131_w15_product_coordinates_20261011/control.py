#!/usr/bin/env sage -python
"""Full constructed N131 six-pair control for product-coordinate source pairs."""

import gzip
import hashlib
import importlib.util
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
OLD = PARENT / "n131_w15_two_fixed_seeds_public_20261010"
SOURCE = PARENT / "n131_w15_coupled_sixpair_20261010"
RAW = Path("/private/tmp/n131_w15_product_coordinates_control_20261011.xcnf")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("product_coordinate_old", OLD / "run.py")
new = load("product_coordinate_new", HERE / "circuit.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked():
    protocol = json.loads((HERE / "control_protocol.json").read_text())
    paths = {"control": Path(__file__), "new_circuit": HERE / "circuit.py",
             "preflight": HERE / "preflight.py",
             "preflight_result": HERE / "result.json",
             "preflight_protocol": HERE / "protocol.json",
             "old_run": OLD / "run.py", "old_circuit": OLD / "circuit.py",
             "support": SOURCE / "support_w15.tsv",
             "runtime": HERE / "sage_runtime_info.json"}
    assert protocol["status"] == "FROZEN_PRODUCT_COORDINATE_COUPLED_CONTROL"
    assert protocol["source_sha256"] == {key: sha(path) for key, path in paths.items()}
    assert json.loads((HERE / "result.json").read_text())["status"] == \
        "PASS_EXACT_PRODUCT_COORDINATE_SOURCE_BIJECTION"
    return protocol


def canonical_masks(masks, fixed):
    out = list(masks)
    for i, part in enumerate(fixed):
        a = out[2*i]
        b = out[2*i+1]
        if a >> part["missing"] & 1:
            a, b = b, a
        assert a >> part["missing"] & 1 == 0
        assert a ^ b == new.SEEDS[i]
        out[2*i], out[2*i+1] = a, b
    return out


def assignment_for(circuit, meta, inp, selected):
    masks = canonical_masks(inp["masks"], meta["fixed"])
    initial = {}
    for i, part in enumerate(meta["fixed"]):
        mask = masks[2*i]
        code = sum((mask >> source_bit & 1) << j
                   for j, source_bit in enumerate(part["selected"]))
        initial.update({wire: code >> bit & 1
                        for bit, wire in enumerate(part["bits"])})
        values = {}
        for node, (bit, low, high) in part["graph"].items():
            child = high if code >> bit & 1 else low
            values[node] = bool(child) if child < 2 else values[child]
        assert values[part["root"]]
        initial.update({part["bdd_wires"][node]: int(value)
                        for node, value in values.items()})
    for row, mask in zip(meta["masks"][4:], masks[4:]):
        initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
    for index, wire in enumerate(meta["flags"]):
        initial[wire] = int(index == selected)
    for row, value in zip(meta["middle"], inp["middle_reciprocals"]):
        initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
    return masks, initial


def main():
    protocol = checked()
    if RAW.exists() or (HERE / "control_result.json").exists():
        raise FileExistsError("constructed control already exists")
    _, _, _, _, inp = old.base.run.source()
    selected = inp["target_preimage_index"]
    started = time.monotonic()
    previous = old.base.run.method
    old.base.run.method = new
    try:
        circuit, meta, raw = old.base.run.formula_for(tuple(inp["target_q"]))
    finally:
        old.base.run.method = previous
    assert list(raw[selected]) == inp["raw_sum"]
    # The trace rules are the same as the previous complete public circuit.
    _, field = old.raw_preimages(inp["target_q"])
    traces = [(field.inv(point[0]) & 1) ^
              ((field.inv(point[0]) >> 129) & 1) for point in raw]
    for index, value in enumerate(traces):
        if value:
            circuit.clauses.append(f"-{meta['flags'][index]} 0")
    for row in meta["middle"]:
        circuit.clauses.extend((f"-{row[0]} {row[129]} 0",
                                f"{row[0]} -{row[129]} 0"))
    circuit.write(RAW)
    try:
        masks, initial = assignment_for(circuit, meta, inp, selected)
        complete = old.base.run.witness_tools.complete_assignment(circuit, initial)
        check = old.base.run.base.check_xcnf(RAW, complete)
        group = old.lift.lift(masks, inp["middle_reciprocals"],
                              tuple(inp["target_q"]), selected)
        assert group["status"] == "GROUP_LIFT_FOUND"
        with (HERE / "control.xcnf.gz").open("xb") as out, RAW.open("rb") as source:
            with gzip.GzipFile(fileobj=out, mode="wb", compresslevel=6) as packed:
                for block in iter(lambda: source.read(1 << 20), b""):
                    packed.write(block)
        receipt = {"status": "PASS_PRODUCT_COORDINATE_COMPLETE_CONSTRUCTED_CONTROL",
                   "candidate_id": None, "target_count": 0,
                   "curve_id": protocol["curve_id"], "seed_codes": list(new.SEEDS),
                   "canonical_masks": masks, "formula": {
                       "variables": circuit.next_var-1,
                       "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
                       "and_gates": circuit.and_count, "raw_bytes": RAW.stat().st_size,
                       "raw_sha256": sha(RAW), "gzip_sha256": sha(HERE / "control.xcnf.gz")},
                   "bdd_nodes": [len(p["graph"]) for p in meta["fixed"]],
                   "valid_unordered_pairs": [p["valid_count"] for p in meta["fixed"]],
                   "bilinear_pair_ands": meta["bilinear_pair_ands"],
                   "xcnf_check": check, "group_lift": group,
                   "elapsed_seconds": time.monotonic()-started,
                   "source_sha256": protocol["source_sha256"]}
        with (HERE / "control_result.json").open("x") as out:
            json.dump(receipt, out, indent=2, sort_keys=True)
            out.write("\n")
        print(json.dumps({"status": receipt["status"],
                          "formula": receipt["formula"],
                          "group_lift": group["status"]}))
    finally:
        RAW.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
