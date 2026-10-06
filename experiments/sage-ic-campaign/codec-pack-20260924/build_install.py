"""Build and install the changed codec extension into the local Sage fork."""
import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
import sysconfig
from pathlib import Path

from sage.schemes.elliptic_curves import binary_hardware_codec


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    fork = root / 'third_party/sage-binary'
    installed = Path(binary_hardware_codec.__file__).resolve().parent
    if not installed.is_relative_to((fork / 'local').resolve()):
        raise RuntimeError('refusing to install outside the local Sage fork')
    args.out.mkdir(parents=True, exist_ok=False)
    relative = Path('src/sage/schemes/elliptic_curves')
    name = 'binary_hardware_codec' + sysconfig.get_config_var('EXT_SUFFIX')
    build = fork / 'build/sage-distro'
    command = [str(fork / 'sage'), '-sh', '-c', shlex.join([
        'ninja', '-C', str(build), '-j6', str(relative / name)])]
    with (args.out / 'build.log').open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                timeout=600)
    (args.out / 'build.json').write_text(json.dumps({
        'command': command, 'returncode': result.returncode}, indent=2) + '\n')
    result.check_returncode()
    previous = args.out / 'previous-installed'
    previous.mkdir()
    files = []
    for source in (fork / relative / 'binary_hardware_codec.pyx', build / relative / name):
        target = installed / source.name
        if target.exists():
            shutil.copy2(target, previous / source.name)
        shutil.copy2(source, target)
        files.append({'source': str(source), 'target': str(target),
                      'sha256': sha(target)})
    (args.out / 'install.json').write_text(json.dumps({'files': files}, indent=2) + '\n')
    print('Installed', name, 'into', installed)


if __name__ == '__main__':
    main()
