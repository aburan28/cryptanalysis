"""Independently stream-check the relaxed-source constructed XCNF model."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
SOURCE_BITS = [bit for bit in range(18) if bit != 7]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "constructed_audit_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "formula": HERE / "relaxed_constructed.xcnf",
             "build": HERE / "relaxed_constructed_build.json",
             "solver_stdout": HERE / "constructed_solver.stdout.txt",
             "solver_result": HERE / "constructed_solver_result.json",
             "derive": BASE / "derive_result.json",
             "planted_chain": BASE / "planted_chain_result.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    solver = json.loads(paths["solver_result"].read_text())
    assert solver["status"] == "SAT_MODEL_UNAUDITED" and solver["exit_code"] == 0
    build = json.loads(paths["build"].read_text())
    lines = paths["solver_stdout"].read_text().splitlines()
    assert any(line == "s SATISFIABLE" for line in lines)
    assignment = {}
    for line in lines:
        if line.startswith("v "):
            for raw in line.split()[1:]:
                lit = int(raw)
                if lit:
                    assert abs(lit) not in assignment
                    assignment[abs(lit)] = lit > 0
    assert len(assignment) == build["xcnf"]["vars"]

    def value(lit):
        return assignment[abs(lit)] if lit > 0 else not assignment[abs(lit)]

    clauses = xors = failed_clauses = failed_xors = 0
    with paths["formula"].open() as source:
        header = source.readline().split()
        assert header == ["p", "cnf", str(len(assignment)),
                          str(build["xcnf"]["clauses"] + build["xcnf"]["xors"])]
        for line in source:
            parts = line.split()
            assert parts[-1] == "0"
            if parts[0].startswith("x"):
                head = parts[0]
                rhs = not head.startswith("x-")
                first = int(head[2:] if not rhs else head[1:])
                failed_xors += (sum(value(lit) for lit in
                                    [first] + [int(item) for item in parts[1:-1]]) & 1) != rhs
                xors += 1
            else:
                failed_clauses += not any(value(int(item)) for item in parts[:-1])
                clauses += 1
    assert clauses == build["xcnf"]["clauses"]
    assert xors == build["xcnf"]["xors"]
    assert failed_clauses == failed_xors == 0

    next_var = 2

    def take(width):
        nonlocal next_var
        result = sum(int(assignment[var]) << bit for bit, var in
                     enumerate(range(next_var, next_var + width)))
        next_var += width
        return result

    codes = [take(17) for _ in range(8)]
    outputs = [take(131) for _ in range(8)]
    intermediates = [take(131) for _ in range(6)]
    masks = [sum(((code >> i) & 1) << bit for i, bit in enumerate(SOURCE_BITS))
             for code in codes]
    pair_masks = [[mask, mask ^ 212] for mask in masks]
    derive = json.loads(paths["derive"].read_text())
    planted = json.loads(paths["planted_chain"].read_text())
    assert pair_masks == [item["masks"] for item in derive["selected"]]
    assert outputs == [item["unrotated_pair_output_z"] for item in derive["selected"]]
    assert intermediates == planted["intermediate_z"]
    assert build["raw_target_z"] == planted["raw_target_z"]
    result = {"status": "PASS_INDEPENDENT_RELAXED_SOURCE_CONSTRUCTED_MODEL",
              "model_variables": len(assignment),
              "clauses_checked": clauses, "xor_rows_checked": xors,
              "failed_clauses": failed_clauses, "failed_xor_rows": failed_xors,
              "source_mask_pairs": pair_masks,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "constructed_audit_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "clauses_checked": clauses, "xor_rows_checked": xors}))


if __name__ == "__main__":
    main()
