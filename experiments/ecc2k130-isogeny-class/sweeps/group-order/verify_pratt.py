"""Pure-python verifier for raw/pratt_certificates.json (no Sage/PARI).
A Pratt node for n: n-1 = prod r^e (checked), a^(n-1) = 1 mod n, a^((n-1)/r) != 1 mod n for every r,
and every r >= 2^20 has its own node; r < 2^20 and 'small' nodes are proven by trial division."""
import json
import sys

C = json.load(open("/Volumes/SSD990/ecdlp-hardness-work/group-order/raw/pratt_certificates.json"))
SMALL = 2 ** 20


def trial_prime(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


def check(node, depth=0, log=None):
    n = int(node["n"])
    if node.get("small"):
        assert n < SMALL and trial_prime(n), n
        return True
    a = int(node["a"])
    fac = [(int(r), int(e)) for r, e in node["factors"]]
    prod = 1
    for r, e in fac:
        prod *= r ** e
    assert prod == n - 1, "factorization of n-1 wrong for %d" % n
    assert pow(a, n - 1, n) == 1, "Fermat fails %d" % n
    for r, e in fac:
        assert pow(a, (n - 1) // r, n) != 1, "a not primitive wrt %d for %d" % (r, n)
    subs = {int(s["n"]): s for s in node["sub"]}
    for r, e in fac:
        if r < SMALL:
            assert trial_prime(r), r
        else:
            assert r in subs, "missing sub-certificate for %d" % r
            check(subs[r], depth + 1, log)
    if log is not None:
        log.append((depth, n, a, len(fac)))
    return True


q = 2 ** 131
t = -22283658519494248867
ok = {}
for key in ("N", "p", "263", "P114"):
    log = []
    ok[key] = check(C[key], log=log)
    print(key, C[key]["n"], "PRIME (Pratt certificate verified, %d nodes)" % max(1, len(log)))
# factorizations of the orders: product check + every factor certified prime
certified = {int(C[k]["n"]) for k in ("N", "p", "263", "P114")} | {2}
for name, target in (("card_factorization", q + 1 - t), ("twist_card_factorization", q + 1 + t)):
    prod = 1
    for r, e in C[name]:
        prod *= int(r) ** e
        assert int(r) in certified, (name, r)
    assert prod == target, name
    print(name, " * ".join("%s^%d" % (r, e) if e > 1 else r for r, e in C[name]), "== ok, all factors certified")
print("ALL OK")
