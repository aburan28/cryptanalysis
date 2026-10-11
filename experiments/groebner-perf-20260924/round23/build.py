"""Pin the independent evaluator and generate bounded sparse exact-proof variants."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREFIX = 'experiments/groebner-perf-20260924/'
PINNED = {
    PREFIX + 'round15/reference/boolean_certificate.cpp':
        '2f0a9df64e77edf2d24d3946b7e52cef8323c2a2c2bcc88726215941edd7d697',
    PREFIX + 'round18/packed_verifier.cpp':
        'e5241cfc3fdfac7c8ac76a4eb15934ca219f82f4d07b6ec9c81511bd6a88ccca',
}


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('frozen generation anchor changed: ' + old[:70])
    return source.replace(old, new)


def generated_sources(snapshot):
    for name, expected in PINNED.items():
        if hashlib.sha256(snapshot[name].encode()).hexdigest() != expected:
            raise ValueError('frozen reference changed: ' + name)
    reference = snapshot[PREFIX + 'round15/reference/boolean_certificate.cpp']
    helpers = reference.split('extern "C" int boolean_certificate(', 1)[0]
    checks = '        out->roots = alive;' + reference.split('        out->roots = alive;', 1)[1].split(
        '    } catch (const std::invalid_argument&)', 1)[0]
    dense = replace_once(checks, '        std::vector<uint64_t> forbidden(blocks, 0);',
        '        stats.dense_table_bytes = uint64_t(blocks) * sizeof(uint64_t);\n'
        '        std::vector<uint64_t> forbidden(blocks, 0);')
    start = dense.index('        // Check output only on independently established input roots.')
    end = dense.index('        std::vector<uint32_t> leading;')
    compact = dense[:start] + '''        for (const auto &row : basis)
            for (uint32_t i = 0; i < alive; ++i) {
                ++stats.root_parity_tests;
                if (parity(row, w.proof_storage.roots[i])) return out->code = 2;
            }
''' + dense[end:]
    start = compact.index('        if (alive <= 256)')
    end = compact.index('        return 0;', start)
    compact = compact[:start] + '''        for (uint32_t i = 0; i < alive; ++i)
            out->solutions[out->solution_count++] = w.proof_storage.roots[i];
''' + compact[end:]
    core = snapshot[PREFIX + 'round18/packed_verifier.cpp']
    core = replace_once(core, '#include "build/certificate_helpers.inc"',
                        '#include "certificate_helpers.inc"\n#include "../proof_types.hpp"')
    core = replace_once(core, '    uint64_t zeta_words, coefficient_bits, scratch_bytes;',
                        '    uint64_t zeta_words, coefficient_bits, scratch_bytes;\n    ProofStats proof;')
    core = replace_once(core, '    std::vector<uint8_t> present;',
                        '    std::vector<uint8_t> present;\n    ProofStorage proof_storage;\n    uint32_t proof_mode = 2;')
    start = core.index('static int check_basis(')
    end = core.index('extern "C" void *truth_create(', start)
    core = core[:start] + '#include "../sparse_proof.hpp"\n\n' + core[end:]
    core = replace_once(core, '        return check_basis(w, basis, alive, out);', '''        const auto started = std::chrono::steady_clock::now();
        const auto code = check_basis(w, basis, alive, out, result->proof);
        result->proof.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        result->scratch_bytes += result->proof.workspace_bytes;
        return code;''')
    core += '''
extern "C" void *truth_create_mode(uint32_t n, uint32_t equations, uint32_t mode)
{
    if (mode > 2) return nullptr;
    auto *handle = static_cast<Workspace *>(truth_create(n, equations));
    if (handle) handle->proof_mode = mode;
    return handle;
}
'''
    return {'certificate_helpers.inc': helpers, 'dense_basis_checks.inc': dense,
            'root_list_checks.inc': compact, 'sparse_verifier.cpp': core}


def main():
    paths = [ROOT / name for name in PINNED] + [HERE / name for name in
             ('build.py', 'proof_types.hpp', 'sparse_proof.hpp')]
    snapshot = {str(p.relative_to(ROOT)): p.read_text() for p in paths}
    generated = generated_sources(snapshot)
    output = HERE / 'build'
    output.mkdir(exist_ok=True)
    for name, source in generated.items():
        (output / name).write_text(source)
    compiler = os.environ.get('CXX', 'clang++')
    shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    commands, binaries = [], {}
    for tag, flags in (('', ['-O3']), ('-ubsan', ['-O1', '-g', '-fsanitize=undefined',
                       '-fsanitize-undefined-trap-on-error', '-fno-sanitize-recover=all']),
                       ('-budget', ['-O2', '-DSPARSE_PROOF_BUDGET=8'])):
        target = output / ('sparse-verifier' + tag + suffix)
        command = [compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', *shared,
                   *flags, str(output / 'sparse_verifier.cpp'), '-o', str(target)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / 'receipt.json').write_text(json.dumps({
        'commands': commands, 'binaries': binaries,
        'compiler': subprocess.check_output([compiler, '--version'], text=True),
        'source_sha256': {name: hashlib.sha256(text.encode()).hexdigest() for name, text in snapshot.items()},
        'generated_sha256': {name: hashlib.sha256(text.encode()).hexdigest() for name, text in generated.items()},
        'test_only_budget_binary': 'sparse-verifier-budget' + suffix,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
