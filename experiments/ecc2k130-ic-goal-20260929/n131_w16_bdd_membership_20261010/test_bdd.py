"""Exhaustive small-width proof check of the emitted existential CNF."""

import itertools
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bdd_under_test", HERE / "bdd.py")
bdd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bdd)


class Circuit:
    def __init__(self, width):
        self.next_var = width + 1
        self.clauses = []

    def variable(self):
        value = self.next_var
        self.next_var += 1
        return value


def satisfies(clauses, values):
    for clause in clauses:
        literals = [int(s) for s in clause.split()[:-1]]
        if not any(values[abs(lit)] == (lit > 0) for lit in literals):
            return False
    return True


def main():
    width = 3
    tested = 0
    for subset_bits in range(1, (1 << (1 << width)) - 1):
        valid = {mask for mask in range(1 << width) if subset_bits >> mask & 1}
        root, graph = bdd.build(valid, width)
        circuit = Circuit(width)
        wires, _ = bdd.emit(circuit, list(range(1, width + 1)), root, graph)
        for mask in range(1 << width):
            prefix = {i + 1: bool(mask >> i & 1) for i in range(width)}
            satisfiable = any(
                satisfies(circuit.clauses,
                          {**prefix, **{wires[node]: bits[index]
                                      for index, node in enumerate(graph)}})
                for bits in itertools.product((False, True), repeat=len(graph)))
            assert satisfiable == (mask in valid)
            tested += 1
    print(f"PASS_EXHAUSTIVE_3_BIT_EMITTED_CNF subsets=254 mask_cases={tested}")


if __name__ == "__main__":
    main()
