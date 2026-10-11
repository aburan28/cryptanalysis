"""Freeze the N41 sparse-product last-pair linear-gate comparison."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    paths={'producer':HERE/'linear_last_pair_sage.py',
           'input':ROOT/'n131_w18_four_pairs/native_join/native_input.txt',
           'fixture':ROOT/'n41_transport_cubic_s8_20261011/fixture.json',
           'n41_circuit':ROOT/'n41_transport_cubic_s8_20261011/circuit.py',
           'runtime':HERE/'sage_runtime_info.json',
           'freezer':HERE/'linear_freeze.py'}
    fixture=json.loads(paths['fixture'].read_text())
    assert fixture['status']=='PASS_TRANSPORTED_N41_PUBLIC_EIGHT_SLOT_WITNESS'
    assert json.loads(paths['runtime'].read_text())['status']=='verified'
    record={'status':'FROZEN_N41_TARGET_DERIVED_LAST_PAIR_LINEAR_GATE',
            'candidate_id':None,'curve_id':fixture['curve_id'],
            'field':'GF(2)[t]/(t^41+t^3+1)',
            'target_raw_preimage_index':0,
            'target_original':fixture['public_target_original'],
            'target_transported':fixture['public_target_transported'],
            'first_three_pair_policy':'exact canonical signed source pairs, six distinct columns',
            'fourth_gate':'S3 halftrace equation with s in W6, p in span(t^2,...,t^12), free branch bit',
            'positive_control':'all 1956 exact fourth-pair sums',
            'negative_control':'one target-derived trace-valid raw fourth output for each of 63 first-pair seed sums',
            'source_sha256':{name:sha(path) for name,path in paths.items()}}
    (HERE/'linear_protocol.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':record['status']}))

if __name__=='__main__':
    main()
