"""Exhaustively check the emitted four-bit unsigned-order CNF."""

import itertools

from canonical import add_pair_order


class Circuit:
    def __init__(self):
        self.next_var = 9
        self.clauses = []
        self.xors = []

    def variable(self):
        result = self.next_var
        self.next_var += 1
        return result

    def xor(self, wires):
        result = self.variable()
        self.xors.append((result, tuple(wires)))
        return result


def sat(clauses, values):
    return all(any(values[abs(lit)] == (lit > 0)
                   for lit in map(int, clause.split()[:-1]))
               for clause in clauses)


def main():
    circuit = Circuit()
    steps = add_pair_order(circuit, [list(range(1, 5)), list(range(5, 9))])[0]
    equal_wires = [equal for _, _, equal in steps]
    for a in range(16):
        for b in range(16):
            base = {i + 1: bool(a >> i & 1) for i in range(4)}
            base.update({i + 5: bool(b >> i & 1) for i in range(4)})
            for output, inputs in circuit.xors:
                base[output] = base[inputs[0]] ^ base[inputs[1]]
            satisfiable = any(sat(circuit.clauses,
                                  {**base, **dict(zip(equal_wires, bits))})
                              for bits in itertools.product((False, True),
                                                            repeat=len(equal_wires)))
            assert satisfiable == (a <= b), (a, b)
    print("PASS_EXHAUSTIVE_4_BIT_PAIR_ORDER 256 ordered inputs")


if __name__ == "__main__":
    main()
