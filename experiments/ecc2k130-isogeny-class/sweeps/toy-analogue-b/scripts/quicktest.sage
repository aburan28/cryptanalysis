RZ.<Z> = GF(2)[]
K.<z> = GF(2^179, modulus=Z^179+Z^4+Z^2+Z+1)
set_random_seed(1)
E0 = EllipticCurve(K,[1,1,0,0,1]); N=60239283133; card=2*N*6360033939490742289168980201322563070730747
s=39413359998
for i in range(3):
    G=(card//N)*E0.random_point(); k=ZZ.random_element(1,N); H=k*G
    h=lambda u: hex(int(u.to_integer()))
    print('R t%d_m1 1 0x1 0x1 %d %d %s %s %s %s 8 5 %d' % (i,N,s,h(G[0]),h(G[1]),h(H[0]),h(H[1]),100+i))
    print('R t%d_m0 0 0x1 0x1 %d %d %s %s %s %s 16 8 %d' % (i,N,s,h(G[0]),h(G[1]),h(H[0]),h(H[1]),200+i))
    import sys; print('#k', k, file=sys.stderr)
