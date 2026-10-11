"""Figures for the F_(2^83) volcano study (PNG + SVG under outputs/figures/).

    python3 figures.py [name ...]      # default: every figure whose inputs exist
"""
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs'
FIG = OUT / 'figures'

INK = '#1f2430'
MUTED = '#6b7280'
CRATER = '#b4432f'
FLOOR = '#2f6db4'
ACCENT = '#d98e04'
GRID = '#e5e7eb'
PALETTE = ['#2f6db4', '#d98e04', '#3a9d5d', '#b4432f', '#7b52ab', '#16838f']

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.edgecolor': MUTED,
                     'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': MUTED,
                     'axes.titleweight': 'bold', 'axes.titlesize': 10, 'axes.grid': True,
                     'grid.color': GRID, 'grid.linewidth': 0.6, 'axes.axisbelow': True})


def load(rel):
    return json.loads((OUT / rel).read_text())


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / (name + '.png'), dpi=180, bbox_inches='tight')
    fig.savefig(FIG / (name + '.svg'), bbox_inches='tight')
    plt.close(fig)
    print('wrote', name)


def fig_volcano():
    inv = load('s00-ring-invariants.json')
    comp = None
    graph = OUT / 'run10-horizontal' / 'adjacency.json'
    if graph.exists():
        adj = json.loads(graph.read_text())['11']
        # orbit -> 11-cycle component index
        seen, comp = {}, {}
        for v in adj:
            if v in seen:
                continue
            idx = len(set(seen.values()))
            stack = [v]
            seen[v] = idx
            while stack:
                u = stack.pop()
                for w in adj[u]:
                    if w not in seen:
                        seen[w] = idx
                        stack.append(w)
        for v, c in seen.items():
            comp[int(v[1:3])] = c
    fig = plt.figure(figsize=(11, 5.2))
    ax = fig.add_axes([0.02, 0.05, 0.56, 0.9])
    ax.set_axis_off()
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.25, 1.2)
    ax.scatter([0], [0.95], s=420, color=CRATER, zorder=5)
    ax.text(0, 1.1, 'E0: j = 1, End = O_K (D = -7)', ha='center', color=INK, fontweight='bold')
    ax.text(0, 0.62, 'h(O_K) = 1; 6473 is inert in Q(sqrt(-7)): no horizontal 6473-isogeny,\n'
                     'all 6474 F_q-rational kernel lines descend', ha='center', color=MUTED, fontsize=8,
            bbox=dict(boxstyle='round,pad=0.3', fc='white', ec=GRID), zorder=6)
    n = 78
    xs = np.linspace(-1.0, 1.0, n)
    ys = -0.62 + 0.18 * (1 - xs ** 2)
    for i in range(n):
        ax.plot([0, xs[i]], [0.95, ys[i]], color=FLOOR, alpha=0.18, lw=0.8, zorder=1)
        color = PALETTE[comp[i] % len(PALETTE)] if comp else FLOOR
        ax.scatter([xs[i]], [ys[i]], s=34, color=color, zorder=4, edgecolors='white', linewidths=0.4)
    ax.text(0, -0.95, 'conductor-6473 floor: 6474 curves = 78 Frobenius orbits x 83 conjugates'
            + ('\ncolour = component of the degree-11 horizontal graph (6 cycles of 1079 = 13 orbits)' if comp else ''),
            ha='center', color=INK, fontsize=8.5)
    ax.text(-1.12, 0.2, 'degree-6473\nvertical isogenies\n(one per floor curve)', color=FLOOR, fontsize=8,
            bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none'), zorder=6)
    ax2 = fig.add_axes([0.6, 0.12, 0.39, 0.76])
    ax2.set_axis_off()
    rows = [['conductor', 'disc.', 'class no.', 'min deg']]
    for o in inv['possible_orders']:
        f = o['conductor']
        rows.append([f'{f:,}', f"{o['discriminant']:.3g}" if abs(o['discriminant']) > 1e9 else f"{o['discriminant']:,}",
                     f"{o['class_number']:.4g}" if o['class_number'] > 1e9 else f"{o['class_number']:,}",
                     f"{o['minimum_noninteger_endomorphism_degree']:.3g}"
                     if o['minimum_noninteger_endomorphism_degree'] > 1e9
                     else f"{o['minimum_noninteger_endomorphism_degree']:,}"])
    table = ax2.table(cellText=rows, loc='center', cellLoc='left', colWidths=[0.3, 0.26, 0.22, 0.22])
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1, 1.6)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor(GRID)
        if r == 0:
            cell.set_text_props(fontweight='bold', color=INK)
        if r == 2:
            cell.set_facecolor('#eef4fb')
    ax2.set_title('All endomorphism orders over F_(2^83)\n[O_K : Z[pi]] = 6473 * 53676929', fontsize=10)
    save(fig, 'fig01-volcano')


