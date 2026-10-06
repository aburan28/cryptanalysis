import sys; sys.path.insert(0, '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-a/scripts')
from toylib import *
from sage.all import set_random_seed, randint
name = sys.argv[1]; mode = sys.argv[2]; cnt = int(sys.argv[3])
fb = family_basics(name)
K, tail = make_field(fb['n'])
E0 = EllipticCurve(K, [1, fb['a'], 0, 0, 1])
assert E0.cardinality() == fb['card']
set_random_seed(1)
G = fb['h'] * E0.random_point()
s = tau_eigen(E0, G, fb['N'], fb['t1'])
print(f"n {fb['n']}\ntail {tail:x}\na2 {fb['a']}\nb 1\nN {fb['N']}\ns {s}\nmode {mode}\nrbits 10\ndpbits {sys.argv[4]}\nmaxwalk 20\nseed 7")
for i in range(cnt):
    P = fb['h'] * E0.random_point()
    k = randint(1, fb['N'] - 1)
    Q = k * P
    print(f"inst q{i} {fe2int(P[0]):x} {fe2int(P[1]):x} {fe2int(Q[0]):x} {fe2int(Q[1]):x} {k}")
