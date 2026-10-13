#!/usr/bin/env python3
"""Check the seed comparator's strict, equal, and reversed truth cases."""

import json
import tempfile
from pathlib import Path

from ordered import HERE, require_leq, runner


def pin(formula, bits, value):
    for position, literal in enumerate(bits):
        formula.clauses.append([literal if value >> position & 1 else -literal])


def main():
    output = HERE / "comparator_control.json"
    assert not output.exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    binary = Path(protocol["solver"]["path"])
    assert runner.sha(binary) == protocol["solver"]["sha256"]
    cases = [(3, 5, "sat"), (7, 7, "sat"), (9, 8, "unsat")]
    rows = []
    with tempfile.TemporaryDirectory(prefix="seedorder-check-", dir=HERE) as folder:
        for index, (left, right, expected) in enumerate(cases):
            formula = runner.Formula()
            a = [formula.new() for _ in range(18)]
            b = [formula.new() for _ in range(18)]
            require_leq(formula, a, b)
            pin(formula, a, left)
            pin(formula, b, right)
            path = Path(folder) / f"case{index}.xcnf"
            formula.write(path)
            raw_sha256 = runner.sha(path)
            native = runner.solve_limited(path, binary, 5, 1000, 256 << 20)
            assert native["status"] == expected, (left, right, native["status"])
            rows.append({"left": left, "right": right,
                         "expected": expected, "status": native["status"],
                         "formula_sha256": raw_sha256,
                         "formula_shape": runner.stats(formula)})
    receipt = {"status": "PASS", "cases": rows,
               "solver_sha256": runner.sha(binary),
               "comparator_source_sha256": runner.sha(HERE / "ordered.py"),
               "checker_source_sha256": runner.sha(Path(__file__))}
    runner.save(output, receipt)
    print(json.dumps({"status": "PASS", "cases": [(r["left"], r["right"],
                r["status"]) for r in rows]}))


if __name__ == "__main__":
    main()