def jsonl(rel_pattern):
    import glob
    for path in sorted(glob.glob(str(OUT / rel_pattern))):
        for line in open(path):
            yield json.loads(line)


def fig_run01():
    census = {}
    for r in jsonl('run01-comparison/yield-census-*.jsonl'):
        census[(r['curve_id'], r['k'], r['profile'])] = r
    solver = {r['curve_id']: r for r in jsonl('run01-comparison/census-*.jsonl')
              if r['k'] == 4 and r['profile'] == 'polynomial'}
    panel = {(r['curve_id'], r['k'], r['profile']): r for r in jsonl('run01-comparison/panel-*.jsonl')}
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    for ax, (k, p) in zip(axes[0], [(4, 'polynomial'), (4, 'random'), (5, 'polynomial')]):
        rows = [r for (c, kk, pp), r in census.items() if kk == k and pp == p and c != 'E0']
        xs = np.array([r['x_count'] for r in rows]) + np.random.default_rng(1).uniform(-0.25, 0.25, len(rows))
        ys = np.array([r['prime_subgroup_distinct_targets'] for r in rows])
        ax.scatter(xs, ys, s=4, alpha=0.25, color=FLOOR, lw=0, label='6474 descendants')
        e0 = census.get(('E0', k, p))
        if e0:
            ax.scatter([e0['x_count']], [e0['prime_subgroup_distinct_targets']], s=70, color=CRATER,
                       marker='*', zorder=5, label='E0')
        ax.set_title('k=%d, %s basis' % (k, p))
        ax.set_xlabel('rational x in subspace')
        ax.set_ylabel('distinct prime-subgroup targets')
        ax.legend(loc='upper left', fontsize=7, frameon=False)

    def maxd(row):
        ds = [c.get('degree_of_regularity') for c in row['cells']
              if c['kind'] == 'satisfiable' and c.get('degree_of_regularity') is not None]
        return max(ds) if ds else None
    panels = [('k=4 polynomial (all curves)', [maxd(r) for c, r in solver.items() if c != 'E0'],
               maxd(solver['E0']) if 'E0' in solver else None)]
    for k, p in [(4, 'random'), (5, 'polynomial')]:
        rows = {c: r for (c, kk, pp), r in panel.items() if kk == k and pp == p}
        panels.append(('k=%d %s (panel of %d)' % (k, p, len(rows)), [maxd(r) for c, r in rows.items() if c != 'E0'],
                       maxd(rows['E0']) if 'E0' in rows else None))
    for ax, (title, vals, e0) in zip(axes[1], panels):
        cnt = {}
        for v in vals:
            cnt[v] = cnt.get(v, 0) + 1
        keys = sorted([k for k in cnt if k is not None]) + ([None] if None in cnt else [])
        labels = [str(k) if k is not None else 'n/a' for k in keys]
        bars = ax.bar(range(len(keys)), [cnt[k] for k in keys], color=FLOOR)
        for i, k in enumerate(keys):
            if k == e0:
                bars[i].set_color(ACCENT)
        ax.set_xticks(range(len(keys)))
        ax.set_xticklabels(labels)
        ax.set_title(title)
        ax.set_xlabel('max sampled formal d_reg (E0 bin in orange)')
        ax.set_ylabel('curves')
    fig.suptitle('Run-01: exact relation coverage and sampled regularity on E0 and all 6474 descendants',
                 fontweight='bold')
    fig.tight_layout()
    save(fig, 'fig02-run01-all-curves')


