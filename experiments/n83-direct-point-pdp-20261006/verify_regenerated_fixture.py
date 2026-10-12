#!/usr/bin/env python3
"""Verify deterministic fixture regeneration and regular planted group path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from direct_point_circuit import DirectPointCircuit
from gf2n import Curve, Point


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "hamming-ic-e2e-20260929"
ORIGINAL = SOURCE / "runs/n83_w34_sat_fixture_v1/public_input.json"
FOLDER = HERE / "runs/regenerated_fixture_v1"
PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = FOLDER / "fixture_regeneration.json"
    if output.exists():
        raise FileExistsError("fixture verification receipt is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    assert sha(ORIGINAL) == sha(FOLDER / "public_input.json") == \
        protocol["source_public_fixture_sha256"]
    assert sha(FOLDER / "private_fixture.json") == \
        protocol["regenerated_private_fixture_sha256_local_only"]
    public = json.loads(ORIGINAL.read_text())
    private = json.loads((FOLDER / "private_fixture.json").read_text())
    assert private["public_input_sha256"] == sha(ORIGINAL)
    field = DirectPointCircuit(83, [0, 2, 4, 7]).field
    curve = Curve(field, 1)
    factors = [Point(int(row["raw_point"][0]), int(row["raw_point"][1]))
               for row in private["selected"]]
    assert len(factors) == 5 and all(curve.on_curve(point) for point in factors)
    regular = []
    prefix = factors[0]
    for factor in factors[1:]:
        regular.append(prefix.x != factor.x)
        prefix = curve.add(prefix, factor)
        assert not prefix.inf
    assert all(regular) and [str(prefix.x), str(prefix.y)] == private["raw_sum"]
    assert private["raw_sum"] in [[row["x"], row["y"]]
                                  for row in public["planted"]["raw_target_fiber"]]
    receipt = {
        "schema_version": 1,
        "kind": "n83_w34_direct_point_fixture_regeneration",
        "status": "PASS", "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "source_public_fixture_sha256": sha(ORIGINAL),
        "regenerated_public_fixture_sha256": sha(FOLDER / "public_input.json"),
        "private_fixture_sha256_local_only": sha(FOLDER / "private_fixture.json"),
        "all_five_factors_on_curve": True,
        "all_four_affine_additions_regular": True,
        "raw_sum_matches_public_fiber": True,
        "checked_sage_runtime_info_sha256": sha(FOLDER / "sage_runtime_info.json"),
        "source_fixture_producer_sha256": sha(SOURCE / "sage_make_n83_w34_sat_fixture.py"),
        "source_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(PROTOCOL),
        "claim_boundary": "Deterministic planted fixture and regular-locus eligibility only; not solver search, ordinary yield, DLP, or speedup.",
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "regular_additions": 4}, sort_keys=True))


if __name__ == "__main__":
    main()
