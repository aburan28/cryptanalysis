#!/usr/bin/env sage -python
"""Independently replay all N41 panel targets and affine-plane witnesses."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_coupled_sixpair_full_ic_20261010"
R = 549756390943
OFFSET = 57


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "audit_protocol_v2.json").read_text())
    paths = {"audit": Path(__file__), "panel_protocol": HERE / "panel_protocol.json",
             "panel_result": HERE / "panel_result.json", "public": HERE / "public_targets.json",
             "private": HERE / "private_fixture.json", "workload": SOURCE / "workload.json",
             "factor_logs": SOURCE / "factor_logs.json",
             "factor_audit": SOURCE / "sage_audit.json",
             "canonical_alias": SOURCE / "canonical_workload.json",
             "runtime": HERE / "sage_runtime_info.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    data = {name: json.loads(path.read_text()) for name, path in paths.items()
            if name not in ("audit", "runtime")}
    panel = data["panel_result"]
    public = data["public"]
    private = data["private"]
    workload = data["workload"]
    logs = data["factor_logs"]["logs_mod_r"]
    assert len(panel["rows"]) == len(public["targets"]) == len(private["targets"]) == 16
    assert data["factor_audit"]["status"] == "PASS_INDEPENDENT_SAGE_N41_FACTOR_LOGS_AND_26_RELATIONS"
    assert data["canonical_alias"]["curve_id"] == public["curve_id"]
    assert data["canonical_alias"]["prior_curve_id_alias_in_frozen_stage_receipts"] == workload["curve_id"]
    assert len(logs) == 26

    poly = PolynomialRing(GF(2), "t")
    t = poly.gen()
    field = GF(2**41, name="t", modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(poly([(int(value) >> i) & 1 for i in range(41)]))

    def point(pair):
        return curve(decode(pair[0]), decode(pair[1]))

    generator = point(private["generator"])
    assert R * generator == curve(0)
    atom_map = {(item["block"], item["mask"], item["sign"]): item
                for item in workload["atoms"]}
    block_map = [0, 1, 2, 2, 4, 4]
    audited = []
    for index, (row, pub, fixture) in enumerate(zip(panel["rows"], public["targets"],
                                                     private["targets"])):
        assert index == row["index"] == pub["index"] == fixture["index"]
        assert row["target"] == pub["target"] == fixture["target"]
        target = point(row["target"])
        assert R * target == curve(0)
        assert fixture["scalar"] * generator == target
        out_dir = HERE / f"run_{index:02d}"
        for name in ("stdout.txt", "stderr.txt"):
            assert row["source_sha256"][name] == digest(out_dir / name)
        assert row["native_sha256"] == digest(out_dir / "native.json")
        assert row["hit_sha256"] == digest(out_dir / "hit.json")
        native = json.loads((out_dir / "native.json").read_text())
        assert row["status"] == native["status"]
        assert row["exit_code"] == 0
        assert row["online_ns"] == native["online_ns"]
        assert row["setup_ns"] == native["setup_ns"]
        assert row["accepted_probes"] == native["accepted_probes"]
        assert row["peak_rss_bytes"] == native["peak_rss_bytes"] < 4294967296
        assert sum(native["exclusive_phase_ns"].values()) == native["online_ns"] < 120_000_000_000
        assert native["pair_states_per_rotation"] == 1956
        assert native["left_four_states"] == 3167136
        assert native["right_quad_a"] == native["right_quad_b"] == 3328
        assert native["offset_mask"] == OFFSET
        if native["status"] == "EXHAUSTED_NO_RELATION":
            assert (out_dir / "hit.json").read_bytes() == b""
            assert native["attempts"] == 3328**2
            assert native["accepted_probes"] == 5529600
            assert native["group_hits"] == native["column_rejects"]
            audited.append({"index": index, "status": native["status"],
                            "accepted_probes": native["accepted_probes"],
                            "group_hits": native["group_hits"],
                            "column_rejects": native["column_rejects"]})
            continue
        assert native["status"] == "VERIFIED_SCALAR"
        assert native["group_hits"] == native["column_rejects"] + 1
        hit = json.loads((out_dir / "hit.json").read_text())
        assert hit["status"] == "NATIVE_SCALAR_VERIFIED"
        assert hit["raw_sum"] == row["target"]
        assert hit["slot_rotations"] == [0, 5, 10, 10, 20, 20]
        assert hit["offset_mask"] == OFFSET
        assert len(hit["masks"]) == len(hit["signs"]) == len(hit["columns"]) == 12
        assert len(set(hit["columns"])) == 12
        selected = []
        scalar = 0
        for slot in range(12):
            atom = atom_map[(block_map[slot // 2], hit["masks"][slot], hit["signs"][slot])]
            assert atom["column"] == hit["columns"][slot]
            representative = point(workload["representatives"][atom["column"]])
            selected.append(point(atom["point"]))
            assert atom["coefficient_mod_r"] * representative == selected[-1]
            scalar = (scalar + atom["coefficient_mod_r"] * logs[atom["column"]]) % R
        for first in (4, 8):
            source_pair = {hit["masks"][first], hit["masks"][first + 1]}
            shifted_pair = {hit["masks"][first + 2], hit["masks"][first + 3]}
            assert {mask ^ OFFSET for mask in source_pair} == shifted_pair
        assert sum(selected, curve(0)) == target
        assert scalar == hit["recovered_scalar"] == native["recovered_scalar"]
        assert scalar == fixture["scalar"]
        assert scalar * generator == target
        audited.append({"index": index, "status": native["status"],
                        "scalar": int(scalar), "relation_points": len(selected),
                        "accepted_probes": native["accepted_probes"],
                        "group_hits": native["group_hits"],
                        "column_rejects": native["column_rejects"]})

    positives = sum(row["status"] == "VERIFIED_SCALAR" for row in audited)
    receipt = {"status": "PASS_INDEPENDENT_SAGE_N41_PLANE_ORDINARY_PANEL",
               "target_count": len(audited), "verified_scalar_count": positives,
               "exhausted_count": len(audited) - positives, "rows": audited,
               "source_sha256": {name: digest(path) for name, path in paths.items()},
               "audit_protocol_sha256": digest(HERE / "audit_protocol_v2.json")}
    with (HERE / "panel_sage_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "verified_scalar_count": positives,
                      "target_count": len(audited)}))


if __name__ == "__main__":
    main()