def fig_run08():
    a = load('run08-subspaces/analysis.json')
    dist = a['scaling_distribution']
    ks = sorted(int(k) for k in dist)
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    best = [dist[str(k)]['best'] for k in ks]
    med = [dist[str(k)]['median'] for k in ks]
    lo = [dist[str(k)]['p05'] for k in ks]
    hi = [dist[str(k)]['p95'] for k in ks]
    ax.fill_between(ks, lo, hi, color=FLOOR, alpha=0.18, label='5%-95% of 6474 descendants')
    ax.plot(ks, med, color=FLOOR, lw=2, label='median')
    ax.plot(ks, best, color=FLOOR, lw=1, ls='--', label='best curve at each k')
    try:
        scale = load('run08-subspaces/scaling.json')
        for cid, color in [('O51-67', CRATER), ('O16-57', ACCENT)]:
            if cid in scale:
                r = scale[cid]['ratios']
                ax.plot(ks, [r[str(k)] for k in ks], color=color, lw=1.4, marker='o', ms=3,
                        label='%s (%s)' % (cid, scale[cid]['candidate']))
    except FileNotFoundError:
        pass
    ax.axhline(1.0, color=INK, lw=0.8)
    ax.axhline(0.8, color=CRATER, lw=0.8, ls=':', label='20% gate')
    ax.set_xlabel('subspace dimension k (each curve keeps its k=8..10 persistent candidate)')
    ax.set_ylabel('modelled target count / optimized E0')
    ax.set_title('Run-08: descendant-adapted subspaces converge to optimized E0')
    ax.legend(fontsize=7, frameon=False, ncol=2)
    save(fig, 'fig08-run08-subspaces')


