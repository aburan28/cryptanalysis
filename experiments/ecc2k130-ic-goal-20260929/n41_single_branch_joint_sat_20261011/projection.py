"""Calibrate the quartic emitter's field-multiplication width at N131."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT.parent / "koblitz-polynomial-w-pair-20260925"))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402

REFERENCE = ROOT / "n131_w15_coupled_sixpair_20261010" / "control_result.json"


def dense_cost(n, low_terms):
    circuit = KaratsubaCircuit(n, low_terms)
    left = [circuit.variable() for _ in range(n)]
    right = [circuit.variable() for _ in range(n)]
    circuit.mul(left, right)
    return {"and_gates": circuit.and_count, "cnf_clauses": len(circuit.clauses),
            "native_xor_rows": len(circuit.xors)}


def main():
    control = json.loads((HERE / "control_result.json").read_text())
    query = json.loads((HERE / "query_result.json").read_text())
    reference = json.loads(REFERENCE.read_text())
    calls = control["formula"]["quartic_field_multiplications"]
    assert calls == query["formula"]["quartic_field_multiplications"] == 312
    n41 = dense_cost(41, [0, 3])
    n131 = dense_cost(131, [0, 1, 2, 13])
    assert n41["and_gates"] == 942 and n131["and_gates"] == 5817
    result = {"status": "COMPLETE_DENSE_KERNEL_TRANSFER_DIAGNOSTIC",
              "source_dimension_n131": 15,
              "n131_actual_factor_base_B": 197292,
              "n131_folded_columns_K": 16381,
              "quartic_field_mul_calls": calls,
              "one_dense_field_multiplication": {"n41": n41, "n131": n131},
              "all_dense_n131_quartic_kernel_estimate": {
                  "and_gates": calls * n131["and_gates"],
                  "cnf_clauses": calls * n131["cnf_clauses"],
                  "note": "Diagnostic if every quartic field-multiplication call has two independent dense operands; structured operands can change the actual emitted gate count."},
              "measured_n41_full_formula_and_gates": control["formula"]["and_gates"],
              "previous_n131_w15_full_formula_and_gates": reference["formula"]["and_gates"],
              "n131_public_promotion_gate": "NOT_ESTABLISHED",
              "reason": "The exact N41 public search ended BOUNDED_UNKNOWN; the N131 complete circuit and its solver cost have not passed one worker, 600 seconds, and 4 GiB.",
              "source_sha256": {"projection.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                "control_result.json": hashlib.sha256((HERE / "control_result.json").read_bytes()).hexdigest(),
                                "query_result.json": hashlib.sha256((HERE / "query_result.json").read_bytes()).hexdigest(),
                                "reference_control_result.json": hashlib.sha256(REFERENCE.read_bytes()).hexdigest()}}
    (HERE / "projection_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "n131_dense_AND_diagnostic": result["all_dense_n131_quartic_kernel_estimate"]["and_gates"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
