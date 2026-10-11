"""Exact gate count and full positive assignment for the factored circuit."""

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "n41_single_branch_joint_sat_20261011"
sys.path.insert(0, str(ROOT.parent / "koblitz-polynomial-w-pair-20260925"))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402
import circuit as method  # noqa: E402

spec = importlib.util.spec_from_file_location("old_n41_run", OLD / "run.py")
old_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old_run)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    _, columns = method.source_columns(old_run.SOURCE_INPUT)
    target = json.loads(old_run.PUBLIC_LIFTS.read_text())["n41"]
    reciprocals = [row["z_h_reciprocal_x"] for row in target["preimages"][:2]]
    start = time.monotonic()
    circuit = KaratsubaCircuit(41, [0, 3])
    meta = method.build(circuit, method.Field(), columns, reciprocals)
    construction = time.monotonic() - start
    known = json.loads(old_run.KNOWN_BLOCKS.read_text())
    audit = json.loads(old_run.KNOWN_BRANCHES.read_text())
    baseline = json.loads((OLD / "control_result.json").read_text())
    initial = {}
    def bind(wires, value):
        initial.update({wire: value >> index & 1 for index, wire in enumerate(wires)})
    for row, mask in zip(meta["masks"], known["masks"]):
        bind(row, mask)
    for row, block in zip(meta["output_z"], known["four_atom_blocks"]):
        bind(row, block["z_h_reciprocal_x"])
    for row, branch in zip(meta["branch_w"], audit["blocks"]):
        bind(row, branch["existential_branch_witness"])
    bind(meta["intermediate"], baseline["joined_reciprocal"])
    initial[meta["target_flag"]] = 1
    assert len(initial) == len(meta["primary_variables"])
    values = old_run.complete_assignment(circuit, initial)
    check = old_run.check_assignment(circuit, values)
    result = {"status": "PASS_FULL_FACTORED_N41_PUBLIC_ASSIGNMENT",
              "target": target["public_target"], "candidate_id": None,
              "formula": {"variables": circuit.next_var - 1,
                          "and_gates": circuit.and_count,
                          "cnf_clauses": len(circuit.clauses),
                          "native_xor_rows": len(circuit.xors),
                          "quartic_field_multiplications": meta["quartic_field_multiplications"],
                          "quartic_field_squares": meta["quartic_field_squares"]},
              "baseline_formula": baseline["formula"],
              "complete_assignment": check,
              "construction_seconds_exploratory": construction,
              "source_sha256": {"measure.py": sha(Path(__file__)),
                                "circuit.py": sha(HERE / "circuit.py"),
                                "old_circuit.py": sha(OLD / "circuit.py"),
                                "coefficient_result.json": sha(OLD / "coefficient_result.json"),
                                "known_blocks.json": sha(old_run.KNOWN_BLOCKS),
                                "known_branch_audit.json": sha(old_run.KNOWN_BRANCHES)}}
    (HERE / "measure_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "field_muls": result["formula"]["quartic_field_multiplications"],
                      "and_gates": result["formula"]["and_gates"],
                      "baseline_and_gates": baseline["formula"]["and_gates"]}, sort_keys=True))


if __name__ == "__main__":
    main()
