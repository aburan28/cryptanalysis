"""Independent trace and group replay for the corrected two-preimage query."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT/'n131_w18_cubic_correct_target_20261011'
PUBLIC = ROOT/'n131_fixed_seed_eight_pair_circuit_20261010/target_preimages.json'
spec = importlib.util.spec_from_file_location('independent_n131_binding', BASE/'verify.py')
field = importlib.util.module_from_spec(spec)
spec.loader.exec_module(field)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE/'protocol.json').read_text())
    full = json.loads((BASE/'protocol.json').read_text())
    public = json.loads(PUBLIC.read_text())
    standard = [field.inverse(int(row['point'][0])) for row in public['preimages']]
    traces = [field.trace(z) for z in standard]
    basis_traces = [field.trace(1 << bit) for bit in range(1, 19)]
    assert traces == [0, 0, 1, 1] and basis_traces == [0] * 18
    assert standard == full['raw_target_preimage_z']
    assert protocol['raw_target_preimage_z'] == standard[:2]
    assert protocol['raw_target_preimage_indices'] == [0, 1]
    assert protocol['excluded_preimage_indices'] == [2, 3]
    assert protocol['all_standard_reciprocal_traces'] == traces
    assert protocol['source_sha256']['corrected_full_protocol.json'] == sha(BASE/'protocol.json')
    for row, z in zip(public['preimages'], standard):
        point = tuple(row['point'])
        assert field.on_curve(point)
        assert field.double(field.double(point)) == tuple(public['public_target'])
        assert field.mul(point[0], z) == 1
    assert protocol['raw_target_preimage_z'][0] ^ (
        protocol['raw_target_preimage_z'][0] ^ protocol['raw_target_preimage_z'][1]
    ) == protocol['raw_target_preimage_z'][1]
    result = {'status': 'PASS_STANDARD_TRACE_TWO_PREIMAGE_BINDING',
              'source_basis_traces': basis_traces,
              'standard_preimage_traces': traces,
              'included_indices': [0, 1], 'excluded_indices': [2, 3],
              'public_target': public['public_target'],
              'source_sha256': {'verify.py': sha(Path(__file__)),
                                'independent_field_checker.py': sha(BASE/'verify.py'),
                                'protocol.json': sha(HERE/'protocol.json'),
                                'target_preimages.json': sha(PUBLIC)}}
    (HERE/'binding_audit.json').write_text(json.dumps(result, indent=2,
                                                       sort_keys=True)+'\n')
    print(json.dumps({'status': result['status'], 'traces': traces}))


if __name__ == '__main__':
    main()
