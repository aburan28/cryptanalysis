#!/usr/bin/env python3
"""Summarize the independently verified paired 32-point probe panel."""

import argparse
import json
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOOTSTRAP_SEED = 2026101301
BOOTSTRAP_REPS = 10000


def quantile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def bootstrap_mean_difference(values, reference, seed):
    assert len(values) == len(reference)
    differences = [a - b for a, b in zip(values, reference)]
    rng = random.Random(seed)
    means = []
    for _ in range(BOOTSTRAP_REPS):
        means.append(statistics.mean(differences[rng.randrange(len(differences))]
                                     for _ in differences))
    return [quantile(means, 0.025), quantile(means, 0.975)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    verification = json.loads((HERE / 'verification.json').read_text())
    assert verification['status'] in ('PASS', 'CENSORED')
    panel = verification['per_target']
    names = sorted(panel, key=lambda name: int(name[1:]))
    assert len(names) == verification['complete_arm_count'] >= 2
    count = len(next(iter(panel.values()))['probes'])
    assert count == 32 and all(len(panel[name]['probes']) == count for name in names)
    winner = min(names, key=lambda name: statistics.mean(panel[name]['probes']))
    win_counts = {name: 0 for name in names}
    for index in range(count):
        minimum = min(panel[name]['probes'][index] for name in names)
        for name in names:
            win_counts[name] += panel[name]['probes'][index] == minimum
    rows = []
    for name in names:
        probes = panel[name]['probes']
        online = panel[name]['online_ms']
        details = verification['details'][name]
        rows.append({'arm': name,
            'actual_usable_points': details['actual_usable_points'],
            'effective_columns': details['effective_columns'],
            'sampled_peak_rss_bytes': details['sampled_peak_rss_bytes'],
            'root_table_allocated_bytes': details['root_table_allocated_bytes'],
            'index_build_ms': details['index_ms'],
            'rank_ms': details['rank_ms'],
            'full_process_s': details['process_wall_s'],
            'probe_mean': statistics.mean(probes),
            'probe_median': statistics.median(probes),
            'probe_p90': quantile(probes, 0.9),
            'probe_max': max(probes),
            'online_mean_ms_exploratory': statistics.mean(online),
            'online_median_ms_exploratory': statistics.median(online),
            'online_p90_ms_exploratory': quantile(online, 0.9),
            'online_max_ms_exploratory': max(online),
            'paired_target_win_count_including_ties': win_counts[name],
            'paired_mean_probe_difference_vs_selected_arm': statistics.mean(
                [a - b for a, b in zip(probes, panel[winner]['probes'])]),
            'paired_mean_probe_difference_bootstrap_95_descriptive':
                bootstrap_mean_difference(probes, panel[winner]['probes'],
                                          BOOTSTRAP_SEED + int(name[1:]))})
    result = {'kind': 'n83_a1_packed_root_held_out_panel_analysis_v1',
        'verification_status': verification['status'],
        'target_count': count,
        'selection_metric': 'arithmetic mean target probes over the 32 frozen points; tie broken by lower K',
        'selected_arm_among_completed_arms': winner,
        'censored_arms': verification['censored_arms'],
        'uncertainty': '10,000 target-resampling paired bootstrap repetitions; post-selection descriptive intervals, not confirmatory significance bounds',
        'timing_status': 'shared Mac CPU; exploratory; no controlled wall-time speedup derived from this panel',
        'rows': rows}
    if args.out:
        with args.out.open('x') as out:
            json.dump(result, out, indent=2, sort_keys=True)
            out.write('\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
