"""Analysis of the frozen rho-arm protocol (protocol.json).

    sage -python analyze.py [RESULTS_DIR]     (default: results/)

Reads RESULTS_DIR/arms.jsonl and runtime-info.json, writes
RESULTS_DIR/summary.json, report/report.md, figures/arms.{svg,png} and
report/report.pdf. Only rows of this run enter any statistic; the 2026-09
records (../results/tau-*.jsonl) are read for the operation-count replay check
alone.
"""

import glob
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import rho_frob as rf  # noqa: E402

PROTO = json.load(open(os.path.join(HERE, 'protocol.json')))
R_ORDER = PROTO['curve']['r']
SQRT_R = math.sqrt(R_ORDER)
N = 19
FLOOR = math.sqrt(math.pi / (4 * N))
BOOT_N, BOOT_SEED = 10000, 20261014
ARMS = ('base', 'tau6', 'rho')
COLORS = {'base': '#3069A0', 'tau6': '#C45132', 'rho': '#3B8C4A'}
LABELS = {'base': 'baseline subspace base (dim 10)', 'tau6': 'tau-orbit base (dim 6)',
          'rho': 'signed-Frobenius rho (mean of 64)'}


def load_rows(rdir):
    rows = []
    path = os.path.join(rdir, 'arms.jsonl')
    if os.path.exists(path):
        for line in open(path):
            if line.strip():
                rows.append(json.loads(line))
    return rows


