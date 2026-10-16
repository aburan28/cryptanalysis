"""Summaries and figures for the floor census and the representation screen."""
import json, math, statistics as st
import twist
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

GATE = {0: 0.001, 1: 0.05}   # PROTOCOL.md "clearly beats" margins


def load(name):
    p = twist.OUT / name
    if not p.exists() and (twist.OUT / (name + '.gz')).exists():   # committed archives are gzipped
        import gzip
        return [json.loads(l) for l in gzip.open(twist.OUT / (name + '.gz'), 'rt').read().splitlines() if l]
    return [json.loads(l) for l in p.read_text().splitlines() if l] if p.exists() else []


def summarise(a2):
    floor = load('floor-a%d.jsonl' % a2); reps = load('reps-a%d.jsonl' % a2)
    if not floor: return None
    e0 = next(r for r in floor if r['curve_id'] == 'E0')
    fl = [r for r in floor if r['curve_id'] != 'E0' and r['matched_eligible'] is not None]
    short = [r['curve_id'] for r in floor if r['matched_eligible'] is None]
    Y = [r['Y_matched'] for r in fl]
    mean_count = st.mean(r['matched_eligible'] for r in fl)
    s = dict(curve=twist.CURVES[a2]['name'], h=twist.CURVES[a2]['h'], k=e0['k'], S=e0['matched_size'],
             floor_curves=len(fl), below_S=short,
             crater=dict(x_count=e0['x_count'], eligible=e0['eligible'], matched_eligible=e0['matched_eligible'],
                         Y_matched=e0['Y_matched']),
             floor_Y=dict(mean=st.mean(Y), sd=st.pstdev(Y), min=min(Y), max=max(Y)),
             poisson_sd_Y=1 / math.sqrt(mean_count) if a2 == 1 else None,
             crater_rank_from_top=1 + sum(y > e0['Y_matched'] for y in Y),
             crater_z=(e0['Y_matched'] - st.mean(Y)) / st.pstdev(Y) if st.pstdev(Y) else None,
             floor_x_count=dict(mean=st.mean(r['x_count'] for r in fl), min=min(r['x_count'] for r in fl),
                                max=max(r['x_count'] for r in fl)),
             gate_margin=GATE[a2],
             floor_beating_crater_by_gate=[r['curve_id'] for r in fl if r['Y_matched'] > e0['Y_matched'] * (1 + GATE[a2])],
             top5=sorted(((r['Y_matched'], r['curve_id']) for r in fl), reverse=True)[:5],
             order_checks_all_passed=all(r['order_checks'] >= 1 for r in floor))
    if reps:
        R = [r['Y_matched'] for r in reps if r['Y_matched'] is not None]
        s['reps'] = dict(n=len(R), mean=st.mean(R), sd=st.pstdev(R), min=min(R), max=max(R),
                         beating_crater_by_gate=[r['curve_id'] for r in reps
                                                 if r['Y_matched'] and r['Y_matched'] > e0['Y_matched'] * (1 + GATE[a2])],
                         x_count_range=[min(r['x_count'] for r in reps), max(r['x_count'] for r in reps)])
    return s, floor, reps


THEORY_S = {0: math.sqrt(math.pi / 2), 1: math.sqrt(math.pi / 4), 2: math.sqrt(math.pi / (4 * 83))}
BAND = (0, 0.1, 1)     # GAE per unpriced operation (canonicalisation squaring), AGENTS.md / crypto CLAUDE.md 5a


def rho_summary():
    rows = load('rho-a1.jsonl')
    if not rows: return None
    out = {}
    for grp, sel in (('crater', lambda r: r['curve_id'] == 'E0'), ('floor', lambda r: r['curve_id'] != 'E0')):
        for mode in (0, 1, 2):
            R = [r for r in rows if sel(r) and r['mode'] == mode]
            if not R: continue
            S = [r['S'] for r in R]
            sq = sum(r['canon_squarings'] for r in R) / sum(r['steps'] for r in R)
            # charged group ops: walk steps + walk starts + multipliers (all counted adds/doubles)
            G = [r['total_group_ops'] / twist.N53 ** 0.5 for r in R]
            out['%s_mode%d' % (grp, mode)] = dict(
                solves=len(R), curves=sorted({r['curve_id'] for r in R}), all_verified=all(r['k_ok'] == 1 for r in R),
                S_steps_mean=st.mean(S), S_steps_se=st.stdev(S) / math.sqrt(len(S)) if len(S) > 1 else None,
                S_theory=THEORY_S[mode], S_group_ops_mean=st.mean(G),
                squarings_per_step=sq,
                S_priced={str(w): st.mean(G) * (1 + w * sq) for w in BAND},
                wall_s_mean=st.mean(r['wall_s'] for r in R), escapes=sum(r['escapes'] for r in R),
                restarts=sum(r['restarts'] for r in R))
    return out


