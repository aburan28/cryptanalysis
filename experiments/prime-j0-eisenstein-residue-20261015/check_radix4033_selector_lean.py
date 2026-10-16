#!/usr/bin/env python3
"""Build the pinned norm-4033 finite selector proof from fresh local oleans and save its receipt."""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def run(command, *, env=None):
    result = subprocess.run(command,cwd=HERE,env=env,text=True,
                            stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    return {'command':command,'returncode':result.returncode,'output':result.stdout}


def main():
    lean = shutil.which('lean')
    assert lean is not None
    receipt = {
        'schema':1,
        'toolchain':(HERE/'lean-toolchain').read_text().strip(),
        'source_sha256':{name:sha256((HERE/name).read_bytes()).hexdigest()
                         for name in ('AlternateRadix.lean','HornerRadix.lean','RotatedRadixStep.lean','Radix4033.lean','Radix4033Bounds.lean','Radix4033Selector.lean')},
        'lean4checker_fresh_available':shutil.which('lean4checker') is not None,
        'steps':[run([lean,'--version'])],
    }
    with TemporaryDirectory(prefix='radix4033-selector-lean-') as temp:
        env=dict(os.environ,LEAN_PATH=temp)
        receipt['steps'].append(run([lean,'-o',str(Path(temp)/'AlternateRadix.olean'),
                                     'AlternateRadix.lean'],env=env))
        if receipt['steps'][-1]['returncode'] == 0:
            receipt['steps'].append(run([lean,'-o',str(Path(temp)/'HornerRadix.olean'),
                                     'HornerRadix.lean'],env=env))
        if receipt['steps'][-1]['returncode'] == 0:
            receipt['steps'].append(run([lean,'-o',str(Path(temp)/'RotatedRadixStep.olean'),
                                     'RotatedRadixStep.lean'],env=env))
        if receipt['steps'][-1]['returncode'] == 0:
            receipt['steps'].append(run([lean,'-o',str(Path(temp)/'Radix4033.olean'),
                                     'Radix4033.lean'],env=env))
        if receipt['steps'][-1]['returncode'] == 0:
            receipt['steps'].append(run([lean,'-o',str(Path(temp)/'Radix4033Bounds.olean'),
                                     'Radix4033Bounds.lean'],env=env))
        if receipt['steps'][-1]['returncode'] == 0:
            receipt['steps'].append(run([lean,'Radix4033Selector.lean'],env=env))
    assert all(step['returncode'] == 0 for step in receipt['steps'])
    output=receipt['steps'][-1]['output']
    for theorem in ('rounded_in_center_window','rounded_candidate_mem',
                    'choose_le_best','choose_le_next','foldl_choose_le_member',
                    'selected_norm_below_radix','selected_pair_congruent',
                    'selected_exact_quotient','signed_selected_norm',
                    'signed_selected_congruent','signed_exact_quotient',
                    'total_selected_step'):
        assert (f"'Radix4033Selector.{theorem}' depends on axioms:" in output
                or f"'Radix4033Selector.{theorem}' does not depend on any axioms" in output)
    assert 'sorryAx' not in output
    (HERE/'radix4033-selector-lean-check.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'ok':True,'theorems':12,'toolchain':receipt['toolchain']},sort_keys=True))


if __name__ == '__main__':
    main()
