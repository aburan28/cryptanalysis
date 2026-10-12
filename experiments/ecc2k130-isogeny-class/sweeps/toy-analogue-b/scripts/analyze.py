#!/usr/bin/env python3
"""analyze.py -- statistics for the toy-b runs; writes ../summary.json and ../per_curve.json."""
import json, math, statistics as st

BASE = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/'
RAW = BASE + 'raw/'
gt = json.load(open(RAW + 'toy_ground_truth.json'))
m = gt['meta']; N = int(m['N']); n = int(m['n'])
R = {k: json.load(open(RAW + 'results_%s.jsonl' % k)) for k in ['i', 'ii', 'iip', 'iii']}
paired = json.load(open(RAW + 'results_timing_paired.jsonl'))

def work(r):            # all group operations of the walk, including cycle-escape traversals
    return r['iters'] + r['iters_escape']

def theory(classes, M, dpbits, r=32):
    base = math.sqrt(math.pi * classes / 2)
    return dict(sqrt_pi_S_over_2=base, with_r_adding=base / math.sqrt(1 - 1 / r),
                with_r_adding_and_dp_tail=base / math.sqrt(1 - 1 / r) + M * 2 ** dpbits)

def summ(recs, classes, M, dpbits, key_c='c_walk'):
    w = [work(r) for r in recs]
    th = theory(classes, M, dpbits)
    mean = st.mean(w); sd = st.pstdev(w); se = sd / math.sqrt(len(w))
    out = dict(count=len(recs), all_found=all(r['found'] for r in recs),
               all_verified_in_C=all(r.get('verified', r.get('verified_on_floor', 0)) for r in recs),
               all_match_planted=all(r['k_matches_planted'] for r in recs),
               work_mean=mean, work_median=st.median(w), work_sd=sd, work_se=se, log2_work_mean=math.log2(mean),
               theory=th, ratio_mean_to_sqrt_pi_S_over_2=mean / th['sqrt_pi_S_over_2'],
               ratio_se=se / th['sqrt_pi_S_over_2'],
               ratio_mean_to_full_theory=mean / th['with_r_adding_and_dp_tail'],
               cv_observed=sd / mean, cv_rayleigh=math.sqrt((4 - math.pi) / math.pi),
               escapes_mean=st.mean(r['escapes'] for r in recs), abandoned_total=sum(r['abandoned'] for r in recs))
    # Kolmogorov-Smirnov distance of the work distribution to a Rayleigh law: (a) scale fitted to the sample mean
    # (tests the shape only), (b) theoretical scale sigma^2 = |S|/(1-1/r) (no DP tail) -- descriptive only
    ws = sorted(w); nn = len(ws)
    def ks(sig):
        D = 0.0
        for i, x in enumerate(ws):
            Fx = 1 - math.exp(-x * x / (2 * sig * sig)); D = max(D, abs(Fx - i / nn), abs(Fx - (i + 1) / nn))
        return D
    out.update(ks_rayleigh_fitted_scale=ks(mean / math.sqrt(math.pi / 2)), ks_rayleigh_theory_scale=ks(math.sqrt(classes / (1 - 1 / 32))),
               ks_crit_5pct=1.358 / math.sqrt(nn),
               work_excluding_cycle_handling_mean=st.mean(r['iters'] - r['escapes'] for r in recs),
               ratio_excl_cycle_handling_to_full_theory=st.mean(r['iters'] - r['escapes'] for r in recs) / th['with_r_adding_and_dp_tail'])
    if key_c in recs[0]:
        c = [r[key_c] for r in recs]
        out.update(cpu_walk_mean_s=st.mean(c), cpu_walk_median_s=st.median(c),
                   cpu_ns_per_iteration=1e9 * sum(c) / sum(w))
    return out

S_neg = (N - 1) / 2; S_tau = (N - 1) / (2 * n)
summary = dict(meta=dict(n=n, N=N, log2N=math.log2(N), l=m['l'], P=m['P'], kP=m['kP'], s=m['tau_eigen_s']))
summary['i_floor_neg'] = summ(R['i'], S_neg, 16, 8)
summary['ii_E0_tau_neg'] = summ(R['ii'], S_tau, 8, 5)
summary['iip_E0_neg_only'] = summ(R['iip'], S_neg, 16, 8)
iii = R['iii']
summary['iii_transport_then_E0_tau_neg'] = summ(iii, S_tau, 8, 5, key_c='c_rho_walk')
summary['iii_checks'] = dict(
    kernel_deg_179=all(r['kernel_deg'] == 179 for r in iii), kernel_order_ok=all(r['kernel_order_ok'] for r in iii),
    codomain_is_E0=all(r['codomain_is_E0'] for r in iii), images_on_E0=all(r['images_on_E0'] for r in iii),
    image_order_N=all(r['image_order_N'] for r in iii), ytrace_ok=all(r['ytrace_ok'] for r in iii),
    verified_on_floor=all(r['verified_on_floor'] for r in iii), rho_verified_on_E0=all(r['rho_verified_on_E0'] for r in iii),
    sign_plus=sum(r['sign'] == 1 for r in iii), sign_minus=sum(r['sign'] == -1 for r in iii))
def med(xs): return st.median(xs)
tk = [r['c_kernel'] for r in iii]; te = [r['c_eval'] for r in iii]; ts = [r['c_signfix'] for r in iii]
tr = [r['c_rho_setup'] + r['c_rho_walk'] for r in iii]
ti = [r['c_setup'] + r['c_walk'] for r in R['i']]
tii = [r['c_setup'] + r['c_walk'] for r in R['ii']]
summary['transport_cost_cpu_seconds'] = dict(
    kernel_one_time_per_curve_median=med(tk), kernel_mean=st.mean(tk),
    eval_two_points_median=med(te), signfix_median=med(ts),
    E0_rho_after_transport_median=med(tr), floor_rho_median=med(ti), E0_rho_direct_median=med(tii),
    ratio_kernel_to_E0rho=med(tk) / med(tr), ratio_kernel_to_floor_rho=med(tk) / med(ti),
    ratio_eval_to_E0rho=med(te) / med(tr), ratio_total_iii_to_i=(med(tk) + med(te) + med(ts) + med(tr)) / med(ti))
