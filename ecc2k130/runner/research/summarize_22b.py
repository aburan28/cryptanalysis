"""Index retained measurements; never infer goal completion from screening."""
import argparse
import csv
import json
from pathlib import Path


def measurements(directory):
    for path in sorted(directory.glob('*.json')):
        result = json.loads(path.read_text())
        summaries = result.get('summary', {})
        control = summaries.get('baseline', {}).get('rate', 0)
        for name, summary in summaries.items():
            variant = result.get('variants', {}).get(name, {})
            resume = variant.get('resume_checks', [])
            samples = result.get('samples', {}).get(name, [])
            yield {
                'receipt': path.name,
                'variant': name,
                'median_Bps': summary.get('rate', 0) / 1000,
                'min_Bps': summary.get('minRate', 0) / 1000,
                'max_Bps': summary.get('maxRate', 0) / 1000,
                'samples': len(samples),
                'relative_to_control': summary.get('rate', 0) / control if control else '',
                'timings_valid': summary.get('valid', False),
                'replay_and_corpus_passed': variant.get('reports_ok', False),
                'resume_checks_passed': all(row['ok'] for row in resume) if resume else '',
                'certification_run': result.get('certification_candidate') == name,
                'collection_corpus_matched': result.get('candidate_corpus_matches', ''),
                'binary_sha256': variant.get('binary_sha256', ''),
            }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'build/goal22-results')
    args = parser.parse_args()
    rows = list(measurements(args.directory))
    output = args.directory / 'index.csv'
    if rows:
        with output.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(f'Indexed {len(rows)} measured rows in {output}')
    candidates = [row for row in rows if row['variant'] != 'baseline'
                  and row['timings_valid'] and row['replay_and_corpus_passed']]
    for row in sorted(candidates, key=lambda row: row['median_Bps'], reverse=True)[:8]:
        print(f"{row['median_Bps']:.6f} B/s  {row['variant']}  {row['receipt']}  "
              f"n={row['samples']}  relative={row['relative_to_control']:.4f}")
    print('Screening rates alone do not certify the 22B target or promote source.')
