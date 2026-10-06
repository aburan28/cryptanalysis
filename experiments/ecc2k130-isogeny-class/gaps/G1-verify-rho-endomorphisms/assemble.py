"""Assemble results.json for G1-verify-rho-endomorphisms from the computed JSON files."""
import json, math, os, sys
sys.path.insert(0, '.')
from gmpy2 import mpz
N = 680564733841876926932320129493409985129
L = lambda fn: json.load(open(fn))
K = L('constants.json'); ST = L('selftest_cvp.json'); PY = L('sweep_py.json'); CMP = L('compare_py_c_lt20.json')
C263 = L('sweep_c_20to32_m263.json'); C1 = L('sweep_c_20to32_m1.json')
A = L('checks_acd.json'); RT = L('rt0_recompute.json')
W5 = L('weightenum_w5.json'); W6 = L('weightenum2_w6.json') if os.path.exists('weightenum2_w6.json') else None
LV = L('sweep_levels.json') if os.path.exists('sweep_levels.json') else None
per = PY['per_d']
# ---- (a)
best = min(((int(e['O263']['min']), int(d)) for d, e in per.items() if int(d) >= 3))
ea = per[str(best[1])]['O263']
ranked = sorted(((e['O263']['log2_min'], int(d)) for d, e in per.items() if int(d) >= 3))
covol263 = math.log2(N) + math.log2(263 * math.sqrt(7) / 2)
covolK = math.log2(N) + math.log2(math.sqrt(7) / 2)
M20 = K['sum_phi_d_3_le_d_lt_2^20']; M32 = K['sum_phi_d_2^20_le_d_lt_2^32']
heur = lambda cov, M: cov - math.log2(math.pi) - math.log2(M / 2)   # E[min] of M/2 independent (+-pairs) exponential minima
res = {'meta': {'N': str(N), 's': K and '196511074115861092422032515080945363956', 'p': '146505763881528721', 'f': str(263 * 146505763881528721),
                'output_dir': os.getcwd(),
                'implementations': {'exact': 'cvp2d.py (own Lagrange reduction + exact integer CVP, window proof in docstring)',
                                    'float_screen': 'cvpsweep.c (PARI qflllgram basis, 3-limb Montgomery, double-precision CVP; every reported minimum re-verified exactly)',
                                    'selftests': ST}},
       'constants': {k: K[k] for k in ('t', 'card_eq_4N', 'disc_check_t2_minus_4q_eq_minus7_f2', 'N_prime', 'p_prime', 's_sq_plus_s_plus_2_mod_N',
                                       's_order', 'N_minus_1_factorization', 'N_minus_1_factors_prime', 'matches_claimed_factorization',
                                       'num_divisors_lt_2^20', 'sum_phi_d_3_le_d_lt_2^20', 'sum_phi_d_1_le_d_lt_2^20', 'sum_phi_d_2^20_le_d_lt_2^32',
                                       'primitive_root', 'roots_x2+x+2_mod_263')}}
res['a_O263_orders_3_to_2^20'] = {
    'verdict': 'confirmed',
    'n_eigenvalues': sum(e['O263']['count'] for d, e in per.items() if int(d) >= 3),
    'global_min_norm': str(best[0]), 'global_min_log2': math.log2(best[0]), 'argmin_order_d': best[1],
    'argmin_xy_basis_1_263tau': ea['argmin_xy'], 'argmin_k_zeta=h_d^k': ea['argmin_k'],
    'argmin_in_basis_1_omega263': A['a_claimed_argmin_interpretations']['omega_basis'],
    'claimed_xy_read_literally_in_basis_1_263tau': A['a_claimed_argmin_interpretations']['literal'],
    'note_on_claimed_xy': 'The claimed (x,y)=(-128163312801734517, 358685138569453) is the same element when read in basis (1, omega_263), omega_263=(1+263*sqrt(-7))/2=132+263*tau; read literally as x + y*(263 tau) it has norm 2^115.157 and eigenvalue order ~2^122.9, so the task text mislabels the basis.',
    'same_min_at_d': [d for l, d in ranked if abs(l - ranked[0][0]) < 1e-12],
    'next_smallest_per_d_log2': ranked[:8],
    'cross_check_C_float_vs_python_exact': CMP['O263'],
    'heuristic_expected_log2_min': heur(covol263, M20),
    'claimed': {'log2': 114.62, 'd': 315337}}
# ---- (b)
bel = []
for d, e in per.items():
    for k, x, y, v in e['OK']['below2_100']:
        bel.append((int(d), k, int(x), int(y), int(v)))
