"""Extra degree-graded RREF profiles (see graded_profile.py): m = 3 at k = 11, 12 on the
polynomial basis, and the b-aligned subspaces span{(b+1)^j} (shiftb) / span{b^j} (powerb) for
class curves at k = 6..10, one fixed random target (the first of graded_profile.py's).
Usage: sage -python graded_extra.py  -> graded_extra.json"""
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import g5lib as L  # noqa: E402

sys.argv = sys.argv[:1]
src = (HERE / "graded_profile.py").read_text()
# reuse graded() and cb() without re-running graded_profile's main loop
ns = {"__file__": str(HERE / "graded_profile.py"), "__name__": "graded_profile_defs"}
exec(src.split("labels = [")[0], ns)  # noqa: S102  (defines L, CTRL, cb, graded)
graded, cb = ns["graded"], ns["cb"]

rng = random.Random(20260924 + 11)
r = L.dec(rng.getrandbits(131))  # identical to graded_profile.py's first target
out = {"rows": []}
t0 = time.time()


def emit(row):
    out["rows"].append(row)
    print(json.dumps(row), flush=True)
    (ROOT / "graded_extra.json").write_text(json.dumps(out, indent=1))


for k in range(6, 11):
    for lab in ("A000", "B000", "A010", "RD00"):
        b = cb(lab)
        for sname, basis in (("shiftb", [(b + 1) ** j for j in range(k)]), ("powerb", [b**j for j in range(k)])):
            ts = time.time()
            emit({"m": 3, "k": k, "label": lab, "sub": sname, "graded": [graded(L.descended_anf(3, basis, b, r))],
                  "seconds": round(time.time() - ts, 2)})
for k in (11, 12):
    for lab, sname in (("E0", "poly"), ("RD00", "poly"), ("A000", "poly"), ("RS00", "poly"), ("A000", "shiftb")):
        b = cb(lab)
        basis = L.poly_basis(k) if sname == "poly" else [(b + 1) ** j for j in range(k)]
        ts = time.time()
        emit({"m": 3, "k": k, "label": lab, "sub": sname, "graded": [graded(L.descended_anf(3, basis, b, r))],
              "seconds": round(time.time() - ts, 2)})
out["seconds"] = time.time() - t0
(ROOT / "graded_extra.json").write_text(json.dumps(out, indent=1))
print("done", out["seconds"])
