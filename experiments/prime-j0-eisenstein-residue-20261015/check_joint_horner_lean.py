#!/usr/bin/env python3
"""Build the joint Horner theorem with a fresh pinned Lean import chain."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
FILES = ('AlternateRadix.lean', 'HornerRadix.lean', 'JointHorner4033.lean')


def run(command, env):
    result = subprocess.run(command, cwd=HERE, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {'command': command, 'returncode': result.returncode,
            'output': result.stdout}


def main():
    lean = shutil.which('lean')
    assert lean is not None
    receipt = {
        'schema': 1,
        'toolchain': (HERE / 'lean-toolchain').read_text().strip(),
        'source_sha256': {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in FILES},
        'lean4checker_fresh_available': shutil.which('lean4checker') is not None,
        'steps': [run([lean, '--version'], os.environ)],
    }
    assert 'version 4.34.1' in receipt['steps'][0]['output']
    with TemporaryDirectory(prefix='joint-horner-lean-') as temp:
        env = dict(os.environ, LEAN_PATH=temp)
        for name in FILES:
            receipt['steps'].append(run(
                [lean, '-o', str(Path(temp) / (Path(name).stem + '.olean')), name], env))
            if receipt['steps'][-1]['returncode']:
                break
    (HERE / 'joint-horner-lean-check.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    assert all(step['returncode'] == 0 for step in receipt['steps'])
    output = receipt['steps'][-1]['output']
    assert "'JointHorner4033.joint_eq_sum' does not depend on any axioms" in output
    assert ("'JointHorner4033.joint_of_valid_traces' "
            "depends on axioms: [propext]" in output)
    assert 'sorryAx' not in output
    print(json.dumps({'ok': True, 'theorems': 2,
                      'toolchain': receipt['toolchain']}, sort_keys=True))


if __name__ == '__main__':
    main()
