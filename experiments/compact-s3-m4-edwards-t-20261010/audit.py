#!/usr/bin/env python3
"""Independent group and exact-base replay for the t-coordinate gate."""

import hashlib
import itertools
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/compact-s3-m4-20261003"
sys.path[:0] = [str(HERE), str(PARENT), str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from t_link import evaluate_t3, t_of_x, x_roots_of_t  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def audit_base(base, profile):
    n = 53
    f = field.Onb(n)
    e = curves.Curve(f)
    torsion = (0, f.one())
    keys = set()
    counts = dict.fromkeys(("nominal_t_masks", "x_quadratic_solvable",
        "rational_t_values", "identity_projection",
        "duplicate_projected_columns", "torsion_pair_checks"), 0)
    for weight in range(1, 4):
        for positions in itertools.combinations(range(n), weight):
            mask = sum(1 << position for position in positions)
            counts["nominal_t_masks"] += 1
            t = f.fromCoords(mask)
            xroots = x_roots_of_t(f, e, t)
            if not xroots:
                continue
            assert len(xroots) == 2
            counts["x_quadratic_solvable"] += 1
            assert all(t_of_x(f, x) == t for x in xroots)
            P = e.pointFromX(xroots[0])
            if P is None:
                assert e.pointFromX(xroots[1]) is None
                continue
            counts["rational_t_values"] += 1
            Q = e.add(P, torsion)
            assert Q[0] == xroots[1]
            counts["torsion_pair_checks"] += 1
            S = e.mul(P, profile["cofactor"])
            if S is None:
                counts["identity_projection"] += 1
                continue
            assert e.mul(Q, profile["cofactor"])[0] == S[0]
            orbit = []
            x = S[0]
            for _ in range(n):
                orbit.append(f.toCoords(x))
                x = f.sqr(x)
            assert x == S[0] and len(set(orbit)) == n
            key = min(orbit)
            if key in keys:
                counts["duplicate_projected_columns"] += 1
            else:
                keys.add(key)
    assert counts["nominal_t_masks"] == sum(math.comb(n, w)
                                           for w in range(1, 4))
    path = HERE / "bases/n53_t_weight3_columns.bin"
    packed = b"".join(value.to_bytes(7, "little") for value in sorted(keys))
    assert path.read_bytes() == packed
    assert digest(path) == base["enumerated_set_sha256"]
    assert len(packed) == base["enumerated_set_bytes"]
    assert len(keys) == base["folded_columns_K"]
    assert base["actual_usable_points_B"] == 106*len(keys)
    assert base["geometric_point_count_before_projection"] == 4*counts[
        "rational_t_values"]
    for name, value in counts.items():
        assert base["metrics"][name] == value
    assert base["metrics"]["subgroup_order_checks"] == min(64, counts[
        "rational_t_values"] - counts["identity_projection"])
    return {"nominal_t_masks": counts["nominal_t_masks"],
            "rational_t_values": counts["rational_t_values"],
            "B": base["actual_usable_points_B"], "K": len(keys)}


def audit_controls(frozen, controls):
    assert len(controls) == 2
    for record in controls:
        n = 53 if record["curve_id"] == frozen["reference_profiles"]["53"][
            "curve_id"] else 83
        profile = frozen["reference_profiles"][str(n)]
        assert record["curve_id"] == profile["curve_id"]
        assert record["triple_count"] == len(record["rows"]) == frozen[
            "triples_per_degree"]
        assert record["elapsed_seconds_exploratory"] >= 0
        f, e = field.Onb(n), curves.Curve(field.Onb(n))
        G = tuple(profile["generator"])
        T2 = (0, f.one())
        assert e.onCurve(G) and e.onCurve(T2)
        for index, row in enumerate(record["rows"]):
            assert row["index"] == index
            P = e.mul(G, row["scalar_a"])
            Q = e.mul(G, row["scalar_b"])
            R = e.neg(e.add(P, Q))
            assert e.add(e.add(P, Q), R) is None
            values = [t_of_x(f, point[0]) for point in (P, Q, R)]
            assert row["t_coords"] == [f.toCoords(value) for value in values]
            assert evaluate_t3(f, *values) == 0
            assert t_of_x(f, e.add(P, T2)[0]) == values[0]
            assert t_of_x(f, e.frob(P)[0]) == f.sqr(values[0])


def main():
    frozen = load(HERE / "freeze.json")
    assert frozen["schema"] == "q20261010173300-freeze-v1"
    assert frozen["proposal_id"] == "Q20261010173300"
    assert frozen["candidate_id"] is frozen["run_id"] is None
    assert frozen["isogeny"] == "none"
    assert frozen["q1419_protocol_sha256"] == digest(
        PARENT / "q1419_partial_pin/protocol.json")
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    result = load(HERE / "run.json")
    assert result["proposal_id"] == frozen["proposal_id"]
    assert result["candidate_id"] is result["run_id"] is None
    assert result["isogeny"] == "none"
    assert result["freeze_sha256"] == digest(HERE / "freeze.json")
    base = audit_base(result["n53_t_base"], frozen["reference_profiles"]["53"])
    audit_controls(frozen, result["identity_controls"])
    shapes = result["formula_shapes"]
    assert [(row["n"], row["variant"]) for row in shapes] == [
        (n, variant) for n in (53, 83, 131) for variant in ("x", "t")]
    for row in shapes:
        assert row["variables"] > 0 and row["cnf_clauses"] > 0
        assert row["xor_rows"] > 0 and row["and_gates"] > 0
        assert row["build_seconds_exploratory"] >= 0
    output = HERE / "audit.json"
    assert not output.exists()
    output.write_text(json.dumps({"schema": "q20261010173300-audit-v1",
        "status": "PASS", "base": base,
        "identity_triples": sum(item["triple_count"] for item in result[
            "identity_controls"]),
        "freeze_sha256": digest(HERE / "freeze.json"),
        "run_sha256": digest(HERE / "run.json"),
        "auditor_sha256": digest(Path(__file__))},
        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "base": base}))


if __name__ == "__main__":
    main()
