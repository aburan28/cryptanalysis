"""Compare the Boolean factored coefficients against independent field values."""

import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "n41_single_branch_joint_sat_20261011"
sys.path.insert(0, str(ROOT.parent / "koblitz-polynomial-w-pair-20260925"))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402
import circuit as method  # noqa: E402

spec = importlib.util.spec_from_file_location("old_n41_runner_for_replay", OLD / "run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
spec2 = importlib.util.spec_from_file_location(
    "independent_integer_coefficient_eval",
    ROOT / "n41_quartic_joint_public_20261010" / "audit_integer.py")
integer = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(integer)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    norm = json.loads((ROOT / "n41_quartic_joint_public_20261010" /
                       "norm_result.json").read_text())
    circuit = KaratsubaCircuit(41, [0, 3])
    inputs = [[circuit.variable() for _ in range(41)] for _ in range(5)]
    A, B, multiplications, squares = method.compile_quartic(circuit, inputs, norm)
    rng = random.Random(2026101101)
    cases = []
    for index in range(5):
        selected = [rng.getrandbits(41) for _ in range(5)]
        initial = {wire: value >> bit & 1
                   for row, value in zip(inputs, selected)
                   for bit, wire in enumerate(row)}
        assignment = runner.complete_assignment(circuit, initial)
        def value(wire):
            return 1 if wire == -1 else 0 if wire == 0 else assignment[wire]
        observed = [sum(value(wire) << bit for bit, wire in enumerate(row))
                    for row in (A, B)]
        expected = [integer.evaluate(norm[label + "_terms"], selected, 41,
                                     (1 << 41) | (1 << 3) | 1)
                    for label in ("A", "B")]
        assert observed == expected
        cases.append({"index": index, "input": selected,
                      "A": observed[0], "B": observed[1]})
    result = {"status": "PASS_FACTORED_BOOLEAN_COEFFICIENT_REPLAY",
              "random_seed": 2026101101, "cases": cases,
              "field_multiplications": multiplications,
              "linear_squares": squares,
              "and_gates": circuit.and_count,
              "source_sha256": {"arith_replay.py": sha(Path(__file__)),
                                "factored_circuit.py": sha(HERE / "circuit.py"),
                                "norm_result.json": sha(ROOT / "n41_quartic_joint_public_20261010" /
                                                       "norm_result.json"),
                                "independent_integer_eval.py": sha(ROOT / "n41_quartic_joint_public_20261010" /
                                                                   "audit_integer.py")}}
    (HERE / "arith_replay.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "cases": len(cases),
                      "field_multiplications": multiplications}, sort_keys=True))


if __name__ == "__main__":
    main()
