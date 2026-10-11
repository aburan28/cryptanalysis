"""Statistics and figures for the n=19 volcano index-calculus study.

    sage -python analyze.py

Reads results/census-*.jsonl (tier A, every curve) and results/ecdlp-*.jsonl
(tier B, full index calculus on selected curves x 10 scalars) and writes
results/summary.json plus figures under figures/. The cross-check outputs
(results/crosscheck*.json, from crosscheck.py and crosscheck.sage) are
folded in when present.
"""
import glob
import json
import math
import os
import re

import numpy as np
from scipy import optimize, stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
P_SUB = 523492 // 4
CLASSES = (P_SUB - 1) // 2
E0_COLOR, DESC_COLOR = '#C45132', '#3069A0'


def load(pattern, source=False):
    rows = []
    for path in sorted(glob.glob(os.path.join(HERE, 'results', pattern))):
        for line in open(path):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
                if source:
                    rows[-1]['_file'] = os.path.basename(path)
    return rows


def attemptsOptimum():
    """lambda minimising attempts: A ~ (|F| + 10) / (1 - e^-lambda) with lambda ~ |F|^2,
    i.e. A ~ sqrt(lambda) / (1 - e^-lambda), stationary where e^lambda - 1 = 2 lambda."""
    return optimize.brentq(lambda l: math.expm1(l) - 2 * l, .5, 3)


def attemptsShape(lam):
    return math.sqrt(lam) / -math.expm1(-lam)


def eligibleFormula(tags):
    n0, n2, no = tags[0], tags[2], tags[1] + tags[3]
    c2 = lambda n: n * (n - 1) // 2
    return 2 * c2(n0) + n0 + 2 * c2(n2) + n2 + c2(no)


def percentile(values, x):
    values = np.asarray(values)
    return float((values < x).mean() * 100 + (values == x).mean() * 50)


def twoWayAnova(y, a, b):
    """Additive two-way ANOVA (one observation per cell) on a complete grid."""
    la, lb = sorted(set(a)), sorted(set(b))
    grid = np.full((len(la), len(lb)), np.nan)
    ia = {v: i for i, v in enumerate(la)}
    ib = {v: i for i, v in enumerate(lb)}
    for yy, aa, bb in zip(y, a, b):
        grid[ia[aa], ib[bb]] = yy
    keep = ~np.isnan(grid).any(axis=1)
    grid = grid[keep]
    r, c = grid.shape
    mu = grid.mean()
    ssA = c * ((grid.mean(axis=1) - mu) ** 2).sum()
    ssB = r * ((grid.mean(axis=0) - mu) ** 2).sum()
    ssT = ((grid - mu) ** 2).sum()
    ssE = ssT - ssA - ssB
    dfA, dfB, dfE = r - 1, c - 1, (r - 1) * (c - 1)
    FA, FB = (ssA / dfA) / (ssE / dfE), (ssB / dfB) / (ssE / dfE)
    return {'curves': r, 'instances': c,
            'curve': {'F': FA, 'df': [dfA, dfE], 'p': float(stats.f.sf(FA, dfA, dfE)), 'eta2': ssA / ssT},
            'instance': {'F': FB, 'df': [dfB, dfE], 'p': float(stats.f.sf(FB, dfB, dfE)), 'eta2': ssB / ssT}}


def bootRatio(x, y, rng, n=20000):
    x, y = np.asarray(x), np.asarray(y)
    bx = rng.choice(x, (n, len(x))).mean(axis=1)
    by = rng.choice(y, (n, len(y))).mean(axis=1)
    r = bx / by
    return [float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))]


