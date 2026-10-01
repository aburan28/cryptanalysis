#include <metal_stdlib>
using namespace metal;

struct Parameters {
    uint branches, features, equations, active_branches;
};

inline uint2 row_bit(uint bit)
{
    return bit < 32 ? uint2(1u << bit, 0) : uint2(0, 1u << (bit - 32));
}
inline bool has_bit(uint2 row, uint2 bit) { return (row.x & bit.x) != 0 || (row.y & bit.y) != 0; }
inline uint2 shuffle_row(uint2 row, ushort lane)
{
    return uint2(simd_shuffle(row.x, lane), simd_shuffle(row.y, lane));
}

// One complete residual branch per SIMD group. Both words participate in
// every lane exchange. Rank/empty-row control flow stays group-uniform.
kernel void quadratic_branches(device const uint *columns [[buffer(0)]],
                               device uint *result [[buffer(1)]],
                               constant Parameters &p [[buffer(2)]],
                               device const uint *branch_ids [[buffer(3)]],
                               uint group [[threadgroup_position_in_grid]],
                               ushort simd [[simdgroup_index_in_threadgroup]],
                               ushort lane [[thread_index_in_simdgroup]])
{
    uint item = group * 4 + simd;
    if (item >= p.active_branches) return;
    uint branch = p.active_branches < p.branches ? branch_ids[item] : item;
    uint base = branch * (p.features + 1);
    uint2 row = uint2(0);
    uint combination = lane < p.equations ? 1u << lane : 0;
    if (lane < p.equations) {
        for (uint j = 0; j < p.features; ++j)
            if ((columns[base + j + 1] >> lane) & 1u) row |= row_bit(j);
        if ((columns[base] >> lane) & 1u) row |= row_bit(p.features);
    }
    uint rank = 0;
    for (uint j = 0; j < p.features; ++j) {
        uint2 bit = row_bit(j);
        uint chosen = simd_min(lane >= rank && has_bit(row, bit) ? uint(lane) : 32u);
        if (chosen < 32) {
            uint2 pivot = shuffle_row(row, ushort(chosen));
            uint2 displaced = shuffle_row(row, ushort(rank));
            uint pivot_combination = simd_shuffle(combination, ushort(chosen));
            uint displaced_combination = simd_shuffle(combination, ushort(rank));
            if (lane == rank) {
                row = pivot;
                combination = pivot_combination;
            } else {
                if (lane == chosen) {
                    row = displaced;
                    combination = displaced_combination;
                }
                if (has_bit(row, bit)) {
                    row ^= pivot;
                    combination ^= pivot_combination;
                }
            }
            ++rank;
        }
    }
    uint bad_lane = simd_min(all(row == row_bit(p.features)) ? uint(lane) : 32u);
    bool inconsistent = bad_lane < 32;
    uint witness = simd_shuffle(combination, ushort(min(bad_lane, 31u)));
    // Explicit little-endian pairs:34 uint64 host cells, no native64-bit
    // shuffle requirement. Row storage and output bytes are fully charged.
    result[branch * 68 + 2 + 2 * lane] = row.x;
    result[branch * 68 + 3 + 2 * lane] = row.y;
    if (lane == 0) {
        result[branch * 68] = rank | (inconsistent ? 0x80000000u : 0u);
        result[branch * 68 + 1] = 0;
        result[branch * 68 + 66] = inconsistent ? witness : 0;
        result[branch * 68 + 67] = 0;
    }
}
