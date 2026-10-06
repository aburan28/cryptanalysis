"""Larger exact Boolean controls; report censored/failed cases without speedup claims."""
import hashlib
import json
import resource
import sys
import time

from solve_dual import HERE, compute_dual_basis, make_instance


def main():
    cases = [c for c in json.loads((HERE / "external-fixtures.json").read_text())
             if c["name"].startswith("planted-dense-mq")]
    for ell in (5, 6):
        start = time.perf_counter()
        instance = make_instance(31, 3, ell, seed=101)
        cases.append({"name": f"pdp-31-3-{ell}-seed101", "nvars": instance.nvars,
                      "equations": [sorted(g) for g in instance.equations()],
                      "input_setup_seconds": time.perf_counter() - start,
                      "field_degree": instance.n, "field_modulus": instance.mod,
                      "curve_b": instance.b, "target_x": instance.xR,
                      "nominal_subspace_dimension": ell})
    report = {"scope": "Complete Boolean GB stage with independent exhaustive certificate; no high-regularity, fastest-solver, or complete-DLP claim",
              "cells": []}
    for c in cases:
        equations = c["equations"]
        start = time.perf_counter()
        result = compute_dual_basis(c["nvars"], equations)
        elapsed = time.perf_counter() - start
        basis = result.pop("basis_terms", None)
        cell = {"name": c["name"], "nvars": c["nvars"], "equations": len(equations),
                "input_terms": sum(map(len, equations)), "wall_seconds": elapsed,
                "input_setup_seconds": c.get("input_setup_seconds"), "result": result,
                "input_sha256": hashlib.sha256(json.dumps({"nvars": c["nvars"], "equations": equations},
                                                          sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                "process_high_water_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                                                 (1 if sys.platform == "darwin" else 1024)}
        if basis is not None:
            cell["basis_terms"] = basis
        report["cells"].append(cell)
        (HERE / "results/scaling-probe.json").write_text(json.dumps(report, indent=2) + "\n")
        print(c["name"], result["status"], elapsed, result.get("basis_certificate"), flush=True)
    # Preserve complete raw equations separately from timing metadata.
    (HERE / "scaling-fixtures.json").write_text(json.dumps(cases, indent=2) + "\n")


if __name__ == "__main__":
    main()
