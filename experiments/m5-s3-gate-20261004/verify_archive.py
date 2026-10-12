#!/usr/bin/env python3
"""Independently audit Q1417 archives and replay SAT relations.

This intentionally does not import the formula builder, runner, or their
model-replay functions.  Run it with the repository's checked Sage launcher.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import sys
from itertools import product
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNS = HERE / "runs"
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import curves  # noqa: E402
import field  # noqa: E402


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def point(record):
    return tuple(map(int, record))


def fold_x(onb, xy, n):
    return min(onb.toCoords(onb.frob(xy[0], shift))
               for shift in range(n))


def read_model(stdout: str, count: int):
    assert "s SATISFIABLE" in stdout
    model = {}
    for line in stdout.splitlines():
        if not line.startswith("v "):
            continue
        for token in line.split()[1:]:
            lit = int(token)
            if lit:
                key = abs(lit)
                assert key not in model and 1 <= key <= count
                model[key] = lit > 0
    assert len(model) == count
    return model


def formula_audit(raw: bytes, model):
    lines = raw.decode("ascii").splitlines()
    header = lines.pop(0).split()
    assert header[:2] == ["p", "cnf"]
    variables, row_count = map(int, header[2:])
    assert len(lines) == row_count
    if model is not None:
        assert len(model) == variables
    cnf = xor = 0
    for line in lines:
        is_xor = line.startswith("x")
        tokens = (line[1:] if is_xor else line).split()
        assert tokens and tokens[-1] == "0"
        lits = list(map(int, tokens[:-1]))
        assert lits and all(0 < abs(lit) <= variables for lit in lits)
        if is_xor:
            xor += 1
        else:
            cnf += 1
        if model is None:
            continue
        values = [model[abs(lit)] == (lit > 0) for lit in lits]
        assert (sum(values) % 2 == 1) if is_xor else any(values), line[:100]
    return {"variables": variables, "cnf_rows": cnf,
            "xor_rows": xor, "all_model_rows_satisfied": model is not None}


def exact_base(n: int, weight: int, profile):
    path = (ROOT / "experiments/compact-s3-m4-20261003/bases" /
            f"n{n}_weight{weight}_orbits.json.gz")
    assert file_digest(path) == profile["base_archive_sha256"]
    with gzip.open(path, "rt") as stream:
        base = json.load(stream)
    fb = base["factor_base"]
    assert fb["enumerated_set_sha256"] == profile["base_digest"]
    assert fb["actual_usable_points_B_before_folding"] == profile["actual_B"]
    assert fb["signed_frobenius_columns"] == profile["folded_columns_K"]
    assert fb["cofactor_projection"] == profile["cofactor"]
    encoded = base64.b64decode(fb["packed_canonical_x_keys_base64"],
                               validate=True)
    assert digest(encoded) == profile["base_digest"]
    width = (n + 7) // 8
    keys = {int.from_bytes(encoded[i:i + width], "little")
            for i in range(0, len(encoded), width)}
    assert len(encoded) == width * len(keys)
    assert len(keys) == profile["folded_columns_K"]
    return base, keys


def independent_relation_replay(receipt, model, onb, curve, base_keys,
                                raw_target_points, order, cofactor):
    relation = receipt["verified_relation"]
    assert relation is not None
    n = receipt["field_degree_n"]
    weight = receipt["normal_basis_weight_bound"]
    # Formula.new() starts after its fixed TRUE variable 1.  The five leaf
    # coordinates are allocated before all other formula variables.
    leaves = [sum(1 << bit for bit in range(n)
                  if model[2 + leaf * n + bit]) for leaf in range(5)]
    assert leaves == relation["raw_leaf_x"]
    assert all(0 < x.bit_count() <= weight for x in leaves)
    raw_points = [curve.pointFromX(onb.fromCoords(x)) for x in leaves]
    assert all(p is not None and curve.onCurve(p) for p in raw_points)
    assert [[str(v) for v in p] for p in raw_points] == (
        relation["raw_leaf_points"])
    target = point(receipt["public_target"])
    selected = point(relation["raw_target"])
    assert raw_target_points[relation["choice"]] == selected
    assert curve.mul(selected, cofactor) == target
    witnesses = []
    for signs in product((1, -1), repeat=5):
        signed = [p if sign > 0 else curve.neg(p)
                  for p, sign in zip(raw_points, signs)]
        raw_sum = None
        for p in signed:
            raw_sum = curve.add(raw_sum, p)
        if raw_sum != selected:
            continue
        projected = [curve.mul(p, cofactor) for p in signed]
        assert all(p is not None and curve.mul(p, order) is None
                   for p in projected)
        keys = [fold_x(onb, p, n) for p in projected]
        assert all(key in base_keys for key in keys)
        projected_sum = None
        for p in projected:
            projected_sum = curve.add(projected_sum, p)
        assert projected_sum == target
        witnesses.append((signs, projected, keys))
    assert witnesses
    assert any(
        list(signs) == relation["signs"] and
        [[str(v) for v in p] for p in projected] ==
        relation["projected_points"] and keys == relation["column_keys"]
        for signs, projected, keys in witnesses)
    assert relation["public_target"] == receipt["public_target"]
    assert relation["distinct_columns"] == (
        len(set(relation["column_keys"])) == 5)
    return {"valid_signed_lifts": len(witnesses),
            "distinct_columns": relation["distinct_columns"],
            "exact_base_membership": True,
            "subgroup_sum_equals_public_target": True}


def audit():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q1417"
    assert protocol["revision"] == 2
    assert protocol["candidate_id"] is None
    assert protocol["claim_gate"]["single_ordinary_query_estimates_yield_rate"] is False
    for name, expected in protocol["source_sha256"].items():
        assert file_digest(ROOT / name) == expected, name
    assert file_digest(HERE / "sage_runtime_info.json") == (
        protocol["sage_runtime_info_sha256"])
    assert file_digest(Path(protocol["solver"]["binary_path"])) == (
        protocol["solver"]["binary_sha256"])
    prior_path = HERE / "protocol_preexec_failure.json"
    failure = json.loads((RUNS / "n53_planted_locked.preexec_failure.json")
                         .read_text())
    assert file_digest(prior_path) == protocol["supersedes_protocol_sha256"]
    assert failure["protocol_sha256"] == file_digest(prior_path)
    assert failure["status"] == "producer_failure_preexec_memory_limit"
    assert failure["solver_started"] is False
    failure_gzip = RUNS / failure["formula_gzip_file"]
    assert file_digest(failure_gzip) == failure["formula_gzip_sha256"]
    with gzip.open(failure_gzip, "rb") as stream:
        failure_raw = stream.read()
    assert len(failure_raw) == failure["formula_raw_bytes"]
    assert digest(failure_raw) == failure["formula_raw_sha256"]
    rows = []
    for item in protocol["run_grid"]:
        n, mode = item["n"], item["mode"]
        profile = protocol["profiles"][str(n)]
        stem = f"n{n}_{mode}"
        receipt_path = RUNS / f"{stem}.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["protocol_sha256"] == file_digest(protocol_path)
        assert receipt["source_sha256"] == protocol["source_sha256"]
        assert receipt["sage_runtime_info_sha256"] == (
            protocol["sage_runtime_info_sha256"])
        assert receipt["solver_binary_sha256"] == (
            protocol["solver"]["binary_sha256"])
        assert receipt["mode"] == mode and receipt["field_degree_n"] == n
        assert receipt["curve_id"] == profile["curve_id"]
        assert receipt["candidate_id"] is None and receipt["run_id"] is None
        assert receipt["verified_single_target_dlp"] is False
        assert receipt["is_controlled_cpu_speedup"] is False
        assert receipt["cofactor"] == profile["cofactor"]
        assert receipt["actual_usable_points_B"] == profile["actual_B"]
        assert receipt["folded_columns_K"] == profile["folded_columns_K"]
        assert receipt["base_archive_sha256"] == (
            profile["base_archive_sha256"])
        assert receipt["observed_verified_relation_count"] == (
            int(receipt["verified_relation"] is not None))
        phases = receipt["online_pdp_phase_ns"]
        assert sum(phases.values()) == receipt["online_pdp_wall_ns_exploratory"]
        assert len(receipt["attempts"]) == 1

        base, base_keys = exact_base(
            n, profile["normal_basis_weight_bound"], profile)
        assert base["curve"]["curve_id"] == profile["curve_id"]
        assert base["isogeny"] == "none"
        onb = field.Onb(n)
        curve = curves.Curve(onb)
        order = int(base["curve"]["subgroup_order"])
        cofactor = profile["cofactor"]
        public = point(receipt["public_target"])
        assert curve.onCurve(public) and curve.mul(public, order) is None
        ordinary_path = (ROOT / "experiments/compact-s3-m4-20261003/runs" /
                         f"n{n}_ordinary_frozen.json")
        raw_path = (ROOT / "experiments/compact-s3-m4-20261003/runs" /
                    f"n{n}_ordinary_raw_preimages.json")
        assert file_digest(ordinary_path) == profile["ordinary_receipt_sha256"]
        assert file_digest(raw_path) == profile["ordinary_preimages_sha256"]
        ordinary = json.loads(ordinary_path.read_text())
        raw_archive = json.loads(raw_path.read_text())
        if mode == "ordinary":
            assert receipt["workload_id"] == profile["ordinary_workload_id"]
            assert receipt["public_target"] == ordinary["public_subgroup_target"]
            assert raw_archive["public_target"] == receipt["public_target"]
            raw_points = [point(p) for p in raw_archive["raw_target_points"]]
        else:
            assert receipt["workload_id"] is None
            fixture = receipt["planted_fixture"]
            assert receipt["public_target"] == fixture["public_target"]
            planted = [point(p) for p in fixture["raw_leaf_points"]]
            assert len(planted) == 5
            assert [onb.toCoords(p[0]) for p in planted] == (
                fixture["raw_leaf_x"])
            assert all(curve.onCurve(p) for p in planted)
            total = None
            mids = []
            for p in planted:
                total = curve.add(total, p)
                if len(mids) < 3 and total is not None and total != planted[0]:
                    mids.append(onb.toCoords(total[0]))
            assert mids == fixture["raw_intermediate_x"]
            assert total == point(fixture["raw_sum"])
            assert curve.mul(total, cofactor) == public
            fixture_keys = sorted(fold_x(onb, curve.mul(p, cofactor), n)
                                  for p in planted)
            assert fixture_keys == fixture["projected_column_keys"]
            assert all(key in base_keys for key in fixture_keys)
            # The complete coset is independently regenerated from the
            # recorded kernel generators, without the producer's routine.
            generators = [point(p) for p in
                          receipt["target_preimage_kernel_generators"]]
            subgroup = {None}
            frontier = [None]
            while frontier:
                element = frontier.pop()
                for generator in generators:
                    successor = curve.add(element, generator)
                    if successor not in subgroup:
                        subgroup.add(successor)
                        frontier.append(successor)
            assert len(subgroup) == cofactor
            assert all(curve.mul(p, cofactor) is None for p in subgroup)
            raw_base = curve.mul(public, pow(cofactor, -1, order))
            raw_points = sorted((curve.add(raw_base, t) for t in subgroup),
                                key=lambda p: (onb.toCoords(p[0]),
                                               onb.toCoords(p[1])))
        assert len(raw_points) == cofactor
        assert all(curve.onCurve(p) and curve.mul(p, cofactor) == public
                   for p in raw_points)
        raw_xs = [onb.toCoords(p[0]) for p in raw_points]
        assert len(set(raw_xs)) == cofactor
        width = (n + 7) // 8
        assert digest(b"".join(x.to_bytes(width, "little") for x in raw_xs)) == (
            receipt["raw_target_x_sha256"])

        attempt = receipt["attempts"][0]
        assert attempt["index"] == 0
        stdout_path = RUNS / attempt["stdout_file"]
        stderr_path = RUNS / attempt["stderr_file"]
        formula_path = RUNS / attempt["xcnf_gzip"]
        assert file_digest(stdout_path) == attempt["stdout_sha256"]
        assert file_digest(stderr_path) == attempt["stderr_sha256"]
        assert file_digest(formula_path) == attempt["xcnf_gzip_sha256"]
        with gzip.open(formula_path, "rb") as stream:
            raw = stream.read()
        assert len(raw) == attempt["xcnf_raw_bytes"]
        assert digest(raw) == attempt["xcnf_raw_sha256"]
        stdout = stdout_path.read_text()
        model = read_model(stdout, receipt["formula_shape"]["variables"]) if (
            attempt["status"] == "sat") else None
        shape = formula_audit(raw, model)
        assert shape["variables"] == receipt["formula_shape"]["variables"]
        assert shape["xor_rows"] == receipt["formula_shape"]["xor_rows"]
        assert shape["cnf_rows"] == receipt["formula_shape"]["cnf_clauses"]
        if mode == "planted_locked":
            assert attempt["return_code"] == 10
            assert attempt["status"] == "sat" and model is not None
            relation_audit = independent_relation_replay(
                receipt, model, onb, curve, base_keys, raw_points,
                order, cofactor)
            assert attempt["replay"] == receipt["verified_relation"]
        else:
            assert receipt["verified_relation"] is None
            assert attempt["replay"] is None
            assert "s SATISFIABLE" not in stdout
            if attempt["status"] == "solver_failure":
                assert attempt["return_code"] == 15
                assert "s INDETERMINATE" in stdout
                assert attempt["solver_conflicts_reported"] >= 1_000_000
            else:
                assert attempt["status"] == "external_timeout"
                assert attempt["solver_wall_seconds"] >= 59
            relation_audit = None
        rows.append({
            "n": n, "mode": mode, "status": attempt["status"],
            "status_interpretation": (
                "conflict_cap_indeterminate" if attempt["status"] ==
                "solver_failure" else attempt["status"]),
            "solver_conflicts": attempt["solver_conflicts_reported"],
            "online_pdp_wall_ns_exploratory": receipt[
                "online_pdp_wall_ns_exploratory"],
            "verified_relations": receipt["observed_verified_relation_count"],
            "formula_audit": shape, "relation_audit": relation_audit,
            "receipt_sha256": file_digest(receipt_path),
        })
    for n in (53, 83):
        locked = json.loads((RUNS / f"n{n}_planted_locked.json").read_text())
        unpinned = json.loads((RUNS / f"n{n}_planted_unpinned.json").read_text())
        assert locked["planted_fixture"] == unpinned["planted_fixture"]
        assert locked["public_target"] == unpinned["public_target"]
    return {
        "kind": "independent_q1417_archive_replay",
        "protocol_sha256": file_digest(protocol_path),
        "verifier_sha256": file_digest(Path(__file__)),
        "preexec_failure_receipt_sha256": file_digest(
            RUNS / "n53_planted_locked.preexec_failure.json"),
        "rows": rows,
        "all_archives_and_two_locked_relations_verified": True,
        "ordinary_relation_yield_rate_estimate": None,
        "complete_single_target_dlp": False,
        "controlled_speedup": False,
    }


if __name__ == "__main__":
    report = audit()
    path = RUNS / "independent_replay.json"
    assert not path.exists(), "refusing to overwrite replay receipt"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"rows": len(report["rows"]),
                      "verified_relations": sum(row["verified_relations"]
                                                for row in report["rows"]),
                      "receipt": str(path)}))
