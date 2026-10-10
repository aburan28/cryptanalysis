#!/usr/bin/env python3
"""Exact projected consistency gate for partially known adjacent pair outputs."""
import hashlib
import importlib.util
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ADJACENT = PARENT / "n131_w14_adjacent_pair_inverse_20261010"
SOURCE = PARENT / "n131_w14_polynomial_pair_inverse_20261010"
SUPPORT = PARENT / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
FULL = (1 << 131) - 1


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_adjacent():
    spec = importlib.util.spec_from_file_location("adjacent_source_run", ADJACENT / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invariant_mask(field, free_low_bits, products):
    """Rows independent of all low-bit changes for every product coefficient."""
    variable = 0
    for bit in range(free_low_bits):
        basis = 1 << bit
        squared = field.mul(basis, basis)
        variable |= squared
        delta_a = squared ^ basis
        for product in products:
            variable |= field.mul(delta_a, product)
    return FULL ^ variable


def gate(candidate, joint, z, width, invariant):
    field = candidate.field
    prefix = z & (FULL ^ ((1 << width) - 1))
    squared = field.mul(prefix, prefix)
    a_prefix = squared ^ prefix
    columns = [field.mul(u, u) & invariant for u in joint["sum_u_basis"]]
    columns += [field.mul(a_prefix, p) & invariant for p in joint["product_basis"]]
    pivots, kernel = candidate_oracle.echelon(columns)
    solution = candidate_oracle.solve(pivots, squared & invariant)
    return {"width": width, "prefix": prefix, "invariant_rows": invariant.bit_count(),
            "rank": len(pivots), "nullity": len(kernel),
            "status": "SPAN_REJECT" if solution is None else "CONSISTENT",
            "one_solution": solution}


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    dependencies = {"run": HERE / "run.py", "adjacent_run": ADJACENT / "run.py",
                    "adjacent_result": ADJACENT / "result.json",
                    "oracle": SOURCE / "oracle.py", "support": SUPPORT}
    assert protocol["status"] == "FROZEN_BEFORE_RUN"
    assert protocol["sha256"] == {name: sha(path) for name, path in dependencies.items()}
    assert not (HERE / "result.json").exists()
    started = time.monotonic_ns()
    adjacent = load_adjacent()
    global candidate_oracle
    candidate_oracle = adjacent.oracle
    candidate = candidate_oracle.PairOracle(candidate_oracle.load_support(SUPPORT))
    joint = adjacent.build_joint(candidate)
    assert len(joint["sum_u_basis"]) == 21
    assert len(joint["product_basis"]) == 40
    source = json.loads((ADJACENT / "result.json").read_text())
    queries = [row for row in source["records"] if row["kind"] in
               ("positive", "uniform_field")]
    assert len(queries) == 32
    widths = protocol["free_low_bits"]
    invariants = {width: invariant_mask(candidate.field, width,
                                        joint["product_basis"]) for width in widths}
    rows = []
    for width in widths:
        mask = invariants[width]
        for query in queries:
            row = gate(candidate, joint, query["z"], width, mask)
            row.update({"kind": query["kind"], "input_index": query["index"]})
            if query["kind"] == "positive" and row["status"] != "CONSISTENT":
                raise AssertionError("projected gate lost a verified source pair")
            rows.append(row)
    measured = time.monotonic_ns() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    result = {"status": "COMPLETE_PROJECTED_GATE", "candidate_id": None,
              "source_sha256": protocol["sha256"],
              "protocol_sha256": sha(HERE / "protocol.json"),
              "seed_dimension": 21, "product_dimension": 40,
              "free_low_bits": widths,
              "invariant_masks": {str(k): v for k, v in invariants.items()},
              "rows": rows, "wall_ns": measured, "peak_rss_bytes": peak}
    if measured > protocol["wall_cap_seconds"] * 1_000_000_000:
        result["status"] = "CENSORED_TIME"
    if peak > protocol["rss_cap_bytes"]:
        result["status"] = "CENSORED_MEMORY"
    (HERE / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "wall_ns": measured,
                      "peak_rss_bytes": peak,
                      "summary": [{"width": w,
                                   "rows": invariants[w].bit_count(),
                                   "control_rejects": sum(row["status"] == "SPAN_REJECT"
                                       for row in rows if row["width"] == w and
                                       row["kind"] == "uniform_field"),
                                   "max_nullity": max(row["nullity"] for row in rows
                                                      if row["width"] == w)}
                                  for w in widths]}))


if __name__ == "__main__":
    main()
