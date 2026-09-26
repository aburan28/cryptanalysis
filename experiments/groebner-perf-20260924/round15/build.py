"""Build frozen, sorted-row and shared-order independent certificate variants."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PINNED = {
    'boolean_certificate.cpp': '2f0a9df64e77edf2d24d3946b7e52cef8323c2a2c2bcc88726215941edd7d697',
    'packed_certificate.cpp': '0d5001dddf05def2bd1fdfb50a136b9503f7974a099ed6cef2e9c3c7f2643101',
}


def main():
    output = HERE/'build'
    output.mkdir(exist_ok=True)
    sources = {}
    for name, expected in PINNED.items():
        data = (HERE/'reference'/name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'frozen reference mismatch: {name}')
        sources[name] = data.decode()
    original = sources['boolean_certificate.cpp']
    old = '        std::sort(row.begin(), row.end());'
    assert original.count(old) == 1
    changed = original.replace(old, '        if (!std::is_sorted(row.begin(), row.end()))\n'+old+' // unordered input')
    (output/'original_core.inc').write_text(original)
    (output/'sorted_core.inc').write_text(changed)
    include = '#include "../../pdp-scaling/boolean_certificate.cpp"'
    decoder = sources['packed_certificate.cpp']
    assert decoder.count(include) == 1
    for arm, core in (('baseline','original'), ('row-check','sorted')):
        (output/(arm+'.cpp')).write_text(decoder.replace(include, f'#include "{core}_core.inc"'))
    cxx = os.environ.get('CXX','clang++')
    suffix = '.dylib' if sys.platform=='darwin' else '.so'
    shared = ['-dynamiclib'] if sys.platform=='darwin' else ['-shared','-fPIC']
    commands, binaries = [], {}
    for arm in ('baseline','row-check','ordered'):
        source = HERE/'ordered_certificate.cpp' if arm=='ordered' else output/(arm+'.cpp')
        for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1','-g','-fsanitize=undefined',
                            '-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'])):
            path = output/(arm+tag+suffix)
            cmd = [cxx,'-std=c++17','-Wall','-Wextra','-Werror',*shared,*flags,str(source),'-o',str(path)]
            subprocess.run(cmd,check=True)
            commands.append(cmd)
            binaries[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    generated = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()
                 if p.suffix in ('.inc','.cpp')}
    (output/'receipt.json').write_text(json.dumps({'commands':commands,'binaries':binaries,
        'compiler':subprocess.check_output([cxx,'--version'],text=True),
        'reference_sha256':PINNED,'generated_sha256':generated,
        'ordered_source_sha256':hashlib.sha256((HERE/'ordered_certificate.cpp').read_bytes()).hexdigest()},indent=2)+'\n')


if __name__=='__main__': main()
