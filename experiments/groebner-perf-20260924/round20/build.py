"""Build the existing native components and bind every executed compiler command."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    commands = []
    original = subprocess.run
    def recorded(command, *args, **kwargs):
        commands.append([str(arg) for arg in command])
        return original(command, *args, **kwargs)
    subprocess.run = recorded
    try:
        for r in (4, 14, 15, 17, 18):
            runpy.run_path(str(HERE.parent/f'round{r}/build.py'), run_name='__main__')
        from ic_query import kernel
        # The shared kernel's normal cache key only includes C source. Rebuild
        # explicitly here so this receipt binds the actual compiler and flags.
        kernel_dir = kernel.HERE/'build'/kernel.SOURCE_SHA256[:16]
        kernel_dir.mkdir(parents=True, exist_ok=True)
        temporary = kernel_dir/f'round20-{os.getpid()}.so'
        cc = os.environ.get('CC', 'gcc')
        subprocess.run([cc, *kernel.CFLAGS, '-o', str(temporary), str(kernel.SOURCE)], check=True)
        os.replace(temporary, kernel_dir/'libpdpkernel.so')
        native_kernel = Path(kernel.lib()._name).resolve()
        compiler = os.environ.get('CXX', 'clang++')
        version = subprocess.check_output([compiler, '--version'], text=True)
        c_version = subprocess.check_output([cc, '--version'], text=True)
    finally:
        subprocess.run = original
    paths = {HERE/'build.py', ROOT/'experiments/pdp-degree-heuristics/kernel.py',
             ROOT/'experiments/pdp-degree-heuristics/pdpkernel.c'}
    binaries = {native_kernel}
    for r in (2, 4, 14, 15, 17, 18):
        folder = HERE.parent/f'round{r}'
        paths.update(p for p in folder.rglob('*') if (p.suffix in ('.cpp','.c','.h') or p.name == 'build.py')
                     and 'build' not in p.parts)
        binaries.update(p for p in (folder/'build').glob('*') if p.suffix in ('.dylib','.so'))
    out = HERE/'build'
    out.mkdir(exist_ok=True)
    (out/'receipt.json').write_text(json.dumps({'commands': commands, 'compiler': version, 'kernel_compiler': c_version,
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
        'binaries': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(binaries)},
        'kernel_cflags': kernel.CFLAGS}, indent=2)+'\n')


if __name__ == '__main__': main()
