#!/usr/bin/env sage -python
"""Independent Sage replay of target-derived backward N41 queries."""

import hashlib
import json
import random
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = Path("/Volumes/SSD990/cryptanalysis/experiments/ecc2k130-ic-goal-20260929")
R = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sage_curve():
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    def elem(value):
        return field(ring([(int(value) >> i) & 1 for i in range(41)]))
    def integer(value):
        return sum(int(v) << i for i, v in enumerate(value.polynomial().list()))
    return curve, elem, integer


def first_rows():
    lines = (GOAL / "n41_lowpower_w8_s6/native_input.txt").read_text().splitlines()
    n = int(lines[1])
    return [list(map(int, line.split())) for line in lines[2:2+n]]


def raw_source(curve, elem, rows, basis, mask, sign):
    grouped = [(x, y) for x, y, col, m, branch, sg in rows
               if m == mask and branch == 0 and sg == sign]
    if len(grouped) != 1:
        raise ValueError("source mask/sign lookup failed")
    u = 0
    for bit, value in enumerate(basis):
        if mask & (1 << bit):
            u ^= value
    x = 1 + 1/elem(u)
    target = curve(elem(grouped[0][0]), elem(grouped[0][1]))
    lifts = [point for point in curve.lift_x(x, all=True) if 4*point == target]
    if len(lifts) != 1:
        raise ValueError("independent Sage raw source lift failed")
    return lifts[0]


def replay_state(curve, elem, integer, basis, rows, rotation, state):
    def frobenius(point):
        for _ in range(rotation):
            point = curve(point[0]**2, point[1]**2)
        return point
    a = frobenius(raw_source(curve, elem, rows, basis,
                             state["a"], state["sign_a"]))
    b = frobenius(raw_source(curve, elem, rows, basis,
                             state["b"], state["sign_b"]))
    total = a+b
    if total == curve(0):
        raise ValueError("source pair is identity")
    actual_raw = [integer(total[0]), integer(total[1])]
    actual_projected = [integer((4*total)[0]), integer((4*total)[1])]
    if (actual_raw != state["raw_sum"] or
            actual_projected != state["projected_sum"] or
            R*(4*total) != curve(0)):
        raise ValueError("independent Sage pair state mismatch")
    z = 1/(total[0]+1)
    if integer(z) != state["z"]:
        raise ValueError("independent Sage phi output mismatch")
    return a, b, total


def audit_result(mode, geometry, curve, elem, integer, basis, rows):
    folder = HERE / mode
    result = json.loads((folder / "result.json").read_text())
    formula = json.loads((folder / "formula.json").read_text())
    if (result["formula_sha256"] != sha(folder / "system.xcnf") or
            formula["formula_sha256"] != result["formula_sha256"] or
            result["solver_stdout_sha256"] != sha(folder / "solver.stdout.txt") or
            result["solver_stderr_sha256"] != sha(folder / "solver.stderr.txt") or
            result["charged_target_dependent_wall_ns"] >
            (30 if mode == "control" else 120) * 1_000_000_000 + 1_000_000_000 or
            result["peak_combined_rss_bytes"] > 4*1024**3):
        raise ValueError("frozen run receipt failed terminal/source checks")
    witness = result["witness"]
    replay_count = 0
    if witness is not None:
        if len(witness["states"]) != 6 or len(set(witness["folded_columns"])) != 12:
            raise ValueError("model witness column count changed")
        raw_sum = curve(0)
        leaves = []
        for block, state in enumerate(witness["states"]):
            a, b, output = replay_state(curve, elem, integer, basis, rows,
                                        geometry["rotations"][block], state)
            raw_sum += output
            leaves.extend((a, b))
            replay_count += 1
        target = curve(elem(result["target_q"][0]), elem(result["target_q"][1]))
        if ([integer(raw_sum[0]), integer(raw_sum[1])] != witness["raw_target"] or
                4*raw_sum != target or R*target != curve(0)):
            raise ValueError("independent Sage target relation replay failed")
    return {"status": result["status"], "sage_witness_pairs": replay_count,
            "charged_wall_ns": result["charged_target_dependent_wall_ns"],
            "peak_rss_bytes": result["peak_combined_rss_bytes"],
            "formula_sha256": result["formula_sha256"]}


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve first independent Sage audit")
    import sys
    sys.path.insert(0, str(HERE))
    import run
    protocol = json.loads((HERE / "protocol.json").read_text())
    if protocol["source_sha256"] != {
            name: sha(path) for name, path in run.source_paths().items()}:
        raise ValueError("frozen source changed")
    geometry = json.loads((HERE / "geometry.json").read_text())
    curve, elem, integer = sage_curve()
    rows = first_rows()
    basis = json.loads((GOAL / "n41_lowpower_w8_s6/basis8.json").read_text())["basis_halftrace_by_unique_rotation"][0]
    rng = random.Random(20261009174001)
    samples = []
    for block, data in enumerate(geometry["blocks"]):
        samples.extend((block, state) for state in rng.sample(data["states"], 4))
    for block, state in samples:
        replay_state(curve, elem, integer, basis, rows,
                     geometry["rotations"][block], state)
    modes = {}
    for mode in ("control", "public"):
        if (HERE / mode / "result.json").exists():
            modes[mode] = audit_result(mode, geometry, curve, elem, integer,
                                       basis, rows)
    if "control" not in modes or "public" not in modes:
        raise ValueError("both frozen run receipts required")
    result = {"status": "PASS_INDEPENDENT_SAGE_AND_TERMINAL_AUDIT",
              "curve_id": geometry["curve_id"],
              "proposal_id": run.PROPOSAL_ID,
              "candidate_id": None, "sampled_pair_state_replays": len(samples),
              "modes": modes, "geometry_sha256": sha(HERE / "geometry.json"),
              "protocol_sha256": sha(HERE / "protocol.json")}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "modes": modes,
                      "sampled_pair_state_replays": len(samples)}))


if __name__ == "__main__":
    main()
