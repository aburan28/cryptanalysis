#!/usr/bin/env python3
"""Independently replay one local N83 SAT model with installed Sage arithmetic."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
GEOMETRY = HERE / "runs/n83_full_w4_geometry_v1"
N = 83


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(public_path: Path, receipt_path: Path, out: Path) -> None:
    public_path, receipt_path, out = (path.resolve() for path in
                                      (public_path, receipt_path, out))
    if not (out / "sage_runtime_info.json").is_file():
        raise FileNotFoundError("save checked Sage --runtime-info before replay")
    if (out / "report.json").exists():
        raise FileExistsError("model replay output is immutable")
    start = time.perf_counter_ns()
    public = json.loads(public_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    geometry = json.loads((GEOMETRY / "geometry.json").read_text())
    representatives = json.loads((GEOMETRY / "representatives.json").read_text())
    assert receipt["status"] == "SAT_GROUP_VERIFIED_PENDING_SAGE"
    assert receipt["model_clause_xor_verified"] is True
    assert receipt["group_check"]["verified"] is True
    assert public["curve_id"] == geometry["curve_id"]
    assert public["field_degree"] == N

    binary = GF(2)
    ring = PolynomialRing(binary, "v")
    v = ring.gen()
    field = GF(2**N, "w", modulus=v**N + v**7 + v**4 + v**2 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def element(value: int):
        return field(ring([(value >> bit) & 1 for bit in range(N)]))

    def word(value) -> int:
        return sum(int(bit) << index for index, bit in
                   enumerate(value.polynomial().list()))

    def point(encoded):
        return curve(element(int(encoded[0])), element(int(encoded[1])))

    def pair(value):
        assert value != curve(0)
        return [str(word(value[0])), str(word(value[1]))]

    alpha = element(int(public["normal_element_polynomial_bits_decimal"]))
    conjugates = [alpha]
    for _ in range(1, N):
        conjugates.append(conjugates[-1]**2)
    assert [str(word(value)) for value in conjugates] == \
        public["normal_conjugates_polynomial_bits_decimal"]

    rep_set = {tuple(row) for row in representatives["representatives"]}

    def orbit_key(value):
        x, y = value[0], value[1]
        keys = set()
        for _ in range(N):
            xword, yword = word(x), word(y)
            keys.update(((xword, yword), (xword, xword ^ yword)))
            x, y = x**2, y**2
        return min(keys)

    masks = receipt["model"]["masks"]
    encoded = receipt["group_check"]["raw_points"]
    assert len(masks) == len(encoded) == 5
    factors = [point(row) for row in encoded]
    for mask, factor, expected_x in zip(
            masks, factors, receipt["model"]["x_codes_decimal"]):
        assert len(mask) in (3, 4) and len(set(mask)) == len(mask)
        assert all(0 <= bit < N for bit in mask)
        x = sum((conjugates[bit] for bit in mask), field(0))
        assert factor[0] == x and word(x) == int(expected_x)
        projected = 4 * factor
        assert projected != curve(0) and orbit_key(projected) in rep_set

    raw_sum = sum(factors, curve(0))
    q = 4 * raw_sum
    assert pair(raw_sum) == receipt["group_check"]["raw_sum"]
    assert pair(q) == public["planted"]["target_Q"]
    assert pair(q) == receipt["group_check"]["projected_sum"]
    assert pair(raw_sum) in [[row["x"], row["y"]]
                              for row in public["planted"]["raw_target_fiber"]]

    report = {
        "schema_version": 1,
        "kind": "n83_w34_sat_model_independent_sage_replay",
        "status": "PASS",
        "curve_id": public["curve_id"],
        "factor_count": 5,
        "all_factors_in_full_measured_base": True,
        "raw_sum_and_cofactor_four_target_verified": True,
        "public_input_sha256": sha(public_path),
        "solver_receipt_sha256_local_only": sha(receipt_path),
        "replay_source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(out / "sage_runtime_info.json"),
        "wall_ms_exploratory": (time.perf_counter_ns() - start) / 1e6,
        "claim_boundary": "Fully pinned planted diagnostic only; no unpinned relation or DLP.",
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"],
                      "factor_count": report["factor_count"]}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("public_input", type=Path)
    parser.add_argument("solver_receipt", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    main(args.public_input, args.solver_receipt, args.out)
