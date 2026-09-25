# G1 step 0: re-derive the constants used by the rho-endomorphism audit (independent code).
from sage.all import ZZ, Integer, factor, is_prime, euler_phi, divisors, kronecker, GF, log
import json, sys, time
t0 = time.time()
q = Integer(2)**131
N = Integer(680564733841876926932320129493409985129)
s = Integer(196511074115861092422032515080945363956)
p = Integer(146505763881528721)
f = 263*p
out = {}
# trace via Lucas recurrence for tau^2+tau+2=0 : t_k = -t_{k-1} - 2 t_{k-2}, t_0=2, t_1=-1
tk = [Integer(2), Integer(-1)]
for k in range(2, 132):
    tk.append(-tk[-1] - 2*tk[-2])
t = tk[131]
out['t'] = str(t)
out['card_E0'] = str(q+1-t)
out['card_eq_4N'] = bool(q+1-t == 4*N)
out['disc_check_t2_minus_4q_eq_minus7_f2'] = bool(t**2 - 4*q == -7*f**2)
out['N_prime'] = bool(is_prime(N)); out['p_prime'] = bool(is_prime(p)); out['263_prime']=bool(is_prime(263))
out['s_sq_plus_s_plus_2_mod_N'] = str((s**2+s+2) % N)
F = GF(N)
S = F(s)
out['s_order'] = int(S.multiplicative_order())
fac = factor(N-1)
out['N_minus_1_factorization'] = [[str(pp), int(e)] for pp, e in fac]
out['N_minus_1_factors_prime'] = all(is_prime(pp) for pp, e in fac)
claimed = [(2,3),(3,1),(11,1),(109,1),(131,1),(263,1),(32326729,1),(21234899465981031419669,1)]
out['matches_claimed_factorization'] = sorted([(int(a),int(b)) for a,b in fac]) == sorted(claimed)
out['product_check'] = bool(prod_ := 1)
pr = Integer(1)
for a,b in claimed: pr *= Integer(a)**b
out['claimed_product_eq_N_minus_1'] = bool(pr == N-1)
# divisors of N-1 below 2^20 (and below 2^32 for part f)
divs = divisors(N-1)
d20 = [int(d) for d in divs if d < 2**20]
d20_ge3 = [d for d in d20 if d >= 3]
out['num_divisors_lt_2^20'] = len(d20)
out['divisors_lt_2^20'] = d20
out['sum_phi_d_3_le_d_lt_2^20'] = int(sum(euler_phi(d) for d in d20_ge3))
out['sum_phi_d_1_le_d_lt_2^20'] = int(sum(euler_phi(d) for d in d20))
d32 = [int(d) for d in divs if d < 2**32]
out['num_divisors_lt_2^32'] = len(d32)
out['sum_phi_d_lt_2^32'] = int(sum(euler_phi(d) for d in d32))
out['sum_phi_d_2^20_le_d_lt_2^32'] = int(sum(euler_phi(d) for d in d32 if d >= 2**20))
out['divisors_2^20_to_2^32'] = [d for d in d32 if d >= 2**20]
# a primitive root mod N
g = F.multiplicative_generator()
out['primitive_root'] = int(g)
# frobenius eigenvalue sanity: s^131 == 1
out['s^131_mod_N'] = int(S**131)
# tau-eigenvalue roots mod 263
R = GF(263)
out['roots_x2+x+2_mod_263'] = sorted(int(r) for r in R['x']('x^2+x+2').roots(multiplicities=False))
out['kronecker_-7_263'] = int(kronecker(-7,263))
out['log2_N'] = float(log(N,2))
out['elapsed_s'] = time.time()-t0
json.dump(out, open('constants.json','w'), indent=1)
for k,v in out.items():
    if k not in ('divisors_lt_2^20',): print(k, v)
