#!/usr/bin/env python3
"""Evaluate the complete N83 XCNF circuit on the frozen planted witness."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import time

from run_n83_w34_sat_branch import Curve, GF2n, Point, build, verify_model


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "n83_w34_sat_protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(public_path: Path, private_path: Path, out: Path) -> None:
    public_path, private_path, out = (path.resolve() for path in
                                      (public_path, private_path, out))
    if not out.is_dir() or not (out / "sage_runtime_info.json").is_file():
        raise FileNotFoundError("save checked Sage runtime beside the audit first")
    if (out / "report.json").exists():
        raise FileExistsError("known-witness audit output is immutable")
    started = time.perf_counter_ns()
    protocol = json.loads(PROTOCOL.read_text())
    public = json.loads(public_path.read_text())
    private = json.loads(private_path.read_text())
    assert private["public_input_sha256"] == sha(public_path)
    assert public["curve_id"] == private["curve_id"] == protocol["curve_id"]
    masks = [entry["mask"] for entry in private["selected"]]
    assert [len(mask) for mask in masks] == [3, 3, 4, 4, 4]
    target_x = int(private["raw_sum"][0])
    assert target_x in {int(item["x"]) for item in public["planted"]["raw_target_fiber"]}

    modulus = (1 << 83) | (1 << 7) | (1 << 4) | (1 << 2) | 1
    curve = Curve(GF2n(83, modulus), 1)
    raw = [Point(int(entry["raw_point"][0]), int(entry["raw_point"][1]))
           for entry in private["selected"]]
    assert all(curve.on_curve(point) for point in raw)
    middle = [curve.sum(raw[:count]) for count in (2, 3, 4)]
    assert all(not point.inf for point in middle)
    raw_sum = curve.sum(raw)
    assert not raw_sum.inf and raw_sum.x == target_x
    twice = curve.add(raw_sum, raw_sum)
    projected = curve.add(twice, twice)
    assert [str(projected.x), str(projected.y)] == public["planted"]["target_Q"]

    conjugates = [int(value) for value in public["normal_conjugates_polynomial_bits_decimal"]]
    circuit, meta = build(target_x, conjugates, masks)
    assignment = {}
    for variables, mask in zip(meta["x_rows"], masks):
        for index, variable in enumerate(variables):
            assignment[variable] = index in mask
    for variables, point in zip(meta["middle_rows"], middle):
        for index, variable in enumerate(variables):
            assignment[variable] = bool(point.x & (1 << index))
    for counter, mask in zip(meta["weight_counters"], masks):
        assignment[counter["choose_three"]] = len(mask) == 3

    definitions = {}
    for clause in circuit.clauses:
        terms = [int(word) for word in clause.split()]
        if len(terms) == 4:
            a, b, output, zero = terms
            assert a < 0 and b < 0 and output > 0 and zero == 0
            assert output not in definitions
            definitions[output] = ("and", -a, -b)
    for row in circuit.xors:
        terms = [int(word) for word in row.split()[1:]]
        assert terms[-1] == 0
        first, operands = terms[0], terms[1:-1]
        output = abs(first)
        assert output not in definitions
        definitions[output] = ("xor", first < 0, operands)
    for variable in range(1, circuit.next_var):
        if variable in assignment:
            continue
        definition = definitions[variable]
        if definition[0] == "and":
            _, left, right = definition
            assert left < variable and right < variable
            assignment[variable] = assignment[left] and assignment[right]
        else:
            _, first_negated, operands = definition
            assert all(operand < variable for operand in operands)
            parity = sum(assignment[operand] for operand in operands) % 2
            assignment[variable] = bool(1 ^ parity ^ first_negated)
    assert len(assignment) == circuit.next_var - 1
    assert verify_model(circuit, assignment)

    report = {
        "schema_version": 1,
        "kind": "n83_w34_known_witness_xcnf_audit",
        "status": "PASS",
        "curve_id": protocol["curve_id"],
        "s3_chain_equations": 4,
        "factor_weight_mix": [len(mask) for mask in masks],
        "full_assignment_satisfies_every_cnf_and_xor_row": True,
        "variable_count": circuit.next_var - 1,
        "cnf_clauses": len(circuit.clauses),
        "xor_rows": len(circuit.xors),
        "and_gates": circuit.and_count,
        "assignment_sha256_local_only": hashlib.sha256(
            json.dumps(assignment, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "public_input_sha256": sha(public_path),
        "private_fixture_sha256_local_only": sha(private_path),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "branch_source_sha256": sha(HERE / "run_n83_w34_sat_branch.py"),
        "sage_runtime_info_sha256": sha(out / "sage_runtime_info.json"),
        "wall_ms_exploratory": (time.perf_counter_ns() - started) / 1e6,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "claim_boundary": "Exact planted assignment satisfaction only; no solver search, ordinary relation, DLP, or speedup.",
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "variable_count": report["variable_count"]}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("public_input", type=Path)
    parser.add_argument("private_fixture", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    main(args.public_input, args.private_fixture, args.out)
