"""Build shared-buffer Metal certification from pinned independent CPU checks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REFERENCE = HERE.parent/'round15/reference/boolean_certificate.cpp'
CPU = HERE.parent/'round18/packed_verifier.cpp'
PINNED = {REFERENCE: '2f0a9df64e77edf2d24d3946b7e52cef8323c2a2c2bcc88726215941edd7d697',
          CPU: 'e5241cfc3fdfac7c8ac76a4eb15934ca219f82f4d07b6ec9c81511bd6a88ccca'}


def generated_sources(snapshot=None):
    def read(path):
        return path.read_text() if snapshot is None else snapshot[str(path.relative_to(ROOT))]
    for path, expected in PINNED.items():
        if hashlib.sha256(read(path).encode()).hexdigest() != expected:
            raise ValueError(f'frozen checker changed: {path}')
    reference = read(REFERENCE)
    helpers = reference.split('extern "C" int boolean_certificate(', 1)[0]
    checks = '        out->roots = alive;' + reference.split('        out->roots = alive;', 1)[1].split(
        '    } catch (const std::invalid_argument&)', 1)[0]
    core = read(CPU).replace('#include "build/', '#include "')
    start, end = core.index('struct Workspace {'), core.index('static void validate(')
    core = core[:start] + core[end:]
    core = core.replace('auto &w = *static_cast<Workspace *>(handle);',
                        'auto &w = *static_cast<Workspace *>(handle);\n        w.begin_call();', 1)
    core = core.replace('8 * (w.values.size() + w.roots.size()) + w.present.size()',
                        'w.shared_bytes() + w.present.size()')
    start, end = core.index('        uint32_t alive = w.universe;'), core.index('        return check_basis(w, basis, alive, out);')
    core = core[:start] + '''        uint32_t alive = w.evaluate();
        result->zeta_words = w.stats.zeta_words;
        const auto proof_start = Clock::now();
        const int code = check_basis(w, basis, alive, out);
        w.stats.basis_check = elapsed(proof_start);
        w.stats.total = elapsed(w.start);
        return code;
''' + core[end + len('        return check_basis(w, basis, alive, out);\n'):]
    core = core.replace('catch (const std::exception &) { return nullptr; }',
                        'catch (const std::exception &e) { last_error = e.what(); return nullptr; }')
    core = core.replace('catch (const std::exception &) { return out->code = 7; }',
                        'catch (const std::exception &e) { last_error = e.what(); return out->code = 7; }')
    shader = read(HERE/'tiled_truth.metal')
    assert ')shader_source"' not in shader
    return {'certificate_helpers.inc': helpers, 'basis_checks.inc': checks,
            'packed_gpu_core.inc': core,
            'shader_source.inc': 'static const char *shader_source = R"shader_source('+shader+')shader_source";\n'}


def main():
    if sys.platform != 'darwin': raise SystemExit('Metal requires macOS')
    out = HERE/'build'
    out.mkdir(exist_ok=True)
    generated = generated_sources()
    for name, text in generated.items(): (out/name).write_text(text)
    compiler = os.environ.get('CXX','clang++')
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1','-g','-fsanitize=undefined',
                       '-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'])):
        path = out/('packed-gpu'+tag+'.dylib')
        command = [compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,
                   '-fobjc-arc','-framework','Foundation','-framework','Metal',
                   '-dynamiclib',str(HERE/'packed_gpu.mm'),'-o',str(path)]
        subprocess.run(command,check=True)
        commands.append(command)
        binaries[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    paths = (REFERENCE, CPU, HERE/'packed_gpu.mm', HERE/'tiled_truth.metal', HERE/'build.py')
    (out/'receipt.json').write_text(json.dumps({'commands': commands, 'binaries': binaries,
        'compiler': subprocess.check_output([compiler,'--version'],text=True),
        'source_sha256': {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'generated_sha256': {name:hashlib.sha256(text.encode()).hexdigest() for name,text in generated.items()}},indent=2)+'\n')


if __name__ == '__main__': main()
