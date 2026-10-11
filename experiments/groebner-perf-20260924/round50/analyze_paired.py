"""Descriptive matched-ratio analysis of every retained admission and query."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import random
import statistics


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    summary = read(args.input / 'summary.json.gz')
    assert summary['status'] == 'COMPLETE'
    plan = summary['plan']
    rng = random.Random(plan['bootstrap_seed'])
    records = []
    for record in summary['trials']:
        if record['status'] != 'VERIFIED':
            records.append(record)
            continue
        path = args.input / (record['name'] + '.json.gz')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['report_sha256']
        trial = read(path)
        assert all(row['matched_reference'] for row in trial['rows'])
        rows = {(r['repetition'], r['arm']): r for r in trial['rows'] if r['repetition'] >= 0}
        assert len(rows) == plan['measured_pairs'] * len(plan['arms'])
        medians, comparisons = {}, {}
        for arm in plan['arms']:
            samples = [rows[i, arm] for i in range(plan['measured_pairs'])]
            medians[arm] = {'query_ms': statistics.median(s['elapsed_ns'] / 1e6 for s in samples)}
            for group, names in (('metrics', ('specialization', 'evaluation', 'gpu_wall', 'gpu_device', 'interpolation')),
                                 ('projection_stats', ('seconds',)), ('normalization_stats', ('seconds',))):
                for name in names:
                    medians[arm][group + '.' + name + '_ms'] = statistics.median(s['answer'][group][name] * 1e3 for s in samples)
            if arm == plan['primary']:
                continue
            ratios = [rows[i, arm]['elapsed_ns'] / rows[i, plan['primary']]['elapsed_ns'] for i in range(plan['measured_pairs'])]
            bootstrap = sorted(statistics.median(rng.choices(ratios, k=len(ratios))) for _ in range(plan['bootstrap_samples']))
            comparisons[arm] = {'paired_median_ratio': statistics.median(ratios),
                                'paired_95pct': [bootstrap[int(.025 * len(bootstrap))], bootstrap[int(.975 * len(bootstrap))]],
                                'ratios': ratios}
        records.append({**record, 'medians': medians, 'comparisons': comparisons})
    cases = {}
    for row in records:
        cases.setdefault(row['input'], []).append(row)
    passed = []
    for name, rows in cases.items():
        if len(rows) == plan['trials_per_input'] and all(r['timing_eligible'] and all(r['comparisons'][c]['paired_95pct'][0] > 1 for c in plan['confirmatory_comparators']) for r in rows):
            passed.append(name)
    result = {'schema': 'gpu-affine-paired-analysis/1', 'plan': plan, 'records': records,
              'queries': sum(r.get('queries', 0) for r in summary['trials']),
              'qualified_trials': sum(r['timing_eligible'] for r in records),
              'repeated_wins_against_all_comparators': passed,
              'primary_acceptance': len([n for n in passed if '-ell9-' in n]) == 3,
              'candidate_id': None, 'online_speedup': None,
              'input_sha256': hashlib.sha256((args.input / 'summary.json.gz').read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('queries', 'qualified_trials', 'repeated_wins_against_all_comparators', 'primary_acceptance')}, indent=2))


if __name__ == '__main__':
    main()
