"""Derive a small, hash-pinned checker change without changing the producer."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIN = '9736227264df81790d623dd52734b9f054f0571ed209a6e51f3898175c606f2a'


def generate():
    original = (HERE.parent/'round65/checker.cpp').read_bytes()
    assert hashlib.sha256(original).hexdigest() == PIN, 'Review changes to the reference checker explicitly.'
    text = original.decode()

    def replace(old, new):
        nonlocal text
        assert text.count(old) == 1, old
        text = text.replace(old, new)

    replace('#include "abi.h"', '#include "abi.h"\n#include "../constant_identity.h"\n#include "../constant_api.h"')
    replace('thread_local PreparationStats preparation_stats{};',
            'thread_local constant_identity::Stats constant_stats{};\nthread_local PreparationStats preparation_stats{};')
    replace('    bool partial_reserved = true;', '''    bool partial_reserved = true;
    using ConstantWorkspace = std::variant<std::monostate, constant_identity::Workspace<uint32_t>,
                                           constant_identity::Workspace<uint64_t>>;
    ConstantWorkspace constant_workspace;
    uint32_t constant_mode = 0;''')
    # The proof extent/equation-bit validation, original-ANF scatter, independent
    # symmetry guard and proof-symmetry check all precede this exact substitution.
    begin = text.index('    // Check a polynomial identity, not a producer\'s rank/consistency assertion:')
    end = text.index('    auto contradicted = std::chrono::steady_clock::now();', begin)
    old = text[begin:end]
    reference = old.replace('        if (bad) return 9;',
                            '        ++constant_stats.features;\n'
                            '        constant_stats.avoided_parities = symmetry_stats.avoided_constant_parities;\n'
                            '        if (bad) return 9;')
    new = '''    // Each prepared word comes from this proof after its equation bits and
    // symmetry aliases have been validated independently. No witness is cached.
    if (w.constant_mode) {
        auto &scratch = std::get<constant_identity::Workspace<Coefficient>>(w.constant_workspace);
        const auto prepared_started = std::chrono::steady_clock::now();
        scratch.prepare(proof, use_symmetry ? w.reuse.data() : nullptr);
        constant_stats.preparation_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - prepared_started).count();
        constant_stats.prepared_words = scratch.low.size() + scratch.high.size();
        constant_stats.used = 1;
        const auto checked = w.constant_mode == 1
            ? scratch.template check<false>(coefficients.data(), uint32_t(w.monomials.size()))
            : scratch.template check<true>(coefficients.data(), uint32_t(w.monomials.size()));
        constant_stats.features = checked.features;
        constant_stats.avoided_parities = checked.avoided_parities;
        symmetry_stats.avoided_constant_parities += checked.avoided_parities;
        constant_stats.seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - prepared_started).count();
#ifdef CHECKER_CONSTANT_AUDIT
        const auto reference = constant_identity::original(coefficients.data(), proof,
            use_symmetry ? w.reuse.data() : nullptr, w.branches,
            uint32_t(w.monomials.size()), w.limbs);
        constant_stats.audit_features = reference.features;
        if (reference.valid != checked.valid || reference.features != checked.features ||
            reference.avoided_parities != checked.avoided_parities) return 8;
#endif
        if (!checked.valid) return 9;
    } else {
''' + reference + '''        constant_stats.avoided_parities = symmetry_stats.avoided_constant_parities;
    }
'''
    text = text[:begin] + new + text[end:]
    replace('    preparation_stats = {};\n    reservation_stats = {};',
            '    constant_stats = {};\n    preparation_stats = {};\n    reservation_stats = {};')
    replace('        const bool ready = w.preparation_ready;', '''        constant_stats.requested = w.constant_mode;
        std::visit([&](const auto &scratch) {
            using S = std::decay_t<decltype(scratch)>;
            if constexpr (!std::is_same_v<S, std::monostate>)
                constant_stats.workspace_bytes = (scratch.low.size() + scratch.high.size()) *
                                                  sizeof(typename decltype(scratch.low)::value_type);
        }, w.constant_workspace);
        const bool ready = w.preparation_ready;''')
    text += '''
extern "C" uint64_t check_constant_stats_size() { return sizeof(constant_identity::Stats); }
extern "C" const constant_identity::Stats *check_last_constant_stats() { return &constant_stats; }
extern "C" int check_constant_configure(void *p, uint32_t mode)
{
    if (!p || mode > 2) return -1;
    auto &w = *static_cast<Checker *>(p);
    std::lock_guard<std::mutex> guard(w.mutex);
    w.preparation_ready = false;
    if (!mode) {
        w.constant_workspace = std::monostate{};
        w.constant_mode = 0;
        return 0;
    }
    try {
        if (!w.constant_mode) {
#ifdef CONSTANT_WORKSPACE_TEST_BYTES
            const uint64_t bytes = uint64_t(w.branches) * w.limbs * (w.equations <= 32 ? 4 : 8);
            if (bytes > CONSTANT_WORKSPACE_TEST_BYTES) return -3;
#endif
            // Construct before replacement: allocation failure preserves the
            // previous valid mode and storage. Configuration is outside queries.
            if (w.equations <= 32) {
                Checker::ConstantWorkspace fresh(std::in_place_type<constant_identity::Workspace<uint32_t>>,
                                                  w.branches, w.limbs);
                w.constant_workspace = std::move(fresh);
            } else {
                Checker::ConstantWorkspace fresh(std::in_place_type<constant_identity::Workspace<uint64_t>>,
                                                  w.branches, w.limbs);
                w.constant_workspace = std::move(fresh);
            }
        }
        w.constant_mode = mode;
        return 0;
    } catch (...) { return -3; }
}
'''
    return text


if __name__ == '__main__':
    print(generate(), end='')
