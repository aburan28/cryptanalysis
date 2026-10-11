"""Exact W9 rational source and signed-Frobenius column scan."""

import hashlib
import json
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
PRIOR=ROOT/"n131_w18_four_pairs/screen.json"
RUNTIME=HERE/"sage_runtime_info.json"
N=41
R=549756390943


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze():
    protocol={"status":"FROZEN_N41_W9_RATIONAL_SOURCE_SCAN",
              "curve":"y^2+xy=x^3+1 over GF(2)[t]/(t^41+t^3+1)",
              "dimension":9,"rotations":[0,10,20,30],
              "limits":{"workers":1,"seconds":120,"rss_bytes":4294967296},
              "sha256":{"source":sha(__file__),"prior":sha(PRIOR),
                        "runtime":sha(RUNTIME)}}
    (HERE/"protocol.json").write_text(json.dumps(protocol,indent=2,sort_keys=True)+"\n")
    print(protocol["status"])


def evaluate():
    protocol=json.loads((HERE/"protocol.json").read_text())
    assert protocol["sha256"]=={"source":sha(__file__),"prior":sha(PRIOR),
                                 "runtime":sha(RUNTIME)}
    assert json.loads(RUNTIME.read_text())["status"]=="verified"
    prior=json.loads(PRIOR.read_text())["n41"]
    ring=PolynomialRing(GF(2),"t")
    t=ring.gen()
    field=GF(2**N,"t",modulus=t**41+t**3+1)
    curve=EllipticCurve(field,[1,0,0,0,1])
    zero=curve(0)
    def dec(value):
        return field(ring([(int(value)>>i)&1 for i in range(N)]))
    def enc(value):
        return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))
    def xy(point):
        return [enc(point[0]),enc(point[1])]
    prior_rows=prior["point_rows_by_unique_rotation"]["0"]
    prior_columns={int(row[3]):int(row[2]) for row in prior_rows
                   if int(row[4])==0 and int(row[5])==0}
    assert len(prior_columns)==32
    rows=[]
    start=time.monotonic_ns()
    for mask in range(1,512):
        w=dec(mask<<1)
        assert w.trace()==0
        u=field.zero()
        a=w
        for _ in range(21):
            u+=a
            a=a**4
        assert u**2+u==w and u!=0
        x=1+1/u
        lifts=curve.lift_x(x,all=True)
        if not lifts:
            continue
        assert len(lifts)==2
        projected=4*lifts[0]
        assert projected!=zero and R*projected==zero
        orbit_x=[]
        value=projected[0]
        for _ in range(N):
            orbit_x.append(enc(value))
            value=value**2
        assert value==projected[0]
        rows.append({"mask":mask,"raw_point":xy(lifts[0]),
                     "projected_point":xy(projected),
                     "orbit_key_x":min(orbit_x)})
        if time.monotonic_ns()-start>120_000_000_000:
            raise TimeoutError("frozen W9 source scan cap")
    by_mask={row["mask"]:row for row in rows}
    assert set(prior_columns)=={m for m in by_mask if m<64}
    for a in prior_columns:
        for b in prior_columns:
            assert (prior_columns[a]==prior_columns[b])==(
                by_mask[a]["orbit_key_x"]==by_mask[b]["orbit_key_x"])
    orbit_keys=sorted({row["orbit_key_x"] for row in rows})
    index={key:i for i,key in enumerate(orbit_keys)}
    for row in rows:row["column"]=index[row["orbit_key_x"]]
    counts={"rational_masks":len(rows),"w6_replay_masks":len(prior_columns),
            "signed_frobenius_columns":len(orbit_keys),
            "usable_points_B":len(rows)*2*4,
            "new_rational_masks":sum(row["mask"]>=64 for row in rows)}
    out={"status":"COMPLETE_N41_W9_RATIONAL_SOURCE_SCAN",
         "candidate_id":None,"curve_id":prior["curve_id"],
         "counts":counts,"rows":rows,
         "elapsed_ns":time.monotonic_ns()-start,
         "protocol_sha256":sha(HERE/"protocol.json")}
    (HERE/"geometry.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(out["status"],counts,out["elapsed_ns"]/1e9)


if __name__=="__main__":
    if len(sys.argv)!=2 or sys.argv[1] not in ("freeze","evaluate"):
        raise SystemExit("usage: scan_sage.py freeze|evaluate")
    (freeze if sys.argv[1]=="freeze" else evaluate)()
