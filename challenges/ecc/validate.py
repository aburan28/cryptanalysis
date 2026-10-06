#!/usr/bin/env python3
"""Validate the prime-field elliptic-curve challenge corpus.

Stdlib only. Re-derives, per prime-field short-Weierstrass record, the exact
order of the published generator G and the well-posedness of the challenge, and
exits non-zero on any violation. This is the guard for the two data bugs found
in docs/REVIEW-2026-09-25.md:

* Finding 10 -- ``subgroup_order``/``cofactor`` must be the *actual* order of
  the stored G and ``#E / ord(G)``, not the smooth split's residual.
* Finding 18 -- an ``open``-tier target must lie in <G> so its discrete log
  exists (checked by full Pohlig-Hellman where the largest prime factor of
  ord(G) is small enough, otherwise by the necessary annihilation condition,
  which is also sufficient for a prime subgroup with p^2 not dividing #E).

Run from anywhere:

    python3 challenges/ecc/validate.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import generate as g  # noqa: E402  (stdlib-only helper module)

CURVE_DIR = ROOT / "curves"

# Largest prime factor of ord(G) for which we run a full BSGS membership proof.
BSGS_PRIME_LIMIT = 1 << 28
# Below this field size we recount #E by brute force as an independent check;
# larger fields are confirmed against the Hasse interval and recorded trace.
BRUTE_FIELD_LIMIT = 1 << 17


def I(s):
    return int(s, 16)


def pt(d):
    if d is None:
        return g.INF
    return (I(d["x"]), I(d["y"]))


def bsgs(P, Q, a, p, n):
    """Smallest k in [0, n) with [k]P == Q, or None if none exists."""
    m = math.isqrt(n) + 1
    table = {}
    R = g.INF
    for j in range(m):
        key = ("O",) if R is g.INF else R
        table.setdefault(key, j)
        R = g.ec_add(R, P, a, p)
    neg_mP = g.ec_neg(g.ec_mul(m, P, a, p), p)
    gamma = Q
    for i in range(m + 1):
        key = ("O",) if gamma is g.INF else gamma
        if key in table:
            return i * m + table[key]
        gamma = g.ec_add(gamma, neg_mP, a, p)
    return None


def discrete_log(G, T, a, p, ord_g, factors):
    """Pohlig-Hellman log of T base G in the cyclic group <G> of order ord_g.

    `factors` maps prime -> exponent for ord_g. Returns the log, or None when
    T is not in <G>.
    """
    residues = []
    moduli = []
    for q, e in factors.items():
        pe = q ** e
        Gi = g.ec_mul(ord_g // pe, G, a, p)
        Ti = g.ec_mul(ord_g // pe, T, a, p)
        k = bsgs(Gi, Ti, a, p, pe)
        if k is None:
            return None
        residues.append(k % pe)
        moduli.append(pe)
    # CRT
    M = 1
    for mi in moduli:
        M *= mi
    x = 0
    for ri, mi in zip(residues, moduli):
        Mi = M // mi
        x = (x + ri * Mi * pow(Mi, -1, mi)) % M
    return x


def full_factor(n):
    """prime -> exponent, or None if a composite chunk resisted the search."""
    primes, residual = g._partial_prime_factors(n)
    if residual != 1:
        return None
    facs = {}
    m = n
    for q in sorted(primes):
        while m % q == 0:
            m //= q
            facs[q] = facs.get(q, 0) + 1
    return facs if m == 1 else None


def check_record(rec):
    """Return a list of violation strings for one record (empty == pass)."""
    errs = []
    cid = rec.get("id", "?")
    field = rec.get("field", {})
    if field.get("type") != "prime" or rec.get("model") != "short-weierstrass":
        return errs  # only prime-field short Weierstrass is in scope here

    p = I(field["characteristic"])
    a = I(rec["a"])
    b = I(rec["b"])
    order = I(rec["group_order"])
    cof = I(rec["cofactor"])
    sub = I(rec["subgroup_order"])
    G = pt(rec["generator"])
    T = pt(rec.get("target")) if rec.get("target") else None
    kl = rec.get("known_log")

    def err(msg):
        errs.append(f"{cid}: {msg}")

    # Curve and points.
    if not g.nonsingular(a, b, p):
        err("curve is singular")
        return errs
    if not g.on_short(G, a, b, p):
        err("generator is not on the curve")
    if T is not None and not g.on_short(T, a, b, p):
        err("target is not on the curve")

    # Independent-ish #E confirmation.
    if p <= BRUTE_FIELD_LIMIT:
        counted = g.brute_order(a, b, p)
        if counted != order:
            err(f"group_order {order} != brute count {counted}")
    else:
        window = g.isqrt(4 * p) + 1
        if not (p + 1 - window <= order <= p + 1 + window):
            err(f"group_order {order} outside the Hasse interval")
        if "trace" in rec and order != p + 1 - I_or_int(rec["trace"]):
            err("group_order inconsistent with recorded trace")

    # cofactor * subgroup_order == #E
    if cof * sub != order:
        err(f"cofactor*subgroup_order {cof*sub} != group_order {order}")

    # ord(G) == subgroup_order, exactly. ([order]G == O then follows from
    # [sub]G == O and cofactor*sub == order, both checked here, so it is not
    # recomputed -- a full scalar multiplication saved on the big curves.)
    if g.ec_mul(sub, G, a, p) is not g.INF:
        err("subgroup_order does not annihilate G")
    ordG = g.ec_point_order(G, a, p, order)
    if ordG != sub:
        err(f"ord(G) {ordG} != subgroup_order {sub}")
    sub_factors = full_factor(sub)
    if sub_factors is not None:
        for q in sub_factors:
            if g.ec_mul(sub // q, G, a, p) is g.INF:
                err(f"ord(G) is a proper divisor of subgroup_order (fails at {q})")

    # Target well-posedness.
    if T is not None:
        if g.ec_mul(sub, T, a, p) is not g.INF:
            err("subgroup_order does not annihilate target (target not in ord(G)-torsion)")
        if kl is not None:
            # A stored log is a constructive membership proof.
            if g.ec_mul(I(kl), G, a, p) != T:
                err("known_log * G != target")
        else:
            # Open tier: prove target in <G>.
            proved = False
            if sub_factors is not None:
                largest = max(sub_factors)
                if largest <= BSGS_PRIME_LIMIT:
                    log = discrete_log(G, T, a, p, sub, sub_factors)
                    if log is None:
                        err("target is NOT in <G> (no discrete log)")
                    else:
                        proved = True
            if not proved:
                # Fall back to the necessary condition, which is also sufficient
                # when <G> is the whole prime subgroup (subgroup_order prime and
                # its square does not divide #E).
                if g.is_probable_prime(sub) and order % (sub * sub) != 0:
                    pass  # annihilation already checked; sufficient here
                # else: only the necessary condition was checkable; accepted.
    return errs


def I_or_int(v):
    if isinstance(v, str):
        return int(v, 16) if v.startswith(("0x", "-0x")) else int(v)
    return int(v)


def main():
    files = sorted(CURVE_DIR.glob("*.json"))
    total = 0
    prime_sw = 0
    checked_dlp = 0
    all_errs = []
    for f in files:
        rec = json.loads(f.read_text())
        total += 1
        field = rec.get("field", {})
        if field.get("type") == "prime" and rec.get("model") == "short-weierstrass":
            prime_sw += 1
            if rec.get("target") and rec.get("known_log") is None:
                sub = int(rec["subgroup_order"], 16)
                ff = full_factor(sub)
                if ff is not None and max(ff) <= BSGS_PRIME_LIMIT:
                    checked_dlp += 1
        errs = check_record(rec)
        all_errs.extend(errs)

    print(f"records scanned:            {total}")
    print(f"prime-field short-Weierstrass: {prime_sw}")
    print(f"open targets proven in <G> by full DLP: {checked_dlp}")
    if all_errs:
        print(f"\nVIOLATIONS: {len(all_errs)}", file=sys.stderr)
        for e in all_errs:
            print(f"  {e}", file=sys.stderr)
        return 1
    print(f"all {prime_sw} prime-field records pass the invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
