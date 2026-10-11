"""Independent checked-Sage rank, product, and raw-group replay."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from sage.all import GF, PolynomialRing, matrix, vector

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
OLD = BASE / "n131_w18_allseed_pair_inverse_20261011"
SUPPORT = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new_json(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.write("\n")


def sources():
    result = {"audit_source": HERE / "audit.py", "runtime": HERE / "sage_runtime_info.json",
              "run_protocol": HERE / "protocol.json", "support": SUPPORT,
              "old_validator": OLD / "validate.py", "old_validation": OLD / "sample_validation.json"}
    for index in range(4):
        result[f"case_{index}"] = HERE / f"case_{index:03d}.json"
        result[f"old_case_{index}"] = BASE / "n131_w18_allseed_linear_query_20261011" / f"case_{index:03d}_target_linear.json"
    return result


def enc(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def freeze():
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    new_json(HERE / "audit_protocol.json", {
        "status": "FROZEN_BEFORE_AUDIT",
        "method": "independent Sage GF(2) 131-by-53 rank and augmented rank; solve positive seed/product; replay archived group signs",
        "source_sha256": {name: sha(path) for name, path in sources().items()},
    })


def main():
    protocol = json.loads((HERE / "audit_protocol.json").read_text())
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "z", modulus=t**131 + t**13 + t**2 + t + 1)
    basis = [field.from_integer(1 << i) for i in range(1, 19)]
    p_basis = [field.from_integer(1 << i) for i in range(2, 37)]
    columns = {int(mask): int(column) for mask, column in
               (line.split() for line in SUPPORT.read_text().splitlines())}
    assert len(columns) == 131307
    spec = importlib.util.spec_from_file_location("prior_validator", OLD / "validate.py")
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    cases = json.loads((HERE / "protocol.json").read_text())["cases"]
    rows = []
    for index, case in enumerate(cases):
        result = json.loads((HERE / f"case_{index:03d}.json").read_text())
        old = json.loads((BASE / "n131_w18_allseed_linear_query_20261011" /
                          f"case_{index:03d}_target_linear.json").read_text())
        c = field.from_integer(case["coordinate"])
        for _ in range((131-case["rotation"]) % 131):
            c *= c
        assert enc(c) == sum(int(word) << (64*j) for j,word in enumerate(result["unrotated_reciprocal"]))
        c2 = c*c
        vectors = [w*w for w in basis] + [c*p+c2*p*p for p in p_basis]
        values = [enc(value) for value in vectors]
        system = matrix(GF(2), 131, 53, lambda row, col: (values[col] >> row) & 1)
        rhs = vector(GF(2), [(enc(c2) >> row) & 1 for row in range(131)])
        rank = int(system.rank())
        augmented = int(system.augment(matrix(GF(2),131,1,list(rhs))).rank())
        assert rank == result["joint_rank"]
        assert (augmented == rank) == result["joint_consistent"]
        assert result["hits"] == old["hits"]
        solved = None
        if rank == 53 and augmented == 53:
            bits = system.solve_right(rhs)
            seed_mask = sum(int(bits[i]) << i for i in range(18))
            product = sum((field.from_integer(int(bits[18+i])) * p_basis[i] for i in range(35)), field.zero())
            solved = {"seed_mask": seed_mask, "product": enc(product)}
            for hit in result["hits"]:
                a,b = hit["masks"]
                assert a ^ b == seed_mask == hit["seed"]
                assert field.from_integer(a << 1)*field.from_integer(b << 1) == product
                assert enc(product) == sum(int(word) << (64*j) for j,word in enumerate(hit["product"]))
                assert (field.one()+product*product)*c2+product*c+field.from_integer(seed_mask << 1)**2 == 0
        sign_matches = sum(prior.group_replay(hit, case["coordinate"], case["rotation"], columns)
                           for hit in result["hits"])
        rows.append({"name": case["name"], "rank": rank, "augmented_rank": augmented,
                     "solution": solved, "hits": len(result["hits"]), "group_sign_matches": sign_matches})
    new_json(HERE / "audit.json", {"status": "PASS_INDEPENDENT_RANK_PRODUCT_GROUP_REPLAY",
                                   "audit_protocol_sha256": sha(HERE / "audit_protocol.json"),
                                   "cases": rows})
    print("PASS", len(rows), "cases")


if __name__ == "__main__":
    assert sys.argv[1:] in (["freeze"], ["run"])
    freeze() if sys.argv[1] == "freeze" else main()
