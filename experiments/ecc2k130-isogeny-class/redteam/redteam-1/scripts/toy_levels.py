# For prime n, list small primes l dividing the conductor f_n of Z[pi] for the two
# Koblitz curves over F_2 (a=0: t1=-1, a=1: t1=+1).  Used to pick a toy class with a
# computable floor (level l) for the PDP comparison E0 vs floor vs random b.
from sage.all import *
import json, sys
out = []
for n in prime_range(11, 70):
    for a, t1 in [(0, -1), (1, 1)]:
        # Lucas: t_k = t1*t_{k-1} - 2*t_{k-2}
        t0, tk = Integer(2), Integer(t1)
        for _ in range(n - 1):
            t0, tk = tk, t1 * tk - 2 * t0
        D = tk**2 - 4 * 2**n
        assert D % 7 == 0 and (-D // 7).is_square()
        f = isqrt(-D // 7)
        fac = factor(f) if f > 1 else []
        small = [(int(l), int(e), int(kronecker(-7, l))) for l, e in fac if l < 3000]
        out.append(dict(n=int(n), a=a, t=int(tk), f=int(f), small_l=small,
                        fac=str(fac)))
        print(n, a, tk, f, fac, small)
json.dump(out, open(sys.argv[1], "w"), indent=1)
