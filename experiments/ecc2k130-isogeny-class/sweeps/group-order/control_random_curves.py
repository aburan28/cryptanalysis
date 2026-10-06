"""Control: the pure-python AGM must also give the right (different) trace on random curves over
F_{2^131} that are NOT in the ECC2K-130 isogeny class; compared against PARI ellcard.
(sage -python control_random_curves.py)"""
import json
import random
import sys

sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/group-order")
from purebin import GF2m, agm_trace
from sage.all import pari

F = GF2m(131, (13, 2, 1, 0))
pari("zz = ffgen(Mod(1,2)*(x^131+x^13+x^2+x+1), 'zz)")
pari("tofq(n) = subst(Pol(binary(n)), x, zz) + 0*zz")
rng = random.Random("group-order-control")
q = 2 ** 131
rows = []
for i in range(4):
    b = rng.getrandbits(131)
    t_agm, inZ2 = agm_trace(F, b, prec=80, warm=92)
    card = int(pari("ellcard(ellinit([1,0,0,0,tofq(%d)]))" % b))
    rows.append({"b": str(b), "t_agm": str(t_agm), "agm_in_Z2": inZ2, "t_pari": str(q + 1 - card),
                 "match": (q + 1 - card == t_agm), "card_factor": str(pari("factor(%d)" % card))})
    print(rows[-1], flush=True)
json.dump(rows, open("/Volumes/SSD990/ecdlp-hardness-work/group-order/raw/control_random_curves.json", "w"), indent=1)
print("all match:", all(r["match"] for r in rows))
