# Pairing / transfer sweep, parts (1)-(3): embedding degrees, anomalous checks, twist.
# Run:  export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp
#       sage -python embedding_degrees.py
# Writes embedding_degrees.json (global facts) next to this script.
import json, sys, time, math
from pathlib import Path
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k
from sage.all import (Integer, factor, is_prime, pari, Mod, Zmod, gcd, kronecker, log)

HERE = Path(__file__).resolve().parent
out = {"script": "embedding_degrees.py", "checks": {}}
T0 = time.time()

q = Integer(ecc2k.q); t = Integer(ecc2k.t); N = Integer(ecc2k.N)
CARD = Integer(ecc2k.CARD); TW = Integer(ecc2k.TWIST_CARD)
assert q == 2**131 and CARD == q + 1 - t == 4 * N and TW == q + 1 + t


def bits(n):
    return float(log(Integer(n), 2).n(60))


def order_from_factorization(g, n, fac):
    """multiplicative order of g mod prime n given the factorization of n-1 (list of (p,e))."""
    k = n - 1
    for (r, e) in fac:
        for _ in range(e):
            if pow(g, k // r, n) == 1:
                k //= r
            else:
                break
    # verify minimality
    assert pow(g, k, n) == 1
    for (r, e) in factor(k):
        assert pow(g, k // r, n) != 1
    return k


def pure_python_order(g, n, fac):
    """independent cross-check in plain Python ints (no Sage arithmetic)."""
    g = int(g); n = int(n)
    k = n - 1
    for (r, e) in fac:
        r = int(r)
        for _ in range(int(e)):
            if pow(g, k // r, n) == 1:
                k //= r
            else:
                break
    assert pow(g, k, n) == 1
    return k


def mr_is_probable_prime(n, rounds=64):
    """plain-Python Miller-Rabin with fixed bases (independent of PARI)."""
    n = int(n)
    if n < 2:
        return False
    small = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
    for s in small:
        if n % s == 0:
            return n == s
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2; s += 1
    import random
    rng = random.Random(12345)
    bases = small + [rng.randrange(2, n - 1) for _ in range(rounds)]
    for a in bases:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def full_record(n, name):
    """factor n-1, certify factors, compute ord_n(q) and ord_n(2) (two ways)."""
    n = Integer(n)
    assert Integer(n).is_prime(proof=True), name
    t1 = time.time()
    fac = list(factor(n - 1))
    tf = time.time() - t1
    prod = 1
    for (r, e) in fac:
        prod *= r**e
        assert Integer(r).is_prime(proof=True), (name, r)          # Sage/PARI proven primality
        assert mr_is_probable_prime(r), (name, r)          # independent plain-Python MR
    assert prod == n - 1
    # PARI factorisation as a second, independent factorisation call
    pf = pari(n - 1).factor()
    pari_fac = [(Integer(pf[0][i]), Integer(pf[1][i])) for i in range(len(pf[0]))]
    assert sorted(pari_fac) == sorted(fac), name
    k_q = order_from_factorization(q % n, n, fac)
    k_2 = order_from_factorization(Integer(2), n, fac)
    # cross-checks: PARI znorder, Sage Mod().multiplicative_order(), plain python
    k_q_pari = Integer(pari(f"znorder(Mod(2,{n})^131)"))
    k_2_pari = Integer(pari(f"znorder(Mod(2,{n}))"))
    k_q_sage = Mod(q, n).multiplicative_order()
    k_q_py = pure_python_order(q % n, n, fac)
    k_2_py = pure_python_order(2, n, fac)
    assert k_q == k_q_pari == k_q_sage == k_q_py, name
    assert k_2 == k_2_pari == k_2_py, name
    # relation ord_n(2^131) = ord_n(2)/gcd(ord_n(2),131)
    assert k_q == k_2 // gcd(k_2, 131)
    rec = {
        "n": str(n), "n_bits_log2": round(bits(n), 4),
        "n_minus_1_factorization": [[str(r), int(e)] for (r, e) in fac],
        "n_minus_1_factor_bits": [round(bits(r), 3) for (r, e) in fac],
        "factorization_time_s": round(tf, 3),
        "embedding_degree_k_ord_n_q": str(k_q),
        "k_log2": round(bits(k_q), 4),
        "k_bit_length": int(k_q.nbits()),
        "k_equals_n_minus_1": bool(k_q == n - 1),
        "index_(n-1)/k": str((n - 1) // k_q),
        "ord_n_2": str(k_2),
        "ord_n_2_bit_length": int(k_2.nbits()),
        "131_divides_ord_n_2": bool(k_2 % 131 == 0),
        "minimal_embedding_field": f"F_(2^{k_2}) (contains mu_n; Hitt's minimal embedding field)",
        "ord_n_q2 (embedding degree over F_(q^2))": str(Mod(q * q, n).multiplicative_order()),
        "small_k_scan": None,
    }
    # direct scan: q^i != 1 mod n for i = 1..10^6 (sanity, redundant with exact k)
    x = Integer(1); qq = q % n; hit = None
    for i in range(1, 10**6 + 1):
        x = (x * qq) % n
        if x == 1:
            hit = i; break
    rec["small_k_scan"] = {"range": "1..1000000", "first_i_with_q^i=1_mod_n": hit}
    assert hit is None or Integer(hit) == k_q
    return rec


# ---------------- (1) N ----------------
out["N"] = full_record(N, "N")
kN = Integer(out["N"]["embedding_degree_k_ord_n_q"])
print("N-1 =", out["N"]["n_minus_1_factorization"])
print("k = ord_N(q) =", kN, " bits", kN.nbits(), " log2 %.3f" % bits(kN))
print("ord_N(2) =", out["N"]["ord_n_2"])

# ---------------- (2) anomalous / SSSA / supersingular ----------------
chk = out["checks"]
chk["char"] = 2
chk["N_odd"] = bool(N % 2 == 1)
chk["N_ne_char"] = bool(N != 2)
chk["gcd_N_q"] = str(gcd(N, q))
chk["#E_ne_q (not anomalous over F_q)"] = bool(CARD != q)
chk["t_ne_1"] = bool(t != 1)
chk["t_mod_2"] = int(t % 2)
chk["ordinary (t odd <=> not supersingular in char 2)"] = bool(t % 2 == 1)
chk["N_does_not_divide_q-1"] = bool((q - 1) % N != 0)
chk["N_does_not_divide_q+1"] = bool((q + 1) % N != 0)
chk["2-part of #E"] = str(CARD // (CARD.prime_to_m_part(2)))
chk["gcd_N_twist_card"] = str(gcd(N, TW))
chk["gcd_N_263"] = str(gcd(N, 263))
chk["N_squared_divides_#E(F_q^2)"] = bool(((q + 1)**2 - t**2) % (N**2) == 0)
# supersingular curves over F_(2^m) have embedding degree <= 4 (MOV); ordinary here.
for lab in ecc2k.LABELS:
    assert int(ecc2k.RECORDS[lab]["j_int"]) != 0      # j != 0 <=> ordinary in char 2
chk["all_263_j_nonzero"] = True

# ---------------- (3) twist ----------------
twf = list(factor(TW))
chk["twist_card"] = str(TW)
chk["twist_factorization"] = [[str(r), int(e)] for (r, e) in twf]
assert TW == 2 * 263**2 * Integer("19678316408850118605767852657510239")
out["twist_factors"] = {}
for (r, e) in twf:
    rec = {"prime": str(r), "exponent": int(e), "log2": round(bits(r), 3)}
    if r == 2:
        rec["note"] = "char-2 torsion: mu_2 = {1} in characteristic 2, Weil/Tate pairings on 2-power torsion are trivial"
        rec["ord_r_q"] = None
    else:
        if r > 2**40:
            rec.update(full_record(r, f"twist prime {r}"))
        else:
            rec["ord_r_q"] = str(Mod(q, r).multiplicative_order())
            rec["ord_r_2"] = str(Mod(2, r).multiplicative_order())
            if e >= 2:
                rec["ord_r^e_q"] = str(Mod(q, r**e).multiplicative_order())
                rec["ord_r^e_2"] = str(Mod(2, r**e).multiplicative_order())
    out["twist_factors"][str(r)] = rec
    print("twist factor", r, "^", e, {k: v for k, v in rec.items() if k.startswith("ord") or k.startswith("embedding")})

# also the 263-part on the curve side over F_(q^2)
chk["v263(q-1)"] = int(Integer(q - 1).valuation(263))
chk["v263(q+1-t)"] = int(Integer(q + 1 - t).valuation(263))
chk["v263(q+1+t)"] = int(Integer(q + 1 + t).valuation(263))
chk["q mod 263"] = int(q % 263)
chk["q mod 263^2"] = int(q % 263**2)
chk["t mod 263"] = int(t % 263)
out["elapsed_s"] = round(time.time() - T0, 2)
(HERE / "embedding_degrees.json").write_text(json.dumps(out, indent=1))
print(json.dumps(chk, indent=1))
print("done in %.1fs" % (time.time() - T0))
