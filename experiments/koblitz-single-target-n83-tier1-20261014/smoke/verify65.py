"""Usage: python3 verify65.py <experiment dir> <smoke dir with base65.jsonl, logs65.json, logs65_bad.json>; n=65 a=0 K200 reduced-scale check of precompute.verify_table."""
import json, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[1] + "/crypto_source_snapshot/research/ic_candidate_tournament_20260915")
import oracle, precompute
SM = sys.argv[2]
h = json.loads(open(SM + "/base65.jsonl").readline())
r = int(h["subgroup_order"]); n = 65
t = -1
s0, s1 = 2, t
for _ in range(1, n): s0, s1 = s1, t * s1 - 2 * s0
order = (1 << n) + 1 - s1
def sqrt_mod(a, p):
    a %= p
    q, s = p - 1, 0
    while q % 2 == 0: q //= 2; s += 1
    z = 2
    while pow(z, (p - 1) // 2, p) != p - 1: z += 1
    m, c, tt, rr = s, pow(z, q, p), pow(a, q, p), pow(a, (q + 1) // 2, p)
    while tt != 1:
        i, t2 = 0, tt
        while t2 != 1: t2 = t2 * t2 % p; i += 1
        b = pow(c, 1 << (m - i - 1), p); m, c, tt, rr = i, b * b % p, tt * b * b % p, rr * b % p
    return rr
root = sqrt_mod(t * t - 8, r); inv2 = pow(2, -1, r)
gen = ["35333168140946998765", "23436638436063806286"]
for lam in ((t + root) * inv2 % r, (t - root) * inv2 % r):
    fx = {"degree": n, "curve_a": 0, "irreducible": {"degree": n, "low_terms": h["field_modulus_low_terms"]},
          "subgroup_order": str(r), "group_order": str(order), "cofactor": order // r, "generator": gen, "lambda": str(lam)}
    try:
        curve = oracle.Curve(fx); break
    except Exception as exc:
        continue
good = precompute.verify_table(SM + "/logs65.json", SM + "/base65.jsonl", None, curve)
bad = precompute.verify_table(SM + "/logs65_bad.json", SM + "/base65.jsonl", None, curve)
print(json.dumps({"good": good["status"], "good_checks": good["checks"], "bad": bad["status"], "bad_columns": bad["bad_columns"]}))
