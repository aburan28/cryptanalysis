#!/usr/bin/env python3
"""Measure final-link pruning on frozen ordinary N53/N83 SAT inputs."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
sys.path.insert(0, str(HERE))
from verify_model import verify  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--wall', type=int, default=10)
    parser.add_argument('--conflicts', type=int, default=5000)
    args = parser.parse_args()
    assert args.wall > 0 and args.conflicts > 0
    measurements = {
        'proposal_id': 'Q1432', 'candidate_id': None, 'run_id': None,
        'claim_class': 'exploratory_stage_diagnostic',
        'binary_sha256': sha(args.binary),
        'source_sha256': sha(HERE / 'insearch.cpp'),
        'build_script_sha256': sha(HERE / 'build.sh'),
        'conflict_cap': args.conflicts, 'wall_cap_seconds': args.wall,
        'ordinary_runs': [], 'control_runs': [],
        'n53_cost_per_solve_log2': None, 'n83_cost_per_solve_log2': None,
        'n131_cost_per_solve_log2': None, 'n131_total_work_log2': None,
        'gap_to_2_pow_61_bits': None,
    }
    for n in (53, 83):
        prefix = Path('/private/tmp/q1430_n53_ordinary' if n == 53 else
                      '/private/tmp/q1430_ordinary')
        control_prefix = Path('/private/tmp/q1430_n53_control' if n == 53 else
                              '/private/tmp/q1430_control')
        target = HERE / f'n{n}_ordinary.targets'
        manifest = json.loads((HERE / f'n{n}_ordinary.targets.json').read_text())
        meta = json.loads(prefix.with_suffix('.json').read_text())
        assert meta['curve_id'] == manifest['curve_id']
        assert meta['workload_id'] == manifest['workload_id']
        assert meta['factor_base_actual_B'] == manifest['factor_base_actual_B']
        assert meta['factor_base_enumerated_set_sha256'] == manifest[
            'factor_base_enumerated_set_sha256']
        assert sha(prefix.with_suffix('.cnf')) == meta['cnf_sha256']
        assert sha(target) == manifest['target_file_sha256']
        for branch in ('allpos', 'allspread'):
            for final_enabled in (False, True):
                label = f'n{n}_{branch}_{"final" if final_enabled else "baseline"}'
                log = HERE / f'{label}.log'
                chosen_target = target if final_enabled else '-'
                command = [str(args.binary), str(prefix.with_suffix('.cnf')),
                           str(prefix.with_suffix('.map')), str(chosen_target),
                           str(STAGE), str(ROOT / 'ecc2k130/codegen'), branch,
                           'satpivot', str(3 if n == 53 else 5),
                           str(args.conflicts), str(args.wall)]
                completed = subprocess.run(command, cwd=ROOT, text=True,
                                           capture_output=True,
                                           timeout=args.wall + 30, check=False)
                log.write_text(completed.stdout)
                if completed.stderr:
                    (HERE / f'{label}.stderr.log').write_text(completed.stderr)
                result = json.loads(completed.stdout.splitlines()[0])
                assert completed.returncode in (0, 10, 20)
                assert result['status'] in (0, 10, 20)
                row = {
                    'degree': n, 'curve_id': meta['curve_id'],
                    'workload_id': meta['workload_id'],
                    'factor_base_actual_B': meta['factor_base_actual_B'],
                    'factor_base_folded_columns': meta['factor_base_folded_columns'],
                    'factor_base_enumerated_set_sha256': meta[
                        'factor_base_enumerated_set_sha256'],
                    'target_file_sha256': sha(target),
                    'cnf_sha256': meta['cnf_sha256'],
                    'map_sha256': sha(prefix.with_suffix('.map')),
                    'branch': branch, 'root_encoding': 'satpivot',
                    'final_enabled': final_enabled,
                    'log': log.name, 'log_sha256': sha(log),
                    'exit_code': completed.returncode,
                    'result': result,
                    'status_label': ('SAT' if result['status'] == 10 else
                                     'UNSAT' if result['status'] == 20 else
                                     'BOUNDED_UNKNOWN'),
                    'verification': None,
                }
                if result['status'] == 10:
                    row['verification'] = verify(prefix.with_suffix('.json'), log)
                measurements['ordinary_runs'].append(row)
                print(json.dumps({'label': label, 'status': row['status_label'],
                                  'conflicts': result['conflicts'],
                                  'root_queries': result['root_queries'],
                                  'final_rejections': result['final_link_rejections']},
                                 sort_keys=True), flush=True)
        control_target = HERE / f'n{n}_control.targets'
        label = f'n{n}_control_final'
        log = HERE / f'{label}.log'
        command = [str(args.binary), str(control_prefix.with_suffix('.cnf')),
                   str(control_prefix.with_suffix('.map')), str(control_target),
                   str(STAGE), str(ROOT / 'ecc2k130/codegen'), 'allpos',
                   'satpivot', str(3 if n == 53 else 5), '1000', '10']
        completed = subprocess.run(command, cwd=ROOT, text=True,
                                   capture_output=True, timeout=40, check=False)
        log.write_text(completed.stdout)
        assert completed.returncode == 10 and not completed.stderr
        verification = verify(control_prefix.with_suffix('.json'), log)
        measurements['control_runs'].append({
            'degree': n, 'curve_id': meta['curve_id'],
            'factor_base_actual_B': meta['factor_base_actual_B'],
            'factor_base_folded_columns': meta['factor_base_folded_columns'],
            'cnf_sha256': sha(control_prefix.with_suffix('.cnf')),
            'target_file_sha256': sha(control_target),
            'log': log.name, 'log_sha256': sha(log),
            'result': json.loads(completed.stdout.splitlines()[0]),
            'verification': verification,
        })
    output = HERE / 'measurements.json'
    output.write_text(json.dumps(measurements, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'measurements': str(output),
                      'ordinary_rows': len(measurements['ordinary_runs']),
                      'control_rows': len(measurements['control_runs'])},
                     sort_keys=True))


if __name__ == '__main__':
    main()