# paired run (same process, interleaved): per instance ratios
pi_ = {r['id']: r for r in paired if r['cmd'] == 'R'}; pt_ = {r['id']: r for r in paired if r['cmd'] == 'T'}
rat_total, rat_kernel, rat_eval, wall_total = [], [], [], []
for iid in pi_:
    a = pi_[iid]; b = pt_[iid]
    ci = a['c_setup'] + a['c_walk']; ciii = b['c_kernel'] + b['c_eval'] + b['c_signfix'] + b['c_rho_setup'] + b['c_rho_walk']
    rat_total.append(ciii / ci); rat_kernel.append(b['c_kernel'] / (b['c_rho_setup'] + b['c_rho_walk']))
    rat_eval.append(b['c_eval'] / (b['c_rho_setup'] + b['c_rho_walk']))
    wall_total.append(b['t_total'] / (a['t_setup'] + a['t_walk']))
summary['paired_timing'] = dict(pairs=len(rat_total), all_match_planted=all(r['k_matches_planted'] for r in paired),
    median_cpu_ratio_iii_over_i=med(rat_total), median_wall_ratio_iii_over_i=med(wall_total),
    median_kernel_over_E0rho=med(rat_kernel), median_eval_over_E0rho=med(rat_eval))
wi = summary['i_floor_neg']['work_mean']; wii = summary['ii_E0_tau_neg']['work_mean']; wiii = summary['iii_transport_then_E0_tau_neg']['work_mean']
wiip = summary['iip_E0_neg_only']['work_mean']
summary['speedups'] = dict(iterations_i_over_ii=wi / wii, iterations_i_over_iii=wi / wiii, iterations_iip_over_ii=wiip / wii,
                           predicted_sqrt_n=math.sqrt(n), log2_gain_i_over_iii=math.log2(wi / wiii), predicted_log2=0.5 * math.log2(n),
                           cpu_i_over_ii=summary['i_floor_neg']['cpu_walk_mean_s'] / summary['ii_E0_tau_neg']['cpu_walk_mean_s'])
json.dump(summary, open(BASE + 'summary.json', 'w'), indent=1)

# per-curve file keyed by toy labels (A000..A178, B000..B178) + E0
byc = {}
for c in gt['curves']:
    byc[c['label']] = dict(orbit=c['orbit'], frob_index=c['frob_index'], level=359, j_int=c['j_int'], b_int=c['b_int'], a2=c['a2'],
                           order_pari=c['order_pari'], order_point_proof=c['order_point_proof'], twist_order_pari=c['twist_order_pari'],
                           twist_sylow359_cyclic=c['twist_sylow359_cyclic'], ascending_codomain_is_E0_sage=c['ascending_codomain_is_E0'],
                           instances=[])
for r in R['i']:
    lab, idx = r['id'].rsplit('_', 1)
    byc[lab]['instances'].append(dict(idx=int(idx), planted_k=r['planted_k'], i_k=r['k'], i_ok=r['k_matches_planted'], i_work=work(r), i_cpu=r['c_setup'] + r['c_walk']))
for r in iii:
    lab, idx = r['id'].rsplit('_', 1)
    d = [x for x in byc[lab]['instances'] if x['idx'] == int(idx)][0]
    d.update(iii_k=r['k'], iii_ok=r['k_matches_planted'] and r['verified_on_floor'] == 1, iii_work=work(r), iii_sign=r['sign'],
             iii_kernel_cpu=r['c_kernel'], iii_eval_cpu=r['c_eval'], iii_rho_cpu=r['c_rho_setup'] + r['c_rho_walk'],
             iii_codomain_is_E0_C=r['codomain_is_E0'])
for lab, d in byc.items():
    d['all_instances_ok'] = all(x.get('i_ok') and x.get('iii_ok') for x in d['instances']) and len(d['instances']) == 3
byc['E0'] = dict(level=1, j_int='1', b_int='1', a2=1, order=m['card'], tau_eigen_s=m['tau_eigen_s'],
                 instances_ii=len(R['ii']), ii_all_ok=all(r['k_matches_planted'] for r in R['ii']),
                 instances_iip=len(R['iip']), iip_all_ok=all(r['k_matches_planted'] for r in R['iip']))
# keys are TOY labels (prefix 'toy179:'), NOT the ECC2K-130 ground-truth labels: per-curve data of the toy do not apply
# to the ECC2K-130 curves individually (the toy mirrors their structure: 2 Frobenius orbits x n on the l = 2n+1 floor).
byc = {'toy179:' + k: v for k, v in byc.items()}
byc['_note'] = ('toy-analogue-b per-curve data. Keys are toy labels over F_{2^179} (A000..A178, B000..B178 = the 358 floor curves '
                'of the 359-volcano, same labelling rule as the ECC2K-130 ground truth; E0 = Koblitz y^2+xy=x^3+x^2+1). '
                'They are NOT ECC2K-130 curves.')
json.dump(byc, open(BASE + 'per_curve.json', 'w'), indent=0)
print(json.dumps(summary, indent=1))
print('curves with all instances ok:', sum(1 for k, d in byc.items() if k.startswith('toy179:') and k != 'toy179:E0' and d['all_instances_ok']), '/ 358')
