#!/usr/bin/env python3
"""Independent checked-Sage replay of the public compact-lookup row."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
INPUT = GOAL / "n131_w18_four_pairs/native_join/native_input.txt"
ORBIT = GOAL / "n41_w6_s8_pipeline/base_orbit_coefficients.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "sage_audit.json"
    if output.exists():
        raise FileExistsError("preserve independent audit receipt")
    freeze = json.loads((HERE / "protocol_v2.json").read_text())
    result = json.loads((HERE / "public_search_v2.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    orbit = json.loads(ORBIT.read_text())
    assert runtime["status"] == "verified"
    assert digest(HERE / "native_compact.cpp") == freeze["source_sha256"]
    assert digest(HERE / "native_compact_v2") == freeze["binary_sha256"]
    assert digest(INPUT) == freeze["public_input_sha256"]
    assert digest(HERE / "protocol.json") == freeze["first_protocol_sha256"]
    assert freeze["first_attempt_status"] == "OUTPUT_WRITE_FAILURE_EMPTY_RECEIPT"
    assert (HERE / "public_search.json").stat().st_size == 0
    assert result["status"] == "VERIFIED_RAW_ROW"
    assert result["target"] == freeze["target"] == [1458168294740, 1672312028033]
    assert result["candidate_id"] is None and result["run_id"] is None
    assert result["online_ns"] < 120 * 10**9
    assert result["peak_rss_bytes"] < 4 * 1024**3
    assert result["online_ns"] == (result["query_and_loop_ns"] +
                                    result["completion_probe_ns"] +
                                    result["internal_verification_ns"])
    assert result["residuals"] == 513088
    assert result["x_hits"] == result["exact_group_hits"] == 6
    assert result["final_column_rejects"] == 5
    assert orbit["status"] == "PASS"
    assert orbit["curve_id"] == freeze["curve_id"]
    assert orbit["actual_usable_points_B"] == 256
    assert orbit["folded_columns_K"] == 26

    poly = PolynomialRing(GF(2), "t")
    t = poly.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    identity = curve(0)

    def point(raw):
        def decode(value):
            return field(poly([(int(value) >> bit) & 1 for bit in range(41)]))
        return curve(decode(raw[0]), decode(raw[1]))

    lines = INPUT.read_text().splitlines()
    qx, qy, subgroup_order, summands = map(int, lines[0].split())
    assert [qx, qy] == result["target"]
    assert subgroup_order == orbit["subgroup_order"] == 549756390943
    assert summands == 8
    slots = []
    cursor = 1
    for _ in range(summands):
        count = int(lines[cursor]); cursor += 1
        assert count == 64
        rows = []
        for _ in range(count):
            x, y, column, mask, branch, sign = map(int, lines[cursor].split())
            cursor += 1
            assert 0 <= column < 26 and 0 < mask < 64 and branch == 0
            assert sign in (0, 1)
            rows.append({"point": [x, y], "column": column,
                         "mask": mask, "sign": sign})
        slots.append(rows)
    assert cursor == len(lines)
    assert all(slots[2*i] == slots[2*i+1] for i in range(4))

    q = point(result["target"])
    assert subgroup_order * q == identity
    representatives = [point(raw) for raw in orbit["column_representatives"]]
    assert len(representatives) == 26
    row = result["row"]
    assert len(row) == 8
    assert len({entry["column"] for entry in row}) == 8
    replayed = []
    for slot, entry in enumerate(row):
        assert entry in slots[slot]
        value = point(entry["point"])
        assert subgroup_order * value == identity
        key = f"{entry['point'][0]},{entry['point'][1]}"
        coefficient = orbit["point_to_column_coefficient"][key]
        assert coefficient["column"] == entry["column"]
        assert int(coefficient["coefficient"]) * representatives[entry["column"]] == value
        replayed.append(value)
    assert sum(replayed, identity) == q
    report = {
        "kind": "n41_compact_lookup_independent_sage_audit",
        "status": "PASS",
        "proposal_id": freeze["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "curve_id": freeze["curve_id"],
        "verified_base_points": 8,
        "verified_subgroup_points": 8,
        "verified_orbit_coefficients": 8,
        "distinct_columns": 8,
        "exact_group_sum": True,
        "result_sha256": digest(HERE / "public_search_v2.json"),
        "protocol_sha256": digest(HERE / "protocol_v2.json"),
        "orbit_sha256": digest(ORBIT),
        "runtime_sha256": digest(HERE / "sage_runtime_info.json"),
        "audit_source_sha256": digest(Path(__file__)),
    }
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print("PASS_INDEPENDENT_SAGE_ROW_AUDIT")


if __name__ == "__main__":
    main()
