#!/usr/bin/env python3
"""Build the pinned norm-4033 radix proof from fresh local oleans and save its receipt."""

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
                         for name in ('AlternateRadix.lean','HornerRadix.lean','RotatedRadixStep.lean','Radix4033.lean')},
        'lean4checker_fresh_available':shutil.which('lean4checker') is not None,
        'steps':[run([lean,'--version'])],
    }
    with TemporaryDirectory(prefix='radix4033-lean-') as temp:
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
            receipt['steps'].append(run([lean,'Radix4033.lean'],env=env))
    assert all(step['returncode'] == 0 for step in receipt['steps'])
    output=receipt['steps'][-1]['output']
    for theorem in ('radix_norm','adjugate_first','adjugate_second',
                    'exact_quotient','radix_as_rotation'):
        assert (f"'Radix4033.{theorem}' depends on axioms:" in output
                or f"'Radix4033.{theorem}' does not depend on any axioms" in output)
    assert 'sorryAx' not in output
    (HERE/'radix4033-lean-check.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'ok':True,'theorems':5,'toolchain':receipt['toolchain']},sort_keys=True))


if __name__ == '__main__':
    main()
