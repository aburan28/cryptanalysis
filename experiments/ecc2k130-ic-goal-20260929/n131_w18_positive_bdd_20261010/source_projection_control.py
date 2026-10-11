"""Check accepted and rejected fixed-source codes through the native solver."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
ROOT = HERE.parents[2]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import cnf  # noqa: E402
import fixed_pair_circuit as pair  # noqa: E402
from positive_bdd import check_positive_gate, emit_positive_bdd  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "source_projection_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "encoding": HERE / "positive_bdd.py",
             "table": HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010" /
                      "support_w18.tsv",
             "source": BASE / "fixed_pair_circuit.py",
             "source_preflight": BASE / "pair_preflight_result.json",
             "cnf": ROOT / "ecc2k130/codegen/cnf.py",
             "solver": Path("/opt/homebrew/bin/cryptominisat5").resolve()}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    check_positive_gate()
    columns = {int(mask): int(column) for mask, column in
               (line.split() for line in paths["table"].read_text().splitlines())}
    valid = pair.valid_codes(columns)
    root, nodes = pair.build_bdd(valid)
    preflight = json.loads(paths["source_preflight"].read_text())
    assert len(valid) == preflight["valid_unordered_pairs"] == 33191
    assert len(nodes) == preflight["bdd_nodes"] == 13093
    accepted = min(valid)
    rejected = next(code for code in range(1 << 17) if code not in valid)
    cases = []
    for label, code, expected in (("accepted", accepted, "SAT"),
                                  ("rejected", rejected, "UNSAT")):
        c = cnf.Cnf()
        selectors = [c.newVar() for _ in range(17)]
        emit_positive_bdd(c, root, nodes, selectors)
        for bit, lit in enumerate(selectors):
            c.addClause([lit if code >> bit & 1 else -lit])
        formula = HERE / ("source_%s.xcnf" % label)
        c.writeDimacs(formula)
        command = [str(paths["solver"]), "--threads=1", "--maxtime=20",
                   "--zero-exit-status", str(formula)]
        started = time.monotonic_ns()
        run = subprocess.run(command, capture_output=True, text=True,
                             timeout=25, check=False)
        stdout = HERE / ("source_%s.stdout.txt" % label)
        stderr = HERE / ("source_%s.stderr.txt" % label)
        stdout.write_text(run.stdout)
        stderr.write_text(run.stderr)
        status = "SAT" if "s SATISFIABLE" in run.stdout else (
            "UNSAT" if "s UNSATISFIABLE" in run.stdout else "UNKNOWN")
        assert status == expected and run.returncode == 0, (label, status, run.returncode)
        cases.append({"label": label, "selector_code": code, "expected": expected,
                      "observed": status, "solver_exit_code": run.returncode,
                      "wall_ns": time.monotonic_ns() - started,
                      "formula_stats": c.stats(), "formula_sha256": digest(formula),
                      "stdout_sha256": digest(stdout), "stderr_sha256": digest(stderr)})
    result = {"status": "PASS_POSITIVE_BDD_SOURCE_PROJECTION_CONTROLS",
              "valid_codes": len(valid), "bdd_nodes": len(nodes), "cases": cases,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "source_projection_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "cases": [
        {"label": item["label"], "code": item["selector_code"],
         "observed": item["observed"]} for item in cases]}))


if __name__ == "__main__":
    main()
