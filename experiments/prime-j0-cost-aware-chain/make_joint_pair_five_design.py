#!/usr/bin/env python3
"""Certify a five-neighbor L1 GLV reduction on the exact pair-table curves."""

import hashlib
import json
from pathlib import Path
import struct

from run import lattice, nearest_quotient


ROOT = Path(__file__).resolve().parent
AXIAL = ((-1, 0), (0, -1), (0, 0), (0, 1), (1, 0))
FULL = tuple((u, v) for u in range(-2, 3) for v in range(-2, 3))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def l1(v):
    return abs(v[0]) + abs(v[1])


def certificate(b1, b2, det):
    threshold = max(l1((b1[0] + b2[0], b1[1] + b2[1])),
                    l1((b1[0] - b2[0], b1[1] - b2[1])))
    m_bound = (max(map(abs, b2)) * threshold - 1) // abs(det)
    n_bound = (max(map(abs, b1)) * threshold - 1) // abs(det)
    short = []
    for m in range(-m_bound, m_bound + 1):
        for n in range(-n_bound, n_bound + 1):
            if m == n == 0:
                continue
            value = (m * b1[0] + n * b2[0], m * b1[1] + n * b2[1])
            if l1(value) < threshold:
                short.append({"coefficients": [m, n], "l1": l1(value)})
    if {tuple(row["coefficients"]) for row in short} != \
            {(-1, 0), (0, -1), (0, 1), (1, 0)}:
        raise ValueError("the five-neighbor certificate does not hold")
    return {"threshold_2M": threshold, "coefficient_bounds_strict": [m_bound, n_bound],
            "all_nonzero_vectors_below_2M": short,
            "proof": "For rounded lattice coordinates the residual R lies in the centered fundamental parallelogram, so ||R||_1<=M. Every lattice translation V with ||V||_1>=2M has ||R-V||_1>=||V||_1-||R||_1>=||R||_1. The inverse-basis coefficient bounds exhaust every translation shorter than 2M; only four axial vectors remain."}


def reduce(k, b1, b2, det, offsets):
    u0 = nearest_quotient(k * b2[1], det)
    v0 = nearest_quotient(-k * b1[1], det)
    best = None
    for du, dv in offsets:
        u, v = u0 + du, v0 + dv
        x = k - u * b1[0] - v * b2[0]
        y = -u * b1[1] - v * b2[1]
        row = (abs(x) + abs(y), x, y, du, dv)
        if best is None or row[0] < best[0]:
            best = row
    return best


def main():
    pair_path = ROOT / "joint-pair-design.json"
    wave_path = ROOT / "joint-pair-wave-design.json"
    inputs_path = ROOT / "joint-pair-wave-inputs/inputs.json"
    panel_path = ROOT / "joint-pair-wave-native-panel.json"
    pair = json.loads(pair_path.read_text())
    wave = json.loads(wave_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    panel = json.loads(panel_path.read_text())
    if inputs.get("design_sha256") != sha256(wave_path) or \
            panel.get("inputs_sha256") != sha256(inputs_path) or \
            panel.get("status") != "pass" or len(panel.get("rows", [])) != 48 or \
            wave.get("status") != "frozen_training_design":
        raise ValueError("pair-wave training custody changed")
    records = []
    for row in pair["records"]:
        curve = row["curve"]
        order, omega = row["order"], row["omega_eigen"]
        b1, b2, det = lattice(order, omega)
        if abs(det) != order:
            raise ValueError("lattice determinant changed")
        proof = certificate(b1, b2, det)
        cases = [case for case in inputs["cases"] if case["curve"]["name"] == curve]
        if len(cases) != 4:
            raise ValueError("training fixture changed")
        same_score = same_representative = 0
        for case in cases:
            scalar_path = inputs_path.parent / case["scalar_file"]
            if sha256(scalar_path) != case["scalar_file_sha256"]:
                raise ValueError("scalar custody changed")
            for (k,) in struct.iter_unpack("<Q", scalar_path.read_bytes()):
                old = reduce(k, b1, b2, det, FULL)
                new = reduce(k, b1, b2, det, AXIAL)
                if old[0] != new[0]:
                    raise ValueError("certified minimum differs from prior search")
                same_score += 1
                same_representative += old[1:3] == new[1:3]
        native = next(result["fields"] for result in panel["rows"]
                      if result["case_id"] == cases[0]["id"] and
                      result["mode"] == "joint-pair-top-triple-pos")
        if (order - int(native["endo_lambda"])) % order != omega:
            raise ValueError("native endomorphism eigenvalue changed")
        records.append({"curve": curve, "field_p": cases[0]["curve"]["p"],
                        "curve_b": cases[0]["curve"]["b"], "order": order,
                        "omega_eigen": omega, "basis": [list(b1), list(b2)],
                        "determinant": det, "certificate": proof,
                        "training_scalars": same_score,
                        "training_same_minimum_score": same_score,
                        "training_same_representative": same_representative,
                        "candidate_evaluations_old": len(FULL),
                        "candidate_evaluations_new": len(AXIAL)})
    design = {"schema": 1, "status": "frozen_proved_design",
              "scope": "variable-time public-scalar GLV reduction on two exact j=0 study curves",
              "method": "replace the 25-neighbor L1 search in bounded Eisenstein pair multiplication with the certified center and four axial neighbors",
              "candidate_offsets_in_old_tie_order": [list(pair) for pair in AXIAL],
              "measurement_gate": "fresh disjoint correctness and operation panel first; CPU timing only with a host-level isolation receipt",
              "prior_art_scope": "nearest-plane GLV decomposition is established; this is an exact curve-specific candidate-cutoff certificate and implementation experiment, not a claim of academic priority",
              "base_pair_design_sha256": sha256(pair_path),
              "base_wave_design_sha256": sha256(wave_path),
              "training_inputs_sha256": sha256(inputs_path),
              "training_panel_sha256": sha256(panel_path),
              "source_sha256": sha256(Path(__file__)), "records": records}
    output = ROOT / "joint-pair-five-design.json"
    content = (json.dumps(design, sort_keys=True, indent=2) + "\n").encode()
    if output.exists() and output.read_bytes() != content:
        raise ValueError("frozen five-neighbor design changed")
    output.write_bytes(content)
    print(json.dumps({"design_sha256": sha256(output), "records": records}, sort_keys=True))


if __name__ == "__main__":
    main()
