"""Statistics for the toy rho runs.

usage: sage -python analyze.py T11 T19 T23 T59 T109
Writes results/summary.json (all families) and prints a table.

Theory: M = N/c classes (c = class size: 1 none, 2 neg, 2n negtau); for a random mapping the
number of generated points up to the first repeat, T, satisfies P(T > x) ~ exp(-x^2/(2M)),
E[T] ~ sqrt(pi*M/2) = sqrt(pi*N/(2c)); T^2/(2M) ~ Exp(1) (checked with a KS test).
"""
import sys, os, json, csv, math
import numpy as np
from scipy import stats

WORK = '/Volumes/SSD990/ecdlp-hardness-work/toy-analogue-a'
fams = sys.argv[1:]
summary = {}


def load_rows(path):
    with open(path) as fh:
        return list(csv.DictReader(fh, delimiter='\t'))


def descr(x):
    x = np.asarray(x, dtype=float)
    return dict(n=int(len(x)), mean=float(x.mean()), sd=float(x.std(ddof=1)) if len(x) > 1 else None,
                sem=float(x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else None, median=float(np.median(x)))


def exact_ET(M):
    """E[T] for uniform random sampling from M classes, T = index of the first repeat
    (points counted including the repeated one): sum_{k>=0} prod_{i<k} (1 - i/M)."""
    Mi = int(round(M))
    if Mi > 10**7:
        return math.sqrt(math.pi * M / 2) + 2.0 / 3
    tot, p = 0.0, 1.0
    for k in range(0, Mi + 1):
        tot += p
        p *= (1 - k / M)
        if p < 1e-18:
            break
    return tot


def ratio(a, b):
    r = a['mean'] / b['mean']
    se = r * math.sqrt((a['sem'] / a['mean'])**2 + (b['sem'] / b['mean'])**2)
    return dict(ratio=r, se=se, ci95=[r - 1.96 * se, r + 1.96 * se])


for fam in fams:
    meta = json.load(open(os.path.join(WORK, 'data', f'{fam}_family.json')))['meta']
    tr = json.load(open(os.path.join(WORK, 'raw', fam, 'transport.json')))
    ver = json.load(open(os.path.join(WORK, 'raw', fam, 'verify.json')))
    n, N = meta['n'], int(meta['N'])
    outd = os.path.join(WORK, 'raw', fam, 'out')
    cfgs = {}
    for fn in sorted(os.listdir(outd)):
        if not fn.endswith('.tsv'):
            continue
        cfg = fn[:-4]
        rows = load_rows(os.path.join(outd, fn))
        if not rows:
            continue
        curve, mode = cfg.split('__')
        c = {'negtau': 2 * n, 'transport_negtau': 2 * n, 'neg': 2, 'none': 1}[mode]
        M = N / c
        th = math.sqrt(math.pi * M / 2)
        merge = [int(r['merge_steps']) for r in rows]
        iters = [int(r['iters']) for r in rows]
        steps = [int(r['steps']) for r in rows]
        cpu = [float(r['walk_cpu_s']) for r in rows]
        z = np.asarray(merge, dtype=float)**2 / (2 * M)
        ks = stats.kstest(z, 'expon')
        d_m, d_i = descr(merge), descr(iters)
        M_exact = (N - 1) / c + 1          # classes incl. the identity class
        th_exact = exact_ET(M_exact)
        cfgs[cfg] = dict(curve=curve, mode=mode, class_size=c, M_classes=M, theory_sqrt_pi_M_over_2=th,
                         theory_exact_finite_M=th_exact, merge_over_exact=d_m['mean'] / th_exact,
                         merge_steps=d_m, iters=d_i, steps=descr(steps),
                         merge_over_theory=d_m['mean'] / th, merge_over_theory_ci95=[(d_m['mean'] - 1.96 * d_m['sem']) / th, (d_m['mean'] + 1.96 * d_m['sem']) / th],
                         iters_over_theory=d_i['mean'] / th,
                         ks_T2_over_2M_vs_Exp1=dict(D=float(ks.statistic), p=float(ks.pvalue)),
                         all_verified=all(r['verified'] == '1' and r['match'] == '1' for r in rows),
                         fruitless_cycles_total=sum(int(r['fruitless']) for r in rows),
                         abandoned_walks_total=sum(int(r['abandoned']) for r in rows),
                         dp_bits=None,
                         cpu_us_per_iter_median=float(np.median([1e6 * a / max(1, b) for a, b in zip(cpu, iters)])))
        hdr = open(os.path.join(WORK, 'raw', fam, 'inputs', cfg + '.txt')).read().split('\n')
        for hl in hdr:
            if hl.startswith('dpbits'):
                cfgs[cfg]['dp_bits'] = int(hl.split()[1])
    # pooled groups
    floor_neg = [k for k in cfgs if cfgs[k]['mode'] == 'neg' and cfgs[k]['curve'] != 'E0']
    floor_tr = [k for k in cfgs if cfgs[k]['mode'] == 'transport_negtau']

    def pooled(keys, field='merge_steps'):
        vals = []
        for k in keys:
            rows = load_rows(os.path.join(outd, k + '.tsv'))
            vals += [int(r[field]) for r in rows]
        return vals
    groups = {
        'i_floor_neg': pooled(floor_neg),
        'ii_E0_negtau': pooled(['E0__negtau']),
        'iii_transport_E0_negtau': pooled(floor_tr),
        'iv_E0_neg': pooled(['E0__neg']),
        'v_E0_none': pooled(['E0__none']),
    }
    groups_it = {
        'i_floor_neg': pooled(floor_neg, 'iters'),
        'ii_E0_negtau': pooled(['E0__negtau'], 'iters'),
        'iii_transport_E0_negtau': pooled(floor_tr, 'iters'),
        'iv_E0_neg': pooled(['E0__neg'], 'iters'),
        'v_E0_none': pooled(['E0__none'], 'iters'),
    }
    G = {k: descr(v) for k, v in groups.items() if v}
    Git = {k: descr(v) for k, v in groups_it.items() if v}
    th = {'i_floor_neg': math.sqrt(math.pi * N / 4), 'ii_E0_negtau': math.sqrt(math.pi * N / (4 * n)),
          'iii_transport_E0_negtau': math.sqrt(math.pi * N / (4 * n)), 'iv_E0_neg': math.sqrt(math.pi * N / 4),
          'v_E0_none': math.sqrt(math.pi * N / 2)}
    thx = {'i_floor_neg': exact_ET((N - 1) / 2 + 1), 'ii_E0_negtau': exact_ET((N - 1) / (2 * n) + 1),
           'iii_transport_E0_negtau': exact_ET((N - 1) / (2 * n) + 1), 'iv_E0_neg': exact_ET((N - 1) / 2 + 1),
           'v_E0_none': exact_ET(N)}
    comp = {}
    if 'i_floor_neg' in G and 'ii_E0_negtau' in G:
        comp['i_over_ii_merge'] = ratio(G['i_floor_neg'], G['ii_E0_negtau'])
        comp['i_over_ii_iters'] = ratio(Git['i_floor_neg'], Git['ii_E0_negtau'])
        comp['predicted_sqrt_n'] = math.sqrt(n)
    if 'iii_transport_E0_negtau' in G:
        comp['iii_over_ii_merge'] = ratio(G['iii_transport_E0_negtau'], G['ii_E0_negtau'])
        comp['iii_over_ii_iters'] = ratio(Git['iii_transport_E0_negtau'], Git['ii_E0_negtau'])
        mw = stats.mannwhitneyu(groups['iii_transport_E0_negtau'], groups['ii_E0_negtau'])
        comp['iii_vs_ii_mannwhitney_p'] = float(mw.pvalue)
    if 'iv_E0_neg' in G:
        comp['iv_over_i_merge'] = ratio(G['iv_E0_neg'], G['i_floor_neg'])
        mw = stats.mannwhitneyu(groups['iv_E0_neg'], groups['i_floor_neg'])
        comp['iv_vs_i_mannwhitney_p'] = float(mw.pvalue)
    # homogeneity across floor curves (neg-only), E0 neg included
    samples = [pooled([k]) for k in floor_neg] + ([groups['iv_E0_neg']] if groups['iv_E0_neg'] else [])
    if len(samples) > 1:
        comp['kruskal_floor_neg_curves_and_E0_neg'] = dict(p=float(stats.kruskal(*samples).pvalue), groups=floor_neg + ['E0__neg'])
    samples = [pooled([k]) for k in floor_tr] + [groups['ii_E0_negtau']]
    if len(samples) > 1:
        comp['kruskal_transport_curves_and_E0_negtau'] = dict(p=float(stats.kruskal(*samples).pvalue), groups=floor_tr + ['E0__negtau'])
    summary[fam] = dict(meta=dict(n=n, l=meta['l'], a=meta['a'], N=str(N), log2N=math.log2(N), n_orbits=meta['n_orbits'],
                                  floor_curves=meta['l'] - 1, velu_ext_degree=meta['velu_ext_degree']),
                        groups_merge=G, groups_iters=Git, theory=th,
                        groups_merge_over_theory={k: G[k]['mean'] / th[k] for k in G},
                        theory_exact_finite_M=thx,
                        groups_merge_over_exact={k: G[k]['mean'] / thx[k] for k in G},
                        comparisons=comp, configs=cfgs, transport=tr['transport'], verify=ver['total'])
    print(f'=== {fam}: n={n} l={meta["l"]} N={N} (2^{math.log2(N):.2f})  verify={ver["total"]}')
    for k in G:
        print(f'  {k:26s} n={G[k]["n"]:5d} mean_merge={G[k]["mean"]:12.1f} (+-{G[k]["sem"]:.1f}) theory={th[k]:12.1f} ratio={G[k]["mean"] / th[k]:.4f} exact={thx[k]:.1f} ratio_exact={G[k]["mean"] / thx[k]:.4f} mean_iters={Git[k]["mean"]:.1f} iters/th={Git[k]["mean"] / th[k]:.4f}')
    for k, v in comp.items():
        print('  ', k, v)
    for k, v in cfgs.items():
        print(f'    {k:32s} n={v["merge_steps"]["n"]:5d} merge/th={v["merge_over_theory"]:.3f} KS p={v["ks_T2_over_2M_vs_Exp1"]["p"]:.3f} fruitless={v["fruitless_cycles_total"]} abandoned={v["abandoned_walks_total"]} cpu_us/it={v["cpu_us_per_iter_median"]:.2f}')

os.makedirs(os.path.join(WORK, 'results'), exist_ok=True)
json.dump(summary, open(os.path.join(WORK, 'results', 'summary.json'), 'w'), indent=1)
