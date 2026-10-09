#!/usr/bin/env python3
"""Exhaustively verify the Frobenius-chain root gate on N19 planted cells."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from sage.all import PolynomialRing

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-20261007"
sys.path.insert(0, str(PRIOR))
from sage_probes import bits, candidate_x_points, curve, field, planted_targets  # noqa: E402


def main():
    old_path = PRIOR / "results/g4_frobenius_followup_final.json"
    old = json.loads(old_path.read_text())
    K, modulus = field(19)
    E = curve(K)
    basis, points = candidate_x_points(E, K, 2)
    targets = planted_targets(points, 3, 12)
    T = PolynomialRing(K, "z")
    z = T.gen()
    cells = []
    for target_index, (Q, _) in enumerate(targets):
        rational_hits = 0
        closure_hits = 0
        all_chain2_roots = 0
        all_chain4_roots = 0
        for assignment in range(64):
            xs = [sum((basis[j] for j in range(2)
                       if assignment >> (2*i+j) & 1), K(0))
                  for i in range(3)]
            def s3(a, b, c):
                return (a*b+a*c+b*c)**2+a*b*c+1
            common = s3(xs[0], xs[1], z).gcd(s3(z, xs[2], Q[0]))
            closure_hits += common.degree() > 0
            roots = [root for root, _ in common.roots()]
            rational_hits += bool(roots)
            for root in roots:
                chain2 = [root**(2**j) for j in range(19)]
                chain4 = [root**(4**j) for j in range(10)]
                assert chain2[-1]**2 == root
                assert chain4[-1]**2 == root
                assert all(chain2[i+1] == chain2[i]**2 for i in range(18))
                assert all(chain4[i+1] == chain4[i]**4 for i in range(9))
                all_chain2_roots += 1
                all_chain4_roots += 1
        old_cell = old["cells"][target_index]
        assert closure_hits == old_cell["algebraic_closure_hits"]
        assert rational_hits == old_cell["field_rational_hits"]
        cells.append({"target_index": target_index,
                      "target_point": [bits(Q[0]), bits(Q[1])],
                      "leaf_assignments": 64,
                      "algebraic_closure_hits": closure_hits,
                      "field_rational_hits": rational_hits,
                      "chain2_rational_root_witnesses": all_chain2_roots,
                      "chain4_rational_root_witnesses": all_chain4_roots})
    result = {"schema_version": 1, "proposal_id": "G4",
              "candidate_id": None, "run_id": None,
              "field_degree": 19, "field_modulus_bits": modulus,
              "cells": cells,
              "total_false_closure_hits_removed": sum(
                  c["algebraic_closure_hits"]-c["field_rational_hits"]
                  for c in cells),
              "chain2_identity": "z_i=z_0^(2^i), z_0=z_18^2",
              "chain4_identity": "z_i=z_0^(4^i), z_0=z_9^2",
              "scope": "finite-field root equivalence; no F4 performance claim",
              "prior_receipt_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    output = HERE / "g4_chain_equivalence.json"
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"cells": len(cells),
                      "false_hits_removed": result["total_false_closure_hits_removed"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
