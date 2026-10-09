#!/usr/bin/env python3
"""Bounded qualification ladder for the N19 invariant-barrel F4 control."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from g2_f4_control import cyclic_rows, equations  # noqa: E402


def main():
    out = HERE / "g2_f4_qualification.json"
    if out.exists():
        raise FileExistsError(out)
    n = 19
    modulus, s3, linear, pair_reps = equations(n)
    rows = set(cyclic_rows(s3, n))
    rows.add(frozenset(linear))
    for pair in pair_reps:
        rows.update(cyclic_rows(pair, n))
    inputs = [sorted(row) for row in sorted(rows, key=lambda row: (len(row), sorted(row)))]
    assert len(inputs) == 191
    equations_text = "\n".join(" ".join(map(str, [len(row), *row])) for row in inputs) + "\n"
    prior = json.loads((HERE / "g2_f4_control.json").read_text())
    attempts = [{"status": prior["native_f4_result"]["status"],
                 "reason": prior["native_f4_result"].get("reason"),
                 "proof_recorded": True,
                 "max_work": prior["native_f4_limits"]["work"],
                 "wall_ns_exploratory": prior["wall_ns_exploratory"]}]
    for work in (1_000_000_000, 5_000_000_000):
        shape = [3*n, len(inputs), work, 5_000_000, 100_000, 256, 0]
        data = " ".join(map(str, shape)) + "\n" + equations_text
        started = time.perf_counter_ns()
        try:
            proc = subprocess.run([str(HERE / "native_f4")], input=data,
                                  text=True, capture_output=True, timeout=120)
            result = json.loads(proc.stdout)
            result["exit_code"] = proc.returncode
        except subprocess.TimeoutExpired:
            result = {"status": "timeout", "timeout_seconds": 120}
        attempts.append({"max_work": work, "max_nodes": shape[3],
                         "max_rows": shape[4], "batch": shape[5],
                         "proof_recorded": False,
                         "status": result["status"], "reason": result.get("reason"),
                         "producer_stats": result.get("stats"),
                         "used_work": result.get("work", result.get("stats", {}).get("work")),
                         "basis_count": len(result["basis"]) if result["status"] == "gb" else None,
                         "wall_ns_exploratory": time.perf_counter_ns()-started})
        receipt = {"schema_version": 1, "proposal_id": "G2",
                   "candidate_id": None, "run_id": None,
                   "field_degree": n, "field_modulus_bits": modulus,
                   "boolean_variables": 3*n, "invariant_input_generators": len(inputs),
                   "equations_sha256": hashlib.sha256(equations_text.encode()).hexdigest(),
                   "attempts": attempts,
                   "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "control_receipt_sha256": hashlib.sha256(
                       (HERE / "g2_f4_control.json").read_bytes()).hexdigest()}
        out.write_text(json.dumps(receipt, sort_keys=True, indent=2)+"\n")
        if result["status"] == "gb":
            break
    print(json.dumps({"statuses": [attempt["status"] for attempt in attempts]}))


if __name__ == "__main__":
    main()
