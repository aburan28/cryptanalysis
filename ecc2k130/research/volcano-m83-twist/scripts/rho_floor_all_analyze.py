"""Analysis of the all-curve 53-bit floor rho census (PROTOCOL.md addendum 2): reads every
outputs/rho-floor-all-a1.shard*.jsonl, checks coverage (6474 distinct curves, all verified), pooled S
against sqrt(pi/4), one-way ANOVA across the 78 Frobenius orbits (83 curves each), permutation check,
Rayleigh comparison; writes outputs/rho-floor-all-summary.json and outputs/rho-floor-all-a1.{png,svg}."""
import glob, json, math, random, statistics as st
import twist
from rho_floor_analyze import anova, f_sf
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    rows = []
    for p in sorted(glob.glob(str(twist.OUT / 'rho-floor-all-a1.shard*.jsonl'))):
        rows += [json.loads(l) for l in open(p).read().splitlines() if l]
    ids = [r['curve_id'] for r in rows]
    expected = {r['curve_id'] for r in twist.load_inventory() if r['curve_id'] != 'E0'}
    missing = sorted(expected - set(ids)); dup = len(ids) - len(set(ids))
    S = [r['S'] for r in rows]
    by = {}
    for r in rows: by.setdefault(r['curve_id'][:3], []).append(r['S'])
    groups = list(by.values())
    F, d1, d2 = anova(groups); p = f_sf(F, d1, d2)
    rng = random.Random(20261016); flat = S[:]; NP = 2000; hits = 0; sizes = [len(g) for g in groups]
    for _ in range(NP):
        rng.shuffle(flat); it = iter(flat)
        if anova([[next(it) for _ in range(s)] for s in sizes])[0] >= F: hits += 1
    theory = math.sqrt(math.pi / 4)
    # Rayleigh check: under the random-mapping model S^2 * 2 / (pi/2 * ...) -- compare quantiles of S/mean
    q = sorted(S); n = len(q); sig = st.mean(S) / math.sqrt(math.pi / 2)
    ks = max(abs((i + 1) / n - (1 - math.exp(-q[i] ** 2 / (2 * sig ** 2)))) for i in range(n))
    out = dict(solves=len(rows), distinct_curves=len(set(ids)), expected_curves=len(expected), missing=missing[:20],
               n_missing=len(missing), duplicates=dup, all_verified=all(r['k_ok'] == 1 for r in rows),
               restarts=sum(r['restarts'] for r in rows), steps_total=sum(r['steps'] for r in rows),
               S_mean=st.mean(S), S_se=st.stdev(S) / math.sqrt(n), S_sd=st.stdev(S), S_theory=theory,
               S_mean_minus_theory_in_se=(st.mean(S) - theory) / (st.stdev(S) / math.sqrt(n)),
               anova=dict(F=F, df=[d1, d2], p=p, permutation_p=(hits + 1) / (NP + 1), permutations=NP),
               rayleigh_ks_D=ks, rayleigh_ks_D_crit95=1.358 / math.sqrt(n),
               orbit_mean_range=[min(st.mean(g) for g in groups), max(st.mean(g) for g in groups)],
               wall_s_mean=st.mean(r['wall_s'] for r in rows))
    (twist.OUT / 'rho-floor-all-summary.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw=dict(width_ratios=[2.2, 1]))
    keys = sorted(by)
    ax[0].boxplot([by[k] for k in keys], showfliers=False, widths=0.6)
    ax[0].axhline(theory, color='#444', ls='--', lw=1, label='√(π/4) = 0.886')
    ax[0].axhline(out['S_mean'], color='#e09f3e', lw=1.5, label='all-curve mean %.3f ± %.3f (%d solves)' % (out['S_mean'], out['S_se'], n))
    ax[0].set_xticks(range(1, len(keys) + 1, 6)); ax[0].set_xticklabels(keys[::6], fontsize=7, rotation=45)
    ax[0].set_ylabel('S = walk steps / √n'); ax[0].legend(fontsize=7)
    ax[0].set_title('{±P} rho on every 53-bit floor curve, grouped by Frobenius orbit (83 curves each)\n'
                    'ANOVA F(%d,%d) = %.2f, p = %.2f (permutation p = %.2f)' % (d1, d2, F, p, out['anova']['permutation_p']), fontsize=9)
    ax[1].hist(S, bins=60, density=True, color='#e09f3e', alpha=.8, label='%d solves' % n)
    xs = [i * 0.02 for i in range(1, 201)]
    ax[1].plot(xs, [x / sig ** 2 * math.exp(-x * x / (2 * sig ** 2)) for x in xs], color='#444', lw=1, label='Rayleigh, same mean')
    ax[1].set_xlabel('S'); ax[1].legend(fontsize=7); ax[1].set_title('KS D = %.3f (95%% crit %.3f)' % (ks, out['rayleigh_ks_D_crit95']), fontsize=9)
    fig.tight_layout()
    for ext in ('png', 'svg'): fig.savefig(twist.OUT / ('rho-floor-all-a1.%s' % ext), dpi=150)


if __name__ == '__main__':
    main()