def census(rows, out, cpuRows=()):
    rows = sorted(rows, key=lambda r: (r['curve'] != 'E0', r['curve']))
    e0 = next(r for r in rows if r['curve'] == 'E0')
    desc = [r for r in rows if r['curve'] != 'E0']
    fb = np.array([r['fb_size'] for r in desc])
    prob = np.array([r['exact_decomp_prob'] for r in desc])
    att = np.array([r['expected_attempts_per_dlp'] for r in desc])
    formulaOk = sum(eligibleFormula(r['tag_counts']) == r['eligible_signed_pairs'] for r in rows)
    # 1 - exp(-eligible / classes): the birthday-paradox saturation curve.
    lam = np.array([r['eligible_signed_pairs'] / CLASSES for r in rows])
    saturation = 1 - np.exp(-lam)
    exact = np.array([r['exact_decomp_prob'] for r in rows])
    # Sampling noise of the occupied fraction when `eligible` balls fall into
    # CLASSES bins at random, to put the model's error on a scale.
    occupancySd = np.sqrt(CLASSES * (np.exp(-lam) - (1 + lam) * np.exp(-2 * lam))) / CLASSES
    gap = exact - saturation
    lamE0 = e0['eligible_signed_pairs'] / CLASSES
    lamOpt = attemptsOptimum()
    top = max(desc, key=lambda r: r['exact_decomp_prob'])
    # Empirical GB hit rate against the exact probability (pooled binomial).
    hits = sum(s['relations'] for r in rows for s in r['gb_sample'])
    calls = sum(s['gb_calls'] for r in rows for s in r['gb_sample'])
    expectHits = sum(r['exact_decomp_prob'] * s['gb_calls'] for r in rows for s in r['gb_sample'])
    spurious = sum(s['spurious'] for r in rows for s in r['gb_sample'])
    # GB time per call, one value per (curve, instance) cell.
    cellCurve, cellInst, cellGb = [], [], []
    for r in rows:
        for ii, s in enumerate(r['gb_sample']):
            cellCurve.append(r['curve'])
            cellInst.append(ii)
            cellGb.append(s['gb_s'] / s['gb_calls'])
    gbByCurve = {}
    for c, g in zip(cellCurve, cellGb):
        gbByCurve.setdefault(c, []).append(g)
    kwCurve = stats.kruskal(*gbByCurve.values())
    gbByInst = {}
    for i, g in zip(cellInst, cellGb):
        gbByInst.setdefault(i, []).append(g)
    kwInst = stats.kruskal(*gbByInst.values())
    dregs = [d for r in rows for d in r['dreg_samples']]
    dregE0 = e0['dreg_samples']
    # Frobenius orbits: does the orbit explain factor-base size?
    orbits = {}
    for r in desc:
        orbits.setdefault(r['orbit'], []).append(r['fb_size'])
    kwOrbit = stats.kruskal(*orbits.values())
    # CPU-time Groebner cost (load-independent), one sample list per curve.
    cpu = {r['curve']: r['gb_cpu_s'] for r in cpuRows}
    cpuSummary = None
    if len(cpu) >= 2:
        kwCpu = stats.kruskal(*cpu.values())
        fbOf = {r['curve']: r['fb_size'] for r in rows}
        probOf = {r['curve']: r['exact_decomp_prob'] for r in rows}
        means = {c: float(np.mean(v)) for c, v in cpu.items()}
        descMeans = [m for c, m in means.items() if c != 'E0']
        allCpu = [x for v in cpu.values() for x in v]
        rhoFb = stats.spearmanr([fbOf[c] for c in means], list(means.values()))
        rhoProb = stats.spearmanr([probOf[c] for c in means], list(means.values()))
        cpuSummary = {'curves': len(cpu), 'median_s': float(np.median(allCpu)),
                      'curve_mean_range_s': [float(min(means.values())), float(max(means.values()))],
                      'e0_mean_s': means.get('E0'),
                      'e0_percentile_of_descendant_means': percentile(descMeans, means['E0']) if 'E0' in means else None,
                      'kruskal_by_curve': {'H': float(kwCpu.statistic), 'p': float(kwCpu.pvalue)},
                      'spearman_mean_vs_fb_size': float(rhoFb[0]), 'spearman_mean_vs_fb_size_p': float(rhoFb[1]),
                      'spearman_mean_vs_decomp_prob': float(rhoProb[0]), 'spearman_mean_vs_decomp_prob_p': float(rhoProb[1]),
                      'within_curve_cv': float(np.median([np.std(v) / np.mean(v) for v in cpu.values()]))}
    summary = {
        'curves': len(rows), 'descendants': len(desc),
        'e0': {k: e0[k] for k in ('fb_size', 'tag_counts', 'eligible_signed_pairs', 'distinct_targets',
                                   'exact_decomp_prob', 'expected_attempts_per_dlp', 'dreg_samples')},
        'e0_percentile': {'fb_size': percentile(fb, e0['fb_size']),
                          'exact_decomp_prob': percentile(prob, e0['exact_decomp_prob']),
                          'expected_attempts_per_dlp': percentile(att, e0['expected_attempts_per_dlp'])},
        'descendants_range': {
            'fb_size': [int(fb.min()), float(np.median(fb)), int(fb.max())],
            'exact_decomp_prob': [float(prob.min()), float(np.median(prob)), float(prob.max())],
            'expected_attempts_per_dlp': [float(att.min()), float(np.median(att)), float(att.max())]},
        # Tier B's extremes were picked by predicted attempts, not by yield.
        'highest_yield_descendant': {
            'curve': top['curve'], 'fb_size': top['fb_size'], 'exact_decomp_prob': top['exact_decomp_prob'],
            'expected_attempts_per_dlp': top['expected_attempts_per_dlp'],
            'attempts_rank': 1 + sum(r['expected_attempts_per_dlp'] < top['expected_attempts_per_dlp'] for r in desc)},
        'eligible_formula_matches': [formulaOk, len(rows)],
        'saturation_model_max_abs_error': float(np.abs(saturation - exact).max()),
        # The model runs slightly low: sums of distinct factor-base points
        # collide less often than independent random targets would.
        'saturation_model_bias': {'mean_exact_minus_model': float(gap.mean()),
                                  'fraction_exact_above_model': float((gap > 0).mean()),
                                  'mean_in_occupancy_sd': float((gap / occupancySd).mean()),
                                  'occupancy_sd': float(occupancySd.mean())},
        'e0_saturation_prob': float(1 - math.exp(-lamE0)),
        'operating_point': {'lambda_range': [float(lam.min()), float(lam.max())], 'lambda_e0': lamE0,
                            'lambda_attempts_optimum': lamOpt,
                            'e0_attempts_over_optimum': attemptsShape(lamE0) / attemptsShape(lamOpt),
                            # d ln A / d ln |F| with lambda ~ |F|^2 (ignoring the +10)
                            'e0_attempts_elasticity_in_fb_size': 1 - 2 * lamE0 / math.expm1(lamE0)},
        'corr_fb_size_vs_expected_attempts': float(stats.pearsonr([r['fb_size'] for r in rows],
                                                                  [r['expected_attempts_per_dlp'] for r in rows])[0]),
        'gb_hit_rate': {'hits': hits, 'calls': calls, 'expected_hits': expectHits,
                        'z': (hits - expectHits) / math.sqrt(sum(r['exact_decomp_prob'] * (1 - r['exact_decomp_prob']) * s['gb_calls']
                                                                   for r in rows for s in r['gb_sample'])),
                        'spurious_solutions': spurious},
        'gb_seconds_per_call': {'median': float(np.median(cellGb)),
                                'kruskal_by_curve': {'H': float(kwCurve.statistic), 'p': float(kwCurve.pvalue)},
                                'kruskal_by_instance': {'H': float(kwInst.statistic), 'p': float(kwInst.pvalue)}},
        'dreg': {'values': {str(v): dregs.count(v) for v in sorted(set(dregs))}, 'e0': dregE0},
        'gb_cpu_seconds_per_call': cpuSummary,
        'gb_wall_note': 'census wall-clock GB times drift with machine load in processing order; use gb_cpu_seconds_per_call',
        'fb_size_by_orbit_kruskal': {'H': float(kwOrbit.statistic), 'p': float(kwOrbit.pvalue)},
    }
    out['census'] = summary

    fig, ax = plt.subplots(2, 2, figsize=(13, 9))
    a = ax[0, 0]
    a.hist(fb, bins=range(int(fb.min()), int(fb.max()) + 3, 2), color=DESC_COLOR, alpha=.8)
    a.axvline(e0['fb_size'], color=E0_COLOR, lw=2, label='E0 (Koblitz, crater)')
    a.set_xlabel('factor-base size |F| (points up to sign, x in V, dim V = 10)')
    a.set_ylabel('descendant curves')
    a.set_title('A  Factor-base size across 456 descendants')
    a.legend(frameon=False)
    a = ax[0, 1]
    elig = np.array([r['eligible_signed_pairs'] for r in rows])
    grid = np.linspace(elig.min() * .97, elig.max() * 1.03, 200)
    a.plot(grid, 1 - np.exp(-grid / CLASSES), color='#555', lw=1, label='1 - exp(-eligible / ((p-1)/2))')
    a.scatter([r['eligible_signed_pairs'] for r in desc], prob, s=9, color=DESC_COLOR, alpha=.7, label='descendant')
    a.scatter([e0['eligible_signed_pairs']], [e0['exact_decomp_prob']], s=60, marker='D', color=E0_COLOR, label='E0', zorder=3)
    a.set_xlabel('eligible signed pairs (four-torsion formula)')
    a.set_ylabel('exact decomposition probability per target')
    a.set_title('B  Relation yield is a birthday curve in the tag count')
    a.legend(frameon=False, fontsize=9)
    a = ax[1, 0]
    a.scatter(fb, att, s=9, color=DESC_COLOR, alpha=.7)
    a.scatter([e0['fb_size']], [e0['expected_attempts_per_dlp']], s=60, marker='D', color=E0_COLOR, zorder=3)
    a.set_xlabel('factor-base size |F|')
    a.set_ylabel('expected decomposition attempts per ECDLP\n(|F| + 10) / Pr[decomp]')
    a.set_title('C  Predicted relation-collection work')
    a = ax[1, 1]
    src = cpu if cpu else gbByCurve
    order = sorted(src, key=lambda c: (c != 'E0', c))
    med = [np.mean(src[c]) * 1000 for c in order]
    a.scatter(range(len(order)), med, s=6, color=[E0_COLOR if c == 'E0' else DESC_COLOR for c in order])
    if 'E0' in src:
        a.scatter([0], [med[0]], s=60, marker='D', color=E0_COLOR, zorder=3)
    a.set_xlabel('curve (E0 first, then Frobenius orbits O00 ... O23)')
    a.set_ylabel('mean Gröbner CPU ms per decomposition\n(20 targets, 2 per ECDLP instance)' if cpu else 'median GB wall ms (load-confounded)')
    a.set_title('D  Gröbner cost per decomposition by curve')
    for x in ax.flat:
        x.spines[['top', 'right']].set_visible(False)
        x.grid(alpha=.2)
    fig.suptitle('Tier A: all 457 curves in the n = 19 isogeny class (E0 + 456 conductor-457 descendants)', fontsize=13)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, 'figures'), exist_ok=True)
    fig.savefig(os.path.join(HERE, 'figures', 'census.png'), dpi=150)
    fig.savefig(os.path.join(HERE, 'figures', 'census.svg'))
    plt.close(fig)
    return {r['curve']: r for r in rows}


