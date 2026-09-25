"""Shared constants/helpers for the rho-endomorphisms sweep (plain python3 OK)."""
import sys, json, math
sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k

N = ecc2k.N
q = ecc2k.q
t = ecc2k.t
f = ecc2k.f
p = ecc2k.p
LAM = ecc2k.TAU_EIGEN            # eigenvalue of tau (x->x^2) on E0's order-N subgroup
# N-1 factorization (computed by factor_nm1.py with Sage factor(proof=True); re-checked here)
NM1_FACT = [(2, 3), (3, 1), (11, 1), (109, 1), (131, 1), (263, 1), (32326729, 1),
            (21234899465981031419669, 1)]
_prod = 1
for _l, _e in NM1_FACT:
    _prod *= _l ** _e
assert _prod == N - 1, "N-1 factorization mismatch"

SQRTM7 = (2 * LAM + 1) % N        # image of sqrt(-7) := 2*tau+1
assert (SQRTM7 * SQRTM7 + 7) % N == 0
INV2 = pow(2, -1, N)
# O_K = Z[omega], omega = (1+sqrt(-7))/2 = tau + 1 ; norm form x^2 + x y + 2 y^2
W_OK = (LAM + 1) % N
C_OK = 2
# O_263 = Z + 263 O_K = Z[omega_263], omega_263 = (1+263 sqrt(-7))/2 = 263 tau + 132
W_O263 = (263 * LAM + 132) % N
C_O263 = (1 + 7 * 263 ** 2) // 4          # 121046
assert W_O263 == ((1 + 263 * SQRTM7) * INV2) % N
assert W_OK == ((1 + SQRTM7) * INV2) % N


def order_mod_N(e):
    """exact multiplicative order of e mod N (e != 0 mod N)"""
    e %= N
    assert e != 0
    o = N - 1
    for l, k in NM1_FACT:
        for _ in range(k):
            if pow(e, o // l, N) == 1:
                o //= l
            else:
                break
    return o


def rho_log2(class_size, n=N):
    """log2 of expected rho iterations sqrt(pi * n / (2 * class_size)) (random mapping on n/class_size classes)"""
    return 0.5 * (math.log2(math.pi) + math.log2(n) - 1 - math.log2(class_size))
