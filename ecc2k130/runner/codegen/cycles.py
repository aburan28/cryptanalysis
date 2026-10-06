"""Fruitless cycles cannot happen to this iteration, and this proves it stays so.

A rho walk that exploits an automorphism group usually pays for it with fruitless
cycles.  The mechanism is specific: an iteration of the form

    f(R) = | R + P_{h(R)} |

picks a canonical representative with |.|, and a short cycle appears when the
representative's sign feeds back into h -- f maps R to a class, the class is
collapsed to a representative, and the representative walks back.  Handling that
costs cycle detection and escape, and getting it wrong silently loses walks.

This attack's iteration is not of that form:

    f(R) = sigma^j(R) + R,    j = 3 + ((HW(x_R) / 2) mod 8)

HW is taken on normal-basis coordinates, which sigma permutes and negation
leaves alone, so j is constant on the whole orbit {+/- sigma^a(R)}.  That makes f
equivariant --

    f(sigma^a(+/- R)) = sigma^a(+/- f(R))

-- so it descends to a genuine map on the quotient by <sigma, -1> and no
representative is ever computed inside the walk.  There is no |.| for a sign to
feed back through.  A representative is still needed to compare two endpoints,
but that happens once per distinguished point, on the host, where a wrong answer
is a missed collision rather than a lost walk.

What remains is an arithmetic coincidence rather than a mechanism.  On the
order-ell subgroup sigma acts as multiplication by lam, so a step multiplies by
(lam^j + 1) and a cycle of length k needs

    prod_{t=1..k} (lam^{j_t} + 1) == +/- lam^i   (mod ell)

for some i.  That is checkable, so this checks it -- for every curve the client
supports, over every multiset of step exponents up to a given length.  At m=131
there are 262 targets in a subgroup of about 2^129, so a hit would be a
coincidence of probability around 1e-32; a hit at a toy curve size means nothing
and the report says how many chance hits to expect.

It also checks the two degeneracies that would break the addition itself:
sigma^j(R) = R would make the step a doubling, and sigma^j(R) = -R would send it
to infinity.  Neither can happen, because both need lam^j = +/-1 while <lam> has
odd prime order m and j never reaches it.

    python3 cycles.py --max-length 8

No type hints, camelCase identifiers, no itertools (project convention).
"""

import argparse
import sys

from curves import curveOrder, isPrimeBig, sqrtMod

# j = 3 + ((HW / 2) mod 8), so the step exponent runs over exactly these.
STEP_EXPONENTS = tuple(range(3, 11))
CURVES = (23, 41, 83, 97, 131)


def multisets(items, k):
    """Every non-decreasing k-tuple from items.  Products commute, so a cycle is
    determined by which exponents it uses and how often, not by their order."""
    if k == 0:
        yield ()
        return
    for i in range(len(items)):
        for rest in multisets(items[i:], k - 1):
            yield (items[i],) + rest


def frobeniusScalar(m, ell):
    """lam with sigma(R) = [lam]R on the order-ell subgroup, or None.

    lam is a root of lam^2 + lam + 2 = 0 with lam^m = 1; both roots of the
    quadratic are tested and the one of order dividing m is the eigenvalue."""
    r = sqrtMod(-7 % ell, ell)
    if r is None:
        return None
    inv2 = pow(2, -1, ell)
    for cand in ((-1 + r) * inv2 % ell, (-1 - r) * inv2 % ell):
        if pow(cand, m, ell) == 1:
            return cand
    return None


def orbitTargets(lam, m, ell):
    """The 2m scalars that mean "same orbit": +/- lam^i."""
    out = {}
    for i in range(m):
        p = pow(lam, i, ell)
        out[p] = "+lam^%d" % i
        out[(-p) % ell] = "-lam^%d" % i
    return out


def degeneracies(lam, m, ell):
    """Step exponents for which the addition degenerates.

    sigma^j(R) = R makes the step a doubling; sigma^j(R) = -R sends it to
    infinity.  The first needs lam^j = 1, the second lam^j = -1, and -1 has
    order 2 while <lam> has odd order m, so neither should ever fire."""
    bad = []
    for j in STEP_EXPONENTS:
        p = pow(lam, j, ell)
        if p == 1:
            bad.append((j, "sigma^j is the identity: the step is a doubling"))
        if p == (-1) % ell:
            bad.append((j, "sigma^j(R) = -R: the step lands on infinity"))
    return bad


def countMultisets(n, k):
    """How many non-decreasing k-tuples from n items."""
    total = 1
    for i in range(k):
        total = total * (n + k - 1 - i) // (i + 1)
    return total


def searchCurve(m, maxLength):
    order = curveOrder(m)
    if order % 4 != 0:
        return None
    ell = order // 4
    if not isPrimeBig(ell):
        return None
    lam = frobeniusScalar(m, ell)
    if lam is None:
        return None
    step = {}
    for j in STEP_EXPONENTS:
        step[j] = (pow(lam, j, ell) + 1) % ell
    targets = orbitTargets(lam, m, ell)
    hits = []
    tried = 0
    for k in range(1, maxLength + 1):
        for combo in multisets(STEP_EXPONENTS, k):
            tried += 1
            p = 1
            for j in combo:
                p = p * step[j] % ell
            if p in targets:
                hits.append((k, combo, targets[p]))
    expected = tried * len(targets) / float(ell)
    return {"ell": ell, "lam": lam, "hits": hits, "tried": tried,
            "expected": expected, "degenerate": degeneracies(lam, m, ell)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-length", type=int, default=8,
                    help="longest cycle to rule out")
    ap.add_argument("--curves", default=",".join(str(m) for m in CURVES))
    args = ap.parse_args()

    failed = False
    print("no-fruitless-cycle check, steps j in %s, cycles up to length %d"
          % (list(STEP_EXPONENTS), args.max_length))
    for m in [int(x) for x in args.curves.split(",") if x]:
        got = searchCurve(m, args.max_length)
        if got is None:
            print("  m=%-4d skipped: not a Koblitz curve of order 4*prime" % m)
            continue
        for j, why in got["degenerate"]:
            print("  m=%-4d DEGENERATE at j=%d: %s" % (m, j, why))
            failed = True
        if not got["hits"]:
            print("  m=%-4d clean: %d multisets, none hit an orbit "
                  "(%.2g expected by chance)" % (m, got["tried"], got["expected"]))
            continue
        # A hit only means something if chance does not explain it.  At toy
        # sizes the subgroup is small enough that random products land on an
        # orbit scalar regularly, which says nothing about the real curve.
        coincidence = got["expected"] > 0.01
        label = "coincidence at this size" if coincidence else "REAL"
        print("  m=%-4d %d hit(s), %s (%.2g expected by chance): %s"
              % (m, len(got["hits"]), label, got["expected"], got["hits"][:2]))
        if not coincidence:
            failed = True

    if failed:
        print("\nA real hit means a walk can loop without reaching a "
              "distinguished point.  The step schedule has to change.")
        return 1
    print("\nNo cycle mechanism: the iteration is equivariant, so it needs no "
          "representative and has nothing for a sign to feed back through.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