def fig_run03():
    rank = load('run02-attribution/frobenius-duplicate-rank.json')
    ks = sorted(int(k) for k in rank)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    ax = axes[0]
    dist = [rank[str(k)]['distinct_targets'] for k in ks]
    excess = [rank[str(k)]['duplicate_rows'] // 2 for k in ks]
    ax.bar(ks, excess, color=CRATER)
    for k, e, d in zip(ks, excess, dist):
        ax.text(k, e, '%d\n(%.3f%%)' % (e, 100 * e / (d + e)), ha='center', va='bottom', fontsize=8)
    ax.set_title('E0 duplicate excess (polynomial basis)')
    ax.set_xlabel('k')
    ax.set_ylabel('eligible - distinct')
    ax.set_xticks(ks)
    ax.set_ylim(0, max(excess) * 1.35)
    ax = axes[1]
    m83f = [100 * e / (d + e) for e, d in zip(excess, dist)]
    ecc = {5: 8 / 668, 6: 28 / 10868, 7: 60 / 79848}
    ax.plot(ks, m83f, marker='o', color=CRATER, label='F_(2^83): 2P_w + P_(w^2) - P_(w^4) = O')
    ax.plot(ks, [100 * ecc[k] for k in ks], marker='s', color=MUTED, label='ECC2K-130: 2P_3 + P_5 + P_17 = O')
    ax.set_yscale('log')
    ax.set_title('duplicate share of eligible triples')
    ax.set_xlabel('k')
    ax.set_ylabel('% of eligible')
    ax.set_xticks(ks)
    ax.legend(fontsize=7, frameon=False)
    ax = axes[2]
    cols = [rank[str(k)]['x_columns'] for k in ks]
    ax.plot(ks, cols, marker='o', color=FLOOR, label='x columns')
    ax.plot(ks, [rank[str(k)]['rank_one_witness_per_target'] for k in ks], ls='--', marker='x', color=INK,
            label='rank, one witness per target')
    ax.plot(ks, [rank[str(k)]['rank_with_all_duplicates'] for k in ks], ls=':', marker='+', color=ACCENT,
            label='rank with every duplicate')
    ax.set_title('coefficient rank mod ELL (duplicate differences: rank 1)')
    ax.set_xlabel('k')
    ax.set_xticks(ks)
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    save(fig, 'fig03-run03-collisions')


def fig_run05():
    fig, ax = plt.subplots(figsize=(9, 3.6))
    labels = ['E0: x of E[l]', 'E0: full E[l]', 'floor: full E[l]', 'ECC2K-130 E0: full E[263]',
              'ECC2K-130 floor: full E[263]']
    vals = [3236, 6472, 6472 * 6473, 2, 526]
    colors_ = [CRATER, CRATER, FLOOR, MUTED, MUTED]
    ax.barh(range(len(vals)), vals, color=colors_)
    ax.set_xscale('log')
    for i, v in enumerate(vals):
        ax.text(v * 1.15, i, 'F_(q^%s)' % format(v, ','), va='center', fontsize=8)
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlim(1, 1e10)
    ax.set_xlabel('extension degree over F_q (log scale)')
    ax.set_title('Conductor-prime torsion fields: l = 6473 at m = 83 (pi = 2514 I, 2514 a primitive root)\n'
                 'large-subgroup embedding degree: 74 bits on every curve of the class')
    save(fig, 'fig05-run05-torsion')


def fig_run06():
    y = load('run06-four-summand/yields.json')
    rho = load('run06-four-summand/rho-comparison.json')
    ids = y['curves']
    ks = sorted(int(k) for k in y['k'])
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.9))
    ax = axes[0]
    w = 0.8 / len(ids)
    for i, cid in enumerate(ids):
        ax.bar([k + (i - len(ids) / 2 + 0.5) * w for k in ks],
               [y['k'][str(k)]['natural'][cid]['raw_yield_vs_E0'] for k in ks], width=w,
               color=(CRATER if cid == 'E0' else [FLOOR, ACCENT, '#3a9d5d', '#7b52ab'][(i - 1) % 4]), label=cid)
    ax.axhline(1, color=INK, lw=0.8)
    ax.set_title('natural bases: eligible 4-tuples / E0')
    ax.set_xticks(ks)
    ax.set_xlabel('k')
    ax.legend(fontsize=7, frameon=False)
    ax = axes[1]
    for i, cid in enumerate(ids):
        if cid == 'E0':
            continue
        ax.plot(ks, [100 * y['k'][str(k)]['equal_cardinality']['deviation_vs_E0'][cid] for k in ks],
                marker='o', color=[FLOOR, ACCENT, '#3a9d5d', '#7b52ab'][(i - 1) % 4], label=cid)
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_title('equal cardinality: yield deviation vs E0 (%)')
    ax.set_xticks(ks)
    ax.set_xlabel('k')
    ax.legend(fontsize=7, frameon=False)
    ax = axes[2]
    model = {int(k): v for k, v in rho['ideal_model_log2_targets'].items()}
    mk = [k for k in sorted(model) if k <= 24]
    ax.plot(mk, [model[k] for k in mk], color=FLOOR, label='ideal half-density model: targets for 1.1b rows')
    for cid in ids:
        ax.scatter(ks, [rho['finite_log2_targets'][str(k)][cid] for k in ks], s=14,
                   color=(CRATER if cid == 'E0' else MUTED), zorder=4)
    ax.axhline(rho['rho']['signed_frobenius_log2'], color=CRATER, ls='--',
               label='signed-Frobenius rho 2^%.2f' % rho['rho']['signed_frobenius_log2'])
    ax.axvline(rho['crossover_k'], color=ACCENT, ls=':', label='crossover k = %d (no solver cost charged)' % rho['crossover_k'])
    ax.set_ylim(20, 70)
    ax.set_xlabel('k')
    ax.set_ylabel('log2 uniform targets')
    ax.set_title('relation targets versus rho')
    ax.legend(fontsize=6.5, frameon=False)
    fig.tight_layout()
    save(fig, 'fig06-run06-four-summand')


