"""Stream-check every clause and native XOR row of a full solver model."""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE_BITS = [bit for bit in range(18) if bit != 7]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("planted", "ordinary"), required=True)
    args = parser.parse_args()
    protocol_path = HERE / ("full_%s_model_audit_protocol.json" % args.mode)
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__),
             "formula": HERE / ("full_%s.xcnf" % args.mode),
             "build": HERE / ("full_%s_build.json" % args.mode),
             "solver_stdout": HERE / ("full_%s_solver.stdout.txt" % args.mode),
             "solver_result": HERE / ("full_%s_solver_result.json" % args.mode),
             "derive": HERE / "derive_result.json",
             "planted_chain": HERE / "planted_chain_result.json",
             "ordinary_target": HERE / "target_preimages.json",
             "mask_columns": HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    solver_result = json.loads(paths["solver_result"].read_text())
    assert solver_result["status"] == "SAT_MODEL_UNAUDITED"
    assert solver_result["exit_code"] == 0
    build = json.loads(paths["build"].read_text())
    stdout = paths["solver_stdout"].read_text().splitlines()
    assert any(line == "s SATISFIABLE" for line in stdout)

    assignment = {}
    for line in stdout:
        if line.startswith("v "):
            for raw in line.split()[1:]:
                lit = int(raw)
                if lit:
                    var = abs(lit)
                    assert var not in assignment
                    assignment[var] = lit > 0
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
                observed = sum(value(lit) for lit in
                               [first] + [int(item) for item in parts[1:-1]]) & 1
                failed_xors += observed != rhs
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
    mask_columns = {int(mask): int(column) for mask, column in
                    (line.split() for line in paths["mask_columns"].read_text().splitlines())}
    masks = [sum(((code >> i) & 1) << bit for i, bit in enumerate(SOURCE_BITS))
             for code in codes]
    pair_masks = [[mask, mask ^ 212] for mask in masks]
    assert all(a in mask_columns and b in mask_columns and
               mask_columns[a] != mask_columns[b] for a, b in pair_masks)
    columns = [[mask_columns[a], mask_columns[b]] for a, b in pair_masks]
    if args.mode == "planted":
        derive = json.loads(paths["derive"].read_text())
        planted = json.loads(paths["planted_chain"].read_text())
        assert pair_masks == [item["masks"] for item in derive["selected"]]
        assert outputs == [item["unrotated_pair_output_z"] for item in derive["selected"]]
        assert intermediates == planted["intermediate_z"]
    receipt = {"status": "PASS_INDEPENDENT_FULL_NATIVE_XOR_MODEL",
               "mode": args.mode, "model_variables": len(assignment),
               "clauses_checked": clauses, "xor_rows_checked": xors,
               "failed_clauses": failed_clauses, "failed_xor_rows": failed_xors,
               "source_codes": codes, "source_mask_pairs": pair_masks,
               "source_folded_columns": columns,
               "unrotated_pair_output_z": outputs,
               "intermediate_z": intermediates,
               "target_z": build["raw_target_z"],
               "source_sha256": {name: digest(path) for name, path in paths.items()},
               "protocol_sha256": digest(protocol_path)}
    with (HERE / ("full_%s_model_audit.json" % args.mode)).open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "mode": args.mode,
                      "clauses_checked": clauses, "xor_rows_checked": xors}))


if __name__ == "__main__":
    main()
