"""Exhaustively compare flattened and reference IR encodings on small DAGs."""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import cnf  # noqa: E402
import ir  # noqa: E402
from flat_emit import emit_constraints  # noqa: E402


CMS = Path("/opt/homebrew/bin/cryptominisat5")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def graphs():
    p = ir.Prog()
    x = [p.addInput("x", index) for index in range(6)]
    a = p.xorList(x[:4])
    b = p.xorList(x[2:])
    nonlinear = p.andOp(a, b)
    shared = p.xor(a, nonlinear)
    yield p, [p.xor(shared, x[0])], [[shared, b, p.xor(nonlinear, x[2])]]

    p = ir.Prog()
    x = [p.addInput("x", index) for index in range(6)]
    a = p.xorList(x)
    b = p.andOp(p.xorList(x[:3]), p.xorList(x[3:]))
    c = p.xor(a, b)
    yield p, [p.xor(c, x[0]), p.xor(b, x[5])], [[a, c, x[1]]]


def make_formula(prog, roots, deltas, assignment, flattened, path):
    c = cnf.Cnf()
    lits = {("x", bit): c.newVar() for bit in range(6)}
    if flattened:
        emit_constraints(prog, roots, deltas, lits, c)
    else:
        output = prog.emitCnf(roots + [bit for d in deltas for bit in d], lits, c)
        for root in output[:len(roots)]:
            c.assertZero(root)
        offset = len(roots)
        for delta in deltas:
            c.addClause(output[offset:offset+len(delta)])
            offset += len(delta)
    for bit in range(6):
        c.addClause([lits[("x", bit)] if assignment >> bit & 1 else
                     -lits[("x", bit)]])
    c.writeDimacs(path)
    result = subprocess.run([str(CMS), "--threads=1", "--verb=0",
                             "--zero-exit-status", str(path)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    sat = "s SATISFIABLE" in result.stdout
    unsat = "s UNSATISFIABLE" in result.stdout
    assert sat != unsat, result.stdout
    return sat


def main():
    result = {"status": "PASS_EXHAUSTIVE_FLAT_EMITTER_EQUIVALENCE",
              "graphs": 0, "assignments_per_graph": 64, "cases": 0,
              "satisfiable_cases": 0,
              "source_sha256": {name: digest(path) for name, path in
                                {"script": Path(__file__),
                                 "emitter": HERE / "flat_emit.py",
                                 "ir": ROOT / "ecc2k130/codegen/ir.py",
                                 "cnf": ROOT / "ecc2k130/codegen/cnf.py",
                                 "solver": CMS.resolve()}.items()}}
    with tempfile.TemporaryDirectory(dir="/private/tmp") as tmp:
        formula = Path(tmp) / "small.xcnf"
        for prog, roots, deltas in graphs():
            result["graphs"] += 1
            for assignment in range(64):
                values = {("x", bit): assignment >> bit & 1 for bit in range(6)}
                root_values = prog.evaluate(values, roots)
                delta_values = [prog.evaluate(values, d) for d in deltas]
                expected = not any(root_values) and all(any(d) for d in delta_values)
                flat = make_formula(prog, roots, deltas, assignment, True, formula)
                reference = make_formula(prog, roots, deltas, assignment, False, formula)
                assert flat == reference == expected, (result["graphs"], assignment)
                result["cases"] += 1
                result["satisfiable_cases"] += int(flat)
    with (HERE / "flat_emit_check_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "graphs", "cases", "satisfiable_cases")}))


if __name__ == "__main__":
    main()
