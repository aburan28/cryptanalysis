#!/usr/bin/env python3
"""Exact N131 W14 ten-source frame formula and constructed control."""
import argparse
import hashlib
import importlib.util
import json
import random
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SUPPORT = ROOT / "n131_w14_ten_source_gate_20261009"
OLD = ROOT / "n41_w5_ten_source_gate_20261010"
R = 680564733841876926932320129493409985129
LOW_TERMS = [0, 1, 2, 13]
CAP_SECONDS = 120
RSS_CAP = 4 * 1024**3


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("n41_w5_gate_for_field_and_witness", OLD / "run.py")
method = load("n131_w14_frame_circuit", HERE / "circuit.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def source():
    protocol = json.loads((SUPPORT / "support_protocol.json").read_text())
    audit = json.loads((SUPPORT / "sage_support_audit.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_ENUMERATION"
    assert audit["status"] == "PASS_FULL_MASKS_ORBITS_AND_TEN_WINDOW_BASE"
    assert audit["actual_subgroup_factor_base_points_B"] == 164400
    assert audit["folded_columns_K"] == 8160
    columns = {}
    with (SUPPORT / "support_w14.tsv").open() as rows:
        for row in rows:
            mask, canonical = map(int, row.split())
            columns[mask] = canonical
    assert len(columns) == 8220 and len(set(columns.values())) == 8160
    field = old.old.base.Field(131, LOW_TERMS)
    curve = old.old.base.Curve(field, 0)
    source_w = [1 << bit for bit in range(1, 15)]
    source_u = [old.old.base.half_trace(field, w) if hasattr(old.old.base, "half_trace")
                else half_trace(field, w) for w in source_w]
    assert all(field.mul(u, u) ^ u == w for u, w in zip(source_u, source_w))
    return protocol, audit, columns, field, curve, source_w, source_u


def half_trace(field, value):
    result = 0
    for _ in range(66):
        result ^= value
        value = field.mul(value, value)
        value = field.mul(value, value)
    return result


def coordinate(basis, mask):
    result = 0
    for i, value in enumerate(basis):
        if mask >> i & 1:
            result ^= value
    return result


def transformed(field, point):
    assert point is not None and point[0] not in (0, 1)
    return field.inv(point[0] ^ 1)


def chain(curve, leaves):
    middle = [curve.add(leaves[2 * i], leaves[2 * i + 1])
              for i in range(5)]
    middle.extend((curve.add(middle[0], middle[1]),
                   curve.add(middle[2], middle[3])))
    middle.append(curve.add(middle[5], middle[6]))
    return middle, curve.add(middle[7], middle[4])


def target_preimages(curve, q):
    core = curve.mul(pow(4, -1, R), q)
    torsion = (1, 0)
    current = None
    targets = []
    for _ in range(4):
        raw = curve.add(core, current)
        assert raw is not None and curve.mul(4, raw) == q
        targets.append(raw)
        current = curve.add(current, torsion)
    assert current is None and len(set(targets)) == 4
    return targets


def construct():
    protocol, audit, columns, field, curve, source_w, source_u = source()
    rotations = protocol["rotations"]
    rng = random.Random(202610102145)
    masks_by_column = {}
    for mask, canonical in columns.items():
        masks_by_column.setdefault(canonical, []).append(mask)
    keys = sorted(masks_by_column)
    for attempt in range(1000):
        picked = rng.sample(keys, 10)
        masks = [rng.choice(masks_by_column[key]) for key in picked]
        signs = [rng.randrange(2) for _ in masks]
        leaves = []
        for mask, sign, rotation in zip(masks, signs, rotations):
            w = coordinate(source_w, mask)
            u = coordinate(source_u, mask)
            assert field.mul(u, u) ^ u == w
            x = 1 ^ field.inv(u)
            options = old.old.base.points_with_x(curve, x)
            assert len(options) == 2
            point = tuple(method.frob(field, value, rotation)
                          for value in options[sign])
            leaves.append(point)
        middle, total = chain(curve, leaves)
        if any(p is None or p[0] in (0, 1)
               for p in [*leaves, *middle, total]):
            continue
        q = curve.mul(4, total)
        if q is None or curve.mul(R, q) is not None:
            continue
        targets = target_preimages(curve, q)
        assert total in targets
        return {"status": "CONSTRUCTED_TEN_SOURCE_CONTROL",
                "seed": 202610102145, "attempt": attempt,
                "masks": masks, "signs": signs,
                "folded_columns": picked, "raw_leaves": [list(p) for p in leaves],
                "middle_u": [transformed(field, p) for p in middle],
                "raw_sum": list(total), "target_q": list(q),
                "target_preimage_index": targets.index(total)}
    raise RuntimeError("no regular constructed target in deterministic budget")


def freeze():
    control = construct()
    save(HERE / "control.json", control)
    protocol, audit, _, _, _, _, _ = source()
    sources = {"runner": Path(__file__), "circuit": HERE / "circuit.py",
               "support_protocol": SUPPORT / "support_protocol.json",
               "support_audit": SUPPORT / "sage_support_audit.json",
               "support_masks": SUPPORT / "support_w14.tsv",
               "old_runner": OLD / "run.py"}
    record = {"status": "FROZEN_BEFORE_FULL_FORMULA",
              "candidate_id": None, "curve_id": protocol["curve_id"],
              "source_dimension": 14, "summands": 10,
              "rotations": protocol["rotations"],
              "rational_source_masks": 8220,
              "actual_factor_base_points_B": audit["actual_subgroup_factor_base_points_B"],
              "effective_folded_columns_K": audit["folded_columns_K"],
              "construction_cap_seconds": CAP_SECONDS,
              "rss_cap_bytes": RSS_CAP,
              "control_sha256": sha(HERE / "control.json"),
              "source_sha256": {name: sha(path) for name, path in sources.items()}}
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"],
                      "control_attempt": control["attempt"]}))


