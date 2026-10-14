#!/usr/bin/env python3
"""Fresh re-derivation of the numbers in papers/frobenius-orbits from raw artefacts.
Read-only on all repos. Prints one line per check: id | printed | recomputed | note."""
import json, glob, math, statistics as st, re, sys
import numpy as np

import os
CR = os.environ.get('CRYPTO_REPO', '../../../crypto')
CA = os.environ.get('CRYPTANALYSIS_REPO', '../../..')
RA = os.environ.get('AUTORESEARCHER_REPO', '../../../crypto-autoresearcher')
out = []
def rec(i, printed, got, note=''):
    out.append((i, printed, got, note)); print(f'{i} | printed={printed} | recomputed={got} | {note}')

# ---- closed forms ---------------------------------------------------------
for n in (19, 23, 37, 41, 53, 61, 83, 131):
    rec(f'floor sqrt(pi/(4n)) n={n}', '', f'{math.sqrt(math.pi/(4*n)):.4f}', f'2n={2*n}')
rec('floor n=61 (tier caption)', 0.1135, round(math.sqrt(math.pi/(2*122)), 4))
rec('floor n=41 (ledger)', 0.138, round(math.sqrt(math.pi/(2*82)), 4))
rec('2n at n=83', 166, 2*83)
rec('Pr[Z>=5] n=83', 0.73, round(1-math.exp(-83/2**6), 3))
rec('Pr[Z>=6] n=83', 0.48, round(1-math.exp(-83/2**7), 3))
rec('r n=19 = 523492/4', 130873, 523492//4)

# ---- canon cost table (examples/koblitz_fold_cost.rs table in RESEARCH_KOBLITZ_INDEX_CALCULUS.md) ----
txt = open(f'{CR}/research/notes/ecc2k130/RESEARCH_KOBLITZ_INDEX_CALCULUS.md').read()
m = re.search(r'\| squaring chain, serial \| ([\d.]+) \|\n\| squaring chain, 8 points in flight \| ([\d.]+) \|\n\| squaring by shifts[^|]*\| ([\d.]+) \|\n\| \*\*normal basis, one at a time\*\* \| \*\*([\d.]+)\*\* \|', txt)
s, l8, sh, nb = map(float, m.groups())
rec('tab canon serial ns', 846.8, s); rec('tab canon 8 lanes ns', 733.7, l8)
rec('tab canon shifts ns', 1299.3, sh); rec('tab canon NB ns', 85.5, nb)
rec('tab canon serial rel', 9.9, round(s/nb, 2)); rec('tab canon 8lane rel', 8.6, round(l8/nb, 2)); rec('tab canon shifts rel', 15.2, round(sh/nb, 2))
rec('50.8/682.6', 0.074, round(50.8/682.6, 4))
rec('398.52/29.20', 13.6, round(398.52/29.20, 2))
rec('6249999/152439', 41.0, round(6249999/152439, 2))
rec('16.9->0.24 + 2.7 vs 50.4->45.2 (as printed arms)', 45.2, round(50.4-(16.9-0.24)+2.7, 2), 'arms do not close')
rec('consistent alt: 58.8-(16.9-0.24)+2.7', 45.2, round(58.8-(16.9-0.24)+2.7, 2))
rec('consistent alt: 50.4-(8.45-0.24)+3.1 (round-2 FB column, rel 41.9->45.0)', 45.2, round(50.4-(8.45-0.24)+(45.0-41.9), 2))

# ---- zero-gap n=83 --------------------------------------------------------
zd = f'{CA}/experiments/koblitz-n83-index-design-20260929/packed_index_e1_canonical_20261009'
rows = {r['sequence_number']: r for r in json.load(open(f'{zd}/summary.json'))['paired_rows']}
order = [rows[i]['mode'] for i in range(1, 7)]
rec('zerogap run order', 'B,Z,Z,B,B,Z', ','.join('B' if m == 'packed_bucket22' else 'Z' for m in order))
rec('adjacent stage ratios', '1.074,1.156,1.118', ','.join(f"{a:.3f}" for a in (rows[1]['target_stage_ns']/rows[2]['target_stage_ns'], rows[4]['target_stage_ns']/rows[3]['target_stage_ns'], rows[5]['target_stage_ns']/rows[6]['target_stage_ns'])))
B = [1, 4, 5]; Z = [2, 3, 6]
med = lambda k, idx: st.median(rows[i][k] for i in idx)
for k, pb, pz in (('index_build_ns', 2.130, 1.980), ('target_cycle_canonical_ns', 2.216, 1.557), ('target_stage_ns', 7.204, 6.511)):
    rec(f'median {k} base/zero (s)', f'{pb}/{pz}', f'{med(k,B)/1e9:.3f}/{med(k,Z)/1e9:.3f}')
rec('canon phase ratio', 1.42, round(med('target_cycle_canonical_ns', B)/med('target_cycle_canonical_ns', Z), 3))
rec('rotations target base', 656000000, rows[1]['target_canonical_rotations']); rec('rotations target zero', 38261354, rows[2]['target_canonical_rotations'])
rec('rotations index base/zero', '328000000/19127078', f"{rows[1]['index_canonical_rotations']}/{rows[2]['index_canonical_rotations']}")
rec('8e6*82', 656000000, 8_000_000*82)
rec('38261354/8e6', 4.78, round(38261354/8e6, 3)); rec('656e6/38261354', 17.1, round(656e6/38261354, 2))
rec('comparisons', 9324648, rows[1]['target_lookup_comparisons_or_probes'])
rec('table bytes', 88777220, rows[1]['table_allocated_bytes']); rec('4e6*18+2^22*4+4', 88777220, 4_000_000*18+2**22*4+4)

# ---- packed index prefix / hashed / tag -----------------------------------
base = f'{CA}/experiments/koblitz-n83-index-design-20260929'
ps = json.load(open(f'{base}/packed_index_e1_prefix_20261007/summary.json'))['medians']
rec('hash table MiB', 192.0, ps['hash']['table_allocated_bytes']/2**20)
rec('prefix packed MiB', 76.7, round(ps['packed']['table_allocated_bytes']/2**20, 2))
rec('2.50x = hash/prefix-packed', 2.50, round(ps['hash']['table_allocated_bytes']/ps['packed']['table_allocated_bytes'], 3))
rec('sec-layout 2.50x = 192MiB / 88,777,220 B (as written in sec-layout)', 2.50, round(192*2**20/88777220, 3), 'MISMATCH')
rec('probe slowdown', 1.41, round(ps['packed']['target_stage_ns']/ps['hash']['target_stage_ns'], 3))
hp = json.load(open(f'{base}/packed_index_e1_hashed_prefix_20261008/summary.json'))
vals = sorted({r['target_lookup_comparisons_or_probes'] for r in hp['paired_rows']})
rec('raw/hashed prefix comparisons', '58251024/25265242', '/'.join(map(str, vals[::-1])))
tg = open(f'{base}/packed_index_e1_tag_20261009/README.md').read()
rec('tag comparisons / rejections', '9324648->4943112; 2912395', 'README: ' + ('4,943,112' in tg and '2,912,395' in tg and '9,324,648' in tg).__str__())
ts = json.load(open(f'{base}/packed_index_e1_tag_20261009/summary.json'))
tr = [r for r in ts['paired_rows'] if 'tag' in r['mode']][0]
rec('tag json comparisons', 4943112, tr['target_lookup_comparisons_or_probes'])
rec('58251024/4943112 (11.8x, two different E-1 directories)', 11.8, round(58251024/4943112, 2))
rec('30977592/186612', 166, 30977592/186612)
rec('186612*16 B', '2.99 MB', f'{186612*16/1e6:.2f} MB'); rec('30977592*16 B', '496 MB', f'{30977592*16/1e6:.1f} MB')

# ---- laned keys -----------------------------------------------------------
rec('Ir n=53', 1.205, round(13354911993/11082479113, 3)); rec('Ir n=61', 1.398, round(65219299765/46663161498, 3))
rec('586*74.4M / 65.2G', 0.668, round(586*74.4e6/65219299765, 3))
portable_tot = [1.092, 1.094, 1.178, 1.149, 1.277, 1.310]
rec('portable total range (n=41 is "not established")', '1.09-1.31', f'{min(portable_tot)}-{max(portable_tot)}', 'n=41 within A/A')

# ---- rho ladder (callgrind raw) -------------------------------------------
Ir = {'R0': 371102176689, 'R1': 281027207019, 'R2': 68926289783, 'R3': 46384789571}
IC = 89190346806
for r, p in zip(Ir, (0.240, 0.317, 1.294, 1.923)):
    rec(f'IC/rho {r}', p, round(IC/Ir[r], 3))
rec('R1/R2', 4.08, round(Ir['R1']/Ir['R2'], 3)); rec('R1/R3 (span of IC/rho 0.317->1.923)', '', round(Ir['R1']/Ir['R3'], 2))
rec('R0/R2', '', round(Ir['R0']/Ir['R2'], 2))
rec('50.82% is R0 (371B) share, not R1', 50.82, round(188577544163/371102176689*100, 2))
rec('R3 FastCanon share', 51.5, round(23873979090/46384789571*100, 2))
rec('steps R2/R0, R3/R0', '', f'{19247253/19103507:.4f}, {19569835/19103507:.4f}')
rec('3-sig: sum 281.0B->68.9B', '281.0->68.9', f'{Ir["R1"]/1e9:.1f}->{Ir["R2"]/1e9:.1f}')

# ---- compact-orbit strong rho (CPU) ---------------------------------------
man = json.load(open(f'{CR}/research/notes/ecc2k130/compact_orbit_strong_rho_20260929/evidence/strong_rho_cbda/MANIFEST.json'))['cases']
for cell, (a, b) in {'n37_L1024': (0.78, 2.08), 'n41_L1024': (0.39, 2.99), 'n53_L1024': (0.34, 3.09)}.items():
    p = man[cell]['paired_to_normal_rho']
    rec(f'strong-rho {cell} IC/normal (printed 2.08/2.99/3.09)', b, round(p['ic']['cpu_ratio_median'], 3))
    rec(f'strong-rho {cell} IC/v2 = (IC/normal)/(v2/normal)', a, round(p['ic']['cpu_ratio_median']/p['rho_v2']['cpu_ratio_median'], 3))
rec('n53 poly/normal paired', 2.80, round(man['n53_L1024']['paired_to_normal_rho']['rho_poly']['cpu_ratio_median'], 3))
rec('13.3444/4.7567', 2.80, round(13.3444/4.7567, 3))
rec('steps normal/poly n53', '+5%', f'{19776622/18843653-1:+.3%}'); rec('steps normal/v2 n53', '', f'{19776622/18465354-1:+.3%}')

# ---- cold panel disjoint v2 -----------------------------------------------
an = json.load(open(f'{CR}/research/notes/ecc2k130/disjoint_cold_v2_outcome_20261001/ANALYSIS.json'))['cells']
printed = {'n37_L1': (2.810, 2.718, 2.874, 64.4), 'n37_L1024': (3.031, 2.998, 3.047, 67.0), 'n41_L1': (13.378, 9.367, 18.491, 92.5),
           'n41_L1024': (1.314, 1.288, 1.359, 23.9), 'n53_L1': (22.675, 17.904, 31.595, 95.6), 'n53_L1024': (1.605, 1.566, 1.666, 37.7)}
for c, p in printed.items():
    a = an[c]; lo, hi = a['ic_over_rho_cpu']['interval_95pct']
    rec(f'cold {c}', p, (round(a['ic_over_rho_cpu']['median'], 3), round(lo, 3), round(hi, 3), round(100*a['required_complete_cpu_reduction_to_parity'], 1)), f"K={a['K']} prefilter={a['prefilter']}")
rec('cold: children / logs', '135 / 46170', f"{sum(a['children'] for a in an.values())} / {sum(a['verified_target_logs'] for a in an.values())}")
rec('1-1/ratio', '', [round(100*(1-1/p[0]), 1) for p in printed.values()])

# ---- tier crossover -------------------------------------------------------
T = json.load(open(f'{CR}/docs/ic/runs/koblitz-tier-crossover-20260921.json'))
paper_tier = {6832: (876342501, 926956220, 1104202174), 9760: (903649246, 880008741, 1009804178), 12688: (941440872, 887500874, 966559218), 18544: (1117432188, 1042518063, 982920004)}
orb = {6832: 56, 9760: 80, 12688: 104, 18544: 152}
sqrt_r = math.sqrt(162888033982417)
orho, ofl = [], []
for w in T['widths']:
    got = tuple(w['tiers'][t]['total_adds'] for t in ('full', 'compact', 'folded'))
    rec(f"tier points={w['points']} orbits={w['signed_orbits']}", paper_tier[w['points']], got, 'cheapest ' + w['cheapest'])
    for t in ('full', 'compact', 'folded'):
        orho.append(w['tiers'][t]['over_rho']); ofl.append(w['tiers'][t]['over_generic_floor'])
        S = w['tiers'][t]['total_adds']/32/sqrt_r
        assert abs(S-w['tiers'][t]['S_lower_bound']) < 5e-4, (S, w['tiers'][t]['S_lower_bound'])
rec('tier over_rho range (printed 12-13x)', '12-13', f'{min(orho)}-{max(orho)}')
rec('tier over_floor range (printed 19-21x)', '19-21', f'{min(ofl)}-{max(ofl)}')
rec('tier S = adds/32/sqrt(r) ties to S_lower_bound; rho S', 0.1774, round(2263934/sqrt_r, 4))
rec('120.85x stored pairs 12688 (full/folded)', 120.85, round(80499016/666120, 2))
rec('+% ops folded/full at 12688 in Table tier', 1.2, round((966559218/941440872-1)*100, 2), 'table tier gives +2.7%; the +1.2% is the earlier flip run (925,906,496 -> 936,803,908)')
rec('flip run +%', 1.2, round((936803908/925906496-1)*100, 2))
rec('-12% at 18544', 12, round((1-982920004/1117432188)*100, 2))
rec('compact vs floor 18.9x', 18.9, 'flip-run compact 18.9; Table tier compact@12688 = %s; full@6832 = %s' % (T['widths'][2]['tiers']['compact']['over_generic_floor'], T['widths'][0]['tiers']['full']['over_generic_floor']))
rec('crossovers', '13623 / pred 13600', f"{T['crossovers']['full_over_folded']['points']} / {T['pre_registered_prediction']['value_points']}")

# ---- fold at equal memory (orbit-fold json) -------------------------------
O = json.load(open(f'{CR}/docs/ic/runs/koblitz-orbit-fold-20260913.json'))['measured']['measured']
want = {'compact_base': 16592, 'folded_base': 183488, 'compact_pairs': 137655528, 'folded_pairs': 138074720, 'probes_per_target_compact': 1183373, 'probes_per_target_folded': 9676,
        'ns_per_probe_compact': 108, 'ns_per_probe_folded': 331, 'hit_rate_compact': 0.0043, 'hit_rate_folded': 0.9974, 'recover_ms_compact': 1.18, 'recover_ms_folded': 0.026,
        'secs_per_decomposition_compact': 0.500, 'secs_per_decomposition_folded': 0.00255}
for k, v in want.items():
    rec(f'fold-equal {k}', v, O[k])
rec('base widening', 11.1, round(183488/16592, 2)); rec('probes ratio', 122, round(O['probes_per_target_compact']/O['probes_per_target_folded'], 1))
rec('net speedup', 196, round(O['net_speedup_at_equal_memory'], 1)); rec('secs ratio', '', round(O['secs_per_decomposition_compact']/O['secs_per_decomposition_folded'], 1))
rec('ns/probe ratio folded/compact (table) vs probe-shape 2.8x', 2.8, round(O['ns_per_probe_folded']/O['ns_per_probe_compact'], 2), 'different run/host')
of = json.load(open(f'{CR}/docs/ic/runs/koblitz-orbit-fold-20260913.json'))
sec = of['the_lever_is_connected_again']['what_was_measured']['secs_per_decomposition']
rec('widening speedups 1.93/2.04', '1.93/2.04', f'{sec[0]/sec[1]:.2f}/{sec[0]/sec[2]:.2f}', 'baseline 0.0027 is a different run (base 177632)')
rec('targets decomposed 22619', 22619, of['the_lever_is_connected_again']['second_run']['measured']['decomposed_folded'])
rec('21779 targets', 21779, 'not in orbit-fold json (only in leaderboard/ledger ic-boundary jsons - not checked as same run)')
rec('recovery 8.66->0.037 ms, 1.4%', '8.66->0.037', of['what_it_costs']['recovery'][:60])

# ---- probe shape -----------------------------------------------------------
P = json.load(open(f'{CR}/docs/ic/runs/koblitz-probe-shape-20260913.json'))
n = P['ns_a_probe']
rec('probe shape fold_costs', '2.8/2.0/1.51', f"{n['one_at_a_time']['fold_costs']}/{n['blocked_1024_prefetched']['fold_costs']}/{n['descent_loop_per_base_point']['fold_costs']}")
rec('blocking buys folded', 1.83, P['what_blocking_buys_each_table']['folded']['median'])
rec('222.5-148.4 (74 ns)', 74, round(n['descent_loop_per_base_point']['folded']['median']-n['descent_loop_per_base_point']['compact']['median'], 1))

# ---- n=61 whole pipeline (RESEARCH_KOBLITZ_INDEX_CALCULUS.md A/B) ----------
rec('collect 779.2/24.8', 31.4, round(779.2/24.8, 2)); rec('solve 162.2/2.5', 64.9, round(162.2/2.5, 2)); rec('descent .0381/.0100', 3.8, round(.0381/.0100, 2))
rec('n61 300,608-pt pipeline charged vs rho (same note)', '12-13 (paper)', '330.7x (note table, after); 326.0x elsewhere in note')

# ---- GFNI / funnel kernels ------------------------------------------------
rec('GFNI ns/key', '0.82-0.94', '0.82-0.94 (n=41,53,59,61,63)'); rec('tables ns/key', '2.9-4.3', '2.88-4.32')
rec('funnel ns/key (excl. 4.42 outlier at n=59)', '2.4-2.8', f"{min(2.73,2.38,2.52,2.45,2.65,2.72,2.83)}-{max(2.73,2.38,2.52,2.45,2.65,2.72,2.83)}")
rec('chained ns/key', '5.4-7.1', f"{min(5.43,7.05,5.75,5.87,7.11,6.12,6.12,6.58)}-{max(5.43,7.05,5.75,5.87,7.11,6.12,6.12,6.58)}")

# ---- n=19 volcano ---------------------------------------------------------
vr = f'{CA}/experiments/volcano-ic/results'
tau = [json.loads(l) for f in sorted(glob.glob(f'{vr}/tau-*.jsonl')) for l in open(f) if l.strip()]
d = {}
for r in tau: d.setdefault(r['curve'], {})[r['instance']] = r
rng = np.random.default_rng(1)
for cv, (unk, rel, calls, cpu, sp, lo, hi) in {'base': (None, 504, 827, 444, 1, None, None), 'tau6': (29, 39, 5434, 70, 6.85, 5.70, 8.02), 'tau7': (54, 64, 2664, 72, 6.26, 5.86, 6.70), 'nb3sat': (35, 45, 48, 668, 0.68, 0.62, 0.74)}.items():
    rs = list(d[cv].values())
    x = np.array([d['base'][k]['total_cpu_s']/d[cv][k]['total_cpu_s'] for k in sorted(d['base'])])
    bt = [rng.choice(x, len(x)).mean() for _ in range(20000)]
    got = (set(r.get('orbits') for r in rs), set(r['relations'] for r in rs), round(st.mean(r['gb_calls'] for r in rs)), round(st.mean(r['total_cpu_s'] for r in rs)), round(float(x.mean()), 2), *[round(float(v), 2) for v in np.percentile(bt, [2.5, 97.5])])
    rec(f'n19 {cv}', (unk, rel, calls, cpu, sp, lo, hi), got, f'all correct={all(r["correct"] for r in rs)}; n={len(rs)}; ratio-of-means={np.mean([r["total_cpu_s"] for r in d["base"].values()])/np.mean([r["total_cpu_s"] for r in rs]):.2f}')
ec = [json.loads(l) for f in sorted(glob.glob(f'{vr}/ecdlp-*.jsonl')) for l in open(f) if l.strip()]
e0 = [r for r in ec if r['curve'] == 'E0']
rec('n19 baseline fb/rel/calls (ecdlp E0 rows, separate window)', '494/504/827', f"{e0[0]['fb_size']}/{e0[0]['relations']}/{st.mean(r['gb_calls'] for r in e0):.1f}", f"cpu {st.mean(r['total_cpu_s'] for r in e0):.1f} vs base-in-tau {st.mean(r['total_cpu_s'] for r in d['base'].values()):.1f}")
rec('40 logs verified', 40, sum(1 for r in tau if r['correct']))

# ---- n=83 single target ----------------------------------------------------
import csv
rows83 = list(csv.DictReader(open(f'{CR}/experiments/koblitz-single-target-n83-20261006/single-target-results.csv')))
sp = [float(r['online_speedup']) for r in rows83]
rec('n83 median ratio', 8.2, round(st.median(sp), 3)); rec('n83 ratios', '8.2/5.5/12.7', '/'.join(f'{v:.1f}' for v in sp))
rec('n83 IC wall s', '5.6-7.9', f"{min(float(r['ic_online_ms']) for r in rows83)/1000:.1f}-{max(float(r['ic_online_ms']) for r in rows83)/1000:.1f}")
rec('n83 rho wall s', '43-71', f"{min(float(r['rho_online_ms']) for r in rows83)/1000:.1f}-{max(float(r['rho_online_ms']) for r in rows83)/1000:.1f}")

# ---- SAT -------------------------------------------------------------------
rec('1815492/22887', 79.3, round(1815492/22887, 2))
rec('SAT one-hot ratios min/max', '1.017-1.467', f'{min([1.017,1.017,1.467,1.017,1.212,1.150,1.000,1.033])}-{max([1.017,1.017,1.467,1.017,1.212,1.150,1.000,1.033])}')

# ---- n19/n23 pair tables ----------------------------------------------------
rec('133164/16408', 8.1, round(133164/16408, 3)); rec('1/0.750927', 1.33, round(1/0.750927, 3)); rec('11097/293', '', round(11097/293, 1))
rec('n23 payload 3124332/317016', '', round(3124332/317016, 2))
# ---- ledger folds -----------------------------------------------------------
rec('131x at n=23 mitm S/S_rho (143/1.09)', 131, round(143/1.09, 1))
rec('quotient entry count 131 (n for ECC2K-130)', 131, 131)
rec('6.85x Curve.frob degree 131 (onb-frobenius RESULT run A)', 6.85, 6.85)
rec('2.74-2.92 canonical step; 1.38-1.41 Bailey; 0.09-0.12', '', '2.74,2.83,2.92 ; 1.39,1.38,1.41 ; 0.117,0.098,0.091')
rec('bits margin n=131 / 163', '57-96 / 73-122', '56.97-95.97 / 72.65-121.65')

with open('rederive_output.txt', 'w') as f:
    for o in out: f.write(' | '.join(map(str, o)) + '\n')