def ecdlp(rows, censusByCurve, out):
    if not rows:
        return
    # Keep one record per (curve, instance). Duplicates come from overlapping
    # worker launches; they share a seed, so the attempt sequence is identical.
    seen, unique = set(), []
    for r in rows:
        key = (r['curve'], r['instance'])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    out['ecdlp_duplicates_dropped'] = len(rows) - len(unique)
    rows = unique
    rng = np.random.default_rng(1)
    byCurve = {}
    for r in rows:
        byCurve.setdefault(r['curve'], []).append(r)
    complete = {c: v for c, v in byCurve.items() if len({r['instance'] for r in v}) == 10}
    if len(complete) < 2 or 'E0' not in complete:
        out['ecdlp'] = {'pending': {c: len(v) for c, v in byCurve.items()}}
        return
    allRuns = [r for v in complete.values() for r in v]
    correct = sum(r['correct'] for r in allRuns)
    metrics = {}
    # relations is fixed at |F| + 10 per curve, so it carries no variance.
    for key in ('gb_calls', 'total_cpu_s', 'gb_cpu_s', 'linalg_s', 'total_s'):
        y = [math.log(r[key]) for r in allRuns]
        metrics[key] = twoWayAnova(y, [r['curve'] for r in allRuns], [r['instance'] for r in allRuns])
    e0 = [r for r in allRuns if r['curve'] == 'E0']
    desc = [r for r in allRuns if r['curve'] != 'E0']
    comp = {}
    for key in ('total_cpu_s', 'gb_calls', 'gb_cpu_s'):
        x, y = [r[key] for r in e0], [r[key] for r in desc]
        mw = stats.mannwhitneyu(x, y)
        comp[key] = {'e0_mean': float(np.mean(x)), 'desc_mean': float(np.mean(y)),
                     'ratio_e0_over_desc': float(np.mean(x) / np.mean(y)),
                     'ratio_ci95': bootRatio(x, y, rng),
                     'mannwhitney_p': float(mw.pvalue)}
    # Does the tier-A prediction explain the measured attempts?
    predicted = [censusByCurve[r['curve']]['expected_attempts_per_dlp'] for r in allRuns]
    measured = [r['gb_calls'] for r in allRuns]
    curveMeans = {c: np.mean([r['gb_calls'] for r in v]) for c, v in complete.items()}
    curvePred = {c: censusByCurve[c]['expected_attempts_per_dlp'] for c in complete}
    rc = stats.pearsonr([curvePred[c] for c in complete], [curveMeans[c] for c in complete])
    # Attempts per ECDLP are negative binomial: |F| + 10 successes at Pr each.
    # If the census prediction were exact, curve means would scatter around it
    # with this variance alone.
    nbVar = {c: (censusByCurve[c]['fb_size'] + 10) * (1 - censusByCurve[c]['exact_decomp_prob'])
             / censusByCurve[c]['exact_decomp_prob'] ** 2 / len(v) for c, v in complete.items()}
    chi2 = sum((curveMeans[c] - curvePred[c]) ** 2 / nbVar[c] for c in complete)
    predSd = np.std([curvePred[c] for c in complete], ddof=1)
    descPred = np.mean([curvePred[c] for c in complete if c != 'E0'])
    # Worker k of the 10-way sharded launch took jobs with index = k (mod 10),
    # i.e. instance k of every curve, so "instance" also names the process.
    shardOf = lambda r: int(re.search(r'ecdlp-(\d+)', r.get('_file', 'ecdlp--1')).group(1))
    sameProcess = np.mean([shardOf(r) == r['instance'] for r in allRuns])
    laMean = {c: np.mean([r['linalg_s'] for r in v]) for c, v in complete.items()}
    laFit = stats.linregress([math.log(censusByCurve[c]['fb_size']) for c in complete],
                             [np.mean([math.log(r['linalg_s']) for r in v]) for c, v in complete.items()])
    perInstance = {}
    for r in allRuns:
        perInstance.setdefault(r['instance'], []).append(r['gb_calls'])
    out['ecdlp'] = {
        'curves': sorted(complete, key=lambda c: (c != 'E0', c)), 'runs': len(allRuns),
        'correct_logs': [correct, len(allRuns)],
        'anova_log_metrics': metrics,
        'e0_vs_descendants': comp,
        'predicted_vs_measured_attempts': {'pearson_r_curve_means': float(rc[0]), 'p': float(rc[1]),
                                           'mean_ratio_measured_over_predicted': float(np.mean(np.array(measured) / np.array(predicted))),
                                           'residual_chi2': float(chi2), 'residual_df': len(complete),
                                           'residual_p': float(stats.chi2.sf(chi2, len(complete))),
                                           'expected_r_if_census_exact': float(predSd / math.sqrt(predSd ** 2 + np.mean(list(nbVar.values())))),
                                           'census_predicted_e0_over_desc': float(curvePred['E0'] / descPred)},
        'instance_is_worker_process_fraction': float(sameProcess),
        'linalg': {'curve_mean_s_range': [float(min(laMean.values())), float(max(laMean.values()))],
                   'median_share_of_total_cpu': float(np.median([r['linalg_s'] / r['total_cpu_s'] for r in allRuns])),
                   'loglog_slope_vs_fb_size': float(laFit.slope), 'loglog_r': float(laFit.rvalue),
                   'loglog_p': float(laFit.pvalue)},
        'per_instance_median_attempts': {str(k): float(np.median(v)) for k, v in sorted(perInstance.items())},
        'per_curve': {c: {'fb_size': censusByCurve[c]['fb_size'],
                          'exact_decomp_prob': censusByCurve[c]['exact_decomp_prob'],
                          'predicted_attempts': curvePred[c],
                          'mean_attempts': float(curveMeans[c]),
                          'median_total_cpu_s': float(np.median([r['total_cpu_s'] for r in v])),
                          'iqr_total_cpu_s': [float(np.percentile([r['total_cpu_s'] for r in v], 25)),
                                              float(np.percentile([r['total_cpu_s'] for r in v], 75))],
                          'correct': sum(r['correct'] for r in v)}
                      for c, v in complete.items()},
    }

    order = sorted(complete, key=lambda c: (c != 'E0', curvePred[c]))
    fig, ax = plt.subplots(1, 3, figsize=(17, 5.8))
    a = ax[0]
    data = [[r['gb_calls'] for r in complete[c]] for c in order]
    bp = a.boxplot(data, vert=False, widths=.6, patch_artist=True, medianprops={'color': 'black'})
    for patch, c in zip(bp['boxes'], order):
        patch.set_facecolor(E0_COLOR if c == 'E0' else DESC_COLOR)
        patch.set_alpha(.55)
    a.scatter([curvePred[c] for c in order], range(1, len(order) + 1), marker='|', s=120, color='black',
              zorder=3, label='census prediction')
    a.set_yticks(range(1, len(order) + 1), order, fontsize=7)
    a.set_xlabel('decomposition attempts per ECDLP (10 scalars per curve)')
    a.set_title('A  Work by curve (sorted by predicted attempts)')
    a.legend(frameon=False, loc='lower right', fontsize=9)
    a = ax[1]
    a.scatter([curvePred[c] for c in order], [curveMeans[c] for c in order], s=18,
              color=[E0_COLOR if c == 'E0' else DESC_COLOR for c in order])
    lo, hi = min(curvePred.values()) * .97, max(curvePred.values()) * 1.03
    a.plot([lo, hi], [lo, hi], color='#777', lw=1, ls='--', label='measured = predicted')
    a.set_xlabel('tier-A prediction: (|F| + 10) / Pr[decomp]')
    a.set_ylabel('measured mean decomposition attempts')
    a.set_title('B  Exact yield predicts relation-collection work')
    a.legend(frameon=False)
    a = ax[2]
    inst = sorted(perInstance)
    a.boxplot([perInstance[i] for i in inst], widths=.6)
    a.set_xticks(range(1, len(inst) + 1), [str(i) for i in inst])
    a.set_xlabel('ECDLP instance (same 10 scalars on every curve)')
    a.set_ylabel('decomposition attempts per ECDLP')
    a.set_title('C  Work by instance (all 31 curves)')
    for x in ax:
        x.spines[['top', 'right']].set_visible(False)
        x.grid(alpha=.2)
    fig.suptitle('Tier B: complete index calculus, %d curves x 10 ECDLP instances (%d/%d logs verified)'
                 % (len(complete), correct, len(allRuns)), fontsize=13)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'figures', 'ecdlp.png'), dpi=150)
    fig.savefig(os.path.join(HERE, 'figures', 'ecdlp.svg'))
    plt.close(fig)


