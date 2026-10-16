#!/usr/bin/env python3
"""Build checkpointed sparse-radix proofs from fresh pinned Lean oleans."""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
THEOREMS = ('inverse_square_mod','inverse_square_times_mod',
            'inverse_cube_mod','normalized_x_mod','normalized_y_mod')


def run(command,env):
    completed = subprocess.run(command,cwd=HERE,env=env,text=True,
                               stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    return {'command':command,'returncode':completed.returncode,'output':completed.stdout}


def main():
    lean = shutil.which('lean')
    assert lean is not None
    sources = ('EisensteinResidue.lean','Secp256k1TauFormula.lean',
               'Secp256k1TauNormalize.lean')
    receipt = {'schema':1,'toolchain':(HERE/'lean-toolchain').read_text().strip(),
               'source_sha256':{name:sha256((HERE/name).read_bytes()).hexdigest()
                                for name in sources},
               'lean4checker_fresh_available':shutil.which('lean4checker') is not None,
               'steps':[run([lean,'--version'],dict(os.environ))]}
    with TemporaryDirectory(prefix='secp256k1-tau-normalize-lean-') as temporary:
        env=dict(os.environ,LEAN_PATH=temporary)
        for name in sources:
            command = [lean,'-o',str(Path(temporary)/(Path(name).stem+'.olean')),name]
            receipt['steps'].append(run(command,env))
            if receipt['steps'][-1]['returncode'] != 0:
                break
    (HERE/'secp256k1-tau-normalize-lean-check.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    assert all(step['returncode'] == 0 for step in receipt['steps'])
    output = receipt['steps'][-1]['output']
    assert 'sorryAx' not in output
    for theorem in THEOREMS:
        lines = [line for line in output.splitlines()
                 if line.startswith(f"'Secp256k1TauNormalize.{theorem}'")]
        assert len(lines) == 1
        if not lines[0].endswith('does not depend on any axioms'):
            prefix = f"'Secp256k1TauNormalize.{theorem}' depends on axioms: ["
            assert lines[0].startswith(prefix) and lines[0].endswith(']')
            foundations = set(lines[0][len(prefix):-1].split(', '))
            assert foundations <= {'propext','Classical.choice','Quot.sound'}
    print(json.dumps({'ok':True,'theorems':len(THEOREMS),
                      'toolchain':receipt['toolchain']},sort_keys=True))


if __name__ == '__main__':
    main()
