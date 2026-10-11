"""Independently stream-check an ordinary W18 eight-pair two-link resultant model."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "ordinary_audit_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "formula": HERE / "resultant_ordinary.xcnf",
             "build": HERE / "resultant_ordinary_build.json",
             "solver_stdout": HERE / "ordinary_solver.stdout.txt",
             "solver_result": HERE / "ordinary_solver_result.json",
             "table": HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010" /
                      "support_w18.tsv",
             "target": HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010" /
                       "target_preimages.json",
             "bdd": HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010" /
                    "pair_preflight_result.json"}
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

    bdd = json.loads(paths["bdd"].read_text())
    source_bits = [bit for bit in range(18) if bit != 7]
    assert bdd["source_dimension"] == 18 and bdd["seed_mask"] == 212
    codes = [take(17) for _ in range(8)]
    outputs = [take(131) for _ in range(8)]
    intermediates = [take(131) for _ in range(3)]
    masks = [sum(((code >> i) & 1) << bit for i, bit in enumerate(source_bits))
             for code in codes]
    pair_masks = [[mask, mask ^ bdd["seed_mask"]] for mask in masks]
    source_columns = {int(mask): int(column) for mask, column in
                      (line.split() for line in paths["table"].read_text().splitlines())}
    assert all(a in source_columns and b in source_columns and
               source_columns[a] != source_columns[b] for a, b in pair_masks)
    columns = [[source_columns[a], source_columns[b]] for a, b in pair_masks]
    target = json.loads(paths["target"].read_text())
    assert build["raw_target_z"] == target["preimages"][0]["reciprocal_x_z"]
    flat_columns = [column for pair in columns for column in pair]
    result = {"status": "PASS_INDEPENDENT_W18_TWO_LINK_RESULTANT_ORDINARY_XCNF_MODEL",
              "model_variables": len(assignment),
              "clauses_checked": clauses, "xor_rows_checked": xors,
              "failed_clauses": failed_clauses, "failed_xor_rows": failed_xors,
              "source_mask_pairs": pair_masks,
              "source_folded_columns": columns,
              "all_source_columns_distinct": len(set(flat_columns)) == len(flat_columns),
              "unrotated_pair_output_z": outputs,
              "retained_intermediate_z": intermediates,
              "target_z": build["raw_target_z"],
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "ordinary_audit_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "clauses_checked": clauses, "xor_rows_checked": xors}))


if __name__ == "__main__":
    main()
