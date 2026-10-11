"""Rebuild the matched two-pair local equations for the gate comparison."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("eliminant_runner", HERE / "run.py")
method = importlib.util.module_from_spec(spec)
spec.loader.exec_module(method)
fixed, cubic = method.fixed, method.cubic


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["source_sha256"]["runner"] == digest(HERE / "run.py")
    selected, chain = method.data()
    c = method.KaratsubaCircuit(fixed.N, [0, 1, 2, 13])
    algebra = method.Algebra(c, cubic.Field(), dense_and_threshold=3000)
    seed_h2 = fixed.gf_square(fixed.gf_half_trace(fixed.coordinate(fixed.SEED)))
    selectors, outputs = [], []
    for item in selected[:2]:
        bits = [c.variable() for _ in range(17)]
        out = [c.variable() for _ in range(fixed.N)]
        selectors.append(bits)
        outputs.append(out)
        rotation = item["rotation"]
        rotated_h2 = fixed.gf_frobenius(seed_h2, rotation)
        basis = [fixed.gf_frobenius(value, rotation)
                 for value in fixed.product_basis()]
        product = algebra.expression(zip(bits, basis))
        square_term = algebra.expression(
            (wire, fixed.gf_mul(1 ^ rotated_h2, fixed.gf_square(1 << bit)))
            for bit, wire in enumerate(out))
        c.require_zero(algebra.add(algebra.mul(algebra.from_bits(out), product),
                                   square_term,
                                   algebra.expression(((-1, rotated_h2),))).bits())
    block_output = [c.variable() for _ in range(fixed.N)]
    branch = c.variable()
    first, second, output = (algebra.from_bits(bits)
                             for bits in (outputs[0], outputs[1], block_output))
    ht_basis, trace_basis = [], []
    for bit in range(fixed.N):
        value = fixed.gf_square(1 << bit)
        image = 0
        for _ in range((fixed.N + 1) // 2):
            image ^= value
            value = fixed.gf_square(fixed.gf_square(value))
        ht_basis.append(image)
        trace_basis.append(cubic.trace(1 << bit))
    triple = algebra.mul(algebra.mul(first, second), output)
    total = algebra.add(first, second, output)
    ht = c.linear_element(total.bits(), ht_basis)
    c.require_zero(algebra.add(triple, algebra.from_bits(ht),
                               algebra.expression(((branch, 1),))).bits())
    c.require_zero([c.xor(wire for wire, flag in zip(total.bits(), trace_basis)
                          if flag)])
    initial = {}
    def bind(bits, value):
        initial.update({wire: value >> bit & 1 for bit, wire in enumerate(bits)})
    a, b = (cubic.standard_reciprocal(chain["pair_rotated_z"][i]) for i in (0, 1))
    target = method.POSITIVE[0]
    for i, value in enumerate((a, b)):
        bind(selectors[i], fixed.selector_code(selected[i]["masks"][0]))
        bind(outputs[i], value)
    bind(block_output, target)
    witness = fixed.gf_mul(fixed.gf_mul(a, b), target) ^ cubic.halftrace(
        fixed.gf_square(a ^ b ^ target))
    assert witness in (0, 1)
    initial[branch] = witness
    checked = cubic.check_assignment(c, cubic.complete_assignment(c, initial))
    result = {"status": "PASS_MATCHED_N131_TWO_PAIR_LOCAL_GATE",
              "and_gates": c.and_count, "variables": c.next_var - 1,
              "clauses": len(c.clauses), "native_xor_rows": len(c.xors),
              "assignment_check": checked,
              "source_sha256": {"script": digest(__file__),
                                "protocol": digest(HERE / "protocol.json"),
                                "method": digest(HERE / "run.py")}}
    with (HERE / "baseline_gate_result.json").open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
