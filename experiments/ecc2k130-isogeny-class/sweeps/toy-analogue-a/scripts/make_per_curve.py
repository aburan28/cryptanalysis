"""per_curve.json keyed by the 263 ground-truth labels (model prediction for the real curves,
supported by the toy measurements and by the real ascending-isogeny checks), and
toy_per_curve.json keyed by '<family>:<toy label>' with the measured toy data.

usage: python3 make_per_curve.py
"""
import json, math, os

WORK = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-a'
GT = json.load(open('/Volumes/SSD990/ecdlp-hardness-work/ground_truth/ground_truth.json'))
N = int(GT['meta']['N'])
n = 131
S = json.load(open(os.path.join(WORK, 'results', 'summary.json')))
rt_all_p = os.path.join(WORK, 'results', 'real_transport_all.json')
RT = json.load(open(rt_all_p)) if os.path.exists(rt_all_p) else {}


def lg(c):
    return math.log2(math.sqrt(math.pi * N / (2 * c)))


toy_ratio = {f: dict(n=S[f]['meta']['n'], i_over_ii=round(S[f]['comparisons']['i_over_ii_merge']['ratio'], 4),
                     i_over_ii_se=round(S[f]['comparisons']['i_over_ii_merge']['se'], 4),
                     sqrt_n=round(math.sqrt(S[f]['meta']['n']), 4),
                     iii_over_ii=round(S[f]['comparisons']['iii_over_ii_merge']['ratio'], 4),
                     iii_over_ii_se=round(S[f]['comparisons']['iii_over_ii_merge']['se'], 4))
             for f in S if 'i_over_ii_merge' in S[f]['comparisons']}
out = {}
for c in GT['curves']:
    lab = c['label']
    rec = dict(level=c['level'], orbit=c['orbit'])
    if lab == 'E0':
        rec.update(native_equivalence_class='{+-tau^i P}, size 2*131 = 262',
                   native_rho_log2_iters=round(lg(262), 3),
                   best_route='rho on E0 with negation + tau classes',
                   effective_log2_iters=round(lg(262), 3),
                   transport=None)
    else:
        rt = RT.get(lab)
        rec.update(native_equivalence_class='{+-P}, size 2 (no efficiently computable endomorphism besides +-1; x->x^2 maps to another curve of the orbit)',
                   native_rho_log2_iters=round(lg(2), 3),
                   best_route='ascending 263-isogeny to E0 (2 evaluations, 131 kernel terms each), then rho on E0 with negation + tau classes',
                   effective_log2_iters=round(lg(262), 3),
                   native_minus_effective_log2=round(lg(2) - lg(262), 3),
                   transport=(dict(checked_here=True, isogeny_degree=rt['isogeny_degree'], codomain_j_is_1=rt['codomain_j_is_1'],
                                   pi_acts_as_minus_1_on_kernel=rt['pi_acts_as_minus_1_on_kernel'], kernel_x_in_Fq=rt['kernel_x_in_Fq'],
                                   E_Fq2_263_torsion_is_one_line=rt['E_Fq2_263_torsion_is_one_line'],
                                   planted_relations_ok=f"{rt['planted_relations_transported_ok']}/{rt['of']}",
                                   sage_eval_s_per_instance=round(rt['eval_s_per_instance_mean'], 4))
                              if rt else dict(checked_here=False)))
    rec['basis'] = ('log2 of sqrt(pi*N/(2*class size)) with N from ground_truth.json; the formula, the sqrt(n) gap between '
                    'native floor rho and E0 rho, and the equality transport+E0 == E0 were measured on toy analogues '
                    '(see toy_per_curve.json and results/summary.json); the real-curve rho itself was not run')
    rec['toy_support'] = toy_ratio
    out[lab] = rec
json.dump(out, open(os.path.join(WORK, 'per_curve.json'), 'w'), indent=1)

toy = {}
for f, s in S.items():
    for cfg, v in s['configs'].items():
        curve, mode = cfg.split('__')
        key = f'{f}:{curve}'
        d = toy.setdefault(key, dict(family=f, n=s['meta']['n'], l=s['meta']['l'], N=s['meta']['N'], runs={}))
        d['runs'][mode] = dict(instances=v['merge_steps']['n'], all_logs_verified=v['all_verified'], class_size=v['class_size'],
                               mean_merge_steps=round(v['merge_steps']['mean'], 2), sem=round(v['merge_steps']['sem'], 2),
                               mean_iters=round(v['iters']['mean'], 2),
                               theory_sqrt_pi_N_over_2c=round(v['theory_sqrt_pi_M_over_2'], 2),
                               merge_over_theory=round(v['merge_over_theory'], 4),
                               ks_p_T2_over_2M_vs_Exp1=round(v['ks_T2_over_2M_vs_Exp1']['p'], 4))
        if curve in s['transport']:
            t = s['transport'][curve]
            d['ascending_isogeny'] = dict(degree=t['isogeny_degree'], codomain_j_is_1=t['codomain_j_is_1'],
                                          floor_l_torsion_one_line=t['floor_l_torsion_cyclic'],
                                          transported_log_preserved=f"{t['transported_log_preserved']}/{t['transported']}",
                                          kernel_points_per_eval=t['kernel_points_used_per_eval'], field_bits=t['L_bits'],
                                          sage_eval_s_per_instance=t['eval_s_per_instance_mean'])
json.dump(toy, open(os.path.join(WORK, 'toy_per_curve.json'), 'w'), indent=1)
print('per_curve.json', len(out), 'toy_per_curve.json', len(toy), 'real transport checked:', len(RT))
