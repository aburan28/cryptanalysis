#!/usr/bin/env python3
"""Check [4] x projection on high-span N131 window representatives."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from enumerate_n131 import (HERE, PROTOCOL, OrbitKey, curves, field,
                            onb_x_from_cycle_mask, projected_x, sha)
from verify_archive import independent_masks


def run() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1484"
    assert protocol["cofactor"] == 4
    assert protocol["curve_id"] == "EC1N131Ckb1h6816f880945e"
    onb = field.Onb(131)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    selected = [(mask, span) for mask, span in independent_masks(27)
                if span >= 14]
    assert selected and all(mask.bit_length() == span for mask, span in selected)
    rational_count = identity_count = 0
    for mask, _ in selected:
        x = onb_x_from_cycle_mask(mask, onb, orbit)
        rational, predicted = projected_x(onb, x)
        point = curve.pointFromX(x)
        assert rational == (point is not None)
        if not rational:
            continue
        rational_count += 1
        image = curve.mul(point, protocol["cofactor"])
        assert (image is None) == (predicted is None)
        if image is None:
            identity_count += 1
            continue
        assert image[0] == predicted
        assert curve.onCurve(image)
        assert curve.mul(image, protocol["subgroup_order"]) is None
    input_bytes = json.dumps(selected, separators=(",", ":")).encode()
    return {
        "kind": "q1484_n131_high_span_projection_preflight",
        "proposal_id": "Q1484",
        "curve_id": protocol["curve_id"],
        "cofactor": protocol["cofactor"],
        "span_min": 14, "span_max": 27,
        "direct_group_checks": len(selected),
        "direct_rational_checks": rational_count,
        "direct_identity_checks": identity_count,
        "selected_mask_list_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "protocol_sha256": sha(PROTOCOL),
        "producer_source_sha256": sha(HERE / "enumerate_n131.py"),
        "source_sha256": sha(Path(__file__)),
        "status": "PASS",
        "actual_usable_B": None,
        "folded_K": None,
        "complete_n131_log2_work": None,
    }


def main() -> None:
    result = run()
    path = HERE / "high_span_preflight.json"
    if path.exists():
        assert json.loads(path.read_text()) == result
        print("Q1484 high-span N131 preflight PASS (archived)")
    else:
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("Q1484 high-span N131 preflight PASS")


if __name__ == "__main__":
    main()
