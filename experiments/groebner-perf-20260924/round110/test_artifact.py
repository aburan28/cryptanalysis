"""Coherent native-result and source-receipt corruption controls."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from audit_native import audit


def test(path):
    path = Path(path)
    report = json.loads(path.read_text())
    assert audit(report, path.parent)['status'] == 'PASS'
    mutations = {
        'forged_original_input': lambda r: r['proof']['nodes'][0].__setitem__(1, 4096),
        'forged_output': lambda r: r['proof']['outputs'].__setitem__(0, len(r['proof']['nodes'])),
        'wrong_basis': lambda r: r['basis'][0].append(0),
        'wrong_continuation': lambda r: r['continuation']['proof']['nodes'][0].__setitem__(1, 4096),
        'wrong_scan_charge': lambda r: (r.__setitem__('scan_work', r['scan_work']+1),
            r.__setitem__('work', r['work']+1), r['native_stats'].__setitem__('scan_work', r['scan_work']),
            r['native_stats'].__setitem__('work', r['native_stats']['work']+1)),
        'wrong_scan_coefficient': lambda r: r['packed_scan']['coefficients'].__setitem__(0, 0),
        'missing_scan': lambda r: r.pop('packed_scan'),
        'wrong_bridge_charge': lambda r: (r.__setitem__('bridge_work', r['bridge_work']+1), r['native_stats'].__setitem__('bridge_work', r['bridge_work'])),
        'wrong_native_status': lambda r: r['native_stats'].__setitem__('status', 2),
        'wrong_native_mode': lambda r: r.__setitem__('native_integration', False),
        'missing_curve_replay': lambda r: r.pop('reference_equations_and_curve_replay'),
        'promoted_timing': lambda r: r.__setitem__('timing_eligible', True),
    }
    rejected = []
    for name, mutate in mutations.items():
        with tempfile.TemporaryDirectory(dir=path.parent) as temp:
            folder = Path(temp)
            for p in path.parent.glob('*.json'): os.link(p, folder/p.name)
            candidate = copy.deepcopy(report)
            for row in candidate['rows']:
                if row['name'] != 'pdp-12-seed-3': continue
                file = folder/row['result']
                result = json.loads(file.read_text())
                mutate(result)
                data = (json.dumps(result, indent=2)+'\n').encode()
                replacement = file.with_suffix('.replacement')
                replacement.write_bytes(data)
                replacement.replace(file)
                row['sha256'] = hashlib.sha256(data).hexdigest()
            try:
                audit(candidate, folder)
            except (AssertionError, KeyError, ValueError, IndexError):
                rejected.append(name)
            else:
                raise AssertionError('Corruption accepted: '+name)
    candidate = copy.deepcopy(report)
    candidate['build']['sources']['seeded.cpp'] = '0'*64
    try:
        audit(candidate, path.parent)
    except AssertionError:
        rejected.append('wrong_native_source')
    else:
        raise AssertionError('Native source mismatch accepted')
    return dict(status='PASS', count=len(rejected), rejected=rejected, native_binaries_loaded=False)


if __name__ == '__main__':
    result = test(sys.argv[1])
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)
