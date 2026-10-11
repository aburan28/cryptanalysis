#!/usr/bin/env python3
"""Construct a planted truth assignment for the committed functional-S3 XCNF."""

import argparse
import gzip
import hashlib
import json
import platform
import resource
import signal
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as gate  # noqa: E402


def peak_rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


class WitnessCircuit(gate.Circuit):
    """Evaluate each gate while emitting the same XCNF as the parent class."""

    def __init__(self, n, low_terms, primary_values, memory_limit_bytes):
        super().__init__(n, low_terms, memory_limit_bytes=memory_limit_bytes)
        self.primary_values = iter(primary_values)
        self.values = {}
        self.gate_depth = 0
        self.primary_count = 0

    def value(self, wire):
        if wire == 0:
            return False
        if wire == -1:
            return True
        return self.values[wire]

    def set_value(self, wire, value):
        if wire in (0, -1):
            assert self.value(wire) == bool(value)
        elif wire in self.values:
            assert self.values[wire] == bool(value)
        else:
            self.values[wire] = bool(value)

    def variable(self):
        wire = super().variable()
        if self.gate_depth == 0:
            self.values[wire] = bool(next(self.primary_values))
            self.primary_count += 1
        return wire

    def and_(self, left, right):
        value = self.value(left) and self.value(right)
        self.gate_depth += 1
        try:
            output = super().and_(left, right)
        finally:
            self.gate_depth -= 1
        self.set_value(output, value)
        return output

    def xor(self, items):
        items = tuple(items)
        value = bool(sum(self.value(wire) for wire in items) & 1)
        self.gate_depth += 1
        try:
            output = super().xor(items)
        finally:
            self.gate_depth -= 1
        self.set_value(output, value)
        return output

    def finish(self):
        try:
            next(self.primary_values)
        except StopIteration:
            pass
        else:
            raise ValueError("unused primary input values")
        assert len(self.values) == self.next_var - 1
        assert self.primary_count == 150

    def packed_assignment(self):
        packed = bytearray((self.next_var + 7)//8)
        for wire, value in self.values.items():
            if value:
                packed[wire >> 3] |= 1 << (wire & 7)
        return bytes(packed)


def witness_inputs(base, basis):
    a, f = gate.a, gate.f
    q, fibers, masks, raw_points, fiber_index = gate.parent_run.control_input(
        base, basis)
    root_bits, branches, partial_us = [], [], []
    prefix = raw_points[0]
    for slot in range(1, 5):
        next_prefix = a.add(prefix, raw_points[slot])
        assert prefix is not None and next_prefix is not None
        current_u = a.inv(prefix[0] ^ 1)
        leaf_u = a.halftrace(a.source_w(masks[slot], basis))
        wanted_u = a.inv(next_prefix[0] ^ 1)
        options = [f.numeric_s3_root(current_u, leaf_u, bit)
                   for bit in (0, 1)]
        assert all(residual == 0 for _, _, residual in options)
        matching = [bit for bit, (root, _, _) in enumerate(options)
                    if root == wanted_u]
        assert matching
        chosen = matching[0]
        root_bits.append(chosen)
        branches.append(options[chosen][1])
        partial_us.append(wanted_u)
        prefix = next_prefix
    values = [fiber_index & 1, (fiber_index >> 1) & 1]
    values.extend((mask >> bit) & 1 for mask in masks for bit in range(24))
    values.extend(root_bits)
    assert len(values) == 150
    return q, fibers, masks, raw_points, fiber_index, root_bits, branches, partial_us, values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "receipt.json").exists() or (out / "system.xcnf").exists():
        parser.error("witness output already exists")
    if not (out / "runtime-info.json").is_file():
        parser.error("save checked Sage runtime-info before building")
    config, base, _workload = gate.load_pinned()
    strict = json.loads((HERE / "runs/planted/receipt.json").read_text())
    assert strict["status"] == "timeout" and strict["model"] is None
    assert strict["xcnf_sha256"] == (
        "1e12c05b798af29e5ccbde939a618caffcd4b5605a19111b6153a0aaff136e6a")
    start = time.perf_counter()
    basis = gate.a.source_basis()
    half_basis = tuple(gate.a.halftrace(w) for w in basis)
    trace_positions = gate.parent_run.field_trace_positions()
    (q, fibers, masks, raw_points, fiber_index, root_bits, branches,
     partial_us, primary_values) = witness_inputs(base, basis)
    query_seconds = time.perf_counter() - start
    circuit = WitnessCircuit(gate.a.N, gate.a.LOW_TERMS, primary_values,
                             config["peak_rss_limit_bytes"])
    build_start = time.perf_counter()

    def alarm_handler(_signum, _frame):
        raise TimeoutError("witness build exceeded frozen wall bound")

    signal.signal(signal.SIGALRM, alarm_handler)
    signal.alarm(config["build_wall_limit_seconds"])
    try:
        gate.build_formula(circuit, basis, half_basis, trace_positions,
                           fibers, masks, fiber_index)
        circuit.finish()
        circuit.write(out / "system.xcnf")
        xcnf_sha256 = gate.parent_run.digest(out / "system.xcnf")
        assert xcnf_sha256 == strict["xcnf_sha256"]
        packed = circuit.packed_assignment()
        (out / "assignment.bin.gz").write_bytes(
            gzip.compress(packed, compresslevel=9, mtime=0))
    except Exception as exc:
        failure = {"schema": "ecc2k130-w24-functional-s3-witness-v1",
                   "status": "build_failure", "error_type": type(exc).__name__,
                   "error": str(exc), "build_seconds": time.perf_counter()-build_start,
                   "source_sha256": {name: gate.parent_run.digest(HERE / name)
                                     for name in ("witness_generate.py", "verify_witness.py", "witness_sage.py")},
                   "candidate_id": None}
        gate.parent_run.save(out / "receipt.json", failure)
        raise
    finally:
        signal.alarm(0)
    report = {
        "schema": "ecc2k130-w24-functional-s3-witness-v1",
        "status": "constructed_unverified",
        "candidate_id": None,
        "planted_masks": masks,
        "planted_raw_points": [list(point) for point in raw_points],
        "planted_fiber_index": fiber_index,
        "public_q": list(q),
        "raw_fibers": [list(point) for point in fibers],
        "root_choice_bits": root_bits,
        "root_branch_classes": branches,
        "partial_sum_us": partial_us,
        "primary_input_count": circuit.primary_count,
        "variables": circuit.next_var-1,
        "and_gates": circuit.and_count,
        "cnf_clauses": len(circuit.clauses),
        "xor_rows": len(circuit.xors),
        "xcnf_sha256": xcnf_sha256,
        "xcnf_bytes": (out / "system.xcnf").stat().st_size,
        "packed_assignment_sha256": gate.parent_run.digest(
            out / "assignment.bin.gz"),
        "packed_assignment_raw_sha256": hashlib.sha256(packed).hexdigest(),
        "packed_assignment_bytes": len(packed),
        "config_sha256": gate.parent_run.digest(HERE / "CONFIG.json"),
        "witness_protocol_sha256": gate.parent_run.digest(
            HERE / "WITNESS_PROTOCOL.md"),
        "sage_runtime_info_sha256": gate.parent_run.digest(
            out / "runtime-info.json"),
        "source_sha256": {name: gate.parent_run.digest(HERE / name)
                          for name in ("witness_generate.py", "verify_witness.py", "witness_sage.py")},
        "query_seconds": query_seconds,
        "build_seconds": time.perf_counter()-build_start,
        "builder_peak_rss_bytes": peak_rss_bytes(),
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "cpu_isolation": "unverified"},
        "natural_target_attempted": False,
        "verified_logarithm": None,
        "online_wall_time": None,
        "rho_ratio": None,
    }
    assert report["variables"] == strict["variables"]
    assert report["cnf_clauses"] == strict["cnf_clauses"]
    assert report["xor_rows"] == strict["xor_rows"]
    assert report["builder_peak_rss_bytes"] < config["peak_rss_limit_bytes"]
    gate.parent_run.save(out / "receipt.json", report)
    print(json.dumps({key: report[key] for key in
                      ("status", "variables", "cnf_clauses", "xor_rows",
                       "xcnf_sha256", "root_choice_bits", "build_seconds")},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
