#!/usr/bin/env python3
"""Pool paired probe counts for the five bases complete in both 32-point panels."""

import hashlib
import json
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIRST = HERE.parent / 'n83-packed-root-panel-20261013'
COMMON = ('K800', 'K899', 'K900', 'K1200', 'K1271')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values, fraction):
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def stratified_interval(groups, seed):
    rng = random.Random(seed)
    means = []
    for _ in range(10000):
        sampled = []
        for group in groups:
            sampled.extend(group[rng.randrange(len(group))] for _ in group)
        means.append(statistics.mean(sampled))
    return [percentile(means, 0.025), percentile(means, 0.975)]


def main():
    first = json.loads((FIRST / 'verification.json').read_text())
    second = json.loads((HERE / 'verification.json').read_text())
    assert first['status'] == 'CENSORED' and second['status'] == 'PASS'
    first_manifest = json.loads((FIRST / 'binary_manifest.json').read_text())
    second_manifest = json.loads((HERE / 'binary_manifest.json').read_text())
    assert first_manifest['ic_sha256'] == second_manifest['ic_sha256']
    for panel in (first, second):
        assert all(len(panel['per_target'][name]['probes']) == 32 for name in COMMON)
    probes = {name: [panel['per_target'][name]['probes']
                     for panel in (first, second)] for name in COMMON}
    means = {name: statistics.mean(sum(probes[name], [])) for name in COMMON}
    winner = min(COMMON, key=lambda name: (means[name], int(name[1:])))
    rows = []
    for name in COMMON:
        groups = [[a - b for a, b in zip(probes[name][group_index],
                                          probes[winner][group_index])]
                  for group_index in (0, 1)]
        all_probes = sum(probes[name], [])
        rows.append({'arm': name,
            'first_panel_mean_probes': statistics.mean(probes[name][0]),
            'second_panel_mean_probes': statistics.mean(probes[name][1]),
            'pooled_mean_probes': means[name],
            'pooled_median_probes': statistics.median(all_probes),
            'paired_mean_probe_difference_vs_selected': statistics.mean(sum(groups, [])),
            'stratified_bootstrap_95_descriptive': stratified_interval(groups,
                                                    2026101316 + int(name[1:]))})
    result = {'kind': 'n83_a1_packed_root_two_panel_probe_pool_v1',
              'panels': [{'protocol_sha256': sha(path / 'protocol.json'),
                          'verification_sha256': sha(path / 'verification.json'),
                          'target_count': 32,
                          'sampled_rss_cap_bytes': json.loads((path / 'protocol.json').read_text())['sampled_rss_cap_bytes']}
                         for path in (FIRST, HERE)],
              'common_completed_bases': list(COMMON),
              'pooled_target_count': 64,
              'selected_arm_by_pooled_mean_probes': winner,
              'scope': 'deterministic target probe counts only; 32 distinct points per panel; shared source binary; different RSS caps; no pooled CPU timing or speedup',
              'uncertainty': '10,000 paired target resamples within each panel; descriptive after selection',
              'rows': rows}
    with (HERE / 'pooled_probe_analysis.json').open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write('\n')
    print(json.dumps({'selected_arm': winner, 'rows': rows}, indent=2))


if __name__ == '__main__':
    main()
