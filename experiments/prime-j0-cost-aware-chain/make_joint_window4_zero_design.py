#!/usr/bin/env python3
"""Freeze a congruence-directed zero-window GLV representative rule."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import lattice, nearest_quotient  # noqa: E402


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digit_metrics(x, y):
    positions = additions = 0
    while x or y:
        dx, dy = x % 16, y % 16
        if dx >= 8:
            dx -= 16
        if dy >= 8:
            dy -= 16
        additions += bool(dx or dy)
        x, y = (x - dx) // 16, (y - dy) // 16
        positions += 1
    return positions, additions


def curve_screen(cases, eigen, input_dir, positions):
    order = cases[0]["curve"]["order"]
    omega_eigen = (order - eigen[cases[0]["id"]]) % order
    v1, v2, det = lattice(order, omega_eigen)
    inverse = pow(det, -1, 16)
    totals = Counter()
    for case in cases:
        if case["curve"]["order"] != order or \
                (order - eigen[case["id"]]) % order != omega_eigen:
            raise ValueError("curve cases disagree on subgroup or endomorphism")
        scalar_file = input_dir / case["scalar_file"]
        if sha256(scalar_file) != case["scalar_file_sha256"]:
            raise ValueError("training scalar file changed")
        for (scalar,) in struct.iter_unpack("<Q", scalar_file.read_bytes()):
            u0 = nearest_quotient(scalar * v2[1], det)
            v0 = nearest_quotient(-scalar * v1[1], det)

            def coords(u, v):
                return (scalar - u * v1[0] - v * v2[0],
                        -u * v1[1] - v * v2[1])

            baseline = None
            for du in range(-2, 3):
                for dv in range(-2, 3):
                    x, y = coords(u0 + du, v0 + dv)
                    l1 = abs(x) + abs(y)
                    if baseline is None or l1 < baseline[0]:
                        baseline = (l1, x, y)
            base_positions, base_adds = digit_metrics(*baseline[1:])
            if base_positions > positions:
                totals["baseline_capacity_fallbacks"] += 1

            u_residue = scalar * v2[1] * inverse % 16
            v_residue = -scalar * v1[1] * inverse % 16
            du = (u_residue - u0) % 16
            dv = (v_residue - v0) % 16
            if du >= 8:
                du -= 16
            if dv >= 8:
                dv -= 16
            x, y = coords(u0 + du, v0 + dv)
            if x % 16 or y % 16:
                raise AssertionError("congruence did not zero the low digit")
            candidate_positions, candidate_adds = digit_metrics(x, y)
            totals["scalars"] += 1
            totals["baseline_adds"] += base_adds
            totals["candidate_recode_attempts"] += scalar != 0
            if candidate_positions <= positions:
                totals["candidate_feasible"] += 1
                if base_positions > positions or candidate_adds < base_adds:
                    totals["selected"] += 1
                    if base_positions <= positions:
                        totals["saved_adds"] += base_adds - candidate_adds
                        totals["selected_adds"] += candidate_adds
    return {"curve": cases[0]["curve"]["name"], "positions": positions,
            "order": order, "omega_eigen": omega_eigen,
            "lattice_basis": [list(v1), list(v2)], "determinant": det,
            "determinant_inverse_mod16": inverse,
            "training": dict(sorted(totals.items()))}


def make(training_path, old_panel_path, output):
    fixture = json.loads(training_path.read_text())
    if fixture.get("status") != "fresh_disjoint_fixture" or len(fixture["cases"]) != 8:
        raise ValueError("expected the frozen eight-case plane fixture")
    plane_design = HERE / "joint-window4-plane-design.json"
    if fixture["design_sha256"] != sha256(plane_design):
        raise ValueError("plane training design changed")
    old = json.loads(old_panel_path.read_text())
    eigen = {row["case_id"]: int(row["fields"]["endo_lambda"])
             for row in old["rows"] if row["mode"] == "pos-compact"}
    records = []
    for curve, positions in (("glv-j0-32", 4), ("j0-56", 7)):
        cases = [case for case in fixture["cases"] if case["curve"]["name"] == curve]
        if len(cases) != 4:
            raise ValueError("expected four training cases per curve")
        records.append(curve_screen(cases, eigen, training_path.parent, positions))
    design = {
        "schema": 1,
        "status": "frozen_training_design",
        "base_plane_design_sha256": sha256(plane_design),
        "training_inputs_sha256": sha256(training_path),
        "endomorphism_receipt_sha256": sha256(old_panel_path),
        "source_sha256": sha256(Path(__file__)),
        "method": "keep the exact minimum-L1 radius-2 baseline; solve x=y=0 modulo 16 in its GLV lattice coset, choose the nearest signed residue shift, recode that one candidate, and use it only when it fits the existing point table and strictly reduces nonzero joint windows or rescues a baseline capacity fallback",
        "congruence": {
            "basis": "v1=(a,c), v2=(b,d), determinant=ad-bc=+/-r",
            "u_mod16": "k*d*inverse(det,16) modulo 16",
            "v_mod16": "-k*c*inverse(det,16) modulo 16",
            "centered_shift": "choose du,dv in [-8,7] relative to the Babai-rounded quotient",
            "proof": "x=k-u*a-v*b and y=-u*c-v*d are both 0 modulo 16 because det is odd",
        },
        "table_policy": "reuse the exact packed two-coordinate unit plane and 71-orbit radix-16 table",
        "scope": "variable-time fixed-base multiplication of public scalars on the two exact j=0 study curves",
        "measurement_gate": "held-out correctness and operation counts first; CPU ratio only with host-level isolation receipt",
        "records": records,
    }
    content = json.dumps(design, indent=2, sort_keys=True).encode() + b"\n"
    if output.exists() and output.read_bytes() != content:
        raise ValueError("frozen zero-window design changed")
    output.write_bytes(content)
    print(json.dumps({"design_sha256": hashlib.sha256(content).hexdigest(),
                      "training": [{"curve": row["curve"], **row["training"]}
                                   for row in records]}, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: make_joint_window4_zero_design.py PLANE_INPUTS OLD_PANEL OUTPUT")
    make(*map(Path, sys.argv[1:]))
