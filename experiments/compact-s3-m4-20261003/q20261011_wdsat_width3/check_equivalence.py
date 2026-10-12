#!/usr/bin/env python3
"""Check shared width-three OR definitions and archived full-lock witnesses."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1460 = PARENT / "q20261011_wdsat_shared_prefix"
sys.path.insert(0, str(Q1460))
from prepare import evaluate  # noqa: E402
spec = importlib.util.spec_from_file_location("q1465_width3_prepare", HERE / "prepare.py")
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
transform = module.transform


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def truth(literal: int, assignment: dict[int, bool]) -> bool:
    return assignment[abs(literal)] == (literal > 0)


def clauses_satisfied(raw: bytes, assignment: dict[int, bool]) -> bool:
    lines = raw.decode("ascii").splitlines()
    assert lines[0].startswith("p cnf ")
    for line in lines[1:]:
        tokens = [int(value) for value in line.split()[:-1]]
        if not any(truth(literal, assignment) for literal in tokens):
            return False
    return True


def extend(original: dict[int, bool], rules: list[tuple[int, tuple[int, ...]]]) -> dict[int, bool]:
    assignment = original.copy()
    for variable, prefix in rules:
        assignment[variable] = any(truth(literal, original) for literal in prefix)
    return assignment


def main() -> None:
    cases = []
    for width in range(4, 9):
        sign_masks = range(1 << width) if width <= 6 else (0, (1 << width) - 1, 0b10101010 & ((1 << width) - 1))
        assignment_count = 0
        auxiliary_checks = 0
        for mask in sign_masks:
            literals = [-(index + 1) if mask >> index & 1 else index + 1
                        for index in range(width)]
            raw = (f"p cnf {width} 1\n" + " ".join(map(str, [*literals, 0])) + "\n").encode()
            derived, rules, stats = transform(raw)
            assert stats["auxiliary_variables"] == width - 3
            assert max(stats["derived_cnf_widths"]) <= 3
            rows = derived.decode("ascii").splitlines()[1:]
            for bits in itertools.product((False, True), repeat=width):
                original = {index + 1: value for index, value in enumerate(bits)}
                wanted = any(truth(literal, original) for literal in literals)
                assert clauses_satisfied(derived, extend(original, rules)) == wanted
                assignment_count += 1
                if width <= 6:
                    satisfiable = False
                    for aux in itertools.product((False, True), repeat=len(rules)):
                        assignment = original | {variable: value
                                                 for (variable, _), value in zip(rules, aux)}
                        satisfiable |= clauses_satisfied(derived, assignment)
                        auxiliary_checks += 1
                    assert satisfiable == wanted
            assert len(rows) == stats["derived_rows"]
        cases.append({"original_width": width, "sign_patterns": len(sign_masks),
                      "original_assignments": assignment_count,
                      "auxiliary_assignment_checks": auxiliary_checks})
    controls = []
    for degree in (53, 83):
        name = f"n{degree}_full_lock"
        source = PARENT / "q1419_partial_pin/runs" / name / "system.xcnf.gz"
        original = gzip.decompress(source.read_bytes())
        derived, rules, stats = transform(original)
        stdout = (Q1460 / "runs" / name / "plain/solver.stdout.txt").read_text()
        width_four_variables = json.loads((Q1460 / "prepare_receipt.json").read_text())["cells"][name]["derived_variables"]
        models = [line for line in stdout.splitlines()
                  if len(line) == width_four_variables and set(line) <= {"0", "1"}]
        assert len(models) == 1
        original_model = {i + 1: value == "1" for i, value in
                          enumerate(models[0][:stats["original_variables"]])}
        original_replay = evaluate(original, original_model)
        derived_model = extend(original_model, rules)
        derived_replay = evaluate(derived, derived_model)
        assert derived_replay["variables"] == stats["derived_variables"]
        assert original_replay["xor_rows"] == derived_replay["xor_rows"]
        controls.append({"degree": degree, "original_archive_sha256": sha(source),
                         "original_replay": original_replay,
                         "derived_replay": derived_replay,
                         "derived_raw_sha256": hashlib.sha256(derived).hexdigest()})
    output = {"proposal_id": "Q1465", "status": "PASS",
              "transform_source_sha256": sha(HERE / "prepare.py"),
              "source_sha256": sha(Path(__file__)),
              "small_clause_cases": cases,
              "full_lock_controls": controls}
    (HERE / "equivalence_check.json").write_text(json.dumps(output, indent=2,
                                                             sort_keys=True) + "\n")
    print("PASS Q1465", len(cases), "clause widths", len(controls), "controls")


if __name__ == "__main__":
    main()
