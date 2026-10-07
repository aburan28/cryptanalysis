#!/usr/bin/env python3
"""Check Q1484 status packing, orbit ordinal and N131 projection controls."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

from enumerate_n131 import (HERE, ROOT, OrbitKey, curves, field,
                            onb_x_from_cycle_mask, projected_x,
                            representatives, sha, status_code)
from verify_archive import code_at, raw_ordinal


def main() -> None:
    onb = field.Onb(131)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    flags = bytearray(1024)
    direct_checks = rational_checks = 0
    for index, (mask, span) in enumerate(
            itertools.islice(representatives(27), 4096)):
        assert raw_ordinal(mask, span) == index
        code = index % 3
        status_code(flags, index, code)
        assert code_at(flags, index) == code
        if index % 128:
            continue
        x = onb_x_from_cycle_mask(mask, onb, orbit)
        rational, projected = projected_x(onb, x)
        point = curve.pointFromX(x)
        assert rational == (point is not None)
        if rational:
            rational_checks += 1
            image = curve.mul(point, 4)
            assert (image is None) == (projected is None)
            if image is not None:
                assert image[0] == projected
                assert curve.onCurve(image)
        direct_checks += 1
    assert code_at(flags, 4095) == 4095 % 3
    result = {
        "kind": "q1484_n131_base_preflight",
        "proposal_id": "Q1484",
        "checked_raw_ordinals": 4096,
        "direct_group_projection_checks": direct_checks,
        "direct_rational_checks": rational_checks,
        "field_degree_n": 131,
        "curve_id": "EC1N131Ckb1h6816f880945e",
        "status": "PASS",
        "enumerator_source_sha256": sha(HERE / "enumerate_n131.py"),
        "archive_auditor_source_sha256": sha(HERE / "verify_archive.py"),
        "self_test_source_sha256": sha(Path(__file__)),
        "field_source_sha256": sha(ROOT / "ecc2k130/codegen/field.py"),
        "curve_source_sha256": sha(ROOT / "ecc2k130/codegen/curves.py"),
        "complete_n131_log2_work": None,
    }
    path = HERE / "preflight.json"
    if path.exists():
        assert json.loads(path.read_text()) == result
        print("Q1484 N131 preflight PASS (archived)")
    else:
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("Q1484 N131 preflight PASS")


if __name__ == "__main__":
    main()
