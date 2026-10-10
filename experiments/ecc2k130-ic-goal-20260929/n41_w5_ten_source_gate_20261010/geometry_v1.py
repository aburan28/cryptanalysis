#!/usr/bin/env python3
"""Exact N41 W5 rational-source and ten-rotation subgroup base census."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "n41_n131_seven_diagonal_20261009"
sys.path.insert(0, str(OLD))
import run as old

PROTOCOL = HERE / "geometry_protocol.json"
RESULT = HERE / "geometry_result.json"
R = 549756390943

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["status"] == "FROZEN_BEFORE_ENUMERATION"
    assert protocol["source_sha256"] == {"geometry":sha(__file__),
           "old_run":sha(OLD/"run.py"), "base":sha(old.base.__file__),
           "screen":sha(old.SCREEN), "public":sha(old.PUBLIC)}
    screen = json.loads(old.SCREEN.read_text())["n41"]
    public = json.loads(old.PUBLIC.read_text())
    assert screen["curve_id"] == public["curve_id"] == protocol["curve_id"]
    assert screen["subgroup_order"] == R
    field = old.base.Field(41,[0,3])
    curve = old.base.Curve(field,0)
    q = tuple(public["target_q"])
    assert curve.on_curve(q) and curve.mul(R,q) is None
    source_w = [int(x) for x in screen["window_basis_w"][0][:5]]
    source_u = [int(x) for x in screen["window_basis_halftrace"][0][:5]]
    assert source_w == [2,4,8,16,32]
    for w,u in zip(source_w,source_u):
        assert field.mul(u,u)^u == w
    rotations = protocol["rotations"]
    bases_u = [[old.frob(field,u,rotation) for u in source_u]
               for rotation in rotations]
    columns = {}
    raw_points = {}
    projected = set()
    for mask in range(1,1<<5):
        w = old.base.coordinate(source_w,mask)
        if old.base.trace(field,field.inv(w)):
            continue
        u = old.base.coordinate(source_u,mask)
        assert u not in (0,1) and field.mul(u,u)^u == w
        raw_x = 1 ^ field.inv(u)
        options = sorted(tuple(p) for p in old.base.points_with_x(curve,raw_x))
        assert len(options) == 2
        raw_points[str(mask)] = [list(p) for p in options]
        keys = set()
        for p in options:
            keys.add(old.base.signed_frob_key(field,curve,p))
            subgroup = curve.mul(4,p)
            assert subgroup is not None
            for rotation in rotations:
                projected.add(old.point_frob(field,subgroup,rotation))
        assert len(keys) == 1
        columns[str(mask)] = list(keys.pop())
    rational = len(columns)
    distinct_columns = len({tuple(v) for v in columns.values()})
    assert len(projected)%2 == 0 and len(projected) > 0
    result={"kind":"n41_w5_ten_source_exact_geometry",
            "status":"PASS_FULL_MASK_AND_PROJECTED_GROUP_ENUMERATION",
            "curve_id":protocol["curve_id"],"subgroup_order_r":str(R),
            "public_target_q":list(q),"rotations":rotations,
            "source_basis_w":source_w,"source_basis_u":source_u,
            "bases_u":bases_u,"checked_nonzero_masks":31,
            "rational_source_masks":rational,
            "folded_columns_K":distinct_columns,
            "actual_subgroup_factor_base_points_B":len(projected),
            "mask_columns":columns,"raw_points":raw_points,
            "source_sha256":{"protocol":sha(PROTOCOL),"script":sha(__file__)}}
    with RESULT.open("x") as f:
        json.dump(result,f,indent=2,sort_keys=True)
        f.write("\n")
    print(json.dumps({"status":result["status"],"rational":rational,
                      "K":distinct_columns,"B":len(projected)}))

if __name__ == "__main__":
    main()
