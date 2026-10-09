#!/usr/bin/env sage -python
"""Freeze a sum-free N131 pair inverse panel, including rank-drop controls."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n131_d13_batched_pair_inverse_20261009"
DUAL = GOAL / "n131_d13_syndrome_pair_inverse_20261009"
SOURCE = GOAL / "n131_d13_same_rotation_pairs_20261009"
CODEGEN = HERE.parents[2] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import field


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


source = load("source_for_freeze", SOURCE / "run.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    old = json.loads((BASE / "protocol.json").read_text())
    if (len(old["inputs"]) != 64 or old["curve_id"] !=
            "EC1N131Ckb1heb5f1998f20b"):
        raise ValueError("source input panel changed")
    onb = field.Onb(131)
    A = lambda value: onb.add(onb.sqr(value), value)
    basis = [onb.fromCoords(int(mask, 16)) for mask in old["basis_masks_hex"]]
    squares = [onb.sqr(value) for value in basis]
    transformed = [A(value) for value in basis]
    products = [onb.mul(transformed[i], transformed[j])
                for i in range(13) for j in range(i, 13)]
    amap_columns = [onb.toCoords(A(onb.gamma(i + 1))) for i in range(131)]
    amap, kernel = source.echelon(amap_columns)
    if len(amap) != 130 or len(kernel) != 1:
        raise ValueError("Artin-Schreier map changed")
    inputs = list(old["inputs"])
    seen = {item["z_mask"] for item in inputs}
    degenerate = []
    for si, square in enumerate(squares):
        for pi, product in enumerate(products):
            if product == 0:
                continue
            target = onb.mul(square, onb.inv(product))
            if onb.trace(target) != 0:
                continue
            code = source.solve(amap, onb.toCoords(target))
            if code is None:
                raise ValueError("trace-zero target lacks Artin-Schreier root")
            z = onb.fromCoords(code)
            if A(z) != target:
                raise ValueError("constructed root is incorrect")
            mask = onb.toCoords(z)
            if mask in seen:
                continue
            columns = [onb.toCoords(value) for value in squares]
            columns += [onb.toCoords(onb.mul(target, value)) for value in products]
            rank = len(source.echelon(columns)[0])
            if rank >= 104:
                raise ValueError("constructed output did not drop combined rank")
            seen.add(mask)
            degenerate.append({"kind": "constructed_rank_drop", "z_mask": mask,
                               "pair": None, "square_basis_index": si,
                               "product_index": pi, "expected_rank": rank})
            if len(degenerate) == 6:
                break
        if len(degenerate) == 6:
            break
    if len(degenerate) != 6:
        raise ValueError("insufficient rank-drop controls")
    inputs += degenerate
    inputs += [{"kind": "exceptional", "z_mask": 0, "pair": None},
               {"kind": "exceptional", "z_mask": (1 << 131) - 1,
                "pair": None}]
    paths = {"run": HERE / "run.py", "audit": HERE / "audit.py",
             "freeze": HERE / "freeze.py", "field": CODEGEN / "field.py",
             "base_run": BASE / "run.py", "base_protocol": BASE / "protocol.json",
             "base_result": BASE / "result.json",
             "dual_run": DUAL / "run.py", "dual_result": DUAL / "result.json",
             "source_run": SOURCE / "run.py", "source_result": SOURCE / "result.json",
             "pivots": SOURCE / "pivots.bin",
             "valid_codes": SOURCE / "valid_codes.json",
             "runtime": HERE / "runtime_info.json"}
    protocol = {"status": "FROZEN", "proposal_id": "Q20261009233000",
                "candidate_id": None, "curve_id": old["curve_id"],
                "basis_masks_hex": old["basis_masks_hex"],
                "inputs": inputs, "repetitions": 2,
                "input_law": "32 source positive outputs, 32 earlier seeded uniform controls, 6 constructed combined-rank-drop controls, and both A(z)=0 exceptional coordinates",
                "methods": ["syndrome8", "joint_linear"],
                "wall_cap_seconds": 300, "rss_cap_bytes": 4 * 1024**3,
                "measurement_boundary": "one complete pair inverse for proposed phi output; shared pair-product basis, pivot index, and syndrome masks constructed before timing; all fallback work charged",
                "host_isolation": None,
                "source_sha256": {name: sha(path) for name, path in paths.items()}}
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "inputs": len(inputs),
                      "rank_drop_controls": [item["expected_rank"]
                                             for item in degenerate]}))


if __name__ == "__main__":
    main()
