"""Isolate one change: retain the CPU mapping of each owned Metal allocation."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = HERE.parent / 'round22'
PREFIX = 'experiments/groebner-perf-20260924/'
PINNED = {
    PREFIX+'round22/build.py': '23792d085d0237b9cde5a5e6078a0cf1895b0eeadab37e18d1c7523a7681a8b4',
    PREFIX+'round22/coefficient_gpu.mm': '1512ce6b642c0f875fc277e662cf3af06d71b0ffba2b88ce016d31545894508d',
    PREFIX+'round22/test_coefficients.mm': '6adefb2f446c4fd9c827ebeb3e8d6632d428769ffb1002c33a927a1986664882',
}


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('mapping-generation anchor changed: '+old[:60])
    return text.replace(old, new)


def generated_sources(snapshot=None):
    def read(name):
        return (ROOT/name).read_text() if snapshot is None else snapshot[name]
    for name, expected in PINNED.items():
        if hashlib.sha256(read(name).encode()).hexdigest() != expected:
            raise ValueError('frozen source changed: '+name)
    # Execute only the locally pinned generator, never an archived snapshot.
    assert hashlib.sha256((BASE/'build.py').read_bytes()).hexdigest() == PINNED[PREFIX+'round22/build.py']
    spec = importlib.util.spec_from_file_location('pinned_coefficient_build', BASE/'build.py')
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    generated = base.generated_sources(snapshot)
    host = read(PREFIX+'round22/coefficient_gpu.mm')
    host = replace_once(host, '    size_t count;', '    size_t count;\n    Word *mapped = nullptr;')
    host = replace_once(host,
        '        if (!buffer || !buffer.contents) throw std::runtime_error("shared buffer allocation failed");',
        '        mapped = buffer ? static_cast<Word *>(buffer.contents) : nullptr;\n'
        '        if (!mapped) throw std::runtime_error("shared buffer allocation failed");')
    host = replace_once(host, '    Word *data() { return static_cast<Word *>(buffer.contents); }',
                        '    Word *data() { return mapped; }')
    host = replace_once(host, '    const Word *data() const { return static_cast<const Word *>(buffer.contents); }',
                        '    const Word *data() const { return mapped; }')
    generated['mapped_gpu.mm'] = host.replace('#include "build/', '#include "')
    test = read(PREFIX+'round22/test_coefficients.mm')
    test = replace_once(test, '#include "coefficient_gpu.mm"', '#include "mapped_gpu.mm"')
    test = replace_once(test, '                if (!w) throw std::runtime_error(truth_gpu_error());',
        '                if (!w) throw std::runtime_error(truth_gpu_error());\n'
        '                if (w->values.data() != w->values.buffer.contents || w->roots.data() != w->roots.buffer.contents)\n'
        '                    throw std::runtime_error("retained mapping mismatch");')
    generated['test_mapped.mm'] = test
    return generated


def main():
    if sys.platform != 'darwin':
        raise SystemExit('Metal requires macOS')
    out = HERE/'build'
    out.mkdir(exist_ok=True)
    generated = generated_sources()
    for name, source in generated.items():
        (out/name).write_text(source)
    compiler = os.environ.get('CXX', 'clang++')
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                       '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all'])):
        for basename, source, shared in (('mapped-gpu', 'mapped_gpu.mm', True),
                                         ('test-mapped', 'test_mapped.mm', False)):
            target = out/(basename+tag+('.dylib' if shared else ''))
            command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags,
                       '-fobjc-arc', '-framework', 'Foundation', '-framework', 'Metal',
                       *(['-dynamiclib'] if shared else []), str(out/source), '-o', str(target)]
            subprocess.run(command, check=True)
            commands.append(command)
            binaries[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    paths = [ROOT/name for name in PINNED] + [HERE/'build.py', BASE/'coefficient_truth.metal',
             HERE.parent/'round18/packed_verifier.cpp', HERE.parent/'round15/reference/boolean_certificate.cpp']
    (out/'receipt.json').write_text(json.dumps({
        'commands': commands, 'binaries': binaries,
        'compiler': subprocess.check_output([compiler, '--version'], text=True),
        'source_sha256': {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'generated_sha256': {name:hashlib.sha256(source.encode()).hexdigest() for name,source in generated.items()},
    }, indent=2)+'\n')


if __name__ == '__main__':
    main()
