#!/usr/bin/env python3
"""Audit Q1484's complete status archive and sampled direct group operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent
Q1481 = PARENT / "q1481_window_orbit_base"
PROTOCOL = HERE / "protocol.json"
RUN = HERE / "runs" / "r1"

sys.path.insert(0, str(PARENT))
from enumerate_q1413_projected_x import canonical_rotation  # noqa: E402
from run_probe import curves, field, sha  # noqa: E402
sys.path.insert(0, str(Q1481))
from enumerate_base import OrbitKey, onb_x_from_cycle_mask  # noqa: E402


def code_at(flags: bytes, index: int) -> int:
    return (flags[index >> 2] >> ((index & 3) << 1)) & 3


def raw_ordinal(mask: int, span: int) -> int:
    assert mask & 1 and mask.bit_length() == span
    if span == 1:
        return 0
    return (1 << (span - 2)) + (
        (mask >> 1) & ((1 << (span - 2)) - 1))


def independent_masks(d: int) -> list[tuple[int, int]]:
    """Choose edge, middle and hashed interior masks in each span."""
    choices = []
    for span in range(1, d + 1):
        if span == 1:
            choices.append((1, 1))
            continue
        limit = 1 << (span - 2)
        interiors = {0, limit - 1, limit // 2}
        for index in range(4):
            digest = hashlib.sha256(
                f"Q1484-independent-{span}-{index}".encode()).digest()
            interiors.add(int.from_bytes(digest, "little") % limit)
        for interior in sorted(interiors):
            choices.append((1 | (1 << (span - 1)) |
                            (interior << 1), span))
    return choices


def audit() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1484"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["source_sha256"]["verify_archive.py"] == sha(
        Path(__file__))
    assert protocol["preflight_sha256"] == sha(HERE / "preflight.json")
    for relative, digest in protocol["dependency_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["reference_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    receipt_path = RUN / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["proposal_id"] == "Q1484"
    assert receipt["candidate_id"] is receipt["run_id"] is None
    assert receipt["curve_id"] == protocol["curve_id"]
    assert receipt["isogeny"] == "none"
    assert receipt["nominal_window_dimension_d"] == 27
    assert receipt["nominal_raw_x_orbits"] == 1 << 26
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["source_sha256"] == protocol["source_sha256"][
        "enumerate_n131.py"]
    assert receipt["runtime_info_sha256"] == protocol[
        "runtime_info_sha256"]
    assert receipt["complete_solve_work_log2"] is None
    assert receipt["challenge_run_admitted"] is False
    assert receipt["progress_file_sha256"] == sha(RUN / "progress.jsonl")

    flags_path = RUN / "status_flags.bin"
    flags = flags_path.read_bytes()
    assert len(flags) == receipt["status_bitmap_bytes"] == 1 << 24
    bitmap_digest = hashlib.sha256(flags).hexdigest()
    assert bitmap_digest == receipt["status_bitmap_sha256"]
    strata = receipt["strata"]
    assert len(strata) == 27
    rational_total = identity_total = nonidentity_total = 0
    for span, row in enumerate(strata, start=1):
        assert row["span"] == span
        start = 0 if span == 1 else 1 << (span - 2)
        stop = 1 << (span - 1)
        assert row["raw_x_orbits"] == stop - start
        counts = [0, 0, 0, 0]
        for index in range(start, stop):
            counts[code_at(flags, index)] += 1
        assert counts[3] == 0, "reserved status code in archive"
        assert counts[1] == row["identity_projection_orbits"]
        assert counts[1] + counts[2] == row["rational_x_orbits"]
        rational_total += counts[1] + counts[2]
        identity_total += counts[1]
        nonidentity_total += counts[2]
    duplicates = sum(row["duplicate_projected_orbits"] for row in strata)
    assert receipt["signed_frobenius_columns_K"] == (
        nonidentity_total - duplicates)
    assert receipt["actual_usable_points_B_before_folding"] == (
        262 * receipt["signed_frobenius_columns_K"])
    assert receipt["geometric_rational_point_count_before_projection"] == (
        262 * rational_total)

    onb = field.Onb(131)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    controls = {row["raw_cycle_mask"]: row for row in receipt[
        "independent_group_control_inputs"]}
    masks = {mask: span for mask, span in independent_masks(27)}
    masks.update({mask: row["span"] for mask, row in controls.items()})
    group_checks = rational_checks = identity_checks = 0
    for mask, span in sorted(masks.items()):
        ordinal = raw_ordinal(mask, span)
        x = onb_x_from_cycle_mask(mask, onb, orbit)
        point = curve.pointFromX(x)
        code = code_at(flags, ordinal)
        if point is None:
            assert code == 0
            key = None
        else:
            rational_checks += 1
            image = curve.mul(point, 4)
            if image is None:
                assert code == 1
                identity_checks += 1
                key = None
            else:
                assert code == 2
                assert curve.onCurve(image)
                assert curve.mul(image, protocol["subgroup_order"]) is None
                key = canonical_rotation(orbit.cycle_bits(image[0]), 131)
                assert 0 < key < (1 << 131) - 1
        if mask in controls:
            control = controls[mask]
            assert control["raw_ordinal"] == ordinal
            assert control["rational"] == (point is not None)
            assert control["status_code"] == code
            assert control["projected_orbit_key"] == key
        group_checks += 1
    return {
        "kind": "q1484_n131_window_base_archive_audit",
        "proposal_id": "Q1484", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(PROTOCOL),
        "receipt_sha256": sha(receipt_path),
        "status_bitmap_sha256": bitmap_digest,
        "full_status_bitmap_count_checked": True,
        "independent_group_checks": group_checks,
        "independent_rational_checks": rational_checks,
        "independent_identity_checks": identity_checks,
        "actual_usable_B": receipt[
            "actual_usable_points_B_before_folding"],
        "folded_K": receipt["signed_frobenius_columns_K"],
        "duplicate_projected_orbits": duplicates,
        "enumerated_set_sha256": receipt["enumerated_set_sha256"],
        "projected_set_digest_independently_recomputed": False,
        "claim_scope": ("Full archived status bitmap counted and hashed; "
                        "deterministic sampled direct group-law checks. "
                        "The sorted projected-set digest is bound to the "
                        "source-bound producer receipt, not independently "
                        "recomputed by this audit."),
        "complete_n131_log2_work": None,
        "status": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = audit()
    path = HERE / "archive_audit.json"
    if args.check or path.exists():
        assert json.loads(path.read_text()) == result
        print("Q1484 N131 base archive audit PASS (archived)")
    else:
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("Q1484 N131 base archive audit PASS")


if __name__ == "__main__":
    main()
