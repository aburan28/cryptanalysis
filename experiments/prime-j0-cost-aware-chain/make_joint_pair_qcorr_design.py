#!/usr/bin/env python3
"""Freeze an exact-corrected binary64 quotient candidate for pair recoding."""

import hashlib
import json
from pathlib import Path
import struct

from run import nearest_quotient


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corrected_quotient(k, multiplier, denominator):
    """Binary64 estimate followed by integer-only nearest-quotient correction."""
    estimate = float(k) * float(multiplier) / float(denominator)
    if not 0 <= estimate < multiplier + 2:
        raise ValueError("floating quotient left the proved study range")
    q = int(estimate + 0.5)
    rem = k * multiplier - q * denominator
    corrections = 0
    while 2 * rem >= denominator:
        q += 1
        rem -= denominator
        corrections += 1
    while 2 * rem < -denominator:
        q -= 1
        rem += denominator
        corrections += 1
    if q != nearest_quotient(k * multiplier, denominator):
        raise ValueError("corrected estimate changed exact quotient")
    return q, corrections


def main():
    guard_path = ROOT / "joint-pair-guard-design.json"
    inputs_path = ROOT / "joint-pair-guard-inputs/inputs.json"
    panel_path = ROOT / "joint-pair-guard-native-panel.json"
    guard = json.loads(guard_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    panel = json.loads(panel_path.read_text())
    if guard.get("status") != "frozen_proved_design" or \
            inputs.get("design_sha256") != sha256(guard_path) or \
            panel.get("status") != "pass" or \
            panel.get("inputs_sha256") != sha256(inputs_path) or \
            len(panel.get("rows", [])) != 112:
        raise ValueError("center-guard training custody changed")
    records = []
    for prior in guard["records"]:
        curve, order = prior["curve"], prior["order"]
        multipliers = [prior["basis"][1][1], -prior["basis"][0][1]]
        if order >= 2**56 or any(not 0 < a < 2**28 for a in multipliers):
            raise ValueError("study quotient bounds changed")
        cases = [case for case in inputs["cases"] if case["curve"]["name"] == curve]
        if len(cases) != 4:
            raise ValueError("training case count changed")
        training_corrections = training_quotients = 0
        for case in cases:
            scalar_path = inputs_path.parent / case["scalar_file"]
            if sha256(scalar_path) != case["scalar_file_sha256"]:
                raise ValueError("training scalar custody changed")
            for (k,) in struct.iter_unpack("<Q", scalar_path.read_bytes()):
                for a in multipliers:
                    _, corrections = corrected_quotient(k, a, order)
                    training_corrections += corrections
                    training_quotients += 1
        boundary = []
        for a in multipliers:
            if pow(2 * a, -1, order) == 0:
                raise ValueError("missing modular inverse")
            near = pow(2 * a, -1, order)
            for k in (near, (-near) % order):
                quotient, corrections = corrected_quotient(k, a, order)
                boundary.append({"scalar": k, "multiplier": a,
                                 "two_numerator_mod_order": (2 * k * a) % order,
                                 "exact_quotient": quotient,
                                 "estimate_corrections": corrections})
        records.append({"curve": curve, "order": order,
                        "multipliers": multipliers,
                        "training_quotients": training_quotients,
                        "training_corrections": training_corrections,
                        "boundary_challenges": boundary})
    design = {"schema": 1, "status": "frozen_exact_correction_design",
              "method": "estimate each positive GLV lattice quotient with binary64, then correct by exact signed 128-bit remainder comparisons until the original nearest-integer quotient is reached",
              "correctness": "For positive numerator N and denominator d, the correction stops exactly when -d <= 2(N-qd) < d, which is equivalent to q=floor((N+floor(d/2))/d) for odd d and the original positive round_div tie rule. Estimate accuracy affects work, never the returned integer. A non-binary64 platform uses the integer-division fallback.",
              "bounds": {"scalar_strict_upper": "2^56", "multiplier_strict_upper": "2^28",
                         "numerator_strict_upper": "2^84",
                         "binary64_gate": "FLT_RADIX == 2 and DBL_MANT_DIG >= 53; otherwise use exact integer division"},
              "scope": "variable-time public-scalar GLV pair reduction on two exact j=0 study curves",
              "measurement_gate": "fresh disjoint correctness and operation panel first; CPU timing only with a host-level isolation receipt",
              "base_guard_design_sha256": sha256(guard_path),
              "training_inputs_sha256": sha256(inputs_path),
              "training_panel_sha256": sha256(panel_path),
              "source_sha256": sha256(Path(__file__)), "records": records}
    output = ROOT / "joint-pair-qcorr-design.json"
    content = (json.dumps(design, sort_keys=True, indent=2) + "\n").encode()
    if output.exists() and output.read_bytes() != content:
        raise ValueError("frozen quotient-correction design changed")
    output.write_bytes(content)
    print(json.dumps({"design_sha256": sha256(output), "records": records}, sort_keys=True))


if __name__ == "__main__":
    main()
