"""Build the experimental Metal direct-ANF verifier with a frozen proof core."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def main():
    if sys.platform!='darwin': raise SystemExit('Metal experiment requires macOS')
    output=HERE/'build';output.mkdir(exist_ok=True)
    core=(HERE.parent/'round15/reference/boolean_certificate.cpp').read_text()
    assert hashlib.sha256(core.encode()).hexdigest()=='2f0a9df64e77edf2d24d3946b7e52cef8323c2a2c2bcc88726215941edd7d697'
    old='        std::sort(row.begin(), row.end());'
    assert core.count(old)==1
    core=core.replace(old,'        if (!std::is_sorted(row.begin(),row.end()))\n'+old)
    start=core.index('        std::vector<uint64_t> roots(blocks,')
    end=core.index('        out->roots = alive;',start)
    core=core[:start]+'''        std::vector<uint64_t> roots(blocks);
        uint32_t alive = gpu_input_roots(n,equations,low,roots);
'''+core[end:]
    (output/'gpu_core.inc').write_text(core)
    decoder=(HERE.parent/'round15/ordered_certificate.cpp').read_text()
    include='#include "build/sorted_core.inc"'
    assert decoder.count(include)==1
    (output/'gpu_decoder.inc').write_text(decoder.replace(include,'#include "gpu_core.inc"'))
    cxx=os.environ.get('CXX','clang++')
    commands=[];binaries={}
    for tag,flags in (('', ['-O3']),('-ubsan',['-O1','-g','-fsanitize=undefined',
                       '-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'])):
        path=output/('gpu-certificate'+tag+'.dylib')
        command=[cxx,'-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-function',
            '-fobjc-arc','-framework','Foundation','-framework','Metal','-dynamiclib',
            *flags,str(HERE/'gpu_certificate.mm'),'-o',str(path)]
        subprocess.run(command,check=True);commands.append(command)
        binaries[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (output/'receipt.json').write_text(json.dumps({'commands':commands,'binaries':binaries,
        'compiler':subprocess.check_output([cxx,'--version'],text=True),
        'generated_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.inc')},
        'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir()
                         if p.suffix in ('.py','.mm','.metal')}},indent=2)+'\n')


if __name__=='__main__': main()
