#!/usr/bin/env python3
"""Independent checked-Sage group and accounting audit for the six-pair gate."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    planted = json.loads((HERE / "planted.json").read_text())
    preflight = json.loads((HERE / "preflight/receipt.json").read_text())
    control = json.loads((HERE / "control/receipt.json").read_text())
    screen = json.loads((ROOT / "n131_w18_four_pairs/screen.json").read_text())["n41"]
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    assert planted["curve_id"] == protocol["curve_id"] == screen["curve_id"]
    assert preflight["status"] == "PASS"
    assert control["status"] == control["solver"]["status"] == "PARENT_WALL_CAP"
    assert control["relation"] is None and control["xcnf_check"] is None
    assert control["protocol_sha256"] == preflight["source_protocol_sha256"] == sha(HERE / "protocol.json")
    assert control["formula"]["sha256"] == preflight["formula"]["sha256"]
    assert control["formula"]["variables"] == preflight["formula"]["variables"]
    assert sum(value for value in control["phase_ns"].values()
               if value is not None) == control["online_ns"]
    assert control["solver"]["peak_group_rss_bytes"] < protocol["memory_cap_bytes"]
    assert control["online_ns"] >= protocol["cap_seconds"]["control"] * 10**9

    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)
    order = 549756390943

    def decode(value):
        return field(ring([(int(value) >> bit) & 1 for bit in range(41)]))

    def encode(value):
        return sum(int(coefficient) << bit for bit, coefficient in
                   enumerate(value.polynomial().list()))

    def point(values):
        return curve(decode(values[0]), decode(values[1]))

    def point_key(value):
        return [encode(value[0]), encode(value[1])]

    def orbit_key(value):
        keys = []
        current = value
        for _ in range(41):
            keys.extend((tuple(point_key(current)), tuple(point_key(-current))))
            current = curve(current[0]**2, current[1]**2)
        assert current == value
        return min(keys)

    def phi(value):
        assert value != zero and value[0] != 1
        return 1 / (value[0] + 1)

    raw = [point(row) for row in planted["raw_points"]]
    assert len(raw) == len(planted["seed_masks"]) == 12
    source_halves = [decode(x) for x in screen["window_basis_halftrace"][0]]
    source_columns = {}
    for x, y, column, mask, branch, sign in screen["point_rows_by_unique_rotation"]["0"]:
        if mask in source_columns:
            assert source_columns[mask] == column
        source_columns[mask] = column
    projected = []
    for slot, (mask, raw_point) in enumerate(zip(planted["seed_masks"], raw)):
        rotation = protocol["rotations"][slot // 2]
        expected_phi = sum((source_halves[bit]**(2**rotation)
                            for bit in range(6) if mask & (1 << bit)),
                           field.zero())
        assert phi(raw_point) == expected_phi
        assert source_columns[mask] == planted["folded_columns"][slot]
        projected_point = 4 * raw_point
        assert projected_point != zero and order * projected_point == zero
        projected.append(projected_point)
    keys = [orbit_key(value) for value in projected]
    assert len(set(keys)) == 12
    pairs = [raw[2*i] + raw[2*i+1] for i in range(6)]
    first = [pairs[2*i] + pairs[2*i+1] for i in range(3)]
    second = first[0] + first[1]
    total = second + first[2]
    assert [encode(phi(value)) for value in pairs] == planted["pair_u"]
    assert [encode(phi(value)) for value in first] == planted["first_u"]
    assert encode(phi(second)) == planted["second_u"]
    assert point_key(total) == planted["raw_sum"]
    q = 4 * total
    assert point_key(q) == planted["target_q"]
    assert sum(projected, zero) == q and order * q == zero
    assert preflight["relation"]["raw_points"] == planted["raw_points"]

    receipt = {"kind": "n41_six_pair_same_rotation_independent_audit",
               "status": "PASS", "control_status": control["status"],
               "public_gate": "NOT_STARTED_CONTROL_TIMEOUT",
               "curve_id": protocol["curve_id"],
               "raw_points_replayed": 12, "distinct_folded_columns": len(set(keys)),
               "target_q": planted["target_q"],
               "control_online_ns": control["online_ns"],
               "control_peak_group_rss_bytes": control["solver"]["peak_group_rss_bytes"],
               "sha256": {"audit_source": sha(__file__),
                          "protocol": sha(HERE / "protocol.json"),
                          "preflight": sha(HERE / "preflight/receipt.json"),
                          "control": sha(HERE / "control/receipt.json"),
                          "runtime": sha(HERE / "sage_runtime_info.json")}}
    path = HERE / "audit.json"
    if path.exists():
        raise FileExistsError("preserve first independent audit")
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "control_status": receipt["control_status"],
                      "distinct_columns": receipt["distinct_folded_columns"]}))


if __name__ == "__main__":
    main()
