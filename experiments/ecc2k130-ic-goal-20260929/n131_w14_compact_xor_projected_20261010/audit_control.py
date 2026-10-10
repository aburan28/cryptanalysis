#!/usr/bin/env sage -python
"""Replay a complete N131 witness through projected XCNF and reverse lift."""

import gzip
import hashlib
import json
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w14_compact_columns_20261010"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_extended_xcnf(path, assignment):
    """Check CNF and both native-XOR parities, including x- first tokens."""
    counts = {"cnf_clauses": 0, "xor_rows": 0}
    with Path(path).open() as stream:
        header = None
        for line in stream:
            if not line.strip() or line.startswith("c"):
                continue
            words = line.split()
            if words[0] == "p":
                assert header is None and words[:2] == ["p", "cnf"]
                header = (int(words[2]), int(words[3]))
                assert len(words) == 4
                continue
            assert header is not None and words[-1] == "0"
            if words[0].startswith("x"):
                first = words[0][2:] if words[0].startswith("x-") else words[0][1:]
                assert first.isdigit() and int(first) > 0
                literals = [int(first)] + [int(word) for word in words[1:-1]]
                parity = int(not words[0].startswith("x-"))
                for literal in literals:
                    assert 1 <= abs(literal) <= header[0]
                    parity ^= int(bool(assignment[abs(literal)])) ^ int(literal < 0)
                assert parity == 0
                counts["xor_rows"] += 1
            else:
                literals = [int(word) for word in words[:-1]]
                assert all(1 <= abs(value) <= header[0] for value in literals)
                assert any(bool(assignment[abs(value)]) == (value > 0)
                           for value in literals)
                counts["cnf_clauses"] += 1
    assert counts["cnf_clauses"] + counts["xor_rows"] == header[1]
    assert len(assignment) == header[0]
    return counts


def main():
    started = time.monotonic()
    protocol = json.loads((HERE / "protocol.json").read_text())
    projection = json.loads((HERE / "constructed/projection_receipt.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_COMPACT_N131_XOR_PROJECTION_AND_SEARCH"
    assert projection["status"] == "PASS"
    assert projection["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert projection["projection"]["source_sha256"]["variable_map.json"] == sha(
        HERE / "constructed/variable_map.json")
    assert projection["projection"]["source_sha256"]["lift_rows.jsonl"] == sha(
        HERE / "constructed/lift_rows.jsonl")
    import importlib.util
    spec = importlib.util.spec_from_file_location("n131_compact_projection_control", SOURCE / "experiment.py")
    compact = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compact)
    control = json.loads((SOURCE.parent / "n131_w14_coupled_sixpair_sat_20261010/control.json").read_text())
    circuit, meta, lifts = compact.run.formula_for(tuple(control["target_q"]))
    assert list(lifts[control["target_preimage_index"]]) == control["raw_sum"]
    initial = {}
    for row, mask in zip(meta["masks"], control["masks"]):
        initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
    for index, wire in enumerate(meta["flags"]):
        initial[wire] = int(index == control["target_preimage_index"])
    for row, value in zip(meta["middle"], control["middle_reciprocals"]):
        initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
    assert len(initial) == meta["primary_variables"]
    assignment = compact.run.witness_tools.complete_assignment(circuit, initial)
    with tempfile.TemporaryDirectory(prefix="n131_compact_projected_control_", dir="/private/tmp") as temp:
        original = Path(temp) / "original.xcnf"
        projected = Path(temp) / "projected.xcnf"
        circuit.write(original)
        assert sha(original) == protocol["input_uncompressed_sha256"]["constructed"]
        with gzip.open(HERE / "constructed/projected.xcnf.gz", "rb") as inp, projected.open("xb") as out:
            for block in iter(lambda: inp.read(1 << 20), b""):
                out.write(block)
        assert sha(projected) == projection["projection"]["source_result"]["source_sha256"]["projected_xcnf"]
        original_check = compact.run.base.check_xcnf(original, assignment)
        mapping = json.loads((HERE / "constructed/variable_map.json").read_text())
        assert mapping["free_private"] == []
        new_to_old = mapping["new_to_old"]
        assert len(new_to_old) == projection["projection"]["source_result"]["projected_variables"] + 1
        projected_values = {new: assignment[old] for new, old in enumerate(new_to_old) if new}
        projected_check = check_extended_xcnf(projected, projected_values)
        lifted = {old: assignment[old] for old in new_to_old[1:]}
        rows = [json.loads(line) for line in (HERE / "constructed/lift_rows.jsonl").open()]
        assert len(rows) == projection["projection"]["source_result"]["private_pivots"]
        for row in reversed(rows):
            pivot = row["pivot"]
            value = row["rhs"]
            for variable in row["variables"]:
                if variable != pivot:
                    value ^= lifted[variable]
            assert pivot not in lifted
            lifted[pivot] = value
        assert len(lifted) == circuit.next_var - 1
        assert all(lifted[variable] == assignment[variable] for variable in lifted)
        lifted_check = compact.run.base.check_xcnf(original, lifted)
    receipt = {
        "status": "PASS_PROJECTED_CONSTRUCTED_WITNESS",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "original_xcnf_check": original_check,
        "projected_xcnf_check": projected_check,
        "reverse_lifted_xcnf_check": lifted_check,
        "reverse_lifted_private_pivots": len(rows),
        "wall_seconds": time.monotonic() - started,
        "source_sha256": {
            "script": sha(Path(__file__)),
            "protocol": sha(HERE / "protocol.json"),
            "projection_receipt": sha(HERE / "constructed/projection_receipt.json"),
            "variable_map": sha(HERE / "constructed/variable_map.json"),
            "lift_rows": sha(HERE / "constructed/lift_rows.jsonl"),
            "checked_sage_runtime": sha(HERE / "sage_runtime_info.json"),
        },
    }
    with (HERE / "constructed/control_audit.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "reverse_lifted_private_pivots": len(rows),
                      "wall_seconds": receipt["wall_seconds"]}))


if __name__ == "__main__":
    main()
