"""Compact only the retained separator variables in a fresh F6 query."""
import hashlib

PARENT_SHA256 = '8a795423f79aa741f8b2ab981d5234cdf7ed57460e6742500b583b6c4e13b1ae'


def once(source, old, new):
    assert source.count(old) == 1, (old, source.count(old))
    return source.replace(old, new, 1)


def generate(source):
    assert hashlib.sha256(source.encode()).hexdigest() == PARENT_SHA256
    source = once(source,
        '#include "../groebner-f6-prepared-20261009/prepared_separator.cpp"',
        '#include "../../groebner-f6-prepared-20261009/prepared_separator.cpp"')
    source = once(source, '''}

extern "C" void* message_separator_create''', '''}

namespace {
uint64_t compact_scope(uint64_t original, uint64_t boundary) {
    uint64_t compact = 0;
    uint32_t position = 0;
    for (uint64_t todo = boundary; todo; todo &= todo - 1, ++position)
        if (original & (todo & (~todo + 1)))
            compact |= UINT64_C(1) << position;
    return compact;
}
uint64_t expand_scope(uint64_t compact, uint64_t boundary) {
    uint64_t original = 0;
    uint32_t position = 0;
    for (uint64_t todo = boundary; todo; todo &= todo - 1, ++position)
        if (compact & (UINT64_C(1) << position))
            original |= todo & (~todo + 1);
    return original;
}
}

extern "C" void* compact_separator_create''')
    source = once(source, 'extern "C" int message_separator_run(',
                  'extern "C" int compact_separator_run(')
    source = once(source, 'extern "C" void message_separator_destroy(',
                  'extern "C" void compact_separator_destroy(')
    source = once(source, '''        const auto reduction_start = Clock::now();
        const int code = eliminate(layout->source->nvars, layout->source->max_bag,
                                   max_states, std::move(factors), out->result);
''', '''        const auto reduction_start = Clock::now();
        for (auto& factor : factors) {
            if (factor.scope & ~layout->boundary_mask) {
                out->result.status = INVALID;
                out->result.stage = 2;
                out->query_elimination_ns = elapsed(reduction_start);
                return int(INVALID);
            }
            // Compacting preserves the increasing variable order used by each
            // factor's truth table, so its allowed words need no rewriting.
            factor.scope = compact_scope(factor.scope, layout->boundary_mask);
        }
        const int code = eliminate(bits(layout->boundary_mask),
                                   layout->source->max_bag, max_states,
                                   std::move(factors), out->result);
''')
    source = once(source,
        '            uint64_t assignment = out->result.assignment;\n',
        '            uint64_t assignment = expand_scope(out->result.assignment,\n'
        '                                               layout->boundary_mask);\n')
    return source
