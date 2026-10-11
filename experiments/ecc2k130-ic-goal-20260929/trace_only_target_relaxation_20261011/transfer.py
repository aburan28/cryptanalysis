"""Check the trace-only relaxation's exact W18/N131 prerequisites."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
N131 = ROOT/'n131_w18_cubic_s8_20261011'
PUBLIC = ROOT/'n131_fixed_seed_eight_pair_circuit_20261010/target_preimages.json'
TRACE = N131/'trace_gate_result.json'
sys.path.insert(0, str(N131))
import circuit  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    field = circuit.Field()
    basis_traces = [circuit.old.trace(field, 1 << (i+1)) for i in range(18)]
    assert basis_traces == [0]*18
    public = json.loads(PUBLIC.read_text())
    z_traces = [circuit.old.trace(field, row['reciprocal_x_z'])
                for row in public['preimages']]
    assert z_traces == [0,1,0,1]
    frozen = json.loads(TRACE.read_text())
    assert frozen['status'] == 'PASS_TRACE_ZERO_TARGET_PREIMAGE_GATE'
    assert frozen['admissible_raw_preimage_indices'] == [0,2]
    result = {'status': 'PASS_N131_TRACE_ONLY_RELAXATION_TRANSFER',
              'field_degree': 131,
              'source_w18_trace_basis': basis_traces,
              'target_raw_preimage_traces': z_traces,
              'admissible_raw_preimage_indices': [0,2],
              'logical_consequence': 'For any three nonexceptional trace-zero pair outputs A,B,C and trace-zero raw target U, the required fourth output D=U-A-B-C also has trace zero whenever its reciprocal coordinate is defined. Target plus trace alone cannot reject A after B,C are fixed; membership in the exact fourth-pair image is the missing constraint.',
              'scope': 'Necessary-condition proof; no N131 natural relation or runtime measurement.',
              'sha256': {'transfer.py': sha(HERE/'transfer.py'),
                         'n131_circuit.py': sha(N131/'circuit.py'),
                         'target_preimages.json': sha(PUBLIC),
                         'trace_gate_result.json': sha(TRACE)}}
    (HERE/'transfer.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'status': result['status'],
                      'admissible_raw_preimage_indices': result['admissible_raw_preimage_indices']}))


if __name__ == '__main__':
    main()
