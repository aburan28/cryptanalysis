// Test-only C ABI. It materializes every output coefficient and instruments
// original-table reads; the timed checker does neither of these extra jobs.
#include "multiplier.h"
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <new>
struct TestIdentity {
    independent_identity::Layout layout;
    uint32_t equations, limbs;
    TestIdentity(uint32_t y, uint32_t e) : layout(y), equations(e), limbs((e + 63) / 64) {}
};
extern "C" void *identity_create(uint32_t y, uint32_t e)
{
    if (y < 1 || y > 10 || e < 1 || e > 128) return nullptr;
    try {
        return new TestIdentity(y, e);
    } catch (...) {
        return nullptr;
    }
}
extern "C" void identity_destroy(void *p) { delete static_cast<TestIdentity *>(p); }
extern "C" int identity_replay(void *p, uint32_t mode, const uint64_t *coefficients,
                               uint32_t coefficient_words, const uint64_t *witness,
                               uint32_t witness_words, unsigned char *output, uint32_t output_bytes,
                               uint64_t *stats, uint32_t stats_words)
{
    if (!p || !coefficients || !witness || !output || !stats || stats_words != 13 ||
        mode >= independent_identity::MODE_COUNT)
        return -1;
    const auto &w = *static_cast<TestIdentity *>(p);
    if (coefficient_words != w.layout.features * w.limbs ||
        witness_words != (w.layout.y + 1) * w.limbs || output_bytes != (1u << w.layout.y))
        return -1;
    if (w.equations % 64) {
        for (uint32_t i = w.limbs - 1; i < coefficient_words; i += w.limbs)
            if (coefficients[i] >> (w.equations % 64)) return -1;
        for (uint32_t i = w.limbs - 1; i < witness_words; i += w.limbs)
            if (witness[i] >> (w.equations % 64)) return -1;
    }
    std::fill_n(output, output_bytes, 0);
    uint64_t loads = 0;
    auto coefficient = [&](uint32_t feature, uint32_t limb) {
        ++loads;
        return coefficients[size_t(feature) * w.limbs + limb];
    };
    independent_identity::OutputSink materialize{output};
    independent_identity::evaluate(w.layout, mode, coefficient, witness, w.limbs, materialize);
    const uint64_t fill_loads = loads;
    loads = 0;
    independent_identity::CheckSink checked;
    const bool valid =
        independent_identity::evaluate(w.layout, mode, coefficient, witness, w.limbs, checked);
    const auto count = w.layout.counts(mode, w.limbs);
    stats[0] = count.ands;
    stats[1] = count.accumulator_xors;
    stats[2] = count.witness_xors;
    stats[3] = count.identity_xors;
    stats[4] = count.parities;
    stats[5] = count.table_loads;
    stats[6] = count.cached_loads;
    stats[7] = count.copy_words;
    stats[8] = valid;
    stats[9] = fill_loads;
    stats[10] = loads;
    stats[11] = sizeof(w.layout);
    stats[12] = w.layout.groups;
    return 0;
}
