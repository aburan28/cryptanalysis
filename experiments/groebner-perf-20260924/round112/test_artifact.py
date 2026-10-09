"""Corruptions of proof, budget, lower bound and result metadata fail closed."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('early_artifact_audit', HERE/'audit.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    report = json.loads(args.report.read_text())
    _, baseline = audit.reference_audit.frozen()
    record = next(r for r in report['rows'] if r['name'] == 'pdp-12-seed-1' and
                  r['early_mode'] == 1 and not r['sanitized'])
    row = json.loads((args.report.parent/record['result']).read_text())
    reference = baseline[record['name'], False]
    mutations = {
        'active-reachability-bound': lambda r: r['result']['attempts'][0]['early'].__setitem__('active_nodes', 1),
        'strict-bound-gate': lambda r: r['result']['attempts'][0]['early'].__setitem__('bound_selected', 0),
        'pruning-work': lambda r: r['result']['attempts'][0]['early'].__setitem__('prune_visits', 1),
        'producer-work': lambda r: r['result'].__setitem__('work', 0),
        'shared-check-work': lambda r: r['result'].__setitem__('check_work', 0),
        'composition-charge': lambda r: r['result']['attempts'][1]['composition'].__setitem__('work', 0),
        'mode': lambda r: r.__setitem__('early_mode', 0),
        'basis': lambda r: r['result']['basis'][0].append(0),
        'certificate': lambda r: r['result']['certificate'].__setitem__('verified', False),
        'curve-replay': lambda r: r['result'].__setitem__('reference_equations_and_curve_replay', False),
        'negative-phase': lambda r: r['result']['phases'].__setitem__('overhead_ns', -1),
        'unsupported-speedup': lambda r: r.__setitem__('qualified_speedup', 2),
    }
    rejected = []
    with tempfile.TemporaryDirectory(dir=args.output.parent) as temporary:
        folder = Path(temporary)
        artifact = row['result']['proof_artifact']
        shutil.copyfile(args.report.parent/artifact['path'], folder/artifact['path'])
        audit.one(row, reference, folder)
        for name, mutation in mutations.items():
            changed = copy.deepcopy(row)
            mutation(changed)
            try: audit.one(changed, reference, folder)
            except (AssertionError, ValueError): rejected.append(name)
            else: raise AssertionError('accepted corrupted artifact: '+name)
        path = folder/artifact['path']
        data = bytearray(path.read_bytes())
        data[-1] ^= 128
        path.write_bytes(data)
        changed = copy.deepcopy(row)
        changed['result']['proof_artifact']['sha256'] = audit.digest(data)
        try: audit.one(changed, reference, folder)
        except (AssertionError, ValueError): rejected.append('proof-with-updated-digest')
        else: raise AssertionError('accepted corrupted proof')
    result = dict(status='PASS', rejected=rejected, count=len(rejected), native_binaries_loaded=False)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
