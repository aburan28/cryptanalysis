#!/usr/bin/env python3
"""Build the sparse-radix theorems in a fresh pinned Lean environment."""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
THEOREMS = ('sparse_pair_shortcut','sparse_norm','tau_residue',
            'tau_residue_polynomial','sparse_residue_multiple','sparse_pair_norm',
            'quotient_step','valid_trace_evaluates','map_evaluatePairs',
            'point_horner_of_valid_trace')


def run(command,env):
    completed = subprocess.run(command,cwd=HERE,env=env,text=True,
                               stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    return {'command':command,'returncode':completed.returncode,'output':completed.stdout}


def main():
    lean = shutil.which('lean')
    assert lean is not None
    receipt = {'schema':1,'toolchain':(HERE/'lean-toolchain').read_text().strip(),
               'source_sha256':{name:sha256((HERE/name).read_bytes()).hexdigest()
                                for name in ('AlternateRadix.lean','SparseTauRadix.lean')},
               'lean4checker_fresh_available':shutil.which('lean4checker') is not None,
               'steps':[]}
    receipt['steps'].append(run([lean,'--version'],dict(os.environ)))
    with TemporaryDirectory(prefix='sparse-tau-lean-') as temporary:
        env=dict(os.environ,LEAN_PATH=temporary)
        receipt['steps'].append(run([lean,'-o',str(Path(temporary)/'AlternateRadix.olean'),
                                     'AlternateRadix.lean'],env))
        if receipt['steps'][-1]['returncode'] == 0:
            receipt['steps'].append(run([lean,'SparseTauRadix.lean'],env))
    (HERE/'sparse-tau-lean-check.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    assert all(step['returncode'] == 0 for step in receipt['steps'])
    output = receipt['steps'][-1]['output']
    assert 'sorryAx' not in output
    for theorem in THEOREMS:
        lines = [line for line in output.splitlines()
                 if line.startswith(f"'SparseTauRadix.{theorem}'")]
        assert len(lines) == 1
        assert lines[0].endswith(('does not depend on any axioms',
                                  'depends on axioms: [propext]',
                                  'depends on axioms: [propext, Quot.sound]'))
    print(json.dumps({'ok':True,'theorems':len(THEOREMS),
                      'toolchain':receipt['toolchain']},sort_keys=True))


if __name__ == '__main__':
    main()
