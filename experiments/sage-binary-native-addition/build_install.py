"""Build and install this additive extension into the existing local Sage fork.

Run with experiments/sage-binary-arithmetic/run-sage.sh -python. The output
directory must be new; it retains the build log and prior installed files.
"""
import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
import sysconfig
from pathlib import Path

from sage.schemes.elliptic_curves import binary_batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    fork = root/'third_party/sage-binary'
    installed = Path(binary_batch.__file__).resolve().parent
    if not installed.is_relative_to((fork/'local').resolve()):
        raise RuntimeError('use the local fork launcher; refusing to change a different Sage')
    args.out.mkdir(parents=True, exist_ok=False)
    build = fork/'build/sage-distro'
    relative = Path('src/sage/schemes/elliptic_curves')
    filename = 'binary_batch_ntl'+sysconfig.get_config_var('EXT_SUFFIX')
    command = [str(fork/'sage'), '-sh', '-c', shlex.join([
        'ninja', '-C', str(build), '-j6', str(relative/filename)])]
    with (args.out/'build.log').open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    receipt = {'command':command, 'returncode':result.returncode, 'files':[]}
    (args.out/'build.json').write_text(json.dumps(receipt, indent=2)+'\n')
    result.check_returncode()
    backup = args.out/'previous-installed'
    backup.mkdir()
    for source in [fork/relative/'binary_batch.py', fork/relative/'binary_batch_ntl.pyx', build/relative/filename]:
        target = installed/source.name
        if target.exists():
            shutil.copy2(target, backup/source.name)
        shutil.copy2(source, target)
        receipt['files'].append({'source':str(source), 'target':str(target),
            'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    (args.out/'install.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(f'Installed native batch addition into {installed}')


if __name__ == '__main__':
    main()
