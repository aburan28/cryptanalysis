#!/usr/bin/env python3
"""Build the pinned Horner proof from fresh local oleans and save its receipt."""

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
                         for name in ('AlternateRadix.lean','HornerRadix.lean')},
        'lean4checker_fresh_available':shutil.which('lean4checker') is not None,
        'steps':[run([lean,'--version'])],
    }
    with TemporaryDirectory(prefix='horner-lean-') as temp:
        env=dict(os.environ,LEAN_PATH=temp)
        receipt['steps'].append(run([lean,'-o',str(Path(temp)/'AlternateRadix.olean'),
                                     'AlternateRadix.lean'],env=env))
        if receipt['steps'][-1]['returncode'] == 0:
            receipt['steps'].append(run([lean,'HornerRadix.lean'],env=env))
    assert all(step['returncode'] == 0 for step in receipt['steps'])
    output=receipt['steps'][-1]['output']
    for theorem in ('valid_trace_evaluates','map_evaluatePairs',
                    'point_horner_of_valid_trace'):
        assert f"'HornerRadix.{theorem}' depends on axioms: [propext]" in output
    assert 'sorryAx' not in output
    (HERE/'horner-lean-check.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'ok':True,'theorems':3,'toolchain':receipt['toolchain']},sort_keys=True))


if __name__ == '__main__':
    main()
