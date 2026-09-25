"""Loader for the ECC2K-130 isogeny-class ground truth (E0 + 262 conductor-263 floor curves).

Usage (under `sage -python`, or `sage` with sys.path including this dir):

    import sys; sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
    import ecc2k
    K, curves = ecc2k.load()          # K = GF(2^131) with modulus z^131+z^13+z^2+z+1
    E = curves["A090"]                # Sage EllipticCurve [1, a2, 0, 0, b]
    ecc2k.N, ecc2k.t, ecc2k.f, ecc2k.p, ecc2k.q, ecc2k.CARD

Module constants (N, t, f, p, q, CARD, MODULUS_INT, TAU_EIGEN, LABELS, RECORDS) are
plain Python ints / dicts and need no Sage; only load(), field(), enc(), dec() need Sage.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GROUND_TRUTH_PATH = HERE / "ground_truth.json"

_DATA = json.loads(GROUND_TRUTH_PATH.read_text())
META = _DATA["meta"]
RECORDS = {c["label"]: c for c in _DATA["curves"]}          # label -> json record
LABELS = [c["label"] for c in _DATA["curves"]]               # E0, A000..A130, B000..B130

MODULUS_INT = int(META["modulus_int"])
q = int(META["q"])
t = int(META["t"])
N = int(META["N"])
f = int(META["f"])
p = int(META["p"])
CARD = int(META["card"])
TWIST_CARD = int(META["twist_card"])
TAU_EIGEN = int(META["E0_tau_eigenvalue"])

# cheap self-consistency of the constants
assert MODULUS_INT == (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
assert q == 2**131 and CARD == q + 1 - t == 4 * N and TWIST_CARD == q + 1 + t
assert t * t - 4 * q == -7 * f * f and f == 263 * p
assert (TAU_EIGEN * TAU_EIGEN + TAU_EIGEN + 2) % N == 0
assert len(LABELS) == 263

_K = None


def field():
    """GF(2^131) with generator z and modulus z^131+z^13+z^2+z+1 (Sage)."""
    global _K
    if _K is None:
        from sage.all import GF, PolynomialRing
        z = PolynomialRing(GF(2), "z").gen()
        _K = GF(2**131, name="z", modulus=z**131 + z**13 + z**2 + z + 1)
    return _K


def dec(n):
    """integer bitmask (bit i = z^i) -> field element"""
    return field().from_integer(int(n))


def enc(u):
    """field element -> integer bitmask (bit i = z^i)"""
    return int(u.to_integer())


def curve(label):
    """Sage EllipticCurve y^2 + xy = x^3 + a2 x^2 + b for one label."""
    from sage.all import EllipticCurve
    r = RECORDS[label]
    return EllipticCurve(field(), [1, int(r["a2"]), 0, 0, dec(r["b_int"])])


def load(labels=None, check=False):
    """Return (K, curves) with curves a dict label -> Sage EllipticCurve [1,a2,0,0,b].

    labels: optional iterable restricting which curves to build.
    check:  if True, re-verify j-invariants and (cheaply) the group order by a
            random-point test [4]P != O, [N][4]P = O  (N > 4 sqrt(q), so #E = 4N).
    """
    K = field()
    wanted = LABELS if labels is None else list(labels)
    curves = {lab: curve(lab) for lab in wanted}
    if check:
        import random
        rng = random.Random(1)
        for lab, E in curves.items():
            assert enc(E.j_invariant()) == int(RECORDS[lab]["j_int"]), lab
            while True:
                pts = E.lift_x(dec(rng.getrandbits(131)), all=True)
                if pts and not (4 * pts[0]).is_zero():
                    break
            assert (N * (4 * pts[0])).is_zero(), lab
    return K, curves


def frobenius_next(label):
    """Label of the curve obtained by (x, y) -> (x^2, y^2): X_k -> X_{k+1 mod 131}."""
    if label == "E0":
        return "E0"
    return "%s%03d" % (label[0], (int(label[1:]) + 1) % 131)


if __name__ == "__main__":
    import time
    t0 = time.time()
    K, cs = load(check=True)
    print("loaded", len(cs), "curves; K =", K, "; checked in %.1fs" % (time.time() - t0))
    print("N =", N, " t =", t, " f =", f, " p =", p)