def profile():
    record = json.loads((HERE / "protocol.json").read_text())
    control = json.loads((HERE / "control.json").read_text())
    assert record["control_sha256"] == sha(HERE / "control.json")
    assert record["source_sha256"]["runner"] == sha(__file__)
    assert record["source_sha256"]["circuit"] == sha(HERE / "circuit.py")
    protocol, audit, columns, field, curve, source_w, source_u = source()
    q = tuple(control["target_q"])
    assert curve.mul(R, q) is None
    targets = target_preimages(curve, q)
    assert tuple(control["raw_sum"]) == targets[control["target_preimage_index"]]
    target_us = [transformed(field, point) for point in targets]
    circuit = old.old.base.KaratsubaCircuit(131, LOW_TERMS)
    started = time.monotonic()
    meta = method.build(circuit, field, source_w, source_u,
                        protocol["rotations"], columns, columns, target_us)
    build_seconds = time.monotonic() - started
    formula = HERE / "constructed_full.xcnf"
    circuit.write(formula)
    initial = {}
    for row, mask in zip(meta["masks"], control["masks"]):
        initial.update({wire: mask >> i & 1 for i, wire in enumerate(row)})
    for i, wire in enumerate(meta["flags"]):
        initial[wire] = int(i == control["target_preimage_index"])
    for row, value in zip(meta["middle"], control["middle_u"]):
        initial.update({wire: value >> i & 1 for i, wire in enumerate(row)})
    assert len(initial) == meta["primary_variables"]
    assignment = old.old.witness_tools.complete_assignment(circuit, initial)
    check = old.old.base.check_xcnf(formula, assignment)
    elapsed = time.monotonic() - started
    rss = psutil.Process().memory_info().rss
    status = "PASS_FULL_FORMULA_CONSTRUCTED_GROUP_WITNESS"
    if elapsed > CAP_SECONDS or rss > RSS_CAP:
        status = "RESOURCE_GATE_EXCEEDED"
    result = {"status": status, "candidate_id": None,
              "curve_id": protocol["curve_id"], "target_count": 1,
              "target_q": control["target_q"],
              "formula": {"variables": circuit.next_var - 1,
                          "clauses": len(circuit.clauses),
                          "xor_rows": len(circuit.xors),
                          "and_gates": circuit.and_count,
                          "duplicate_column_clauses": meta["duplicate_column_clauses"],
                          "bytes": formula.stat().st_size,
                          "sha256": sha(formula)},
              "full_xcnf_assignment_check": check,
              "formula_build_seconds": build_seconds,
              "profile_wall_seconds": elapsed,
              "sampled_python_rss_bytes": rss,
              "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                "control": sha(HERE / "control.json"),
                                "formula": sha(formula)}}
    save(HERE / "profile.json", result)
    print(json.dumps({"status": status, "formula": result["formula"],
                      "wall_seconds": elapsed, "rss_bytes": rss}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "profile"))
    {"freeze": freeze, "profile": profile}[parser.parse_args().mode]()
