# Normal-basis conversion tables for F_{2^179} = F_2[z]/(z^179+z^4+z^2+z+1), used by toyrho.c for Frobenius canonical forms.
# Uses the type-II optimal normal basis element beta = gamma + 1/gamma (gamma a primitive 359th root of unity), which
# exists because 359 = 2*179+1 is prime and ord_359(2) = 179 (359 = 3 mod 4).  Any normal basis would do.
RZ.<Z> = GF(2)[]
K.<z> = GF(2^179, modulus=Z^179+Z^4+Z^2+Z+1)
n = 179
K2 = K.extension(2, 'w') if False else None
# beta is a root of the minimal polynomial of gamma+1/gamma; find it as a root in K of the degree-179 factor of
# the 359th cyclotomic polynomial "folded" by x -> x + 1/x.  Simpler: the minimal polynomial of zeta+1/zeta over Q is
# the real cyclotomic polynomial; reduce it mod 2 and take a root in K.
x = polygen(QQ)
Phi = cyclotomic_polynomial(359)
# real subfield polynomial: psi(x) with Phi(t) = t^179 * psi(t + 1/t)
R.<u> = QQ[]
# compute via resultant: psi(u) = Res_t(Phi(t), t^2 - u t + 1)^(1/2) -- easier: build numerically exact by recursion
# use PARI: polsubcyclo(359, 179) gives the degree-179 subfield polynomial (maximal real subfield, since [Q(zeta):Q]=358)
psi = R(pari('polsubcyclo(359,179)'))
KY.<Y> = K[]
rts = KY(psi.change_ring(GF(2))).roots(multiplicities=False)
beta = None
for r in rts:
    conj = [r]
    for i in range(1, n): conj.append(conj[-1]^2)
    M = matrix(GF(2), [[(int(c.to_integer()) >> bit) & 1 for bit in range(n)] for c in conj])
    if M.is_invertible():
        beta = r; break
assert beta is not None
Minv = M.inverse()
def rowint(r): return sum(int(r[i]) << i for i in range(n))
with open('/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/nb_tables.txt', 'w') as fo:
    for i in range(n): fo.write(hex(rowint(Minv.row(i))) + '\n')   # poly -> NB : image of z^i
    for i in range(n): fo.write(hex(rowint(M.row(i))) + '\n')      # NB -> poly : beta^(2^i)
print('beta =', hex(int(beta.to_integer())), ' is the root of polsubcyclo(359,179) mod 2; normal:', M.is_invertible())
