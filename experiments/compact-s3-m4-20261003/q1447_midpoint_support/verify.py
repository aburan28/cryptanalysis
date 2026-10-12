"""Independent integer and finite-group audit of the Q1447 bound."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXP = ROOT / "experiments/compact-s3-m4-20261003"
PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "result.json"
REPORT = HERE / "verification.json"
INPUTS = (
    EXP / "q1438_dense_base/protocol.json",
    EXP / "q1413_projected_x_protocol.json",
    EXP / "q1438_dense_base/n53_w4_base.json",
    EXP / "q1438_dense_base/n83_w6_base.json",
    EXP / "runs/n131_q1413_projected_x_w6.json",
    EXP / "q1442_selected_base_screen/result.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ceil_ratio(a: int, b: int) -> int:
    return (a + b - 1) // b


def toy_group_check() -> int:
    """Check the sign-orbit step for every symmetric set in small groups."""
    checked = 0
    for order in range(3, 13):
        for mask in range(1 << (order - 1)):
            base = {j for j in range(1, order) if mask >> (j - 1) & 1}
            if any((-j) % order not in base for j in base):
                continue
            sums = {(a + b) % order for a in base for b in base}
            x_orbits = {min(j, (-j) % order) for j in sums if j != 0}
            maximum_pairs = len(base) * (len(base) + 1) // 2
            assert len(x_orbits) <= ceil_ratio(maximum_pairs, 2)
            checked += 1
    return checked


def audit() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    result = json.loads(RESULT.read_text())
    assert protocol["source_sha256"] == sha(HERE / "screen.py")
    assert protocol["audit_source_sha256"] == sha(Path(__file__))
    assert result["protocol_sha256"] == sha(PROTOCOL)
    assert result["source_sha256"] == sha(HERE / "screen.py")
    assert result["proposal_id"] == protocol["proposal_id"] == "Q1447"
    assert result["candidate_id"] is None and result["isogeny"] == "none"
    assert result["complete_n131_log2_work"] is None
    assert result["challenge_run_admitted"] is False
    for path in INPUTS:
        relative = str(path.relative_to(ROOT))
        assert protocol["input_sha256"][relative] == sha(path)
    curves = json.loads(INPUTS[0].read_text())
    q1413 = json.loads(INPUTS[1].read_text())
    actual = [json.loads(path.read_text()) for path in INPUTS[2:5]]
    selected = json.loads(INPUTS[5].read_text())
    expected = []
    for record in actual:
        n = int(record["field_degree_n"])
        b = int(record["actual_usable_points_B_before_folding"])
        k = int(record["signed_frobenius_columns_K"])
        assert b == 2 * n * k
        assert "both signs" in record["enumerated_set_encoding"]
        if n in (53, 83):
            curve = curves["instances"][str(n)]["curve"]
            assert curve["curve_id"] == record["curve_id"]
            assert curve["a1"] == 1 and curve["a3"] == 0
        else:
            assert q1413["instances"]["131"]["curve_id"] == record["curve_id"]
            assert q1413["mathematical_identity"].startswith(
                "For y^2+xy=x^3+1")
        assert all(entry.get("duplicate_projected_orbits_at_insertion",
                             entry.get("duplicate_projection_orbits")) == 0
                   for entry in record["strata"])
        expected.append((n, b, k, record["curve_id"],
                         record["enumerated_set_sha256"], False))
    model = next(entry for entry in selected["rows"]
                 if entry["label"] == "selected_W7_conditional_model")
    expected.append((131, int(model["B_model"]), int(model["K_model"]),
                     selected["curve_id"], None, True))
    assert len(result["rows"]) == len(expected) == 4
    for entry, (n, b, k, curve_id, digest, conditional) in zip(
            result["rows"], expected):
        m = b * (b + 1) // 2
        x = ceil_ratio(m, 2)
        field_size = 1 << n
        t = ceil_ratio(19 * field_size, 20 * x)
        assert entry["curve_id"] == curve_id
        assert entry["field_degree_n"] == n
        assert entry["base_set_sha256"] == digest
        assert entry["conditional_base_model"] is conditional
        assert entry["actual_B"] == (None if conditional else b)
        assert entry["actual_K"] == (None if conditional else k)
        assert int(entry["B_used_in_bound"]) == b
        assert int(entry["K_reference"]) == k
        assert int(entry["maximum_unordered_raw_pair_sums"]) == m
        assert int(entry["maximum_first_pair_x_support"]) == x
        assert int(entry["minimum_uniform_midpoint_trials_for_95pct_one_relation"]) == t
        assert entry["minimum_trials_exceed_2pow61"] == (t > 2**61)
        assert (t - 1) * x * 20 < 19 * field_size <= t * x * 20
    assert all(entry["minimum_trials_exceed_2pow61"]
               for entry in result["rows"][-2:])
    return {
        "proposal_id": "Q1447",
        "status": "pass",
        "proof_boundary": "uniform raw midpoint x, fixed target, free suffix oracle; conditional W7 size is not enumerated",
        "finite_group_symmetric_sets_checked": toy_group_check(),
        "rows_checked": len(expected),
        "protocol_sha256": sha(PROTOCOL),
        "result_sha256": sha(RESULT),
        "audit_source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.emit == args.check:
        parser.error("choose --emit or --check")
    value = audit()
    if args.emit:
        if REPORT.exists():
            raise FileExistsError(f"refusing to overwrite {REPORT}")
        REPORT.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(REPORT.read_text()) == value
        print("Q1447 independent integer and finite-group audit: PASS")


if __name__ == "__main__":
    main()
