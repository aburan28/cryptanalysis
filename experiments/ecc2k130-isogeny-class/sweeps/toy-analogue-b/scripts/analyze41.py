#!/usr/bin/env python3
"""analyze41.py -- solve the n=41 level-1721 instances with toyrho41 and compare transport cost with rho cost.

(i)   R mode 0 on the level-1721 curve itself (negation only)
(iii) R mode 1 on E0 after the Sage/PARI transport (images of G, H under the ascending 1721-isogeny)
(ii)  R mode 1 on E0 directly (60 instances, role A)
"""
import json, math, statistics as st, subprocess, glob, os

RAW = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/raw/'
BIN = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/scripts/toyrho41'
NBT = RAW + 'nb_tables41_A.txt'
roles = [r for r in 'ABC' if os.path.exists(RAW + 'bigfield41_%s.json' % r)]
data = {r: json.load(open(RAW + 'bigfield41_%s.json' % r)) for r in roles}
N = 549756390943; n = 41
lines, planted = [], {}
for r in roles:
    d = data[r]
    if not d.get('complete'):
        print('role', r, 'incomplete; using the instances saved so far:', len(d.get('instances', [])))
    s41 = None
    for x in d.get('instances', []):
        iid = '%s_%d' % (x['curve'], x['idx'])
        planted['L41i_' + iid] = (x['k'], 1); planted['L41iii_' + iid] = (x['k'], x['sign'])
    for x in d.get('instances_E0', []):
        planted['L41ii_E0_%d' % x['idx']] = (x['k'], 1)
    if os.path.exists(RAW + 'instances41_%s.txt' % r):
        lines += [l.strip() for l in open(RAW + 'instances41_%s.txt' % r) if l.strip()]
    else:   # rebuild lines from the checkpoint if the process did not finish
        s41 = 256851699273
        for x in d.get('instances', []):
            iid = '%s_%d' % (x['curve'], x['idx'])
            lines.append('R L41i_%s 0 0x0 %s %d %d %s %s %s %s 16 8 %d' % (iid, x['b'], N, s41, x['Gx'], x['Gy'], x['Hx'], x['Hy'], 1000 + len(iid) + x['idx']))
            lines.append('R L41iii_%s 1 0x0 0x1 %d %d %s %s %s %s 8 5 %d' % (iid, N, s41, x['tGx'], x['tGy'], x['tHx'], x['tHy'], 2000 + x['idx']))
p = subprocess.run([BIN, NBT], input='\n'.join(lines) + '\n', capture_output=True, text=True, timeout=2400)
recs = [json.loads(l) for l in p.stdout.splitlines() if l.startswith('{')]
for rr in recs:
    k, sg = planted[rr['id']]
    rr['planted_k'] = k; rr['sign'] = sg
    kk = rr['k']
    rr['ok'] = rr['found'] == 1 and rr['verified'] == 1 and (kk == k if sg == 1 else (N - kk) % N == k)
json.dump(recs, open(RAW + 'results41.jsonl', 'w'))
def grp(prefix): return [x for x in recs if x['id'].startswith(prefix)]
S_neg = (N - 1) / 2; S_tau = (N - 1) / (2 * n)
def summ(rs, S, M, dp):
    w = [x['iters'] + x['iters_escape'] for x in rs]; th = math.sqrt(math.pi * S / 2)
    c = [x['c_setup'] + x['c_walk'] for x in rs]
    return dict(count=len(rs), all_ok=all(x['ok'] for x in rs), work_mean=st.mean(w), ratio_to_sqrt_pi_S_over_2=st.mean(w) / th,
                ratio_se=st.pstdev(w) / math.sqrt(len(w)) / th, log2_work_mean=math.log2(st.mean(w)),
                cpu_mean_s=st.mean(c), cpu_median_s=st.median(c))
out = dict(i_level1721_neg=summ(grp('L41i_'), S_neg, 16, 8), iii_transport_then_E0_tau=summ(grp('L41iii_'), S_tau, 8, 5))
if grp('L41ii_'): out['ii_E0_tau'] = summ(grp('L41ii_'), S_tau, 8, 5)
# transport costs (Sage/PARI over F_{2^8815}); rho costs (C over F_{2^41})
tim = {r: data[r]['timings'] for r in roles}
asc = {}
for r in roles:
    t = tim[r]; nm = 'E1' + r
    if 'ascend_%s_find_order_1721_point' % nm in t:
        asc[r] = dict(find_point_s=t['ascend_%s_find_order_1721_point' % nm], additions_860_s=t['ascend_%s_860_additions' % nm],
                      descend_total_s=t.get('descend_total_find_point_plus_velu'),
                      eval_two_points_median_s=(st.median([x['t_eval_two_points'] for x in data[r].get('instances', [])]) if data[r].get('instances') else None),
                      log2_cofactor_scalar=t.get('log2_cofactor_scalar'))
out['transport_wall_seconds_sage_pari'] = asc
ci = out['i_level1721_neg']['cpu_median_s']; ciii = out['iii_transport_then_E0_tau']['cpu_median_s']
one_time = st.median([a['find_point_s'] + a['additions_860_s'] for a in asc.values()])
evals = st.median([a['eval_two_points_median_s'] for a in asc.values() if a['eval_two_points_median_s']])
out['comparison'] = dict(rho_level_curve_cpu_median_s=ci, rho_E0_after_transport_cpu_median_s=ciii,
                         transport_one_time_wall_median_s=one_time, transport_eval_two_points_wall_median_s=evals,
                         ratio_one_time_transport_to_rho_on_level_curve=one_time / ci,
                         ratio_per_instance_eval_to_rho_on_level_curve=evals / ci,
                         iterations_ratio_i_over_iii=out['i_level1721_neg']['work_mean'] / out['iii_transport_then_E0_tau']['work_mean'],
                         predicted_sqrt_n=math.sqrt(n),
                         note='transport timings are Sage/PARI wall-clock on a heavily loaded machine; rho timings are thread-CPU of the C code')
out['level_curves'] = {r: (data[r].get('level_curve_b') or (data[r].get('meta', {}).get('level_curves', {}).get('E1' + r, {}).get('b_int'))) for r in roles}
bench = RAW + 'bench41_cpu.json'
if os.path.exists(bench):
    b = json.load(open(bench)); out['transport_cpu_benchmark'] = b
    one_cpu = b['cofactor_scalar_mult_cpu'] + b['kernel_860_additions_cpu']; ev_cpu = 2 * b['velu_eval_one_point_cpu']
    out['comparison_cpu'] = dict(one_time_transport_cpu_s=one_cpu, eval_two_points_cpu_s=ev_cpu, ratio_one_time_to_rho_level_curve=one_cpu / ci, ratio_eval_to_rho_level_curve=ev_cpu / ci, ratio_one_time_to_rho_E0=one_cpu / ciii)
out['checks'] = {r: [(l['check'], l['ok']) for l in data[r]['log']] for r in roles}
json.dump(out, open('/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-b/summary41.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != 'checks'}, indent=1))
print('mismatches:', [x['id'] for x in recs if not x['ok']])
