#!/usr/bin/env python3
"""Direct 23,426-mask check of the grouped-orbit N53 weight-three geometry."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

from n53_group import COFACTOR, Curve, Field, N, normal_basis

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/n53_weight3_geometry_v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(points):
    payload = json.dumps([list(point) for point in sorted(points)],
                         sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def main():
    expected = json.loads((RUN / "receipt.json").read_text())
    field = Field()
    curve = Curve(field)
    _, basis = normal_basis(field)
    raw, projected = set(), set()
    rational = 0
    for mask in itertools.combinations(range(N), 3):
        x = basis[mask[0]] ^ basis[mask[1]] ^ basis[mask[2]]
        lifts = curve.lift(x)
        if lifts:
            rational += 1
        for point in lifts:
            raw.add(point)
            image = curve.mul(point, COFACTOR)
            if image is not None:
                projected.add(image)
    assert rational == expected["rational_x_count"]
    assert len(raw) == expected["geometric_points"]
    assert len(projected) == expected["actual_usable_projected_points"]
    assert digest(raw) == expected["raw_set_sha256"]
    assert digest(projected) == expected["projected_set_sha256"]
    report = {"status": "PASS", "kind": "n53_weight3_direct_geometry_replay",
              "rational_x_count": rational,
              "raw_points": len(raw), "projected_points": len(projected),
              "raw_set_sha256": digest(raw),
              "projected_set_sha256": digest(projected),
              "source_geometry_receipt_sha256": sha(RUN / "receipt.json"),
              "source_sha256": {"verify_n53_weight3_direct.py": sha(Path(__file__)),
                                "n53_group.py": sha(HERE / "n53_group.py")}}
    (RUN / "direct_replay.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("status", "rational_x_count", "raw_points", "projected_points")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
