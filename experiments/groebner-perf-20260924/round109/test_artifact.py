"""Coherently altered discovery records still fail the independent audit."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from audit import audit


def test(path):
    path = Path(path)
    report = json.loads(path.read_text())
    valid = audit(report, path.parent)
    assert valid['status'] == 'PASS'
    mutations = {
        'forged_original_input': lambda r: r['proof']['nodes'][0].__setitem__(1, 4096),
        'forged_output': lambda r: r['proof']['outputs'].__setitem__(0, len(r['proof']['nodes'])),
        'wrong_basis': lambda r: r['basis'][0].append(0),
        'wrong_composition_work': lambda r: (r['composition']['stats'].__setitem__('work', r['composition']['stats']['work']+1), r.__setitem__('work', r['work']+1)),
        'wrong_bridge_work': lambda r: (r.__setitem__('bridge_work', r['bridge_work']+1), r.__setitem__('work', r['work']+1)),
        'wrong_seed_reservation': lambda r: r['attempts'][1].__setitem__('reserved_seed_nodes', 0),
        'forged_continuation_input': lambda r: r['continuation']['proof']['nodes'][0].__setitem__(1, 4096),
        'missing_curve_replay': lambda r: r.pop('reference_equations_and_curve_replay'),
        'wrong_live_terms': lambda r: r['certificate']['liveness'].__setitem__('peak_terms', 0),
        'promoted_timing': lambda r: r.__setitem__('timing_eligible', True),
    }
    rejected = []
    for name, mutate in mutations.items():
        with tempfile.TemporaryDirectory(dir=path.parent) as temp:
            folder = Path(temp)
            for p in path.parent.glob('*.json'):
                os.link(p, folder/p.name)
            candidate = copy.deepcopy(report)
            # Alter both optimization modes and their digests, so agreement or
            # checksums alone cannot reject the corruption.
            for row in candidate['rows']:
                if row['name'] != 'pdp-12-seed-3':
                    continue
                file = folder/row['result']
                result = json.loads(file.read_text())
                mutate(result)
                encoded = (json.dumps(result, indent=2)+'\n').encode()
                replacement = file.with_suffix('.replacement')
                replacement.write_bytes(encoded)
                replacement.replace(file)
                row['sha256'] = hashlib.sha256(encoded).hexdigest()
            try:
                audit(candidate, folder)
            except (AssertionError, KeyError, ValueError, IndexError):
                rejected.append(name)
            else:
                raise AssertionError('corruption accepted: '+name)
    return dict(status='PASS', count=len(rejected), rejected=rejected, native_binaries_loaded=False)


if __name__ == '__main__':
    result = test(sys.argv[1])
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)
