#!/usr/bin/env python3
"""Independently check the N41 XCNF witness, projection, and reverse lift."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_w5_allpair_index_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model(path, count):
    values = [None] * (count + 1)
    assert path.read_text().startswith("s SATISFIABLE\n")
    for line in path.read_text().splitlines():
        if not line.startswith("v "):
            continue
        terms = [int(token) for token in line[2:].split()]
        assert terms and terms[-1] == 0
        for term in terms[:-1]:
            assert 1 <= abs(term) <= count and values[abs(term)] is None
            values[abs(term)] = term > 0
    assert all(value is not None for value in values[1:])
    return values


def write_model(path, values):
    with path.open("x") as out:
        out.write("s SATISFIABLE\n")
        for i, value in enumerate(values[1:], 1):
            out.write(f"v {i if value else -i} 0\n")


def verify(path, values):
    clauses = xors = 0
    with path.open() as stream:
        header = next(stream).split()
        assert header[:2] == ["p", "cnf"] and int(header[2]) == len(values) - 1
        declared = int(header[3])
        for line in stream:
            if not line.strip() or line.startswith("c"):
                continue
            tokens = line.split()
            is_xor = tokens[0].startswith("x")
            if is_xor:
                if tokens[0] == "x":
                    tokens = tokens[1:]
                else:
                    tokens[0] = tokens[0][1:]
            assert tokens[-1] == "0"
            literals = [int(token) for token in tokens[:-1]]
            assert literals and all(1 <= abs(v) < len(values) for v in literals)
            truths = [values[abs(v)] if v > 0 else not values[abs(v)]
                      for v in literals]
            if is_xor:
                assert sum(truths) & 1, (path, "XOR", xors)
                xors += 1
            else:
                assert any(truths), (path, "CNF", clauses)
                clauses += 1
    assert clauses + xors == declared
    return {"clauses": clauses, "xor_rows": xors}


def audit_case(name, input_name):
    folder = HERE / name
    original = SOURCE / input_name
    result = json.loads((folder / "result.json").read_text())
    assert result["status"] == "PASS"
    assert sha(original) == result["source_sha256"]["input_xcnf"]
    projected = folder / "projected.xcnf"
    mapping = folder / "variable_map.json"
    lift = folder / "lift_rows.jsonl"
    assert sha(projected) == result["source_sha256"]["projected_xcnf"]
    assert sha(mapping) == result["source_sha256"]["variable_map"]
    assert sha(lift) == result["source_sha256"]["lift_rows"]
    control = model(HERE / "control_model.stdout.txt", result["original_variables"])
    original_check = verify(original, control)
    new_to_old = json.loads(mapping.read_text())["new_to_old"]
    reduced = [None] + [control[v] for v in new_to_old[1:]]
    reduced_check = verify(projected, reduced)
    lifted = [None] * len(control)
    for new, old in enumerate(new_to_old[1:], 1):
        lifted[old] = reduced[new]
    pivots = [json.loads(line) for line in lift.read_text().splitlines()]
    assert len(pivots) == result["private_pivots"]
    for row in reversed(pivots):
        pivot = row["pivot"]
        assert lifted[pivot] is None
        other = [v for v in row["variables"] if v != pivot]
        assert all(lifted[v] is not None for v in other)
        lifted[pivot] = bool(row["rhs"] ^ (sum(lifted[v] for v in other) & 1))
    free = sum(v is None for v in lifted[1:])
    lifted = [None] + [False if v is None else v for v in lifted[1:]]
    lifted_check = verify(original, lifted)
    return {"original": original_check, "projected": reduced_check,
            "lifted": lifted_check, "free_defaulted": free,
            "lift_mismatches": sum(a != b for a, b in zip(control[1:], lifted[1:])),
            "projection": result,
            "source_sha256": {"original": sha(original), "projected": sha(projected),
                              "model": sha(HERE / "control_model.stdout.txt"),
                              "map": sha(mapping), "lift": sha(lift)}}


def main():
    cases = {"public": audit_case("public", "public_allpair.xcnf"),
             "all_fixed": audit_case("all_fixed", "all_fixed.xcnf")}
    output = {"status": "PASS_EXACT_XCNF_PROJECTION_AND_LIFT", "cases": cases,
              "audit_sha256": sha(Path(__file__))}
    path = HERE / "control_audit.json"
    with path.open("x") as out:
        json.dump(output, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": output["status"],
                      "public": cases["public"]["projected"],
                      "all_fixed": cases["all_fixed"]["projected"]}))


if __name__ == "__main__":
    main()
