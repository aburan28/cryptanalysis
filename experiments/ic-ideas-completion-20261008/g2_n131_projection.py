#!/usr/bin/env python3
"""Exact degree-three barrel matrix dimensions at N131, without an F4 run."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def dimension(n):
    assert n > 3 and n % 2 == 1
    variables = 3*n
    columns = sum(math.comb(variables, d) for d in range(4))
    monomial_orbits = 1+(columns-1)//n
    assert 1+(columns-1)%n == 1
    pair_equations = math.comb(n, 2)
    full_rows = n + (1+variables+math.comb(variables, 2)) + \
                pair_equations*(1+variables)
    multiplier_orbits = 1+3+math.comb(variables, 2)//n
    pair_orbits = (n-1)//2
    source_seed_rows = 1+multiplier_orbits+pair_orbits*(1+variables)
    return {"n": n, "boolean_variables": variables,
            "ambient_columns_degree3": columns,
            "monomial_orbit_columns": monomial_orbits,
            "onehot_pair_equations": pair_equations,
            "full_source_rows": full_rows,
            "source_seed_rows": source_seed_rows}


def main():
    cells = [dimension(n) for n in (19, 23, 131)]
    for n, path in ((19, HERE / "g2_n19.json"),
                    (23, HERE / "g2_n23.json")):
        measured = json.loads(path.read_text())["cells"][0]
        expected = next(item for item in cells if item["n"] == n)
        assert measured["ambient_binary_columns"] == expected["ambient_columns_degree3"]
        assert measured["monomial_orbit_columns"] == expected["monomial_orbit_columns"]
        assert measured["source_seed_rows"] == expected["source_seed_rows"]
    n131 = cells[-1]
    extension_degree = 1
    while pow(2, extension_degree, 131) != 1:
        extension_degree += 1
    assert extension_degree == 130
    # Even one dense nontrivial block requires this many bytes if each field
    # coefficient is stored in the minimum ceil(130/8) bytes; actual algebra
    # packages incur additional representation overhead.
    n131["nontrivial_character_extension_degree"] = extension_degree
    n131["dense_nontrivial_block_coefficient_bytes_floor"] = (
        n131["source_seed_rows"]*n131["monomial_orbit_columns"]*
        math.ceil(extension_degree/8))
    n131["dense_binary_matrix_packed_bytes_floor"] = (
        n131["full_source_rows"]*n131["ambient_columns_degree3"]+7)//8
    result = {"schema_version": 1, "proposal_id": "G2",
              "candidate_id": None, "run_id": None, "degree": 3,
              "cells": cells,
              "scope": "exact combinatorial dimensions; N131 block elimination and F4 timing unmeasured",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "n19_receipt_sha256": hashlib.sha256((HERE / "g2_n19.json").read_bytes()).hexdigest(),
              "n23_receipt_sha256": hashlib.sha256((HERE / "g2_n23.json").read_bytes()).hexdigest()}
    output = HERE / "g2_n131_projection.json"
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps(n131, sort_keys=True))


if __name__ == "__main__":
    main()
