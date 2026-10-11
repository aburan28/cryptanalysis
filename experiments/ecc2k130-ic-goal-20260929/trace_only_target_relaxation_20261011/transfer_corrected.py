"""Replay N131 trace transfer using the S3 circuit's standard z=1/x coordinate."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CHECKER = ROOT/'n131_w18_cubic_correct_target_20261011/verify.py'
PROTOCOL = ROOT/'n131_w18_cubic_correct_target_20261011/protocol.json'
PUBLIC = ROOT/'n131_fixed_seed_eight_pair_circuit_20261010/target_preimages.json'
spec = importlib.util.spec_from_file_location('independent_n131_binding', CHECKER)
field = importlib.util.module_from_spec(spec)
spec.loader.exec_module(field)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads(PROTOCOL.read_text())
    public = json.loads(PUBLIC.read_text())
    source_traces = [field.trace(1 << bit) for bit in range(1, 19)]
    assert source_traces == [0] * 18
    standard = [field.inverse(int(row['point'][0])) for row in public['preimages']]
    assert standard == protocol['input_binding']['standard_z']
    traces = [field.trace(z) for z in standard]
    assert traces == [0, 0, 1, 1]
    for row, z in zip(public['preimages'], standard):
        point = tuple(row['point'])
        assert field.on_curve(point)
        assert field.double(field.double(point)) == tuple(public['public_target'])
        assert field.mul(point[0], z) == 1
    result = {'status': 'PASS_STANDARD_RECIPROCAL_N131_TRACE_TRANSFER',
              'source_w18_trace_basis': source_traces,
              'all_standard_reciprocal_traces': traces,
              'admissible_raw_preimage_indices': [0, 1],
              'coordinate': 'z=1/x',
              'logical_consequence': 'For three trace-zero S3 pair outputs and an admissible trace-zero raw public preimage, the required fourth output has trace zero when its reciprocal coordinate is defined.',
              'sha256': {'transfer_corrected.py': sha(Path(__file__)),
                         'independent_field_and_group_checker.py': sha(CHECKER),
                         'corrected_query_protocol.json': sha(PROTOCOL),
                         'target_preimages.json': sha(PUBLIC)}}
    (HERE/'transfer_corrected.json').write_text(json.dumps(result, sort_keys=True,
                                                            indent=2)+'\n')
    print(json.dumps({'status': result['status'], 'admissible_raw_preimage_indices': [0, 1]}))


if __name__ == '__main__':
    main()