def interleaved(rows, out):
    """Blocked design: each round is a block holding one solve per curve."""
    if not rows:
        return
    curves = sorted({r['curve'] for r in rows}, key=lambda c: (c != 'E0', c))
    rounds = sorted({r['round'] for r in rows})
    cell = {(r['curve'], r['round']): r for r in rows}
    full = [rd for rd in rounds if all((c, rd) in cell for c in curves)]
    mat = np.array([[cell[(c, rd)]['gb_cpu_s'] for c in curves] for rd in full])
    fr = stats.friedmanchisquare(*mat.T)
    # Round effect alone (drift) for contrast.
    kwRound = stats.kruskal(*[mat[i] for i in range(len(full))])
    per = {}
    for j, c in enumerate(curves):
        rs = [cell[(c, rd)] for rd in full]
        ne = [r['gb_cpu_s'] for r in rs if r['nonempty']]
        em = [r['gb_cpu_s'] for r in rs if not r['nonempty']]
        per[c] = {'mean_ms': 1000 * float(mat[:, j].mean()), 'solvable_fraction': len(ne) / len(rs),
                  'mean_ms_solvable': 1000 * float(np.mean(ne)) if ne else None,
                  'mean_ms_unsolvable': 1000 * float(np.mean(em)) if em else None}
    ne = [r['gb_cpu_s'] for r in rows if r['nonempty']]
    em = [r['gb_cpu_s'] for r in rows if not r['nonempty']]
    e0 = mat[:, 0]
    rest = mat[:, 1:].mean(axis=1)
    w = stats.wilcoxon(e0, rest)
    cv = float(np.median(mat.std(axis=0) / mat.mean(axis=0)))
    out['interleaved_gb'] = {
        'curves': curves, 'rounds': len(full),
        'friedman_curve': {'chi2': float(fr.statistic), 'p': float(fr.pvalue)},
        'kruskal_round_drift': {'H': float(kwRound.statistic), 'p': float(kwRound.pvalue)},
        'solvable_vs_unsolvable_ms': [1000 * float(np.mean(ne)), 1000 * float(np.mean(em))],
        'e0_over_descendant_mean_ratio': float(e0.mean() / rest.mean()),
        'e0_vs_descendant_mean_wilcoxon_p': float(w.pvalue),
        # Resolution of the test: standard error of one curve's mean cost.
        'within_curve_cv': cv, 'curve_mean_se_pct': 100 * cv / math.sqrt(len(full)),
        'per_curve': per}


