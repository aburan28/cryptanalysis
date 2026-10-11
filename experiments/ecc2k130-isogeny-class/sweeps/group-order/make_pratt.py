"""Build recursive Pratt (Lucas n-1) primality certificates with Sage for the primes that matter to
the group orders: N (curve order 4N), p, 263 (conductor), P114 (twist order 2*263^2*P114).
Also records the full factorizations of 4N and q+1+t.  Verification is done separately by
verify_pratt.py in pure python (no Sage).  (sage -python make_pratt.py)"""
import json
from sage.all import factor, Integer

q = 2 ** 131
t = -22283658519494248867
N = 680564733841876926932320129493409985129
p = 146505763881528721
P114 = 19678316408850118605767852657510239
SMALL = 2 ** 20


def pratt(n):
    n = Integer(n)
    if n < SMALL:
        return {"n": str(n), "small": True}
    fac = factor(n - 1)
    primes = [int(r) for r, e in fac]
    a = 2
    while True:
        if pow(a, n - 1, n) == 1 and all(pow(a, (n - 1) // r, n) != 1 for r in primes):
            break
        a += 1
    return {"n": str(n), "a": a, "factors": [[str(r), int(e)] for r, e in fac],
            "sub": [pratt(r) for r in primes if r >= SMALL]}


out = {
    "N": pratt(N), "p": pratt(p), "263": pratt(263), "P114": pratt(P114),
    "card_factorization": [[str(r), int(e)] for r, e in factor(q + 1 - t)],
    "twist_card_factorization": [[str(r), int(e)] for r, e in factor(q + 1 + t)],
    "N_minus_1_factorization": [[str(r), int(e)] for r, e in factor(N - 1)],
    "N_plus_1_factorization": [[str(r), int(e)] for r, e in factor(N + 1)],
}
json.dump(out, open("/Volumes/SSD990/ecdlp-hardness-work/group-order/raw/pratt_certificates.json", "w"), indent=1)
print(json.dumps({k: out[k] for k in ("card_factorization", "twist_card_factorization", "N_minus_1_factorization")}))
