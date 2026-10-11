"""Independently stream-check the native-XOR pair SAT witness."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "pair_model_audit_protocol.json").read_text())
    paths = {"script": Path(__file__), "formula": HERE / "pair_pinned.xcnf",
             "solver_stdout": HERE / "pair_solver.stdout.txt",
             "solver_result": HERE / "pair_solver_result.json",
             "preflight": HERE / "pair_preflight_result.json",
             "derive": HERE / "derive_result.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    stdout = paths["solver_stdout"].read_text().splitlines()
    assert any(line == "s SATISFIABLE" for line in stdout)
    result = json.loads(paths["solver_result"].read_text())
    assert result["status"] == "SAT_MODEL_UNAUDITED" and result["exit_code"] == 0
    preflight = json.loads(paths["preflight"].read_text())
    witness = json.loads(paths["derive"].read_text())["selected"][0]

    assignment = {}
    for line in stdout:
        if not line.startswith("v "):
            continue
        for raw in line.split()[1:]:
            lit = int(raw)
            if lit == 0:
                continue
            var = abs(lit)
            assert var not in assignment
            assignment[var] = lit > 0
    assert len(assignment) == preflight["pinned_xcnf"]["vars"]

    def value(lit):
        return assignment[abs(lit)] if lit > 0 else not assignment[abs(lit)]

    clauses = xors = failed_clauses = failed_xors = 0
    with paths["formula"].open() as source:
        header = source.readline().split()
        assert header == ["p", "cnf", str(len(assignment)),
                          str(preflight["pinned_xcnf"]["clauses"] +
                              preflight["pinned_xcnf"]["xors"])]
        for line in source:
            parts = line.split()
            assert parts[-1] == "0"
            if parts[0].startswith("x"):
                head = parts[0]
                rhs = not head.startswith("x-")
                first = int(head[2:] if not rhs else head[1:])
                lits = [first] + [int(item) for item in parts[1:-1]]
                observed = sum(value(lit) for lit in lits) & 1
                failed_xors += observed != rhs
                xors += 1
            else:
                lits = [int(item) for item in parts[:-1]]
                failed_clauses += not any(value(lit) for lit in lits)
                clauses += 1
    assert clauses == preflight["pinned_xcnf"]["clauses"]
    assert xors == preflight["pinned_xcnf"]["xors"]
    assert failed_clauses == failed_xors == 0
    code = sum(assignment[var] << bit for bit, var in enumerate(range(2, 19)))
    z = sum(assignment[var] << bit for bit, var in enumerate(range(19, 150)))
    assert code == sum(((witness["masks"][0] >> bit) & 1) << index
                       for index, bit in enumerate([i for i in range(18) if i != 7]))
    assert z == witness["unrotated_pair_output_z"]
    receipt = {"status": "PASS_INDEPENDENT_NATIVE_XOR_PAIR_MODEL",
               "model_variables": len(assignment), "clauses_checked": clauses,
               "xor_rows_checked": xors, "failed_clauses": failed_clauses,
               "failed_xor_rows": failed_xors, "source_mask_code": code,
               "pair_output_z": z,
               "source_sha256": {name: digest(path) for name, path in paths.items()},
               "protocol_sha256": digest(HERE / "pair_model_audit_protocol.json")}
    with (HERE / "pair_model_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "clauses": clauses,
                      "native_xors": xors}))


if __name__ == "__main__":
    main()
