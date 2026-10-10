#!/usr/bin/env python3
"""Independently replay the N83 direct-point sign-enumeration SAT model."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent
FOLDER = HERE / "runs/sign_enum_v1"
PUBLIC = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json"
REPS = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_full_w4_geometry_v1/representatives.json"
PROTOCOL = HERE / "sign_enum_protocol.json"
R = 2417851639230796216685689


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    runtime = FOLDER / "sage_replay_runtime_info.json"
    output = FOLDER / "sage_replay.json"
    if not runtime.is_file() or output.exists():
        raise FileExistsError("save checked Sage runtime before immutable replay")
    protocol = json.loads(PROTOCOL.read_text())
    assert sha(PUBLIC) == protocol["source_public_fixture_sha256"]
    summary_path = FOLDER / "receipt.json"
    summary = json.loads(summary_path.read_text())
    assert summary["status"] == "SAT_GROUP_VERIFIED_PENDING_SAGE"
    sat_rows = [row for row in summary["branches"]
                if row["status"] == "SAT_GROUP_VERIFIED_PENDING_SAGE"]
    assert len(sat_rows) == 1
    sat = sat_rows[0]
    private_path = FOLDER / f"branch_{sat['branch_index']:02d}/private_model.json"
    private = json.loads(private_path.read_text())
    assert sha(private_path) == sat["private_model_sha256_local_only"]
    assert private["verified"] and len(private["masks"]) == len(private["signs"]) == 5
    assert sum(sign << bit for bit, sign in enumerate(private["signs"])) == \
        sat["branch_index"]
    public = json.loads(PUBLIC.read_text())
    reps_record = json.loads(REPS.read_text())
    assert reps_record["curve_id"] == public["curve_id"] == protocol["curve_id"]
    representatives = {tuple(row) for row in reps_record["representatives"]}
    started = time.perf_counter_ns()
    base = PolynomialRing(GF(2), "u")
    u = base.gen()
    field = GF(2**83, "z", modulus=u**83 + u**7 + u**4 + u**2 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    identity = curve(0)
    assert curve.cardinality() == 4 * R and ZZ(R).is_prime(proof=True)

    def element(bits: int):
        return field(base([(bits >> bit) & 1 for bit in range(83)]))

    def word(value) -> int:
        return sum(int(bit) << index for index, bit in
                   enumerate(value.polynomial().list()))

    def point(pair):
        result = curve(element(int(pair[0])), element(int(pair[1])))
        assert result != identity
        return result

    def encoded(value):
        assert value != identity
        return [str(word(value[0])), str(word(value[1]))]

    def orbit_key(value):
        x, y = value[0], value[1]
        keys = []
        for _ in range(83):
            a, b = word(x), word(y)
            keys.extend(((a, b), (a, a ^ b)))
            x, y = x**2, y**2
        return min(keys)

    conjugates = [element(int(value)) for value in
                  public["normal_conjugates_polynomial_bits_decimal"]]
    factors = []
    for mask, sign, raw_pair in zip(private["masks"], private["signs"],
                                    private["raw_factor_points"]):
        assert len(mask) in (3, 4) and len(mask) == len(set(mask))
        assert all(bit in range(83) for bit in mask)
        x = sum((conjugates[bit] for bit in mask), field(0))
        assert x != 0
        value = point(raw_pair)
        assert value[0] == x
        w = x + (x**-1)**2
        assert w.trace() == 0
        v = sum((w**(2**(2 * index)) for index in range(42)), field(0)) + field(sign)
        assert value[1] == x * v
        projected = 4 * value
        assert projected != identity and R * projected == identity
        assert orbit_key(projected) in representatives
        factors.append(value)
    prefix = factors[0]
    for factor in factors[1:]:
        assert prefix[0] != factor[0]
        prefix += factor
        assert prefix != identity
    assert encoded(prefix) == private["raw_sum"]
    fiber = public["planted"]["raw_target_fiber"][0]
    assert encoded(prefix) == [fiber["x"], fiber["y"]]
    assert encoded(4 * prefix) == private["projected_sum"] == \
        public["planted"]["target_Q"]
    receipt = {
        "schema_version": 1,
        "kind": "n83_w34_direct_point_sign_enum_sage_replay",
        "status": "PASS", "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "factor_count": 5,
        "all_masks_exact_weight_three_or_four": True,
        "all_five_points_on_curve": True,
        "all_projected_factors_in_measured_base_orbits": True,
        "all_four_additions_regular": True,
        "raw_fiber_and_subgroup_target_verified": True,
        "solver_cnf_xor_model_verified_by_producer": True,
        "sign_enumeration_receipt_sha256": sha(summary_path),
        "private_model_sha256_local_only": sha(private_path),
        "public_fixture_sha256": sha(PUBLIC),
        "representatives_sha256": sha(REPS),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(runtime),
        "wall_ms_exploratory": (time.perf_counter_ns() - started) / 1e6,
        "claim_boundary": "Independently verified planted pinned-mask positive control. Factor masks were supplied to the circuit; no natural relation yield, DLP, rho, or speedup.",
    }
    save(output, receipt)
    print(json.dumps({"status": "PASS", "factors": 5}, sort_keys=True))


if __name__ == "__main__":
    main()
