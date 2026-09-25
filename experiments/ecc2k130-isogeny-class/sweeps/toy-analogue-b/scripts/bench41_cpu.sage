# CPU-time benchmark (sage cputime, this process only) of the transport building blocks over F_{2^8815}
# for the n=41 toy: one cofactor scalar multiplication (8794-bit scalar), 860 kernel additions, one Velu-sum
# evaluation at a point (860 terms: 3 mult + 1 sqr each, 1 inversion).  Output ../raw/bench41_cpu.json
import json, time
set_random_seed(7)
pari.allocatemem(2*10^9)
KBIG = 41*215; P = 1721
Lg = pari('ffgen(2^%d, \'b)' % KBIG); ONE = Lg^0; ZERO = 0*Lg
def lucas(m, t1, qq=2):
    a, b = 2, t1
    for i in range(m-1): a, b = b, t1*b - qq*a
    return b
cardL = 2^KBIG + 1 - lucas(KBIG, -1); v = valuation(cardL, P); cofL = cardL // P^v
E0L = pari.ellinit(pari([1, 0, 0, 0, 1])*ONE, Lg)
res = {}
R = pari.random(E0L)
c0 = cputime(); w0 = time.time(); Q = pari.ellmul(E0L, R, cofL); res['cofactor_scalar_mult_cpu'] = cputime(c0); res['cofactor_scalar_mult_wall'] = time.time()-w0
while True:
    Q2 = pari.ellmul(E0L, Q, P)
    if Q2 == pari([0]): break
    Q = Q2
K = Q
c0 = cputime(); w0 = time.time()
xs = []; T = K
for i in range((P-1)//2):
    xs.append(T[0]); T = pari.elladd(E0L, T, K)
res['kernel_860_additions_cpu'] = cputime(c0); res['kernel_860_additions_wall'] = time.time()-w0
x = pari.random(Lg)
c0 = cputime(); w0 = time.time()
num = ZERO; den = ONE
for xq in xs:
    d2 = (x + xq)^2
    num = num*d2 + xq*den; den = den*d2
X = x + x*num/den
res['velu_eval_one_point_cpu'] = cputime(c0); res['velu_eval_one_point_wall'] = time.time()-w0
u = pari.random(Lg); w = pari.random(Lg)
c0 = cputime()
for i in range(2000): z = u*w
res['one_mult_cpu_us'] = cputime(c0)/2000*1e6
c0 = cputime()
for i in range(200): z = 1/u
res['one_inv_cpu_us'] = cputime(c0)/200*1e6
res['log2_cofactor'] = float(RR(log(cofL, 2)))
json.dump({k: float(v) for k, v in res.items()}, open('/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/bench41_cpu.json', 'w'), indent=1)
print(res)
