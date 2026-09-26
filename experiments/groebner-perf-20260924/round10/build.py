"""Build the experiment and its independent round-four checker."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--m4ri-prefix',type=Path)
    parser.add_argument('--cpu-only',action='store_true')
    args = parser.parse_args()
    compiler = os.environ.get('CXX','clang++')
    includes = ([f'-I{args.m4ri_prefix}/include',f'-L{args.m4ri_prefix}/lib','-lm4ri'] if args.m4ri_prefix
                else subprocess.check_output(['pkg-config','--cflags','--libs','m4ri'],text=True).split())
    mac = sys.platform == 'darwin'
    shared = ['-dynamiclib'] if mac else ['-shared','-fPIC']
    suffix = '.dylib' if mac else '.so'
    (HERE/'build').mkdir(exist_ok=True)
    common = [compiler,'-O3','-std=c++17']
    flags = (['-x','c++','-DHYBRID_CPU_ONLY'] if args.cpu_only or not mac else
             ['-fobjc-arc','-framework','Foundation','-framework','Metal'])
    subprocess.run([*common,*shared,*flags,str(HERE/'hybrid_query.mm'),*includes,
                    '-o',str(HERE/'build'/('hybrid_query'+suffix))],check=True)
    if mac and not args.cpu_only:
        subprocess.run([*common,*flags,str(HERE/'test_workspace.mm'),*includes,
                        '-o',str(HERE/'build/test-workspace')],check=True)
    subprocess.run([sys.executable,str(HERE.parent/'round4/build.py')],check=True)


if __name__ == '__main__':
    main()
