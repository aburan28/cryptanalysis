"""Markdown tables for report.md from results/summary.json and results/families.json.
usage: python3 make_tables.py > results/tables.md"""
import json, math

W = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-a'
S = json.load(open(f'{W}/results/summary.json'))
F = json.load(open(f'{W}/results/families.json'))
fams = [f for f in ('T11', 'T19', 'T23', 'T59', 'T109') if f in S]

print('### Families\n')
print('| family | E0 (a2) | n | l | N (bits) | #E0 | f | lambda = t/2 mod l, ord | Velu field | floor curves / orbits | checks |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for f in fams:
    x = F[f]
    print(f"| {f} | {x['a']} | {x['n']} | {x['l']} | {x['N']} ({x['log2N']}) | {x['card_fac']} | {x['f_fac']} | {x['lambda_mod_l']}, {x['ord_lambda']} | "
          f"F_(2^{x['n'] * x['velu_ext_degree']}) | {x['floor_curves']} / {x['n_orbits']} | {x['build_checks_ok']}/{x['build_checks']}"
          f"{', H_D mod 2 = Velu set' if x['HD_crosscheck'] else ''} |")

names = [('i_floor_neg', '(i) floor, neg'), ('ii_E0_negtau', '(ii) E0, neg+tau'), ('iii_transport_E0_negtau', '(iii) floor->E0, neg+tau'),
         ('iv_E0_neg', '(iv) E0, neg only'), ('v_E0_none', '(v) E0, no classes')]
print('\n### Mean birthday time (points generated up to the first repeated class) vs sqrt(pi N / (2c))\n')
print('| family | method | instances | mean | s.e. | theory | mean/theory | mean iterations (incl. DP overhead) |')
print('|---|---|---|---|---|---|---|---|')
for f in fams:
    s = S[f]
    for k, lab in names:
        if k not in s['groups_merge']:
            continue
        g, gi, th = s['groups_merge'][k], s['groups_iters'][k], s['theory'][k]
        print(f"| {f} | {lab} | {g['n']} | {g['mean']:.1f} | {g['sem']:.1f} | {th:.1f} | {g['mean'] / th:.3f} +- {1.96 * g['sem'] / th:.3f} | {gi['mean']:.1f} |")

print('\n### Ratios\n')
print('| family | n | (i)/(ii) | sqrt(n) | (i)/(ii) / sqrt(n) | (iii)/(ii) | (iv)/(i) | Kruskal p (floor curves + E0, neg) | Kruskal p (transported + E0, neg+tau) |')
print('|---|---|---|---|---|---|---|---|---|')
for f in fams:
    c = S[f]['comparisons']
    n = S[f]['meta']['n']
    r = c['i_over_ii_merge']
    print(f"| {f} | {n} | {r['ratio']:.3f} +- {1.96 * r['se']:.3f} | {math.sqrt(n):.3f} | {r['ratio'] / math.sqrt(n):.3f} | "
          f"{c['iii_over_ii_merge']['ratio']:.3f} +- {1.96 * c['iii_over_ii_merge']['se']:.3f} | {c['iv_over_i_merge']['ratio']:.3f} +- {1.96 * c['iv_over_i_merge']['se']:.3f} | "
          f"{c['kruskal_floor_neg_curves_and_E0_neg']['p']:.3f} | {c['kruskal_transport_curves_and_E0_negtau']['p']:.3f} |")

print('\n### Per curve (birthday time / theory; KS p of T^2/(2M) vs Exp(1))\n')
print('| family | curve | mode | instances | mean/theory | KS p | fruitless cycles | abandoned walks | all logs verified |')
print('|---|---|---|---|---|---|---|---|---|')
for f in fams:
    for cfg, v in S[f]['configs'].items():
        print(f"| {f} | {v['curve']} | {v['mode']} | {v['merge_steps']['n']} | {v['merge_over_theory']:.3f} | {v['ks_T2_over_2M_vs_Exp1']['p']:.3f} | "
              f"{v['fruitless_cycles_total']} | {v['abandoned_walks_total']} | {v['all_verified']} |")

print('\n### Transport (ascending l-isogeny floor -> E0)\n')
print('| family | curve | degree | Velu field | kernel terms / point | codomain j = 1 | floor l-torsion over Velu field is one line | transported logs preserved | Sage s / instance |')
print('|---|---|---|---|---|---|---|---|---|')
for f in fams:
    for lab, t in S[f]['transport'].items():
        print(f"| {f} | {lab} | {t['isogeny_degree']} | F_(2^{t['L_bits']}) | {t['kernel_points_used_per_eval']} | {t['codomain_j_is_1']} | {t['floor_l_torsion_cyclic']} | "
              f"{t['transported_log_preserved']}/{t['transported']} | {t['eval_s_per_instance_mean']:.3f} |")
