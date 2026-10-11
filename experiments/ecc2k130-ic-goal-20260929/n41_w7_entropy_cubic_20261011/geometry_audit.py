"""Independently count distinct signed points across four Frobenius windows."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
N=41
MASK=(1<<N)-1


def square(a):
    value=0
    while a:
        bit=(a&-a).bit_length()-1
        value^=1<<(2*bit)
        a&=a-1
    while value>>N:
        upper=value>>N
        value=(value&MASK)^upper^(upper<<3)
    return value


def mul(a,b):
    value=0
    while b:
        if b&1:value^=a
        b>>=1
        a<<=1
        if a>>N:a=(a&MASK)^(a>>N)^((a>>N)<<3)
    return value


def on_curve(x,y):
    return (square(y)^mul(x,y))==(mul(square(x),x)^1)


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


rows=[]
for dimension in (7,8,9):
    directory=HERE if dimension==7 else HERE/f"w{dimension}"
    data=json.loads((directory/"geometry.json").read_text())
    points=set()
    per_window=[]
    for rotation in (0,10,20,30):
        window=set()
        for item in data["rows"]:
            x,y=item["projected_point"]
            assert on_curve(x,y)
            for _ in range(rotation):x,y=square(x),square(y)
            assert on_curve(x,y)
            window.add((x,y))
            window.add((x,y^x))
        assert len(window)==2*len(data["rows"])
        points.update(window)
        per_window.append(len(window))
    result={"dimension":dimension,"per_window_points":per_window,
            "distinct_union_B":len(points),
            "sum_window_points":sum(per_window),
            "cross_window_duplicates":sum(per_window)-len(points),
            "geometry_sha256":digest(directory/"geometry.json")}
    rows.append(result)
out={"status":"PASS_INDEPENDENT_N41_W7_W8_W9_UNION_COUNT",
     "rows":rows}
(HERE/"geometry_audit.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print(out["status"],[(r["dimension"],r["distinct_union_B"],r["cross_window_duplicates"]) for r in rows])
