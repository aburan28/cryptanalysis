"""Independent bit-field checks of the basis-aware quartic expression."""

import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT.parent / "koblitz-polynomial-w-pair-20260925"))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402
from sparse import Algebra  # noqa: E402
import circuit as method  # noqa: E402
import run  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "independent_bit_field",
    ROOT / "n41_quartic_joint_public_20261010" / "audit_integer.py")
integer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integer)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    norm = json.loads(method.NORM.read_text())
    field = method.Field()
    circuit = KaratsubaCircuit(41, [0, 3])
    algebra = Algebra(circuit, field)
    primaries = []

    def source_basis(exponents, rotation):
        wires = [circuit.variable() for _ in exponents]
        values = [field.frob(1 << exponent, rotation) for exponent in exponents]
        primaries.append((wires, values))
        return algebra.expression(zip(wires, values))

    a = source_basis(range(1, 7), 10)
    b = source_basis(range(1, 7), 15)
    P = source_basis(range(2, 13), 10)
    Q = source_basis(range(2, 13), 15)
    z = source_basis(range(41), 0)
    w = source_basis(range(41), 0)
    S = algebra.add(a, b)
    A, B = method.compile_quartic(algebra, (a, S, z, P, Q), norm)
    wB = algebra.mul(w, B)
    output_bits = [expr.bits() for expr in (A, B, wB)]
    rng = random.Random(2026101102)
    rows = []
    for index in range(7):
        initial = {wire: rng.randrange(2)
                   for wires, _ in primaries for wire in wires}
        values = []
        for wires, basis in primaries:
            value = 0
            for wire, coefficient in zip(wires, basis):
                if initial[wire]:
                    value ^= coefficient
            values.append(value)
        av, bv, pv, qv, zv, wv = values
        assignment = run.base.complete_assignment(circuit, initial)
        observed = []
        for bits in output_bits:
            value = 0
            for bit, wire in enumerate(bits):
                value |= (1 if wire == -1 else 0 if wire == 0 else assignment[wire]) << bit
            observed.append(value)
        expected = [integer.evaluate(norm[label + "_terms"],
                                     (av, av ^ bv, zv, pv, qv), 41,
                                     (1 << 41) | (1 << 3) | 1)
                    for label in ("A", "B")]
        expected.append(field.mul(wv, expected[1]))
        assert observed == expected
        rows.append({"case": index, "inputs": values, "A": observed[0],
                     "B": observed[1], "wB": observed[2]})
    result = {"status": "PASS_BASIS_AWARE_QUARTIC_ARITHMETIC_REPLAY",
              "random_seed": 2026101102, "cases": rows,
              "sparse_multiplications": algebra.sparse_mul_calls,
              "generic_multiplications": algebra.generic_mul_calls,
              "sparse_pair_products": algebra.sparse_pair_products,
              "and_gates": circuit.and_count,
              "source_sha256": {"arith_replay.py": sha(Path(__file__)),
                                "sparse.py": sha(HERE / "sparse.py"),
                                "circuit.py": sha(HERE / "circuit.py"),
                                "norm_result.json": sha(method.NORM),
                                "integer_eval.py": sha(ROOT / "n41_quartic_joint_public_20261010" /
                                                       "audit_integer.py")}}
    (HERE / "arith_replay.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "cases": len(rows), "and_gates": circuit.and_count}, sort_keys=True))


if __name__ == "__main__":
    main()