def figure(results):
    fig, axes = plt.subplots(1, len(results), figsize=(6.2 * len(results), 4.3))
    axes = axes if len(results) > 1 else [axes]
    for ax, (a2, (s, floor, reps)) in zip(axes, results.items()):
        Y = [r['Y_matched'] for r in floor if r['curve_id'] != 'E0' and r['Y_matched'] is not None]
        lo, hi = min(Y), max(Y)
        if reps: lo, hi = min(lo, s['reps']['min']), max(hi, s['reps']['max'])
        bins = [lo + (hi - lo) * i / 60 for i in range(61)]
        ax.hist(Y, bins=bins, color='#e09f3e', alpha=.8, label='floor, %d curves (conductor 6473)' % len(Y))
        if reps:
            ax.hist([r['Y_matched'] for r in reps], bins=bins, color='#3b6fb6', alpha=.6,
                    label='crater, %d field representations' % s['reps']['n'], weights=[len(Y) / s['reps']['n'] / 8] * s['reps']['n'])
        ax.axvline(s['crater']['Y_matched'], color='#9e2a2b', lw=2, label='crater E0, polynomial basis')
        ax.axvline(s['crater']['Y_matched'] * (1 + s['gate_margin']), color='#9e2a2b', ls='--', lw=1,
                   label='"clearly beats" gate (+%g %%)' % (100 * s['gate_margin']))
        ax.set_xlabel('normalised 4-summand yield at equal cardinality S = %d\n(eligible / (16·C(S,4)/h)), k = %d' % (s['S'], s['k']))
        ax.set_ylabel('curves' + (' (representations scaled ×%.1f)' % (len(Y) / s['reps']['n'] / 8) if reps else ''))
        ax.set_title('%s: y²+xy=x³+%sb over GF(2^83), h = %d' % (s['curve'], 'x²+' if a2 else '', s['h']), fontsize=9)
        ax.legend(fontsize=7)
        if a2 == 0: ax.ticklabel_format(useOffset=False, style='plain', axis='x')
    fig.tight_layout()
    for ext in ('png', 'svg', 'pdf'):
        fig.savefig(twist.OUT / ('yield-census.%s' % ext), dpi=150)


def rho_figure():
    rows = load('rho-a1.jsonl')
    if not rows: return
    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    groups = [('E0', 2, 'crater\n{±τ^i P}'), ('E0', 1, 'crater\n{±P}'), ('E0', 0, 'crater\nplain'),
              ('floor', 1, 'floor (3 curves)\n{±P}'), ('floor', 0, 'floor (3 curves)\nplain')]
    for i, (g, mode, lab) in enumerate(groups):
        R = [r for r in rows if r['mode'] == mode and ((r['curve_id'] == 'E0') == (g == 'E0'))]
        S = [r['S'] for r in R]
        ax.scatter([i + (j - len(S) / 2) * 0.025 for j in range(len(S))], S, s=14, color='#3b6fb6', zorder=3)
        m = st.mean(S); se = st.stdev(S) / math.sqrt(len(S))
        ax.errorbar([i + 0.28], [m], yerr=[1.96 * se], fmt='s', color='#9e2a2b', capsize=4, zorder=4)
        ax.hlines(THEORY_S[mode], i - 0.35, i + 0.35, color='#444', ls='--', lw=1)
    ax.set_xticks(range(len(groups))); ax.set_xticklabels([g[2] for g in groups], fontsize=8)
    ax.set_yscale('log'); ax.set_ylabel('S = walk steps / sqrt(n)   (n = 8569786107849059)')
    ax.set_title('Pollard rho on the a2 = 1 twist, f83x, one walk per solve, every scalar verified\n'
                 'dots: solves; red: mean ± 1.96 se; dashed: sqrt(pi/2), sqrt(pi/4), sqrt(pi/(4·83))', fontsize=9)
    fig.tight_layout()
    for ext in ('png', 'svg'):
        fig.savefig(twist.OUT / ('rho-a1.%s' % ext), dpi=150)


def main():
    results = {}
    for a2 in (0, 1):
        r = summarise(a2)
        if r: results[a2] = r
    summary = {a2: r[0] for a2, r in results.items()}
    rs = rho_summary()
    if rs:
        summary['rho_a1'] = rs
        if 1 in results:   # IC at this k against measured rho, same subgroup (lower bound on IC queries)
            c = results[1][0]['crater']
            q = math.ceil(1.1 * c['x_count']) * (twist.N53 - 1) / c['eligible']
            summary['ic_k12_vs_rho_a1'] = dict(
                rows_needed=math.ceil(1.1 * c['x_count']), eligible=c['eligible'],
                log2_queries_for_rows_lower_bound=math.log2(q),
                log2_rho_steps_mode2_measured=math.log2(rs['crater_mode2']['S_steps_mean'] * twist.N53 ** 0.5),
                note='k = 12 subspace base; the N83 pipeline uses ~5.7e5 projected points and a root index, not this base')
    (twist.OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    figure(results)
    rho_figure()
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
