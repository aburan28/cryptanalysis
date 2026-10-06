#!/usr/bin/env python3
"""Evaluate the known planted m5 witness against the exact unpinned XCNF."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from pathlib import Path

import arithmetic as a
import run as gate


class EvaluatingCircuit(gate.Circuit):
    def __init__(self, primary_values, limit):
        super().__init__(a.N, a.LOW_TERMS, memory_limit_bytes=limit)
        self.inputs = iter(primary_values)
        self.values: dict[int, bool] = {}
        self.gate_depth = 0
        self.primary_count = 0

    def value(self, wire):
        if wire == 0:
            return False
        if wire == -1:
            return True
        return self.values[wire]

    def set_value(self, wire, truth):
        if wire in (0, -1):
            assert self.value(wire) == bool(truth)
        elif wire in self.values:
            assert self.values[wire] == bool(truth)
        else:
            self.values[wire] = bool(truth)

    def variable(self):
        wire = super().variable()
        if self.gate_depth == 0:
            self.values[wire] = bool(next(self.inputs))
            self.primary_count += 1
        return wire

    def and_(self, left, right):
        truth = self.value(left) and self.value(right)
        self.gate_depth += 1
        try:
            output = super().and_(left, right)
        finally:
            self.gate_depth -= 1
        self.set_value(output, truth)
        return output

    def xor(self, items):
        items = tuple(items)
        truth = bool(sum(self.value(wire) for wire in items) & 1)
        self.gate_depth += 1
        try:
            output = super().xor(items)
        finally:
            self.gate_depth -= 1
        self.set_value(output, truth)
        return output

    def finish(self):
        try:
            next(self.inputs)
        except StopIteration:
            pass
        else:
            raise ArithmeticError("known witness has unused primary bits")
        if len(self.values) != self.next_var - 1:
            raise ArithmeticError("known witness lacks a gate value")

    def packed(self):
        packed = bytearray((self.next_var + 7) // 8)
        for wire, truth in self.values.items():
            if truth:
                packed[wire >> 3] |= 1 << (wire & 7)
        return bytes(packed)


def bits(word, count):
    return [(word >> bit) & 1 for bit in range(count)]


def known_inputs(controls, fiber_index):
    values = bits(fiber_index, 2)
    points = []
    for row in controls:
        mask, exponent, word = row["mask"], row["exponent"], int(row["word"])
        values.extend(bits(mask, 24))
        values.extend(bits(exponent, 8))
        values.extend(bits(a.inv(word), a.N))
        points.append(tuple(row["raw_point"]))
    prefix = points[0]
    partial_us = []
    for point in points[1:4]:
        prefix = a.add(prefix, point)
        assert prefix is not None and prefix[0] != 1
        partial_us.append(a.inv(prefix[0] ^ 1))
    for u in partial_us:
        values.extend(bits(u, a.N))
    assert len(values) == 2 + 5 * (24 + 8 + a.N) + 3 * a.N == 1210
    return values, partial_us


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-run-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "receipt.json").exists():
        parser.error("witness receipt already exists")
    strict = json.loads((args.strict_run_dir / "receipt.json").read_text())
    assert strict["mode"] == "planted" and strict["xcnf_sha256"]
    config, seed, normal, _ = gate.load_inputs()
    basis = a.source_basis()
    columns, output_columns = gate.normal_seed_columns(basis, normal)
    q, fibers, controls, fiber_index = gate.planted_input(seed, config, basis)
    assert strict["public_q"] == list(q)
    assert strict["planted_controls"] == controls
    values, partial_us = known_inputs(controls, fiber_index)
    started = time.perf_counter()
    circuit = EvaluatingCircuit(values, config["peak_rss_limit_bytes"])
    gate.build_formula(circuit, columns, output_columns, fibers)
    circuit.finish()
    rebuilt = out / "rebuilt.xcnf"
    circuit.write(rebuilt)
    try:
        rebuilt_hash = gate.digest(rebuilt)
        assert rebuilt_hash == strict["xcnf_sha256"]
        assert circuit.next_var - 1 == strict["variables"]
        assert len(circuit.clauses) == strict["cnf_clauses"]
        assert len(circuit.xors) == strict["xor_rows"]
        packed = circuit.packed()
        assignment = out / "assignment.bin.gz"
        assignment.write_bytes(gzip.compress(packed, compresslevel=9, mtime=0))
        receipt = {
            "schema": "ecc2k130-orbit-w24-m5-sat-witness-v1",
            "status": "constructed_unverified",
            "candidate_id": None,
            "strict_result_sha256": gate.digest(args.strict_run_dir / "receipt.json"),
            "xcnf_sha256": rebuilt_hash,
            "raw_assignment_sha256": hashlib.sha256(packed).hexdigest(),
            "compressed_assignment_sha256": gate.digest(assignment),
            "raw_assignment_bytes": len(packed),
            "primary_input_count": circuit.primary_count,
            "variables": circuit.next_var - 1,
            "cnf_clauses": len(circuit.clauses),
            "xor_rows": len(circuit.xors),
            "partial_sum_us": [str(value) for value in partial_us],
            "fiber_index": fiber_index,
            "public_q": list(q),
            "build_seconds_exploratory": time.perf_counter() - started,
            "source_sha256": {name: gate.digest(gate.HERE / name)
                              for name in (*gate.SOURCE_FILES, "witness.py")},
        }
        gate.save(out / "receipt.json", receipt)
        print(json.dumps({key: receipt[key] for key in
                          ("status", "xcnf_sha256", "variables",
                           "primary_input_count", "build_seconds_exploratory")},
                         sort_keys=True), flush=True)
    finally:
        if rebuilt.exists():
            rebuilt.unlink()


if __name__ == "__main__":
    main()