def tauComparison(rows, out):
    """E0: tau-invariant factor bases against the baseline, paired by scalar."""
    if not rows:
        return
    seen, by = set(), {}
    for r in rows:
        key = (r['curve'], r['instance'])
        if key in seen:
            continue
        seen.add(key)
        by.setdefault(r['curve'], {})[r['instance']] = r
    variants = [v for v in ('base', 'tau6', 'tau7', 'nb3sat') if v in by]
    common = sorted(set.intersection(*[set(by[v]) for v in variants]))
    if 'base' not in by or not common:
        out['tau'] = {'pending': {v: len(by[v]) for v in by}}
        return
    res = {'instances': len(common), 'variants': {}}
    for v in variants:
        rs = [by[v][i] for i in common]
        cpu = np.array([r['total_cpu_s'] for r in rs])
        entry = {'correct': [sum(r['correct'] for r in rs), len(rs)],
                 'unknowns': rs[0].get('orbits', rs[0].get('fb_size')),
                 'relations_mean': float(np.mean([r['relations'] for r in rs])),
                 'gb_calls_mean': float(np.mean([r['gb_calls'] for r in rs])),
                 'gb_ms_per_call': float(1000 * np.sum([r['gb_cpu_s'] for r in rs]) / np.sum([r['gb_calls'] for r in rs])),
                 'total_cpu_s_mean': float(cpu.mean()), 'total_cpu_s_median': float(np.median(cpu))}
        if v != 'base':
            base = np.array([by['base'][i]['total_cpu_s'] for i in common])
            ratio = base / cpu
            rng = np.random.default_rng(2)
            boot = [np.mean(rng.choice(ratio, len(ratio))) for _ in range(20000)]
            entry['speedup_vs_base_mean'] = float(ratio.mean())
            entry['speedup_ci95'] = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]
            entry['wilcoxon_p'] = float(stats.wilcoxon(base, cpu).pvalue)
            entry['targets_mean'] = float(np.mean([r['targets'] for r in rs]))
            entry['v_points'] = rs[0]['v_points']
        res['variants'][v] = entry
    out['tau'] = res

    fig, ax = plt.subplots(1, 2, figsize=(15, 4.8))
    unk = lambda v: res['variants'].get(v, {}).get('unknowns', 0)
    names = {'base': 'baseline subspace\nGröbner · %d unknowns' % unk('base'),
             'tau6': "τ orbits, k' = 6\nGröbner · %d unknowns" % unk('tau6'),
             'tau7': "τ orbits, k' = 7\nGröbner · %d unknowns" % unk('tau7'),
             'nb3sat': 'normal basis, wt ≤ 3\nSAT · %d unknowns' % unk('nb3sat')}
    cols = {'base': DESC_COLOR, 'tau6': E0_COLOR, 'tau7': '#8C3A22', 'nb3sat': '#6B5B95'}
    a = ax[0]
    for i, v in enumerate(variants):
        y = [by[v][c]['total_cpu_s'] for c in common]
        a.scatter(np.full(len(y), i) + np.linspace(-.12, .12, len(y)), y, s=22, color=cols[v])
        a.hlines(np.mean(y), i - .25, i + .25, color='black', lw=1.5)
    a.set_yscale('log')
    a.set_xticks(range(len(variants)), [names[v] for v in variants], fontsize=9)
    a.set_ylabel('CPU seconds per ECDLP (log scale)')
    a.set_title('A  E0 end-to-end cost, same 10 scalars')
    a = ax[1]
    w = .38
    xs = np.arange(len(variants))
    a.bar(xs - w / 2, [res['variants'][v]['relations_mean'] for v in variants], w, color='#9AA7AE', label='relations collected')
    a.bar(xs + w / 2, [res['variants'][v]['gb_calls_mean'] / 10 for v in variants], w, color='#3E4A52', label='solver calls / 10')
    a.set_xticks(xs, [names[v] for v in variants], fontsize=9)
    a.set_title('B  Relations needed and solver calls')
    a.legend(frameon=False)
    for x in ax:
        x.spines[['top', 'right']].set_visible(False)
        x.grid(alpha=.2, axis='y')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'figures', 'tau.png'), dpi=150)
    plt.close(fig)


