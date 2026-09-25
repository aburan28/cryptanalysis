"""Validate purebin.py (field, curve arithmetic, Mestre AGM) against brute-force counts on small
binary fields F_{2^d}, d prime in {5,7,11,13,17}.  Pure python3, no Sage/PARI."""
import json
import random
import sys
import time

sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/group-order")
from purebin import GF2m, Curve, agm_trace


def irreducible_prime_degree(d, taps):
    """For prime d: m = z^d + sum z^taps is irreducible iff z^(2^d) = z mod m and m has no root in F_2."""
    if len(taps) % 2 == 1 or 0 not in taps:  # need m(0)=1 and an odd number of terms (m(1)=1)
        return False
    F = GF2m.__new__(GF2m)
    F.d = d
    F.taps = tuple(sorted(taps, reverse=True))
    F.modulus = (1 << d) | sum(1 << i for i in taps)
    F.mask = (1 << d) - 1
    x = 2  # z
    for _ in range(d):
        x = GF2m.mul(F, x, x)
    return x == 2


def find_modulus(d):
    for a in range(1, d):
        if irreducible_prime_degree(d, (a, 0)):
            return (a, 0)
    for a in range(3, d):
        for b in range(2, a):
            for c in range(1, b):
                if irreducible_prime_degree(d, (a, b, c, 0)):
                    return (a, b, c, 0)


def main():
    rng = random.Random(20260923)
    out = {"irreducible_131": irreducible_prime_degree(131, (13, 2, 1, 0)), "cases": []}
    assert out["irreducible_131"]
    nfail = 0
    t0 = time.time()
    for d in (5, 7, 11, 13, 17):
        taps = find_modulus(d)
        F = GF2m(d, taps)
        q = 1 << d
        nb = 12 if d <= 13 else 5
        for _ in range(nb):
            b = F.rand(rng) or 1
            for a2 in (0, 1):
                E = Curve(F, a2, b)
                n = E.count_bruteforce()
                # random-point sanity: n * P = O
                for _ in range(3):
                    P = E.random_point(rng)
                    assert E.on_curve(P) and E.mul(n, P) is None
                t_bf = q + 1 - n
                rec = {"d": d, "taps": taps, "b": b, "a2": a2, "count_bf": n, "t_bf": t_bf}
                if a2 == 0:
                    t_agm, inZ2 = agm_trace(F, b, prec=40, guard=16)
                    rec.update(t_agm=t_agm, agm_in_Z2=inZ2, agm_ok=(t_agm == t_bf and inZ2))
                    nfail += not rec["agm_ok"]
                else:
                    rec["twist_rel_ok"] = (n == q + 1 + (q + 1 - out["cases"][-1]["count_bf"]))
                    nfail += not rec["twist_rel_ok"]
                    # 2-primary structure: a2=1, odd d => #E = 2 mod 4
                    rec["twist_2mod4"] = (n % 4 == 2)
                    nfail += not rec["twist_2mod4"]
                out["cases"].append(rec)
    out["n_cases"] = len(out["cases"])
    out["n_fail"] = nfail
    out["seconds"] = round(time.time() - t0, 1)
    json.dump(out, open("/Volumes/SSD990/ecdlp-hardness-work/group-order/test_small_fields.json", "w"), indent=1)
    print("cases", len(out["cases"]), "fail", nfail, "time", out["seconds"])
    for r in out["cases"][:6]:
        print(r)


if __name__ == "__main__":
    main()
