# Search Koblitz curves y^2+xy=x^3+a*x^2+1 over F_{2^n}, n prime, for toy analogues of the
# ECC2K-130 263-volcano: Frobenius conductor f_n (t^2-4q=-7 f_n^2) with a small odd prime
# factor l that splits in Q(sqrt(-7)).
from sage.all import *
import json, sys
out = []
for a in (0, 1):
    t1 = -1 if a == 0 else 1
    for n in prime_range(5, 110):
        tt = [Integer(2), Integer(t1)]
        for k in range(2, n + 1):
            tt.append(t1 * tt[-1] - 2 * tt[-2])
        t = tt[n]; q = Integer(2)**n
        card = q + 1 - t
        D = t*t - 4*q
        assert D % 7 == 0 and (-D // 7).is_square()
        f = isqrt(-D // 7)
        fac_f = factor(f)
        fac_c = factor(card)
        Nn = max(pp for pp, e in fac_c)
        good = [(int(l), int(e)) for l, e in fac_f if l != 2 and l != 7 and kronecker(-7, l) == 1 and l < 10**6]
        rec = dict(a=a, n=int(n), t=int(t), card=int(card), card_fac=str(fac_c), N=int(Nn),
                   N_bits=float(log(Nn, 2)), f=int(f), f_fac=str(fac_f), split_l=good)
        out.append(rec)
        if good:
            print(a, n, 'card=', fac_c, 'f=', fac_f, 'split l:', good, 'log2N=%.1f' % float(log(Nn, 2)))
json.dump(out, open(sys.argv[1], 'w'), indent=1)
