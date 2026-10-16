"""Analysis of outputs/rho-floor-a1.jsonl per PROTOCOL.md addendum: pooled S, one-way ANOVA across the
78 Frobenius-orbit representatives, permutation cross-check, figure.  Writes outputs/rho-floor-summary.json."""
import json, math, random, statistics as st
import twist
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt


def betacf(a, b, x):
    # continued fraction for the incomplete beta (Numerical Recipes, modified Lentz)
    tiny = 1e-300; qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny); h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c if abs(1 + aa / c) > tiny else tiny; h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c if abs(1 + aa / c) > tiny else tiny
        de = d * c; h *= de
        if abs(de - 1) < 1e-14: break
    return h


def betainc(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lb = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2): return math.exp(lb) * betacf(a, b, x) / a
    return 1 - math.exp(lb) * betacf(b, a, 1 - x) / b


def f_sf(F, d1, d2):
    return betainc(d2 / 2, d1 / 2, d2 / (d2 + d1 * F))


def anova(groups):
    allv = [v for g in groups for v in g]; gm = st.mean(allv); k = len(groups); n = len(allv)
    ssb = sum(len(g) * (st.mean(g) - gm) ** 2 for g in groups)
    ssw = sum((v - st.mean(g)) ** 2 for g in groups for v in g)
    d1, d2 = k - 1, n - k
    F = (ssb / d1) / (ssw / d2)
    return F, d1, d2


def main():
    rows = [json.loads(l) for l in (twist.OUT / 'rho-floor-a1.jsonl').read_text().splitlines() if l]
    crater = [json.loads(l) for l in (twist.OUT / 'rho-a1.jsonl').read_text().splitlines() if l]
    c1 = [r['S'] for r in crater if r['curve_id'] == 'E0' and r['mode'] == 1]
    c2 = [r['S'] for r in crater if r['curve_id'] == 'E0' and r['mode'] == 2]
    by = {}
    for r in rows: by.setdefault(r['curve_id'], []).append(r['S'])
    groups = [v for v in by.values() if len(v) == 2]
    S = [r['S'] for r in rows]
    F, d1, d2 = anova(groups)
    p = f_sf(F, d1, d2)
    # permutation cross-check (labels shuffled, 20000 draws, fixed seed)
    rng = random.Random(20261016); flat = [v for g in groups for v in g]; hits = 0; NP = 20000
    for _ in range(NP):
        rng.shuffle(flat)
        if anova([flat[2 * i:2 * i + 2] for i in range(len(groups))])[0] >= F: hits += 1
    out = dict(solves=len(rows), orbits=len(by), complete_orbits=len(groups),
               all_verified=all(r['k_ok'] == 1 for r in rows), restarts=sum(r['restarts'] for r in rows),
               S_mean=st.mean(S), S_se=st.stdev(S) / math.sqrt(len(S)), S_sd=st.stdev(S),
               S_theory=math.sqrt(math.pi / 4), S_min=min(S), S_max=max(S),
               crater_pm=dict(n=len(c1), mean=st.mean(c1), se=st.stdev(c1) / math.sqrt(len(c1))),
               crater_tau=dict(n=len(c2), mean=st.mean(c2), se=st.stdev(c2) / math.sqrt(len(c2))),
               floor_minus_crater_pm=st.mean(S) - st.mean(c1),
               floor_over_crater_tau=st.mean(S) / st.mean(c2),
               anova=dict(F=F, df=[d1, d2], p=p, permutation_p=(hits + 1) / (NP + 1), permutations=NP),
               lowest_orbit_means=sorted((st.mean(v), k) for k, v in by.items())[:3],
               wall_s_mean=st.mean(r['wall_s'] for r in rows), steps_total=sum(r['steps'] for r in rows))
    (twist.OUT / 'rho-floor-summary.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw=dict(width_ratios=[2.2, 1]))
    keys = sorted(by)
    for i, k in enumerate(keys):
        ax[0].scatter([i] * len(by[k]), by[k], s=9, color='#e09f3e')
    ax[0].axhline(out['S_theory'], color='#444', ls='--', lw=1, label='√(π/4) = 0.886')
    ax[0].axhline(out['S_mean'], color='#e09f3e', lw=1.5, label='floor mean %.3f ± %.3f (%d solves)' % (out['S_mean'], out['S_se'], len(S)))
    ax[0].axhline(out['crater_tau']['mean'], color='#3b6fb6', lw=1.5, label='crater {±τ^i P} mean %.3f' % out['crater_tau']['mean'])
    ax[0].set_xticks(range(0, len(keys), 6)); ax[0].set_xticklabels([keys[i] for i in range(0, len(keys), 6)], fontsize=7, rotation=45)
    ax[0].set_ylabel('S = walk steps / √n'); ax[0].set_yscale('log')
    ax[0].set_title('{±P} rho on one curve per Frobenius orbit of the 53-bit floor (2 solves each)\n'
                    'ANOVA across orbits F(%d,%d) = %.2f, p = %.2f (permutation p = %.2f)' % (d1, d2, F, p, out['anova']['permutation_p']), fontsize=9)
    ax[0].legend(fontsize=7, loc='lower right')
    bins = [i * 0.1 for i in range(0, 36)]
    ax[1].hist(S, bins=bins, color='#e09f3e', alpha=.8, density=True, label='floor {±P}')
    ax[1].hist(c1, bins=bins, color='#9e2a2b', alpha=.6, density=True, label='crater {±P} (%d)' % len(c1))
    # rho collision-time law for {±P}: steps ~ Rayleigh with mean sqrt(pi/4) in S units
    xs = [i * 0.02 for i in range(1, 176)]; sig2 = (out['S_theory'] / math.sqrt(math.pi / 2)) ** 2
    ax[1].plot(xs, [x / sig2 * math.exp(-x * x / (2 * sig2)) for x in xs], color='#444', lw=1, label='Rayleigh, mean 0.886')
    ax[1].set_xlabel('S'); ax[1].set_ylabel('density'); ax[1].legend(fontsize=7); ax[1].set_title('distribution of S', fontsize=9)
    fig.tight_layout()
    for ext in ('png', 'svg'): fig.savefig(twist.OUT / ('rho-floor-a1.%s' % ext), dpi=150)


if __name__ == '__main__':
    main()
