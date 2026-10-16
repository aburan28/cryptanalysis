"""Summaries and figures for the floor census and the representation screen."""
import json, math, statistics as st
import twist
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

GATE = {0: 0.001, 1: 0.05}   # PROTOCOL.md "clearly beats" margins


def load(name):
    p = twist.OUT / name
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


def main():
    results = {}
    for a2 in (0, 1):
        r = summarise(a2)
        if r: results[a2] = r
    (twist.OUT / 'summary.json').write_text(json.dumps({a2: r[0] for a2, r in results.items()}, indent=1) + '\n')
    figure(results)
    for a2, r in results.items():
        print(json.dumps(r[0], indent=1))


if __name__ == '__main__':
    main()
