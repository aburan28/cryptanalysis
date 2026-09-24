# Reduced bases of the kernel lattices L_m = {(x,y): x + m*s*y = 0 mod N} from PARI qflllgram (independent of cvp2d.py).
from sage.all import pari, Integer, matrix, ZZ
import json
N = Integer(680564733841876926932320129493409985129)
s = Integer(196511074115861092422032515080945363956)
out = {}
for m in (1, 263):
    c = (m * s) % N
    M = matrix(ZZ, [[N, -c], [0, 1]])          # columns = basis vectors (x;y)
    A = matrix(ZZ, [[2, -m], [-m, 4 * m * m]])  # Gram of 2Q in (x,y)
    G = M.transpose() * A * M
    U = pari(G).qflllgram().sage()
    B = M * U
    b1 = (B[0, 0], B[1, 0]); b2 = (B[0, 1], B[1, 1])
    Q = lambda v: v[0]**2 - m*v[0]*v[1] + 2*m*m*v[1]**2
    bil2 = lambda u, v: 2*u[0]*v[0] - m*(u[0]*v[1] + u[1]*v[0]) + 4*m*m*u[1]*v[1]
    if Q(b1) > Q(b2):
        b1, b2 = b2, b1
    D = b1[0]*b2[1] - b2[0]*b1[1]
    assert abs(D) == N
    for v in (b1, b2):
        assert (v[0] + c*v[1]) % N == 0
    sg = 1 if D > 0 else -1
    A1 = (sg * b2[1]) % N      # frac(u1) = (z*A1 mod N)/N
    A2 = (-sg * b1[1]) % N     # frac(u2) = (z*A2 mod N)/N
    out[str(m)] = {'b1': [str(b1[0]), str(b1[1])], 'b2': [str(b2[0]), str(b2[1])], 'D': str(D),
                   'A1': str(A1), 'A2': str(A2), 'g11': str(Q(b1)), 'g22': str(Q(b2)), 'g12x2': str(bil2(b1, b2)),
                   'c': str(c)}
    print(m, out[str(m)])
json.dump(out, open('basis_pari.json', 'w'), indent=1)
