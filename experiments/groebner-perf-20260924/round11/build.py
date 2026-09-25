"""Build independent producer/checker libraries; retain the original CLI baseline."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def main():
    output=HERE/'build';output.mkdir(exist_ok=True)
    original=HERE.parent/'round5/native_f4.cpp'
    text=original.read_text()
    marker='\nstatic void print_success('
    if text.count(marker)!=1:
        raise RuntimeError('native Engine boundary changed; review the library adapter')
    (output/'native_engine.inc').write_text(text.split(marker)[0]+'\n')
    suffix='.dylib' if sys.platform=='darwin' else '.so'
    shared=['-dynamiclib'] if sys.platform=='darwin' else ['-shared','-fPIC']
    compiler=os.environ.get('CXX','clang++')
    commands=[]
    # Trap mode keeps UBSan checks in libraries loaded by signed macOS Python,
    # which can reject the dynamic sanitizer runtime under library validation.
    for tag,flags in [('', ['-O3']),('-ubsan',['-O1','-g','-fsanitize=undefined',
                        '-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'])]:
        for name in ('packed_producer','native_checker'):
            command=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,*shared,
                str(HERE/(name+'.cpp')),'-o',str(output/(name+tag+suffix))]
            subprocess.run(command,check=True);commands.append(command)
    (output/'build-receipt.json').write_text(json.dumps({'commands':commands,
        'engine_source_sha256':hashlib.sha256(original.read_bytes()).hexdigest()},indent=2)+'\n')
    subprocess.run([sys.executable,str(HERE.parent/'round5/build.py')],check=True)


if __name__=='__main__':
    main()