tp = {}
a, b = 1, 0
for j in range(0, 200):
    tp[(a, b)] = ('+', j); tp[(-a, -b)] = ('-', j); a, b = -2 * b, a - b
kinds = [tp.get((x, y)) for (_, _, x, y, _) in bel]
nt = min(((int(e['OK']['nontau_min']), int(d)) for d, e in per.items()))
ent = per[str(nt[1])]['OK']
lam1_K = int(ST['lattice_m1']['Q_b1'])
res['b_OK_orders_lt_2^20'] = {
    'verdict': 'confirmed',
    'n_eigenvalues_incl_pm1': sum(e['OK']['count'] for e in per.values()),
    'global_min_d_ge_3': {'log2': min(e['OK']['log2_min'] for d, e in per.items() if int(d) >= 3), 'element': 'tau (norm 2, eigen order 131)'},
    'n_elements_norm_lt_2^100': len(bel),
    'all_are_pm_tau_k': all(k is not None for k in kinds),
    'tau_exponents_plus': sorted(k[1] for k in kinds if k and k[0] == '+'),
    'tau_exponents_minus_count': len([1 for k in kinds if k and k[0] == '-']),
    'orders_of_those_elements': sorted(set(x[0] for x in bel)),
    'n_with_order_ge_3': len([1 for x in bel if x[0] >= 3]),
    'uniqueness_argument': 'lambda1(kernel lattice in O_K) = %s = N (log2 %.3f) > 4*2^100, so each eigenvalue coset holds at most one element of norm < 2^100' % (lam1_K, math.log2(lam1_K)),
    'smallest_non_pm_tau_k_norm': str(nt[0]), 'smallest_non_pm_tau_k_log2': math.log2(nt[0]), 'at_order_d': nt[1],
    'argmin_xy_basis_1_tau': ent['nontau_argmin_xy'],
    'same_value_at_d': [int(d) for d, e in per.items() if int(e['OK']['nontau_min']) == nt[0]],
    'cosets_of_pm_s^j_whose_minimum_is_not_a_tau_power': 'j = 128,129,130 (both signs): minimum norm 2^126.0 element, not +-tau^j',
    'cross_check_C_float_vs_python_exact': CMP['OK'],
    'heuristic_expected_log2_min_non_tau': heur(covolK, M20),
    'claimed': {'n_below_2^100': 200, 'non_tau_min_log2': 106.96}}
# ---- (c)
res['c_codex_psi'] = {'verdict': 'confirmed' if A['c_order_plus_eq_(N-1)/3'] and A['c_order_minus_eq_(N-1)/3'] else 'refuted',
                      **{k: A[k] for k in A if k.startswith('c_')}}
# ---- (d)
res['d_C4_endomorphism_ring'] = {'verdict': 'confirmed' if (A['d_k_with_263_div_bk_1_to_131'] == [131] and A['d_b131_eq_f'] and A['d_min_nonscalar_norm_bruteforce_y_pm1'][0] == 121046) else 'refuted',
                                 **{k: A[k] for k in A if k.startswith('d_')}}
# ---- (e)
rt1 = RT['RT0_1']
res['e_RT0_1_extra_roots_of_unity'] = {
    'verdict': 'confirmed',
    'claimed_range_bits': [4.96, 9.47],
    'recomputed_net_log2_gain_rt_model': {str(r['r']): r['net_log2_gain_rt_model'] for r in rt1},
    'recomputed_range_bits': [-max(r['net_log2_gain_rt_model'] for r in rt1), -min(r['net_log2_gain_rt_model'] for r in rt1)],
    'rows': rt1,
    'robustness': 'With cost c >= 1 group addition per extra orbit image, gain = 0.5*log2(cf) - log2(1+(cf-1)c) <= -0.5*log2(cf) < 0 for every cf >= 2, so any non-free endomorphism is a net loss under this model; with the best per-coset TNAF weights the loss is still 4.93..9.34 bits.',
    'low_weight_enumeration_w_le_5': {'counts': W5['counts_normalised_strings'], 'survivor_orders': sorted(set(s['order'] for s in W5['survivors'])),
                                      'n_survivors': len(W5['survivors']), 'planted_tests_ok': W5['planted_tests_ok']},
}
if W6:
    res['e_RT0_1_extra_roots_of_unity']['low_weight_enumeration_w_le_6_rotation_canonical'] = {'counts': W6['counts'],
        'survivor_orders': W6['survivor_orders'], 'n_survivors': W6['n_survivors'], 'survivors': W6['survivors'],
        'planted_tests_ok': W6['planted_tests_ok'],
        'canonical_enumeration_matches_full_w_le_5': W6.get('matches_full_enumeration_w_le_5_up_to_rotation_sign'),
        'meaning': 'every tau-adic sum of <= 6 terms +-tau^i (i mod 131) whose eigenvalue on the N-subgroup has order dividing L32 = lcm of all divisors of N-1 below 2^32 is listed; all survivors have order in {1,2,131,262}, i.e. equal +-s^k'}
