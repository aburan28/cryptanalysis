"""Check the exact curve and factor-base identity of n=83 stage records.

These are proposal-stage receipts, so their candidate and run IDs stay null.
The checks prevent a receipt from entering the Q1062 coverage/work ledger
under a matching label but a different field, curve, base, or target.
"""

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CURVE_ID = re.compile(r"EC1N([1-9][0-9]*)C[a-z0-9]+h([0-9a-f]{12,64})\Z")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_reference(screen):
    match = CURVE_ID.fullmatch(screen["curve_id"])
    assert match, "malformed curve ID"
    identity = screen["curve_identity_record"]
    assert set(identity) == {"field", "curve"}
    assert "curve_id" not in identity["curve"]
    assert identity["field"]["p"] == 2
    assert identity["field"]["n"] == int(match.group(1)) == 83
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    assert digest.startswith(match.group(2)), "curve ID does not hash field and curve"
    assert screen["isogeny"] == "none"
    assert screen["candidate_id"] is None and screen["run_id"] is None

    base = screen["factor_base"]
    assert base["selected_point_orbits"] == base["signed_frobenius_columns"]
    assert base["signed_frobenius_orbit_size"] == 2 * identity["field"]["n"]
    assert (base["actual_usable_points_B_before_folding"] ==
            base["selected_point_orbits"] * base["signed_frobenius_orbit_size"])
    assert base["unknown_log_columns"] == 0
    assert base["initially_known_log_columns"] == base["signed_frobenius_columns"]
    assert re.fullmatch(r"[0-9a-f]{64}", base["enumerated_set_sha256"])
    artifact = HERE / base["key_and_log_file"]
    assert artifact.stat().st_size == base["key_and_log_file_bytes"]
    assert sha(artifact) == base["key_and_log_file_sha256"]


def validate_receipt(screen, row):
    assert row["curve_id"] == screen["curve_id"]
    assert row["curve_identity_record"] == screen["curve_identity_record"]
    base = screen["factor_base"]
    if "factor_base" in row:
        assert row["factor_base"] == base
    else:
        # Failed attempts retain a compact base identity in their start record.
        assert row["factor_base_enumerated_set_sha256"] == base[
            "enumerated_set_sha256"]
        assert row["actual_usable_points_B_before_folding"] == base[
            "actual_usable_points_B_before_folding"]
        assert row["signed_frobenius_columns"] == base[
            "signed_frobenius_columns"]
    assert row["isogeny"] == "none"
    assert row["candidate_id"] is None and row.get("run_id") is None
    assert row["public_target"] == screen["public_target"]
