#!/usr/bin/env python3
"""Replay frozen scatter panel through both native evaluators sequentially."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(text):
    return dict(part.split('=', 1) for part in text.strip().split() if '=' in part)


def run(binary, mode, case, path):
    argv = [str(binary), mode, case['curve']['name'], str(case['id'].rsplit('point', 1)[1]),
            str(path)]
    result = subprocess.run(argv, cwd=ROOT.parents[1], capture_output=True, text=True,
                            check=False)
    return {'mode': mode, 'case_id': case['id'], 'exit_code': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr,
            'fields': parse(result.stdout) if result.returncode == 0 else {}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    build_cache = binary.parent / 'CMakeCache.txt'
    if not build_cache.is_file():
        raise SystemExit(f'missing build cache beside binary: {build_cache}')
    inputs_path = ROOT / 'tau3-scatter-inputs/inputs.json'
    design_path = ROOT / 'tau3-scatter-design.json'
    model_path = ROOT / 'tau3-scatter-panel.json'
    inputs = json.loads(inputs_path.read_text())
    model = json.loads(model_path.read_text())
    expected = {row['case_id']: row for row in model['rows']}
    rows = []
    for index, case in enumerate(inputs['cases']):
        path = ROOT / 'tau3-scatter-inputs' / case['scalar_file']
        assert sha256(path) == case['scalar_file_sha256']
        modes = ('tau3-fused-pos', 'tau3-scatter-pos')
        if index & 1: modes = tuple(reversed(modes))
        pair = [run(binary, mode, case, path) for mode in modes]
        rows.extend(pair)
        if any(row['exit_code'] or row['fields'].get('verified') != '1' for row in pair):
            continue
        full = next(row['fields'] for row in pair if row['mode'] == 'tau3-fused-pos')
        scatter = next(row['fields'] for row in pair if row['mode'] == 'tau3-scatter-pos')
        want = expected[case['id']]
        valid = (full['output_digest'] == scatter['output_digest'] and
                 int(full['adds']) == want['base_adds'] and
                 int(scatter['adds']) == want['scatter_adds'] and
                 int(scatter['scatter_pairs']) == want['matched_pairs'] and
                 int(scatter['point_entries']) == want['point_entries'] and
                 int(full['fallbacks']) == int(scatter['fallbacks']) == 0 and
                 int(scatter['scatter_preparation_checks']) == want['point_entries'])
        for row in pair: row['gate_pass'] = valid
    passed = len(rows) == 2 * len(inputs['cases']) and all(row.get('gate_pass') for row in rows)
    report = {'schema': 1, 'status': 'pass' if passed else 'fail',
              'cpu_timing_claim': None, 'host_exploratory': True,
              'isolated_receipt': None,
              'host': {'system': platform.system(), 'machine': platform.machine(),
                       'processor': platform.processor()},
              'online_interval': 'native per-scalar computation excluding preparation and verification; local timing exploratory',
              'design_sha256': sha256(design_path), 'inputs_sha256': sha256(inputs_path),
              'model_sha256': sha256(model_path), 'source_sha256': sha256(Path(__file__)),
              'bench_source_sha256': sha256(ROOT / 'bench.c'),
              'ec_tau_source_sha256': sha256(ROOT.parents[1] / 'src/ec_tau.c'),
              'map_header_sha256': sha256(ROOT.parents[1] / 'src/generated/tau3_scatter.h'),
              'binary_sha256': sha256(binary), 'cmake_cache_sha256': sha256(build_cache),
              'rows': rows}
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': report['status'], 'rows': len(rows),
                      'verified_pairs': sum(bool(row.get('gate_pass')) for row in rows) // 2},
                     sort_keys=True))
    if not passed: raise SystemExit(1)


if __name__ == '__main__': main()