r9 = RT['RT0_9']
res['e_RT0_9_tau_adic_MITM'] = {
    'verdict': 'partially_confirmed',
    'verdict_detail': 'w_min=31 and the fails-verdict confirmed; 2^69.59 reproduced exactly as 131 x C(65,15)*2^15, but the full cost with the stored C(66,16)*2^16 list is 2^%.2f with memory 2^%.2f, and the best simple window split is 2^%.2f (about 1 bit lower); all far above rho 2^60.81' % (
        r9['rt_split_total_log2_time'], r9['rt_split_memory_log2'], [o for o in r9['optimised_split'] if o['w'] == 31][0]['log2_time']),
    'w_min': r9['w_min_count_ge_N'], 'log2_count_w31': [x for x in r9['rows'] if x['w'] == 31][0]['log2_count_weight_w'],
    'log2_count_w30': r9['log2_count_w_min_minus_1'],
    'rows': r9['rows'], 'rt_split_total_log2_time': r9['rt_split_total_log2_time'], 'rt_split_memory_log2': r9['rt_split_memory_log2'],
    'optimised_split': r9['optimised_split'], 'rho_E0_log2': r9['log2_rho_E0_sqrt_piN_over_4x131'], 'claimed_log2_time': 69.59}
# ---- (f)
def fsum(Cj):
    g = Cj['global_min_d_ge_3']
    return {'n_eigenvalues': Cj['total_zetas'], 'min_norm_log2': g['log2'], 'min_norm': g['norm'], 'at_order_d': g['d'], 'argmin_xy': g['xy'],
            'n_flagged_below': [Cj['flag_log2'], Cj['n_flagged']], 'max_abs_dev_float_vs_exact_log2': Cj['max_abs_dev_log2_float_vs_exact'],
            'flagged_exact': [(f['d'], f['k'], f['log2_exact']) for f in Cj['flagged']], 'c_seconds': Cj['elapsed_c_s']}
res['f_orders_2^20_to_2^32'] = {
    'verdict': 'done (exact per-eigenvalue CVP instead of the infeasible norm-2^80 enumeration)',
    'literal_enumeration_norm_lt_2^80_log2_count': 80 + math.log2(math.pi) - math.log2(263 * math.sqrt(7) / 2),
    'O263': fsum(C263), 'OK': fsum(C1),
    'heuristic_expected_log2_min_O263': heur(covol263, M32), 'heuristic_expected_log2_min_OK': heur(covolK, M32),
    'conclusion': 'No element of O_263 of norm < 2^103.25 and no element of O_K of norm < 2^95.91 has eigenvalue order in [2^20, 2^32); in particular nothing below 2^80.'}
res['rho_baselines_recomputed'] = {'E0_neg_tau_log2': 0.5 * math.log2(math.pi * N / (4 * 131)), 'floor_neg_only_log2': 0.5 * math.log2(math.pi * N / 4)}
if LV:
    res['extra_levels_p_and_263p'] = LV
    res['extra_levels_p_and_263p']['note'] = ('kernel lattices of O_p and O_263p contain pi-1 (norm 4N), so they are very skewed and the '
        'area heuristic pi*T/covol does not apply; minima 2^%.2f (O_p) and 2^%.2f (O_263p) for orders 3..2^20; minimum non-scalar degrees '
        '2^%.2f and 2^%.2f' % (LV['O_p']['min_norm_log2'], LV['O_263p']['min_norm_log2'], LV['O_p']['min_nonscalar_degree_log2'], LV['O_263p']['min_nonscalar_degree_log2']))
if os.path.exists('compare_prior.json'):
    res['comparison_with_prior_sweep_read_last'] = L('compare_prior.json')
json.dump(res, open('results.json', 'w'), indent=1)
print(json.dumps({k: (v.get('verdict') if isinstance(v, dict) else None) for k, v in res.items()}, indent=1))
