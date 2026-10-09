#!/usr/bin/env python3
"""Check installed extension-field F4 routes for the N19 mixed encoding."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent


def main():
    out = HERE / "g4_backend_gate.json"
    if out.exists():
        raise FileExistsError(out)
    K = GF(2**19, "a19")
    R = PolynomialRing(K, "x", 1, order="degrevlex")
    x = R.gen()
    ideal = R.ideal([x*x+x])
    rows = []
    for algorithm in ("msolve", "libsingular:std"):
        try:
            basis = ideal.groebner_basis(algorithm=algorithm)
            rows.append({"algorithm": algorithm, "status": "completed",
                         "basis": [str(poly) for poly in basis]})
        except Exception as error:
            rows.append({"algorithm": algorithm, "status": "unsupported",
                         "exception_type": type(error).__name__,
                         "exception_message": str(error)})
    answer = {"schema_version": 1, "proposal_id": "G4",
              "candidate_id": None, "run_id": None,
              "field_degree": 19, "probe_system": "x^2+x over GF(2^19)",
              "available_macaulay2_executable": shutil.which("M2"),
              "backend_rows": rows,
              "scope": "installed backend capability probe for matched mixed-field F4",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"backends": [(row["algorithm"],row["status"])
                                    for row in rows],
                      "M2": answer["available_macaulay2_executable"]}))


if __name__ == "__main__":
    main()
