"""Editable source of the preregistration figures.

    python3 prereg_figures.py      (needs matplotlib)

figures/protocol.{svg,png}: interleaved schedule and the rho walk design
(drawn from protocol.json). figures/validation-steps.{svg,png}: rho step
counts of the pure-Python validation (validation/local-validation.json)
against the floor. Step counts only; no timing is plotted.
"""

import json
import math
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = json.load(open(os.path.join(HERE, 'protocol.json')))
COLORS = {'base': '#3069A0', 'tau6': '#C45132', 'rho': '#3B8C4A'}


def protocol_diagram():
    fig, ax = plt.subplots(figsize=(11, 5.2))
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 12)
    ax.axis('off')
    ax.text(0, 11.5, 'One job, one process, one host: 30 slots, scalar by scalar, arm order = permutation (i mod 6)',
            fontsize=10, weight='bold')
    w = {'base': 1.0, 'tau6': 1.0, 'rho': 1.0}
    for sl in PROTO['order']['slots']:
        x = sl['slot']
        a = sl['arm']
        ax.add_patch(FancyBboxPatch((x + 0.05, 9.2), w[a] - 0.1, 1.4, boxstyle='round,pad=0.02',
                                    fc=COLORS[a], ec='none', alpha=.9))
        ax.text(x + 0.5, 9.9, a, ha='center', va='center', fontsize=6, color='white', rotation=90)
    for i in range(10):
        ax.text(3 * i + 1.5, 8.7, 's%d=%d' % (i, PROTO['scalars'][i]), ha='center', fontsize=7)
        ax.plot([3 * i, 3 * i], [8.5, 10.8], color='#999', lw=.6)
    boxes = [
        (0.2, 4.6, 9.2, 3.2, COLORS['base'], 'base: ../ic.sage solveDlp',
         'x in span{1..z^9}, PolyBoRi S3, 2 summands\nrng tau:base:i (2026-09 seeds; counts\nmust replay exactly)\nCPU: first query .. left-kernel log'),
        (10.2, 4.6, 9.2, 3.2, COLORS['tau6'], 'tau6: ../tau.sage tauDlp',
         'tau-orbits of x in span{1..z^5}, 19 shifts\nrng tau:tau6:i (2026-09 seeds)\nCPU: first query .. left-kernel log'),
        (20.2, 4.6, 9.6, 3.2, COLORS['rho'], 'rho: rho_frob.solve x 64 reps',
         'classes of <tau,-1> (38 points), R = 16 adding walk\nM_i = alpha_i P + eps_i tau^e_i(Q), BLS look-ahead\nall classes stored; fruitless: escape to 2*min\nCPU: building M_i .. s*P == Q verified'),
    ]
    for x, y, bw, bh, c, title, body in boxes:
        ax.add_patch(FancyBboxPatch((x, y), bw, bh, boxstyle='round,pad=0.1', fc='white', ec=c, lw=1.6))
        ax.text(x + 0.3, y + bh - 0.4, title, fontsize=8.5, weight='bold', color=c, va='top')
        ax.text(x + 0.3, y + bh - 1.0, body, fontsize=7.2, va='top')
    ax.text(0.2, 3.4, 'Statistics (frozen): per-scalar CPU ratios base/rho, tau6/rho (primary), base/tau6 (secondary); '
            'geometric mean, 95% percentile bootstrap over scalars (10000, seed 20261014).', fontsize=7.8)
    ax.text(0.2, 2.7, 'Units: S = ops / sqrt(r), r = 130873; rho steps/sqrt(r) vs floor sqrt(pi/(4n)) = %.4f; '
            'IC CPU also as rho-op equivalents (calibrated in-run).' % math.sqrt(math.pi / 76), fontsize=7.8)
    ax.text(0.2, 2.0, 'Gate: all rho logs verified and S_steps/floor in [0.8, 1.5]. >= 9/10 scalars verified '
            'for a complete result; no scalar dropped in advance.', fontsize=7.8)
    ax.text(0.2, 1.3, 'Old 444 s / 70 s / 6.85x (results/tau-*.jsonl) enter no statistic; only their counts '
            'are compared, as a code-path replay check.', fontsize=7.8)
    ax.text(0.2, 0.4, 'source: rho-arm-20261014/protocol.json (frozen 2026-10-14, before data); '
            'editable: prereg_figures.py', fontsize=6.5, color='#555')
    for ext in ('svg', 'png'):
        fig.savefig(os.path.join(HERE, 'figures', 'protocol.' + ext), dpi=150)
    plt.close(fig)


def validation_hist():
    v = json.load(open(os.path.join(HERE, 'validation', 'local-validation.json')))
    g = v['generators'][0]
    steps = [x['steps'] for p in g['per_scalar'] for x in p['solves']]
    sq = math.sqrt(130873)
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.hist([s / sq for s in steps], bins=30, color=COLORS['rho'], alpha=.8)
    ax.axvline(g['floor_S'], color='k', ls='--', lw=1, label='floor sqrt(pi/(4n)) = %.4f' % g['floor_S'])
    ax.axvline(g['S_steps_mean'], color=COLORS['rho'], lw=1.5,
               label='mean %.4f, 95%% CI %.4f-%.4f' % (g['S_steps_mean'], *g['S_steps_ci95']))
    ax.set_xlabel('rho steps / sqrt(r)  (r = 130873)')
    ax.set_ylabel('solves')
    ax.set_title('Pure-Python validation: %d solves (10 scalars x 64), %d failures' % (len(steps), g['failures']),
                 fontsize=9)
    ax.legend(fontsize=7.5)
    fig.text(0.01, 0.01, 'step counts only; source: validation/local-validation.json', fontsize=6.5, color='#555')
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    for ext in ('svg', 'png'):
        fig.savefig(os.path.join(HERE, 'figures', 'validation-steps.' + ext), dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    os.makedirs(os.path.join(HERE, 'figures'), exist_ok=True)
    protocol_diagram()
    validation_hist()
