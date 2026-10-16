#!/usr/bin/env python3
"""Independently replay the native tau formula on the secp256k1 generator."""

from hashlib import sha256
from pathlib import Path
import json
import tarfile

HERE = Path(__file__).resolve().parent
PROVENANCE = HERE / 'tau32cp5-native-provenance.tar.gz'
P = 2**256 - 2**32 - 977
N = int('fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141', 16)
BETA = int('7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee', 16)
LAMBDA = int('ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0', 16)
G = (int('79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798', 16),
     int('483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8', 16))
WINDOWS_SHA256 = '1e2a2637d8d1c82e7e1e210bfb35a093b57327d2f8effe9d2255109a81481a0f'
BINARY_SHA256 = '6feacb9f638885c18e4627c3119ec2090e9b81efb05167954981fc075a9b3626'
FRONT_SHA256 = '6cd0962b58b4673708af813a913474791400a7297142e4e5970e7af11faf0b34'


def add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a[0] == b[0] and (a[1] + b[1]) % P == 0:
        return None
    if a == b:
        slope = 3*a[0]*a[0] * pow(2*a[1], -1, P)
    else:
        slope = (b[1]-a[1]) * pow((b[0]-a[0]) % P, -1, P)
    slope %= P
    x = (slope*slope-a[0]-b[0]) % P
    return x, (slope*(a[0]-x)-a[1]) % P


def mul(k, a):
    result = None
    while k:
        if k & 1:
            result = add(result, a)
        a = add(a, a)
        k >>= 1
    return result


def native_tau_affine(a):
    x, y = a
    x3 = pow(x, 3, P)
    y2 = pow(y, 2, P)
    rx = (4*y2-3*x3) % P
    ry = ((3*x3-2*rx)*y) % P
    w = (x-BETA*x) % P
    assert w
    return rx*pow(w*w, -1, P) % P, ry*pow(w*w*w, -1, P) % P


def main():
    with tarfile.open(PROVENANCE, 'r:gz') as archive:
        stem = 'prime-j0-sparse-tau32-checkpoint5/'
        front = archive.extractfile(stem+'src/bin/eisenstein_fixed.rs').read()
        windows = archive.extractfile(stem+'src/bin/eisenstein_fixed/unit_orbit_windows.rs').read()
        binary = archive.extractfile(stem+'target/release/eisenstein_fixed').read()
    assert sha256(front).hexdigest() == FRONT_SHA256
    assert sha256(windows).hexdigest() == WINDOWS_SHA256
    assert sha256(binary).hexdigest() == BINARY_SHA256
    assert f'b"{BETA:064x}"'.encode() in front
    source = windows.decode()
    start = source.index('fn tau(self) -> Self {')
    end = source.index('\n    fn double(self)', start)
    tau_source = source[start:end]
    for exact in ('let rx = u256_sub(four_y2, three_x3);',
                  'let ry = u256_mul(inner, self.y);',
                  'let w = u256_sub(self.x, u256_mul(self.x, U256_BETA_UNITS[1]));',
                  'let rzz = u256_mul(w2, self.zz);',
                  'let rzzz = u256_mul(w3, self.zzz);'):
        assert exact in tau_source
    assert (G[1]*G[1]-G[0]**3-7) % P == 0
    assert BETA != 1 and (BETA*BETA+BETA+1) % P == 0
    assert (LAMBDA*LAMBDA-3*LAMBDA+3) % N == 0
    assert mul(N, G) is None
    omega = (BETA*G[0] % P, G[1])
    tau_by_addition = add(G, (omega[0], -omega[1] % P))
    tau_by_formula = native_tau_affine(G)
    tau_by_scalar = mul(LAMBDA, G)
    assert tau_by_addition == tau_by_formula == tau_by_scalar
    receipt = {'schema':1,'provenance_sha256':sha256(PROVENANCE.read_bytes()).hexdigest(),
               'front_sha256':FRONT_SHA256,'windows_sha256':WINDOWS_SHA256,
               'binary_sha256':BINARY_SHA256,
               'tau_source_sha256':sha256(tau_source.encode()).hexdigest(),
               'generator_order_check':True,'beta_root_check':True,
               'lambda_root_check':True,'native_formula_equals_g_minus_omega_g':True,
               'native_formula_equals_lambda_g':True,
               'tau_generator_hex':[f'{v:064x}' for v in tau_by_formula]}
    (HERE/'secp256k1-tau-generator-check.json').write_text(
        json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'ok':True,'tau_source_sha256':receipt['tau_source_sha256']},sort_keys=True))


if __name__ == '__main__':
    main()
