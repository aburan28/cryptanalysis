#!/usr/bin/env python3
"""Independent Sage replay of the N131 W14 diagonal-pair inverse panel."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix, vector

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
ORDER = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lift(F, value):
    t = F.gen()
    out = F.zero()
    i = 0
    while value:
        if value & 1:
            out += t**i
        value >>= 1
        i += 1
    return out


def encode(value):
    return sum(int(c) << i for i, c in enumerate(value.polynomial()))


def coordinate(values, mask):
    return sum((values[i] for i in range(len(values)) if mask >> i & 1),
               values[0].parent().zero())


def half_trace(F, value):
    total = F.zero()
    term = value
    for _ in range(66):
        total += term
        term = term**4
    if total**2+total != value:
        raise AssertionError("W14 half-trace changed")
    return total


def main():
    output = HERE / "sage_audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    if sha(SUPPORT) != protocol["sha256"]["support"]:
        raise ValueError("support digest changed")
    inputs = json.loads((HERE / "inputs.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    if result["protocol_sha256"] != sha(protocol_path) or \
            result["inputs_sha256"] != sha(HERE / "inputs.json"):
        raise ValueError("producer receipt changed")
    binary = PolynomialRing(GF(2), "t")
    t0 = binary.gen()
    F = GF(2**131, "t", modulus=t0**131+t0**13+t0**2+t0+1)
    E = EllipticCurve(F, [1, 0, 0, 0, 1])
    identity = E(0)
    basis_w = [F.gen()**i for i in range(1, 15)]
    basis_u = [half_trace(F, w) for w in basis_w]
    columns = dict(tuple(map(int, line.split())) for line in SUPPORT.read_text().splitlines())
    if len(columns) != 8220:
        raise AssertionError("support changed")
    atom_cache = {}
    two_torsion = E(F.zero(), F.one())

    def atom_options(mask):
        if mask in atom_cache:
            return atom_cache[mask]
        u = coordinate(basis_u, mask)
        w = coordinate(basis_w, mask)
        raw_x = F.one()+1/u
        atoms = [P+E(P[0]**2, P[1]**2) for P in E.lift_x(raw_x, all=True)]
        if len(atoms) != 2 or atoms[0] != -atoms[1]:
            raise AssertionError("diagonal sign pair changed")
        if any(P == identity or P[0] != 1/w or
               4*P == identity or ORDER*(4*P) != identity or
               ORDER*P not in (identity, two_torsion) for P in atoms):
            raise AssertionError("diagonal projection or cofactor class changed")
        atom_cache[mask] = atoms
        return atoms

    ranks = []
    positives = controls = 0
    positive_cofactor = {"subgroup": 0, "order_two": 0}
    for case, row in zip(inputs["cases"], result["rows"]):
        if case["z"] != row["z"] or case["kind"] != row["kind"]:
            raise AssertionError("panel row order changed")
        z = lift(F, case["z"])
        z2 = z**2
        basis_s2 = [w**2 for w in basis_w]
        basis_p = [F.gen()**d for d in range(2, 29)]
        basis = basis_s2+[z*p+z2*p**2 for p in basis_p]
        bits = [encode(value) for value in basis]
        M = matrix(GF(2), 131, 41,
                   lambda i, j: (bits[j] >> i) & 1)
        rank = int(M.rank())
        if rank != 41 or rank != row["rank"]:
            raise AssertionError("joint rank changed")
        ranks.append(rank)
        rhs = vector(GF(2), [(encode(z2) >> i) & 1 for i in range(131)])
        consistent = M.augment(rhs.column()).rank() == rank
        if case["kind"] == "positive":
            if not consistent or row["status"] != "PAIR":
                raise AssertionError("positive joint solve failed")
            solution = M.solve_right(rhs)
            recovered_s = sum(int(solution[i]) << i for i in range(14))
            recovered_p = sum((F.gen()**d for d in range(2, 29)
                               if solution[14+d-2]), F.zero())
            a, b = case["a"], case["b"]
            if recovered_s != a ^ b or \
                    recovered_p != coordinate(basis_w, a)*coordinate(basis_w, b):
                raise AssertionError("joint source/product inverse failed")
            if columns[a] == columns[b]:
                raise AssertionError("positive folded columns collide")
            target = E(lift(F, case["point"][0]), lift(F, case["point"][1]))
            if target[0] != 1/z or 4*target == identity or \
                    ORDER*(4*target) != identity:
                raise AssertionError("positive group point changed")
            cofactor = ORDER*target
            if cofactor == identity:
                positive_cofactor["subgroup"] += 1
            elif cofactor == two_torsion:
                positive_cofactor["order_two"] += 1
            else:
                raise AssertionError("unexpected raw cofactor class")
            if not any(P+Q == target for P in atom_options(a) for Q in atom_options(b)):
                raise AssertionError("positive pair has no group lift")
            if sorted(row["pairs"]) != [[a, b]]:
                raise AssertionError("producer pair set changed")
            positives += 1
        else:
            if consistent or row["status"] != "SPAN_REJECT" or row["pairs"]:
                raise AssertionError("trace-zero control accepted")
            controls += 1
    if (positives, controls) != (32, 32):
        raise AssertionError("panel size changed")
    audit = {"status": "PASS", "source_sha256": sha(Path(__file__)),
             "protocol_sha256": sha(protocol_path),
             "inputs_sha256": sha(HERE / "inputs.json"),
             "result_sha256": sha(HERE / "result.json"),
             "runtime_sha256": sha(HERE / "sage_runtime_info.json"),
             "positive_group_pairs_checked": positives,
             "positive_raw_pair_cofactor_classes": positive_cofactor,
             "trace_zero_span_rejects_checked": controls,
             "joint_rank_histogram": {"41": len(ranks)},
             "distinct_positive_atoms_checked": len(atom_cache)}
    with output.open("x") as stream:
        json.dump(audit, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(audit))


if __name__ == "__main__":
    main()
