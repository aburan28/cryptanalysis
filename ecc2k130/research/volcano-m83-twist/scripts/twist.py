"""Shared definitions for the volcano-m83 twist study (plain Python 3, no Sage).

The conductor-6473 floor of ../volcano-m83 is a set of j-invariants, the roots of
the ring class polynomial mod 2; it does not depend on the twist.  For every floor
j (b = 1/j) this study uses both
    a2 = 0:  y^2 + xy = x^3 + b,        #E = 4 * ELL            (81-bit prime)
    a2 = 1:  y^2 + xy = x^3 + x^2 + b,  #E = h1 * N53, h1 = 2 * 10459 * 53951 (53-bit prime)
over F_2[z]/(z^83 + z^7 + z^4 + z^2 + 1).  The a2 = 1 crater b = 1 is the N83
index-calculus instance EC1N83Ckb1a1 of the crypto repository.
"""
import hashlib, json, subprocess
from pathlib import Path
from gf2m import Field, koblitz_order

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / 'outputs'
PARENT = ROOT.parent / 'volcano-m83'
NATIVE = ROOT / 'native' / 'f83x'

MODULUS = (1 << 83) | (1 << 7) | (1 << 4) | (1 << 2) | 1
FIELD = Field(83, MODULUS)
ELL = 2417851639230796216685689
N53 = 8569786107849059
CURVES = {
    0: dict(name='a0_81bit', N=4 * ELL, n=ELL, h=4, factors='2^2'),
    1: dict(name='a1_53bit', N=1128547018 * N53, n=N53, h=1128547018, factors='2,10459,53951'),
}
assert koblitz_order(83, 0)[0] == CURVES[0]['N'] and koblitz_order(83, 1)[0] == CURVES[1]['N']
ORBIT = 83


def curve_id(orbit, shift):
    return 'O%02d-%02d' % (orbit, shift)


def load_inventory():
    """E0 plus all 6474 conductor-6473 floor curves, in ../volcano-m83's order (b = 1/j)."""
    data = json.loads((PARENT / 'outputs' / 'inventory' / 'inventory.json').read_text())
    assert data['field_modulus_nonzero_exponents'] == [0, 2, 4, 7, 83]
    rows = [{'curve_id': 'E0', 'b': 1}]
    for orbit in data['orbits']:
        j = int(orbit['j_canonical'])
        assert FIELD.inv(j) == int(orbit['b_canonical'])
        for shift in range(ORBIT):
            rows.append({'curve_id': curve_id(orbit['orbit'], shift), 'b': FIELD.inv(j)})
            j = FIELD.sqr(j)
        assert j == int(orbit['j_canonical'])
    assert len(rows) == 6475
    return rows


def polynomial_basis(k):
    return [1 << i for i in range(k)]


def power_basis(rho, k):
    out, v = [], 1
    for _ in range(k):
        out.append(v); v = FIELD.mul(v, rho)
    return out


def tags(a2, b, basis):
    c = CURVES[a2]
    args = [str(NATIVE), 'tags', str(a2), '%x' % b, str(c['N']), str(c['h']), c['factors'], str(len(basis))]
    args += ['%x' % v for v in basis]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError('f83x tags failed (%d): %s' % (r.returncode, r.stderr))
    lines = r.stdout.split('\n')
    head = lines[0].split()
    rows = [tuple(map(int, l.split())) for l in lines[1:] if l]
    assert int(head[1]) == len(rows)
    return rows, {'order_checks': int(head[3]), 'group_ops': int(head[5])}


def count(a2, tag_list):
    r = subprocess.run([str(NATIVE), 'count', str(CURVES[a2]['h'])], input='\n'.join(map(str, tag_list)),
                       capture_output=True, text=True, check=True)
    f = r.stdout.split()
    assert f[0] == 'eligible', r.stdout
    return int(f[1])


def sha_order(masks):
    """../volcano-m83 run06's equal-cardinality order: sorted by SHA-256(b'%d' % mask)."""
    return sorted(masks, key=lambda m: hashlib.sha256(b'%d' % m).digest())
