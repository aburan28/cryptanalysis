#include <metal_stdlib>
using namespace metal;
constant uint Y [[function_constant(0)]];
constant uint LIMBS [[function_constant(1)]];
constant uint WORD_BITS [[function_constant(2)]];
constant uint GROUPS [[function_constant(3)]];
struct Group { uint mask, main, degree, feature[3], slot[3]; };
struct Parameters { uint branches, records, materialize; };

inline uint table_word(device const uint *table, constant Parameters &p, uint feature,
                       uint branch, uint lane)
{
    if (WORD_BITS == 32) return table[feature * p.branches + branch];
    return table[((feature * LIMBS + lane / 2) * p.branches + branch) * 2 + lane % 2];
}
inline uint witness_word(device const uint *u, uint record, uint slot, uint lane)
{
    return u[(record * (Y + 1) * LIMBS + slot * LIMBS) * 2 + lane];
}
inline uint identity_coefficient(device const uint *table, device const uint *u,
                                 constant Group &g, constant Parameters &p, uint record, uint branch)
{
    uint value = 0;
    for (uint lane = 0; lane < LIMBS * (WORD_BITS / 32); ++lane) {
        if (g.main != UINT_MAX) {
            uint combined = witness_word(u, record, 0, lane);
            for (uint j = 0; j < g.degree; ++j)
                combined ^= witness_word(u, record, g.slot[j], lane);
            value ^= combined & table_word(table, p, g.main, branch, lane);
        }
        for (uint j = 0; j < g.degree; ++j)
            value ^= witness_word(u, record, g.slot[j], lane) &
                     table_word(table, p, g.feature[j], branch, lane);
    }
    return popcount(value) & 1u;
}

kernel void check_records(device const uint *table [[buffer(0)]],
                          device const uint *u [[buffer(1)]],
                          device const uint *branches [[buffer(2)]],
                          constant Group *groups [[buffer(3)]],
                          device uint *first [[buffer(4)]],
                          device uchar *output [[buffer(5)]],
                          constant Parameters &p [[buffer(6)]], uint tid [[thread_position_in_grid]])
{
    if (tid >= p.records) return;
    uint bad = UINT_MAX;
    for (uint g = 0; g < GROUPS; ++g) {
        const uint value = identity_coefficient(table, u, groups[g], p, tid, branches[tid]);
        if (p.materialize) output[tid * GROUPS + g] = uchar(value);
        if (value != uint(groups[g].mask == 0)) bad = min(bad, groups[g].mask);
    }
    first[tid] = bad;
}

kernel void check_coefficients(device const uint *table [[buffer(0)]],
                               device const uint *u [[buffer(1)]],
                               device const uint *branches [[buffer(2)]],
                               constant Group *groups [[buffer(3)]],
                               device atomic_uint *first [[buffer(4)]],
                               device uchar *output [[buffer(5)]],
                               constant Parameters &p [[buffer(6)]], uint tid [[thread_position_in_grid]])
{
    if (tid >= p.records * GROUPS) return;
    // Adjacent lanes gather the same feature from neighboring selected branches.
    const uint record = tid % p.records, g = tid / p.records;
    const uint value = identity_coefficient(table, u, groups[g], p, record, branches[record]);
    if (p.materialize) output[record * GROUPS + g] = uchar(value);
    if (value != uint(groups[g].mask == 0))
        atomic_fetch_min_explicit(first + record, groups[g].mask, memory_order_relaxed);
}