def fig_run07():
    h = load('run07-halftrace/halftrace-results.json')
    rows = h['rows']
    ks = sorted({r['k'] for r in rows})
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    for cid in sorted({r['curve_id'] for r in rows}):
        rr = sorted((r for r in rows if r['curve_id'] == cid), key=lambda r: r['k'])
        axes[0].plot([r['k'] for r in rr], [r['pair_anf_terms'] for r in rr], marker='o', label='pair ' + cid)
        axes[0].plot([r['k'] for r in rr], [r['direct_anf_terms'] for r in rr], ls=':', marker='x', color=MUTED)
        axes[1].plot([r['k'] for r in rr], [r['pair_anf_degree'] for r in rr], marker='o')
        axes[1].plot([r['k'] for r in rr], [r['direct_anf_degree'] for r in rr], ls=':', marker='x', color=MUTED)
    axes[1].plot(ks, [3 * k - 1 for k in ks], color=INK, lw=0.8, ls='--', label='3k-1 pair variables')
    axes[0].set_yscale('log')
    axes[0].set_title('invalid-pair indicator: ANF terms (dotted: direct x-membership)')
    axes[1].set_title('ANF degree')
    for ax in axes:
        ax.set_xlabel('k')
        ax.set_xticks(ks)
        ax.legend(fontsize=6.5, frameon=False)
    fig.tight_layout()
    save(fig, 'fig07-run07-halftrace')


def fig_run09():
    a = load('run09-frobenius-atlas/analysis.json')
    rows = a['orbits']
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6))
    axes[0].bar([r['orbit'] for r in rows], [r['images_k5']['coverage_gain'] for r in rows], color=FLOOR)
    axes[0].axhline(83, color=CRATER, ls='--', lw=0.8, label='83 chart solves')
    axes[0].set_title('k=5 atlas coverage gain over the best chart, per orbit')
    axes[0].set_xlabel('Frobenius orbit')
    axes[0].legend(fontsize=7, frameon=False)
    axes[1].bar([r['orbit'] for r in rows], [r['images_k5']['total_solver_work_vs_best'] for r in rows],
                color=ACCENT)
    axes[1].set_title('total solver work vs best single chart')
    axes[1].set_xlabel('Frobenius orbit')
    fig.tight_layout()
    save(fig, 'fig09-run09-frobenius-atlas')


def fig_run10():
    g = load('run10-horizontal/horizontal-graph.json')['summary']
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6))
    ls = sorted(int(l) for l in g)
    axes[0].bar([str(l) for l in ls], [g[str(l)]['component_sizes'][0] for l in ls], color=FLOOR)
    for i, l in enumerate(ls):
        axes[0].text(i, g[str(l)]['component_sizes'][0], '%d x %d' % (g[str(l)]['components'],
                                                                   g[str(l)]['component_sizes'][0]),
                     ha='center', va='bottom', fontsize=8)
    axes[0].set_title('horizontal l-isogeny graph on the 6474-curve floor: cycle length')
    axes[0].set_xlabel('l')
    axes[0].set_ylim(0, 7400)
    try:
        at = load('run10-horizontal/horizontal-atlas.json')
        labels = ['column union / largest chart', 'coverage gain', 'total work vs best']
        vals = [at['union_over_largest_chart'], at['coverage_gain'], at['total_solver_work_vs_best']]
        axes[1].bar(labels, vals, color=[FLOOR, ACCENT, CRATER])
        for i, v in enumerate(vals):
            axes[1].text(i, v, '%.1f' % v, ha='center', va='bottom', fontsize=8)
        axes[1].set_title('degree-11 atlas over %d charts (%d orbits)' % (at['cycle_length'], at['orbits_in_cycle']))
    except FileNotFoundError:
        axes[1].set_axis_off()
    fig.tight_layout()
    save(fig, 'fig10-run10-horizontal')


FIGURES = {'volcano': fig_volcano, 'run01': fig_run01, 'run03': fig_run03, 'run05': fig_run05,
           'run06': fig_run06, 'run07': fig_run07, 'run08': fig_run08, 'run09': fig_run09, 'run10': fig_run10}


if __name__ == '__main__':
    names = sys.argv[1:] or list(FIGURES)
    for name in names:
        FIGURES[name]()
