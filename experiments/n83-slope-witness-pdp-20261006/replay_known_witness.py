#!/usr/bin/env python3
"""Evaluate every Boolean gate on the frozen planted N83 group witness."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from run_slope_branch import (HERE, PRIVATE, PROTOCOL, PUBLIC, REPS,
                              SlopeWitnessCircuit, replay, verify_model)
from indexed_factor import factor
from gf2n import Curve, Point

SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main(out: Path) -> None:
    out = out.resolve()
    if out.exists():
        raise FileExistsError("known-witness replay output is immutable")
    out.mkdir(parents=True)
    with (out / "sage_runtime_info.json").open("wb") as f:
        subprocess.run([str(SAGE), "--runtime-info"], stdout=f, check=True)
    protocol = json.loads(PROTOCOL.read_text())
    public = json.loads(PUBLIC.read_text())
    private = json.loads(PRIVATE.read_text())
    assert sha(PUBLIC) == protocol["source_public_fixture_sha256"]
    assert sha(PRIVATE) == protocol["regenerated_private_fixture_sha256_local_only"]
    assert sha(REPS) == protocol["full_w34_representatives_sha256"]
    assert private["public_input_sha256"] == sha(PUBLIC)
    fiber = public["planted"]["raw_target_fiber"][0]
    assert [fiber["x"], fiber["y"]] == private["raw_sum"]
    sources = {
        "replay": Path(__file__),
        "branch_runner": HERE / "run_slope_branch.py",
        "slope_circuit": HERE / "slope_witness_circuit.py",
        "indexed_factor": HERE.parent / "n83-indexed-factor-pdp-20261006/indexed_factor.py",
    }
    save(out / "started.json", {
        "kind": "n83_slope_known_witness_boolean_replay_start",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(PROTOCOL),
        "public_fixture_sha256": sha(PUBLIC),
        "private_fixture_sha256_local_only": sha(PRIVATE),
        "source_sha256": {name: sha(path) for name, path in sources.items()},
        "sage_runtime_info_sha256": sha(out / "sage_runtime_info.json"),
    })
    started = time.perf_counter_ns()
    builder = SlopeWitnessCircuit(83, [0, 2, 4, 7])
    c = builder.circuit
    conjugates = [int(v) for v in public["normal_conjugates_polynomial_bits_decimal"]]
    encoded = [factor(c, conjugates) for _ in range(5)]
    witness = builder.require_sum([item["x"] for item in encoded],
                                  int(fiber["x"]), int(fiber["y"]))
    group = Curve(builder.field, 1)
    model: dict[int, bool] = {}

    def set_word(wires: list[int], word: int) -> None:
        assert len(wires) == 83
        for bit, wire in enumerate(wires):
            if wire > 0:
                value = bool(word & (1 << bit))
                if wire in model:
                    assert model[wire] == value
                else:
                    model[wire] = value

    points = []
    for item, pair_wires, selected in zip(encoded, witness["factors"],
                                          private["selected"]):
        mask = selected["mask"]
        values = sorted(mask) + ([83] if len(mask) == 3 else [])
        assert len(values) == 4
        for position, value in zip(item["positions"], values):
            for bit, wire in enumerate(position["bits"]):
                model[wire] = bool(value & (1 << bit))
            for index, wire in position["onehot"].items():
                model[wire] = index == value
        point = Point(*(int(v) for v in selected["raw_point"]))
        assert group.on_curve(point) and point.x != 0
        computed_x = 0
        for bit in mask:
            computed_x ^= conjugates[bit]
        assert computed_x == point.x
        set_word(pair_wires[1], point.y)
        points.append(point)
    prefix = points[0]
    for other, slope_wires in zip(points[1:], witness["slopes"]):
        denominator = prefix.x ^ other.x
        assert denominator != 0
        slope = builder.field.mul(prefix.y ^ other.y,
                                  builder.field.inv(denominator))
        set_word(slope_wires, slope)
        prefix = group.add(prefix, other)
        assert not prefix.inf
    assert [str(prefix.x), str(prefix.y)] == private["raw_sum"]

    and_by_output = {output: pair for pair, output in c.and_cache.items()}
    xor_by_output = {output: key for key, output in c.xor_cache.items()}

    def value(wire: int) -> bool:
        if wire == -1:
            return True
        if wire == 0:
            return False
        return model[wire]

    for wire in range(1, c.next_var):
        if wire in model:
            continue
        if wire in and_by_output:
            a, b = and_by_output[wire]
            model[wire] = value(a) and value(b)
        elif wire in xor_by_output:
            terms, parity = xor_by_output[wire]
            model[wire] = bool(parity ^ (sum(value(term) for term in terms) % 2))
        else:
            raise AssertionError(f"unassigned primary wire {wire}")
    assert len(model) == c.next_var - 1
    assert verify_model(c, model)
    checked = replay(model, encoded, witness, conjugates,
                     public, "planted", fiber)
    assert checked["verified"]
    save(out / "private_model.json", checked)
    packed = bytearray((c.next_var + 7) // 8)
    for wire, truth in model.items():
        if truth:
            packed[wire // 8] |= 1 << (wire % 8)
    receipt = {
        "schema_version": 1,
        "kind": "n83_slope_known_witness_boolean_replay",
        "status": "BOOLEAN_MODEL_VERIFIED_PENDING_SAGE",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "factor_count": 5,
        "variables_fully_assigned": c.next_var - 1,
        "cnf_clauses_verified": len(c.clauses),
        "xor_rows_verified": len(c.xors),
        "all_boolean_constraints_verified": True,
        "group_verified_by_reference_python": True,
        "private_model_sha256_local_only": sha(out / "private_model.json"),
        "assignment_bitset_sha256_local_only": hashlib.sha256(packed).hexdigest(),
        "started_sha256": sha(out / "started.json"),
        "wall_ns_exploratory": time.perf_counter_ns() - started,
        "online_target_wall_ns": None,
        "rho_online_wall_ns": None,
        "online_speedup": None,
        "claim_boundary": "Known private factor points and slopes were supplied. This proves the full circuit has a valid Boolean model, not that SAT search can find it, and not ordinary relation yield.",
    }
    save(out / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"],
                      "variables": receipt["variables_fully_assigned"]},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: replay_known_witness.py OUT_DIR")
    main(Path(sys.argv[1]))
