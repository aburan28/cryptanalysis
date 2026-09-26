"""Shared definitions for the F_(2^83) Koblitz-curve volcano study.

The curve is the repository's m=83 test instance of the ECC2K-130 client,
E0: y^2 + xy = x^3 + 1 over F_2[z]/(z^83 + z^7 + z^4 + z^2 + 1), with
#E0 = 4 * ELL (see ecc2k130/runner/generated/eccF83.h).  Field elements are
encoded as integers whose bit i is the coefficient of z^i.

Import from Sage (`sage -python` or a .sage driver).  Nothing here computes
a discrete logarithm.
"""
import ctypes
import json
import re
from pathlib import Path

from sage.all import GF, PolynomialRing, EllipticCurve, ZZ

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / 'outputs'
REPO = ROOT.parents[2]

M = 83
Q = 2 ** M
ELL = 2417851639230796216685689
N = 4 * ELL
TAU_A = -3249459927382          # tau^83 = TAU_A + TAU_B * tau in Z[tau], tau^2 + tau + 2 = 0
TAU_B = -347450761417
TRACE = 2 * TAU_A - TAU_B       # trace of q-Frobenius on E0
F1 = 6473                        # conductor prime nearest the crater
F2 = 53676929                    # second conductor prime
D_FLOOR = -7 * F1 ** 2           # discriminant of the conductor-6473 order
FLOOR_SIZE = F1 + 1              # h(O_6473): 6473 is inert in Q(sqrt(-7))
ORBIT = M                        # Frobenius orbit length of a strict descendant
N_ORBITS = FLOOR_SIZE // ORBIT   # 78
FROB_ON_F1 = TAU_A % F1          # pi acts on E0[6473] as this scalar (2514)

PR = PolynomialRing(GF(2), 'z')
_z = PR.gen()
MODULUS = _z ** 83 + _z ** 7 + _z ** 4 + _z ** 2 + 1
FIELD = GF(2 ** M, name='w', modulus=MODULUS)
W = FIELD.gen()


_CPU = None


def alarm(seconds):
    """CPU-time cap: raises cysignals' AlarmInterrupt after `seconds` of process CPU."""
    global _CPU
    if _CPU is None:
        _CPU = ctypes.CDLL(str(ROOT / 'native' / 'libcpualarm.dylib'))
        _CPU.cpu_alarm.argtypes = [ctypes.c_double]
    _CPU.cpu_alarm(float(seconds))


def cancel_alarm():
    if _CPU is not None:
        _CPU.cpu_alarm_cancel()


def enc(u):
    return int(u.to_integer())


def dec(u):
    return FIELD.from_integer(int(u))


def curve(b):
    """y^2 + xy = x^3 + b over FIELD; b may be an integer encoding."""
    if not hasattr(b, 'parent') or b.parent() is not FIELD:
        b = dec(b)
    return EllipticCurve(FIELD, [1, 0, 0, 0, b])


def point_key(p):
    return None if p.is_zero() else (enc(p[0]), enc(p[1]))


def _header_constants():
    text = (REPO / 'ecc2k130/runner/generated/eccF83.h').read_text()

    def limbs(name):
        body = re.search(r'%s\[3\] = \{([^}]*)\}' % name, text).group(1)
        words = [int(w.strip().rstrip('ul'), 16) for w in body.split(',') if w.strip()]
        return sum(w << (64 * i) for i, w in enumerate(words))

    table = re.search(r'GAMMA_TO_PB\[83\]\[3\] = \{(.*?)\n\};', text, re.S).group(1)
    rows = re.findall(r'\{([^}]*)\}', table)
    gamma = []
    for row in rows:
        words = [int(w.strip().rstrip('ul'), 16) for w in row.split(',') if w.strip()]
        gamma.append(sum(w << (64 * i) for i, w in enumerate(words)))
    assert len(gamma) == 83
    ell = int(re.search(r'ELL_DEC = "(\d+)"', text).group(1))
    assert ell == ELL
    return {name: limbs(name) for name in ('PX', 'PY', 'QX', 'QY')}, gamma


def onb_to_pb(v, gamma):
    out = 0
    for j in range(83):
        if (v >> j) & 1:
            out ^= gamma[j]
    return out


def public_points():
    """The header's primary P, Q (Q = [k]P with k never recorded)."""
    consts, gamma = _header_constants()
    E0 = curve(1)
    P = E0(dec(onb_to_pb(consts['PX'], gamma)), dec(onb_to_pb(consts['PY'], gamma)))
    Qp = E0(dec(onb_to_pb(consts['QX'], gamma)), dec(onb_to_pb(consts['QY'], gamma)))
    assert (ELL * P).is_zero() and (ELL * Qp).is_zero()
    assert not P.is_zero() and not Qp.is_zero()
    return P, Qp


def curve_id(orbit, shift):
    return 'O%02d-%02d' % (orbit, shift)


def load_inventory():
    """E0 plus all 6474 conductor-6473 floor curves, in a fixed order."""
    data = json.loads((OUT / 'inventory' / 'inventory.json').read_text())
    rows = [{'curve_id': 'E0', 'orbit': None, 'shift': 0, 'b': '1', 'j': '1', 'conductor': 1}]
    for orbit in data['orbits']:
        j = dec(orbit['j_canonical'])
        for shift in range(ORBIT):
            rows.append({'curve_id': curve_id(orbit['orbit'], shift), 'orbit': orbit['orbit'],
                         'shift': shift, 'b': str(enc(1 / j)), 'j': str(enc(j)),
                         'conductor': F1})
            j = j * j
        assert enc(j) == int(orbit['j_canonical'])
    assert len(rows) == FLOOR_SIZE + 1
    return rows
