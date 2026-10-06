#!/usr/bin/env python3
"""Exhaustive N3 and archived N53/N83 checks for the joint S3 tail join."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from chain_s3 import evaluate_s3, field  # noqa: E402
from q1423_target_coupled.target_inputs import target_list  # noqa: E402
from q1455_joint_tail.joint_tail import (  # noqa: E402
    PartialLeaf, join, options)

OUTPUT = HERE / "controls.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def small_field() -> dict:
    n, weight = 3, 2
    onb = field.Onb(n)
    full = (1 << n) - 1
    values = [x for x in range(1, 1 << n) if x.bit_count() <= weight]
    elements = [onb.fromCoords(x) for x in range(1 << n)]
    direct_pair = {
        (a, b): frozenset(m for m in range(1 << n)
                          if evaluate_s3(onb, elements[a], elements[b],
                                         elements[m]) == 0)
        for a in values for b in values
    }
    direct_final = {
        (m, p, t): evaluate_s3(onb, elements[m], elements[p],
                              elements[t]) == 0
        for m in range(1 << n) for p in range(1 << n)
        for t in range(1, 1 << n)
    }

    def direct_exists(domains: list[tuple[int, ...]], t: int) -> bool:
        for a, b in itertools.product(domains[0], domains[1]):
            for c, d in itertools.product(domains[2], domains[3]):
                for m in direct_pair[a, b]:
                    for p in direct_pair[c, d]:
                        if direct_final[m, p, t]:
                            return True
        return False

    checked_full = 0
    for leaves in itertools.product(values, repeat=4):
        state = tuple(PartialLeaf(full, x) for x in leaves)
        for t in range(1, 1 << n):
            observed = join(onb, state, t, weight, 1)
            assert (observed["status"] == "x_only_witness") == direct_exists(
                [(x,) for x in leaves], t)
            checked_full += 1

    rng = random.Random(1455)
    checked_partial = 0
    for _ in range(128):
        state = []
        for _leaf in range(4):
            seed = rng.choice(values)
            free = rng.sample(range(n), rng.randrange(n + 1))
            mask = full ^ sum(1 << j for j in free)
            state.append(PartialLeaf(mask, seed & mask))
        t = rng.randrange(1, 1 << n)
        domains = [options(leaf, n, weight) for leaf in state]
        observed = join(onb, tuple(state), t, weight, len(values) ** 2)
        assert observed["status"] != "skipped"
        assert (observed["status"] == "x_only_witness") == direct_exists(
            domains, t)
        checked_partial += 1
    return {"degree_n": n, "weight_bound": weight,
            "complete_leaf_target_cases": checked_full,
            "partial_four_leaf_cases": checked_partial,
            "direct_oracle": "full-field S3 evaluation, independent of roots"}


def partial_witness(values: list[int], n: int) -> tuple[PartialLeaf, ...]:
    full = (1 << n) - 1
    leaves = []
    for value in values:
        ones = [j for j in range(n) if value >> j & 1]
        zeros = [j for j in range(n) if not value >> j & 1]
        free = [ones[0], *zeros[:3]]
        mask = full ^ sum(1 << j for j in free)
        leaves.append(PartialLeaf(mask, value & mask))
    return tuple(leaves)


def archived_witness(n: int) -> dict:
    if n == 53:
        source = PARENT / "q1452_known_satisfiable_phi5/controls.json"
        record = json.loads(source.read_text())
        assert record["status"] == "pass"
        curve_id = "EC1N53Ckb1hf77aab617904"
        leaves = record["known_witness_raw_leaf_x"]
        target_x = record["selected_raw_target_x"]
        target_index = record["target_preimage_index"]
        weight = 4
        base = json.loads((PARENT / "q1438_dense_base/n53_w4_base.json").read_text())
    else:
        assert n == 83
        source = PARENT / "q1446_joint_pair_span/validation.json"
        record = json.loads(source.read_text())["controls"][1]
        assert record["degree"] == n
        curve_id = record["curve_id"]
        leaves = record["point_relation"]["raw_leaf_x"]
        q1436 = json.loads((PARENT / "q1436_affine_pair/protocol.json").read_text())[
            "workloads"]["n83_free_partner"]
        q1420 = json.loads((PARENT / "q1420_root_theory/protocol.json").read_text())[
            "workloads"][q1436["parent_q1420_key"]]
        raw_targets = target_list(n, "free_mids", q1420)
        assert len(raw_targets) == 4
        target_index = 3
        target_x = raw_targets[target_index]
        weight = 6
        base = json.loads((PARENT / "q1438_dense_base/n83_w6_base.json").read_text())
    assert base["curve_id"] == curve_id
    assert max(value.bit_count() for value in leaves) <= weight
    partial = partial_witness(leaves, n)
    assert all(value in options(state, n, weight)
               for value, state in zip(leaves, partial))
    start = time.perf_counter_ns()
    observed = join(field.Onb(n), partial, target_x, weight, 256)
    wall = time.perf_counter_ns() - start
    assert observed["status"] == "x_only_witness", observed
    assert observed["witness"]["leaf_x"] == leaves
    return {"degree_n": n, "curve_id": curve_id,
            "factor_base_actual_B": base[
                "actual_usable_points_B_before_folding"],
            "folded_columns_K": base["signed_frobenius_columns_K"],
            "factor_base_enumerated_set_sha256": base[
                "enumerated_set_sha256"],
            "source_sha256": sha(source), "weight_bound": weight,
            "target_preimage_index": target_index,
            "target_x": target_x,
            "archived_group_verified_leaf_x": leaves,
            "result": observed,
            "control_wall_ns_exploratory": wall}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q1455"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["source_sha256"]["joint_tail.py"] == sha(
        HERE / "joint_tail.py")
    assert protocol["source_sha256"]["run_controls.py"] == sha(
        Path(__file__))
    small = small_field()
    witnesses = [archived_witness(n) for n in (53, 83)]
    result = {"kind": "q1455_joint_bounded_pair_controls",
              "proposal_id": "Q1455", "candidate_id": None,
              "isogeny": "none", "status": "pass",
              "small_field": small, "archived_witnesses": witnesses,
              "protocol_sha256": sha(protocol_path),
              "successful_ordinary_query_measured": False,
              "complete_n131_log2_work": None,
              "challenge_run_admitted": False}
    if args.check:
        archived = json.loads(OUTPUT.read_text())
        assert {key: val for key, val in result.items()
                if key != "archived_witnesses"} == {
                    key: val for key, val in archived.items()
                    if key != "archived_witnesses"}
        for actual, saved in zip(witnesses, archived["archived_witnesses"]):
            assert {key: val for key, val in actual.items()
                    if key != "control_wall_ns_exploratory"} == {
                        key: val for key, val in saved.items()
                        if key != "control_wall_ns_exploratory"}
        print("Q1455 joint bounded-pair controls: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1455",
                          "small_field_cases": small[
                              "complete_leaf_target_cases"] +
                              small["partial_four_leaf_cases"],
                          "witness_degrees": [53, 83]}))


if __name__ == "__main__":
    main()
