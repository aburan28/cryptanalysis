#!/usr/bin/env python3
"""Independently certify selected fresh F4 bases in the N31 trace gate."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCER = HERE.parent / "groebner-perf-20260924/round5"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PRODUCER))
from g1_f4_trace import native_f4, solution_set, systems  # noqa: E402
from algebraic_certificate import verify  # noqa: E402


def main():
    out = HERE / "g1_f4_audit.json"
    if out.exists():
        raise FileExistsError(out)
    prior = json.loads((HERE / "g1_f4_trace.json").read_text())
    cells = []
    for arity, indices in ((2, (0, 1)), (3, (0, 2))):
        _, cases = systems(arity, 16)
        for index in indices:
            target_x, equations = cases[index]
            fresh = native_f4(HERE / "native_f4", equations, 3 * arity, True)
            assert fresh["status"] == "gb"
            certificate = verify(3 * arity, equations, fresh["basis"], fresh["proof"],
                                 max_work=1_000_000_000,
                                 max_retained_terms=10_000_000)
            truth = solution_set(equations, 3 * arity)
            basis_truth = solution_set(fresh["basis"], 3 * arity)
            assert certificate["verified"] and truth == basis_truth
            cells.append({"arity": arity, "target_index": index,
                          "target_x_bits": target_x,
                          "certificate_status": certificate["status"],
                          "certificate_verified": certificate["verified"],
                          "fresh_basis_solution_set_equal": truth == basis_truth,
                          "solution_count": len(truth),
                          "basis_count": len(fresh["basis"]),
                          "proof_nodes": len(fresh["proof"]["nodes"])})
    answer = {"schema_version": 1, "proposal_id": "G1",
              "candidate_id": None, "run_id": None,
              "audited_cells": cells,
              "trace_receipt_sha256": hashlib.sha256(
                  (HERE / "g1_f4_trace.json").read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"audited": len(cells),
                      "verified": sum(c["certificate_verified"] for c in cells)}))


if __name__ == "__main__":
    main()
