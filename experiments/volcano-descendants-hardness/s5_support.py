"""m = 4 (S_5) descent support at l = 5: E0 vs a descendant, standard vs b^(1/4) basis.

Only the monomial support of the descended system is compared (deterministic);
msolve at m = 4, l = 4, n = 131 takes over 10 minutes per instance here.

    python3 s5_support.py > s5_support.txt
"""

import json
import sys
import time
from collections import Counter

import pdp_descendants as P

L = 5
res = json.load(open(P.HERE / "results.json"))
bd = int(res["descendants"][0]["b_hex"], 16)
supports = {}
for name, b, kind in (("E0/std", 1, "std"), ("E0/shift", 1, "shift"),
                      ("d0/std", bd, "std"), ("d0/qroot", bd, "qroot")):
    t0 = time.time()
    assert P.liftable_in_V(4, L, b, kind) >= 4
    inst = P.make_instance_basis(4, L, 1, b, kind)
    supports[name] = set(inst.anf)
    deg = max(bin(k).count("1") for k in inst.anf)
    print(f"{name}: {len(inst.anf)} monomials, max degree {deg} ({time.time() - t0:.0f}s)", flush=True)


def shape(k):
    return tuple(sorted((bin((k >> (i * L)) & ((1 << L) - 1)).count("1") for i in range(4)), reverse=True))


for a, b in (("d0/std", "E0/std"), ("E0/shift", "E0/std"), ("d0/std", "d0/qroot"), ("E0/shift", "d0/std")):
    only_a, only_b = supports[a] - supports[b], supports[b] - supports[a]
    print(f"{a} minus {b}: {len(only_a)} {dict(Counter(map(shape, only_a)))};"
          f" {b} minus {a}: {len(only_b)}")