def geo(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def boot_geo(xs):
    rng = random.Random(BOOT_SEED)
    m = len(xs)
    if m < 2:
        return [None, None]
    lg = [math.log(x) for x in xs]
    vals = sorted(math.exp(sum(lg[rng.randrange(m)] for _ in range(m)) / m) for _ in range(BOOT_N))
    return [vals[int(0.025 * BOOT_N)], vals[int(0.975 * BOOT_N) - 1]]


def boot_mean(xs):
    rng = random.Random(BOOT_SEED)
    m = len(xs)
    if m < 2:
        return [None, None]
    vals = sorted(sum(xs[rng.randrange(m)] for _ in range(m)) / m for _ in range(BOOT_N))
    return [vals[int(0.025 * BOOT_N)], vals[int(0.975 * BOOT_N) - 1]]


def ratio_block(name, num, den, scal):
    per = {i: num[i] / den[i] for i in scal}
    xs = [per[i] for i in scal]
    if not xs:
        return {'name': name, 'n': 0}
    g, ci = geo(xs), boot_geo(xs)
    blk = {'name': name, 'n': len(xs), 'per_scalar': per, 'geomean': g, 'ci95': ci}
    if ci[0] is not None:
        blk['online_speedup_rho_over_X'] = 1 / g
        blk['online_speedup_ci95'] = [1 / ci[1], 1 / ci[0]]
    return blk


def decide_vs_rho(blk):
    lo, hi = blk.get('ci95', [None, None])
    if lo is None:
        return 'no data'
    if hi < 1:
        return 'X costs less CPU than matched rho (exploratory; needs Tier 1 replication on an independent host)'
    if lo > 1:
        return 'X costs more CPU than matched rho: not an advance against rho on E0/F_2^19'
    return 'inconclusive against rho'


def decide_base_tau(blk):
    lo, hi = blk.get('ci95', [None, None])
    if lo is None:
        return 'no data'
    if lo > 1:
        return 'orbit-base speedup over the baseline replicates within this run'
    if hi < 1:
        return 'orbit-base speedup reverses in this run'
    return 'inconclusive'


def replay_nominal_ops(arm, ii, count):
    """Replay the arm's rng to recover the (alpha, beta) of every target and
    count double-and-add group operations of alpha P + beta Q (+1 add)."""
    rng = random.Random(PROTO['arms'][arm]['rng_seed'] % ii)
    shifts = list(range(N))
    ops = 0
    for _ in range(count):
        al, be = rng.randrange(1, R_ORDER), rng.randrange(1, R_ORDER)
        ops += rf.nominal_mul_ops(al) + rf.nominal_mul_ops(be) + 1
        if arm == 'tau6':
            rng.shuffle(shifts)
    return ops


def replay_check(rows):
    old = {}
    for path in glob.glob(os.path.join(PARENT, 'results', 'tau-*.jsonl')):
        for line in open(path):
            r = json.loads(line)
            if r['curve'] in ('base', 'tau6'):
                old[(r['curve'], r['instance'])] = r
    out = []
    for r in rows:
        if r['arm'] == 'rho':
            continue
        o = old.get((r['arm'], r['instance']))
        if o is None:
            continue
        f = 'attempts' if r['arm'] == 'base' else 'gb_calls'
        out.append({'arm': r['arm'], 'instance': r['instance'], 'field': f,
                    'this_run': r.get(f), 'record_2026_09': o.get(f), 'equal': r.get(f) == o.get(f)})
    return out


def analyse(rdir):
    rows = load_rows(rdir)
    info_path = os.path.join(rdir, 'runtime-info.json')
    info = json.load(open(info_path)) if os.path.exists(info_path) else {}
    by = {(r['instance'], r['arm']): r for r in rows}
    complete = sorted(i for i in range(10) if all((i, a) in by for a in ARMS))
    verified = [i for i in complete if all(by[(i, a)]['correct'] for a in ARMS)]
    cpu = {a: {i: by[(i, a)]['cpu_s'] for i in verified} for a in ARMS}
    rho_rep0 = {i: by[(i, 'rho')]['cpu_s_rep0'] for i in verified}
    rho_rec = {i: by[(i, 'rho')]['cpu_s_to_recovery'] for i in verified}
    wall = {a: {i: (by[(i, a)]['wall_s'] if a == 'rho' else by[(i, a)].get('total_s')) for i in verified}
            for a in ARMS}

    # Rho: every solve of the run.
    solves = [x for r in rows if r['arm'] == 'rho' for x in r['reps']]
    S_steps = [x['steps'] / SQRT_R for x in solves]
    S_ops = [x['group_ops'] / SQRT_R for x in solves]
    rho_ops_total = sum(x['group_ops'] for x in solves)
    rho_cpu_total = sum(x['cpu_s'] for x in solves)
    cpu_per_op = rho_cpu_total / rho_ops_total if rho_ops_total else None
    rho = {'solves': len(solves), 'verified': sum(1 for x in solves if x['correct']),
           'fruitless_cycles': sum(x['fruitless'] for x in solves),
           'restarts': sum(x['restarts'] for x in solves),
           'mean_steps': sum(x['steps'] for x in solves) / len(solves) if solves else None,
           'mean_group_ops': rho_ops_total / len(solves) if solves else None,
           'S_steps_mean': sum(S_steps) / len(S_steps) if solves else None,
           'S_steps_ci95': boot_mean(S_steps), 'S_ops_mean': sum(S_ops) / len(S_ops) if solves else None,
           'S_ops_ci95': boot_mean(S_ops), 'floor_S': FLOOR, 'cpu_s_per_group_op': cpu_per_op}
    if solves:
        rho['S_steps_over_floor'] = rho['S_steps_mean'] / FLOOR
        rho['S_steps_over_floor_ci95'] = [c / FLOOR if c else None for c in rho['S_steps_ci95']]
        gate = rho['verified'] == len(solves) and 0.8 <= rho['S_steps_over_floor'] <= 1.5
        rho['validity_gate'] = 'pass' if gate else 'fail'

    # Per-arm table, unit S.
    table = {}
    for a in ARMS:
        if not verified:
            break
        c = [cpu[a][i] for i in verified]
        t = {'cpu_s_mean': sum(c) / len(c), 'cpu_s_per_scalar': cpu[a]}
        if cpu_per_op:
            t['S_cpu_equiv_mean'] = t['cpu_s_mean'] / cpu_per_op / SQRT_R
        if a == 'base':
            att = [by[(i, a)]['attempts'] for i in verified]
            nom = [replay_nominal_ops(a, i, by[(i, a)]['attempts']) for i in verified]
            t.update({'attempts_mean': sum(att) / len(att), 'gb_calls_mean':
                      sum(by[(i, a)]['gb_calls'] for i in verified) / len(verified),
                      'nominal_group_ops_mean': sum(nom) / len(nom), 'S_nominal_ic': sum(nom) / len(nom) / SQRT_R})
        elif a == 'tau6':
            nom = [replay_nominal_ops(a, i, by[(i, a)]['targets']) for i in verified]
            t.update({'targets_mean': sum(by[(i, a)]['targets'] for i in verified) / len(verified),
                      'gb_calls_mean': sum(by[(i, a)]['gb_calls'] for i in verified) / len(verified),
                      'nominal_group_ops_mean': sum(nom) / len(nom), 'S_nominal_ic': sum(nom) / len(nom) / SQRT_R})
        else:
            t.update({'steps_mean': rho['mean_steps'], 'group_ops_mean': rho['mean_group_ops'],
                      'S_steps_mean': rho['S_steps_mean'], 'S_ops_mean': rho['S_ops_mean']})
        table[a] = t

    prim = {'base_over_rho': ratio_block('base_over_rho', cpu['base'], cpu['rho'], verified),
            'tau6_over_rho': ratio_block('tau6_over_rho', cpu['tau6'], cpu['rho'], verified)}
    sec = {'base_over_tau6': ratio_block('base_over_tau6', cpu['base'], cpu['tau6'], verified)}
    sens = {'rep0': {k: ratio_block(k, cpu[k.split('_')[0]], rho_rep0, verified) for k in prim},
            'rho_to_recovery': {k: ratio_block(k, cpu[k.split('_')[0]], rho_rec, verified) for k in prim},
            'wall': {k: ratio_block(k, wall[k.split('_')[0]], wall['rho'], verified) for k in prim}}
    status = 'complete' if len(verified) >= 9 else 'incomplete'
    decisions = {k: decide_vs_rho(v) for k, v in prim.items()}
    decisions['base_over_tau6'] = decide_base_tau(sec['base_over_tau6'])
    if rho.get('validity_gate') == 'fail':
        decisions['note'] = 'rho validity gate failed: X_over_rho conclusions are provisional'
    if status == 'incomplete':
        decisions['note_incomplete'] = 'fewer than 9 scalars with all three arms verified: result incomplete'
    summary = {'protocol': PROTO['id'], 'status': status, 'scalars_complete': complete,
               'scalars_verified': verified, 'failed_rows': [{'instance': r['instance'], 'arm': r['arm']}
                                                             for r in rows if not r['correct']],
               'tier': PROTO['environment']['tier'], 'runtime': {k: info.get(k) for k in (
                   'sage_version', 'cpu_model', 'nproc', 'github', 'protocol_sha256', 'started_utc',
                   'finished_utc', 'setup_cpu_s')},
               'rho': rho, 'table': table, 'primary': prim, 'secondary': sec, 'sensitivity': sens,
               'decisions': decisions, 'replay_check': replay_check(rows)}
    return summary, rows, by, verified


def fmt(x, d=3):
    if x is None:
        return 'n/a'
    if abs(x) >= 1000 or (abs(x) < 0.01 and x != 0):
        return '%.3g' % x
    return '%.*f' % (d, x)


def ci(blk):
    c = blk.get('ci95', [None, None])
    return '%s (%s-%s)' % (fmt(blk.get('geomean')), fmt(c[0]), fmt(c[1]))


def report_md(summ):
    t, p, s, rho = summ['table'], summ['primary'], summ['secondary'], summ['rho']
    L = ['# Matched signed-Frobenius rho arm, E0/F_2^19', '',
         'Protocol `%s` (frozen before data, `protocol.json`, sha256 `%s`). Status: **%s** (%d of 10 scalars '
         'with all three arms verified). Tier: %s' % (summ['protocol'], summ['runtime'].get('protocol_sha256'),
                                                    summ['status'], len(summ['scalars_verified']), summ['tier']),
         '', 'Host: %s, %s logical CPUs, Sage %s, commit `%s`, run %s.' % (
             summ['runtime'].get('cpu_model'), summ['runtime'].get('nproc'), summ['runtime'].get('sage_version'),
             (summ['runtime'].get('github') or {}).get('GITHUB_SHA'),
             (summ['runtime'].get('github') or {}).get('GITHUB_RUN_ID')), '',
         'All three arms ran in one process, interleaved scalar by scalar (`protocol.json` order). '
         'No number from the 2026-09 taucmp run enters these statistics.', '',
         '## CPU per complete ECDLP (measured, this run only)', '',
         '| arm | CPU s / ECDLP (mean) | operations | S | S_cpu-equiv | CPU / rho (geo. mean, 95% CI) |',
         '|---|---:|---|---:|---:|---:|']
    if t:
        L.append('| %s | %s | %s attempts, %s GB calls, %s nominal group ops | %s (nominal, excludes GB) | %s | %s |' % (
            LABELS['base'], fmt(t['base']['cpu_s_mean'], 1), fmt(t['base']['attempts_mean'], 1),
            fmt(t['base']['gb_calls_mean'], 1), fmt(t['base']['nominal_group_ops_mean'], 0),
            fmt(t['base']['S_nominal_ic']), fmt(t['base'].get('S_cpu_equiv_mean'), 0), ci(p['base_over_rho'])))
        L.append('| %s | %s | %s targets, %s GB calls, %s nominal group ops | %s (nominal, excludes GB) | %s | %s |' % (
            LABELS['tau6'], fmt(t['tau6']['cpu_s_mean'], 1), fmt(t['tau6']['targets_mean'], 1),
            fmt(t['tau6']['gb_calls_mean'], 1), fmt(t['tau6']['nominal_group_ops_mean'], 0),
            fmt(t['tau6']['S_nominal_ic']), fmt(t['tau6'].get('S_cpu_equiv_mean'), 0), ci(p['tau6_over_rho'])))
        L.append('| %s | %s | %s steps, %s group ops | %s steps, %s ops | %s | 1 |' % (
            LABELS['rho'], fmt(t['rho']['cpu_s_mean'], 4), fmt(t['rho']['steps_mean'], 1),
            fmt(t['rho']['group_ops_mean'], 1), fmt(t['rho']['S_steps_mean'], 4), fmt(t['rho']['S_ops_mean'], 4),
            fmt(t['rho'].get('S_cpu_equiv_mean'), 4)))
    L += ['', 'S = operations / sqrt(r), r = %d. S_cpu-equiv converts CPU seconds into rho group operations at '
          'this run\'s pooled rho CPU per operation (%s s); it is a calibrated conversion, not a count. '
          'The IC nominal S counts only the double-and-add work of building targets.' % (
              R_ORDER, fmt(rho.get('cpu_s_per_group_op'))), '',
          '## Statistics', '',
          '- base / rho CPU: %s; online speedup rho/base %s' % (ci(p['base_over_rho']),
                                                                fmt(p['base_over_rho'].get('online_speedup_rho_over_X'))),
          '- tau6 / rho CPU: %s; online speedup rho/tau6 %s' % (ci(p['tau6_over_rho']),
                                                                fmt(p['tau6_over_rho'].get('online_speedup_rho_over_X'))),
          '- base / tau6 CPU (within-run replication): %s' % ci(s['base_over_tau6']),
          '- rho steps / sqrt(r): %s (95%% CI %s-%s) against the floor sqrt(pi/(4n)) = %s: ratio %s (%s-%s), '
          '%s/%s logs verified, %s fruitless cycles, %s restarts; validity gate %s' % (
              fmt(rho.get('S_steps_mean'), 4), fmt((rho.get('S_steps_ci95') or [None])[0], 4),
              fmt((rho.get('S_steps_ci95') or [None, None])[1], 4), fmt(FLOOR, 4), fmt(rho.get('S_steps_over_floor')),
              fmt((rho.get('S_steps_over_floor_ci95') or [None])[0]),
              fmt((rho.get('S_steps_over_floor_ci95') or [None, None])[1]), rho.get('verified'), rho.get('solves'),
              rho.get('fruitless_cycles'), rho.get('restarts'), rho.get('validity_gate')), '',
          'Sensitivity (geometric means): rho rep 0 only: base %s, tau6 %s; rho CPU to recovery: base %s, tau6 %s; '
          'wall clock: base %s, tau6 %s.' % tuple(ci(summ['sensitivity'][k][m]) for k in ('rep0', 'rho_to_recovery', 'wall')
                                                   for m in ('base_over_rho', 'tau6_over_rho')), '',
          '## Decisions (pre-stated in protocol.json)', '']
    for k, v in summ['decisions'].items():
        L.append('- %s: %s' % (k, v))
    L += ['', '## Replay check (code path only)', '',
          'IC arms reuse the 2026-09 rng seeds, so their counts must equal the old records: %d/%d equal.' % (
              sum(1 for x in summ['replay_check'] if x['equal']), len(summ['replay_check'])), '',
          '## Figure', '', '![CPU per ECDLP by scalar and arm](../figures/arms.png)', '',
          'Failed or unverified rows: %s.' % (summ['failed_rows'] or 'none'), '']
    return '\n'.join(L)


def figures(summ, by, verified, rdir):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
    except ImportError:
        print('matplotlib not available: figures and PDF skipped')
        return
    fdir = os.path.join(HERE, 'figures')
    os.makedirs(fdir, exist_ok=True)
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={'width_ratios': [3, 2]})
    for k, a in enumerate(ARMS):
        xs = [i + (k - 1) * 0.22 for i in verified]
        ys = [by[(i, a)]['cpu_s'] for i in verified]
        ax.scatter(xs, ys, color=COLORS[a], label=LABELS[a], s=22, zorder=3)
        if a == 'rho':
            lo = [min(x['cpu_s'] for x in by[(i, a)]['reps']) for i in verified]
            hi = [max(x['cpu_s'] for x in by[(i, a)]['reps']) for i in verified]
            ax.vlines(xs, lo, hi, color=COLORS[a], alpha=.5, lw=1)
    ax.set_yscale('log')
    ax.set_xticks(range(10))
    ax.set_xlabel('planted scalar index (10 scalars, interleaved in one process)')
    ax.set_ylabel('CPU seconds per complete verified ECDLP (log)')
    ax.set_title('E0/F_2^19, r = %d: IC arms vs matched rho' % R_ORDER, fontsize=10)
    ax.grid(True, which='both', alpha=.25)
    ax.legend(fontsize=8, loc='center right')
    solves = [x for r in by.values() if r['arm'] == 'rho' for x in r['reps']]
    if solves:
        ax2.hist([x['steps'] / SQRT_R for x in solves], bins=30, color=COLORS['rho'], alpha=.8)
        ax2.axvline(FLOOR, color='k', ls='--', lw=1, label='floor sqrt(pi/(4n)) = %.4f' % FLOOR)
        ax2.axvline(summ['rho']['S_steps_mean'], color=COLORS['rho'], lw=1.5,
                    label='mean %.4f (n = %d)' % (summ['rho']['S_steps_mean'], len(solves)))
        ax2.set_xlabel('rho steps / sqrt(r)')
        ax2.set_ylabel('solves')
        ax2.set_title('signed-Frobenius rho, all solves', fontsize=10)
        ax2.legend(fontsize=8)
    fig.text(0.01, 0.01, 'exploratory tier (GitHub-hosted runner); bars: min-max over 64 rho solves; '
             'source: rho-arm-20261014/results/arms.jsonl', fontsize=7)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(os.path.join(fdir, 'arms.png'), dpi=150)
    fig.savefig(os.path.join(fdir, 'arms.svg'))
    rep = os.path.join(HERE, 'report')
    os.makedirs(rep, exist_ok=True)
    text = report_md(summ)
    with PdfPages(os.path.join(rep, 'report.pdf')) as pdf:
        lines = []
        for ln in text.split('\n'):
            while len(ln) > 120:
                cut = ln.rfind(' ', 0, 120)
                cut = cut if cut > 0 else 120
                lines.append(ln[:cut])
                ln = '    ' + ln[cut:].lstrip()
            lines.append(ln)
        for start in range(0, len(lines), 62):
            pg = plt.figure(figsize=(8.27, 11.69))
            pg.text(0.05, 0.97, '\n'.join(lines[start:start + 62]), va='top', family='monospace', fontsize=6.4)
            pdf.savefig(pg)
            plt.close(pg)
        pdf.savefig(fig)
    plt.close(fig)


def main():
    rdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'results')
    summ, rows, by, verified = analyse(rdir)
    json.dump(summ, open(os.path.join(rdir, 'summary.json'), 'w'), indent=1)
    rep = os.path.join(HERE, 'report')
    os.makedirs(rep, exist_ok=True)
    open(os.path.join(rep, 'report.md'), 'w').write(report_md(summ) + '\n')
    figures(summ, by, verified, rdir)
    print(json.dumps({'status': summ['status'], 'decisions': summ['decisions']}, indent=1))


if __name__ == '__main__':
    main()
