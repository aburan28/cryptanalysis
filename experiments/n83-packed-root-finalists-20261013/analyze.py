#!/usr/bin/env python3
"""Apply the frozen paired-mean-probe decision rule to 256 public points."""

import json
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 20261013256
REPS = 10000


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def main():
    protocol = json.loads((HERE / 'protocol.json').read_text())
    verified = json.loads((HERE / 'verification.json').read_text())
    assert verified['status'] == 'PASS' and verified['complete_arm_count'] == 2
    assert verified['censored_arms'] == [] and all(verified['checks'].values())
    assert protocol['arms'] == ['K1271', 'K1200'] and protocol['target_count'] == 256
    k1200 = verified['per_target']['K1200']
    k1271 = verified['per_target']['K1271']
    probes1200, probes1271 = k1200['probes'], k1271['probes']
    assert len(probes1200) == len(probes1271) == 256
    differences = [a - b for a, b in zip(probes1200, probes1271)]
    rng = random.Random(SEED)
    boot = []
    for _ in range(REPS):
        boot.append(statistics.mean(differences[rng.randrange(256)] for _ in range(256)))
    interval = [percentile(boot, 0.025), percentile(boot, 0.975)]
    if interval[0] > 0:
        decision = 'K1271'
    elif interval[1] < 0:
        decision = 'K1200'
    else:
        decision = 'unresolved'
    rows = []
    for name in ('K1200', 'K1271'):
        probes = verified['per_target'][name]['probes']
        online = verified['per_target'][name]['online_ms']
        details = verified['details'][name]
        rows.append({'arm': name,
            'actual_usable_points': details['actual_usable_points'],
            'effective_columns': details['effective_columns'],
            'mean_probes': statistics.mean(probes),
            'median_probes': statistics.median(probes),
            'p90_probes': percentile(probes, 0.9),
            'max_probes': max(probes),
            'pointwise_win_count': sum(a < b for a, b in zip(
                probes, verified['per_target']['K1271' if name == 'K1200' else 'K1200']['probes'])),
            'mean_online_ms_exploratory': statistics.mean(online),
            'median_online_ms_exploratory': statistics.median(online),
            'full_process_s': details['process_wall_s'],
            'index_ms': details['index_ms'],
            'rank_ms': details['rank_ms'],
            'sampled_peak_rss_bytes': details['sampled_peak_rss_bytes']})
    result = {'kind': 'n83_a1_packed_root_256_point_finalist_analysis_v1',
        'target_count': 256,
        'metric': 'paired arithmetic mean target probes, K1200 minus K1271',
        'paired_mean_probe_difference': statistics.mean(differences),
        'paired_median_probe_difference': statistics.median(differences),
        'paired_bootstrap_95': interval,
        'bootstrap_seed': SEED, 'bootstrap_repetitions': REPS,
        'decision_by_frozen_rule': decision,
        'observed_mean_winner': min(rows, key=lambda row: row['mean_probes'])['arm'],
        'timing_status': 'shared Mac CPU; exploratory; no controlled speedup from this secondary panel',
        'rows': rows}
    with (HERE / 'analysis.json').open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write('\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
