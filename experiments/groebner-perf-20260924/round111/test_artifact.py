"""Coherent artifact mutations must fail independent acceptance."""
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
    spec = importlib.util.spec_from_file_location('leased_seeded_audit', HERE/'audit.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    report = json.loads(args.report.read_text())
    _, expected = audit.frozen()
    item = next(r for r in report['rows'] if r['name'] == 'pdp-12-seed-3' and not r['sanitized'])
    row = json.loads((args.report.parent/item['result']).read_text())
    reference = expected[item['name'], item['sanitized']]
    mutations = {
        'total-work': lambda r: r['result'].__setitem__('work', r['result']['work']-1),
        'shared-check-work': lambda r: r['result'].__setitem__('check_work', 0),
        'composition-charge': lambda r: r['result']['attempts'][1]['composition'].__setitem__('work', 0),
        'native-scan-charge': lambda r: r['result']['attempts'][1]['stats'].__setitem__('scan_work', 0),
        'phase-total': lambda r: r['result']['phases'].__setitem__('proof_copy_ns', 0),
        'phase-negative': lambda r: r['result']['phases'].__setitem__('overhead_ns', -1),
        'curve-replay': lambda r: r['result'].__setitem__('reference_equations_and_curve_replay', False),
        'basis': lambda r: r['result']['basis'][0].append(0),
        'certificate': lambda r: r['result']['certificate'].__setitem__('verified', False),
        'status': lambda r: r['result'].__setitem__('status', 'inconclusive'),
        'unsupported-speedup': lambda r: r.__setitem__('qualified_speedup', 2),
    }
    results = []
    with tempfile.TemporaryDirectory(dir=args.output.parent) as temporary:
        folder = Path(temporary)
        artifact = row['result']['proof_artifact']
        shutil.copyfile(args.report.parent/artifact['path'], folder/artifact['path'])
        audit.one(row, reference, folder)
        for name, mutation in mutations.items():
            changed = copy.deepcopy(row)
            mutation(changed)
            try:
                audit.one(changed, reference, folder)
            except (AssertionError, ValueError):
                results.append(dict(name=name, rejected=True))
            else:
                raise AssertionError('accepted corrupted artifact: '+name)
        path = folder/artifact['path']
        data = bytearray(path.read_bytes())
        data[-1] ^= 128
        path.write_bytes(data)
        changed = copy.deepcopy(row)
        changed['result']['proof_artifact']['sha256'] = audit.digest(data)
        try:
            audit.one(changed, reference, folder)
        except (AssertionError, ValueError):
            results.append(dict(name='proof-with-updated-digest', rejected=True))
        else:
            raise AssertionError('accepted corrupted proof')
    result = dict(status='PASS', controls=results, native_binaries_loaded=False)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
