#!/usr/bin/env python3
"""Check the exact lattice constants behind the four-corner coordinate envelope."""

import json

N = int('fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141', 16)
LAMBDA_TAU = int('ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0', 16)
U = (193508920647619669885755136084601127231,
     238911465918039986966665730306072050094)
V = (-U[1], 303414439467246543595250775667605759171)
W = (U[0] - 2*V[0], U[1] - 2*V[1])
LIMIT = 1 << 130


def norm(a, b):
    return a*a + 3*a*b + 3*b*b


def main():
    assert U[0]*V[1] - U[1]*V[0] == N
    assert W[0]*V[1] - W[1]*V[0] == N
    assert all((a + b*LAMBDA_TAU) % N == 0 for a,b in (U,V,W))
    assert norm(*W) == norm(*V) == norm(W[0]+V[0], W[1]+V[1]) == N
    coordinate_envelope = [abs(W[i])+abs(V[i]) for i in range(2)]
    assert max(coordinate_envelope) < LIMIT
    print(json.dumps({'scalar_order':N, 'w':W, 'v':V,
                      'coordinate_envelope':coordinate_envelope,
                      'coordinate_limit_exclusive':LIMIT}, sort_keys=True))


if __name__ == '__main__':
    main()