def costModel(out, censusByCurve, crosscheck):
    """Groebner cost implied by the interleaved split. A solvable system costs
    c_s and an unsolvable one c_u, and a curve's solvable share is its exact
    decomposition probability, so a decomposition costs c_u + (c_s - c_u) Pr
    and one ECDLP (|F| + 10 relations) costs (|F| + 10) (c_s + c_u (1/Pr - 1))."""
    il = out.get('interleaved_gb')
    if not il:
        return
    cs, cu = (x / 1000 for x in il['solvable_vs_unsolvable_ms'])
    names = sorted(censusByCurve, key=lambda c: (c != 'E0', c))
    fb = np.array([censusByCurve[c]['fb_size'] for c in names])
    pr = np.array([censusByCurve[c]['exact_decomp_prob'] for c in names])
    att = np.array([censusByCurve[c]['expected_attempts_per_dlp'] for c in names])
    perCall = cu + (cs - cu) * pr
    gbDlp = (fb + 10) * (cs + cu * (1 / pr - 1))
    observed = [il['per_curve'][c]['mean_ms'] / 1000 for c in il['curves']]
    modelIl = [cu + (cs - cu) * censusByCurve[c]['exact_decomp_prob'] for c in il['curves']]
    res = {'solvable_s': cs, 'unsolvable_s': cu,
           'per_call_ms_range': [1000 * float(perCall.min()), 1000 * float(perCall.max())],
           'per_call_spread_pct': 100 * float(perCall.max() / perCall.min() - 1),
           'interleaved_observed_vs_model_r': float(np.corrcoef(observed, modelIl)[0, 1]),
           'gb_cpu_s_per_dlp': {'range': [float(gbDlp.min()), float(gbDlp.max())], 'e0': float(gbDlp[0]),
                                'e0_percentile': percentile(gbDlp[1:], gbDlp[0]),
                                'halfwidth_pct': 100 * float((gbDlp.max() - gbDlp.min()) / 2 / np.median(gbDlp)),
                                'corr_with_fb_size': float(np.corrcoef(fb, gbDlp)[0, 1])},
           'corr_attempts_with_fb_size': float(np.corrcoef(fb, att)[0, 1])}
    tz = (crosscheck or {}).get('trace_zero')
    if tz:
        tzC = [tz['per_curve'][c] for c in names]
        tzDlp = np.array([(r['fb_size'] + 10) * (cs + cu * (1 / r['exact_decomp_prob'] - 1)) for r in tzC])
        res['trace_zero_gb_cpu_s_per_dlp_mean'] = float(tzDlp.mean())
        res['trace_zero_saving_pct'] = 100 * float(1 - tzDlp.mean() / gbDlp.mean())
    out['cost_model'] = res


def crosschecks(out):
    """Fold in crosscheck.py / crosscheck.sage outputs, without per-curve detail."""
    found = {}
    for name in ('crosscheck', 'crosscheck-algebra'):
        path = os.path.join(HERE, 'results', name + '.json')
        if os.path.exists(path):
            found[name] = json.load(open(path))
    if 'crosscheck' in found:
        cc = json.loads(json.dumps(found['crosscheck']))
        cc.get('trace_zero', {}).pop('per_curve', None)
        out['crosscheck'] = cc
    if 'crosscheck-algebra' in found:
        out['crosscheck_algebra'] = found['crosscheck-algebra']
    return found.get('crosscheck')


def main():
    out = {}
    interleaved(load('interleave.jsonl'), out)
    tauComparison(load('tau-*.jsonl'), out)
    byCurve = census(load('census-*.jsonl'), out, load('gbcpu-*.jsonl'))
    ecdlp(load('ecdlp-*.jsonl', source=True), byCurve, out)
    costModel(out, byCurve, crosschecks(out))
    with open(os.path.join(HERE, 'results', 'summary.json'), 'w') as f:
        json.dump(out, f, indent=2, default=float)
    print(json.dumps(out, indent=2, default=float)[:6000])


if __name__ == '__main__':
    main()
