#include <metal_stdlib>
using namespace metal;

struct Parameters { uint branches, features, equations, active_branches; };

// One complete linearized branch per SIMD group. All lane permutations and
// collectives execute uniformly, including rank-deficient and empty rows.
kernel void quadratic_branches(device const uint* columns [[buffer(0)]],
                               device uint* result [[buffer(1)]],
                               constant Parameters& p [[buffer(2)]],
                               device const uint* branch_ids [[buffer(3)]],
                               uint group [[threadgroup_position_in_grid]],
                               ushort simd [[simdgroup_index_in_threadgroup]],
                               ushort lane [[thread_index_in_simdgroup]]) {
    uint item = group * 4 + simd;
    if (item >= p.active_branches) return; // Uniform for the whole SIMD group.
    uint branch = p.active_branches < p.branches ? branch_ids[item] : item;
    uint base = branch * (p.features + 1);
    uint row = 0;
    uint combination = lane < p.equations ? 1u << lane : 0;
    if (lane < p.equations) {
        for (uint j = 0; j < p.features; ++j)
            row |= ((columns[base+j+1] >> lane) & 1u) << j;
        row |= ((columns[base] >> lane) & 1u) << p.features;
    }
    uint rank = 0;
    for (uint j = 0; j < p.features; ++j) {
        uint bit = 1u << j;
        uint chosen = simd_min((lane >= rank && (row & bit)) ? uint(lane) : 32u);
        if (chosen < 32) {
            uint pivot = simd_shuffle(row, ushort(chosen));
            uint displaced = simd_shuffle(row, ushort(rank));
            uint pivot_combination = simd_shuffle(combination, ushort(chosen));
            uint displaced_combination = simd_shuffle(combination, ushort(rank));
            if (lane == rank) { row = pivot; combination = pivot_combination; }
            else {
                if (lane == chosen) { row = displaced; combination = displaced_combination; }
                if (row & bit) { row ^= pivot; combination ^= pivot_combination; }
            }
            ++rank;
        }
    }
    uint bad_lane = simd_min(row == (1u << p.features) ? uint(lane) : 32u);
    bool inconsistent = bad_lane < 32;
    uint witness = simd_shuffle(combination, ushort(min(bad_lane, 31u)));
    result[branch*34+1+lane] = row;
    if (lane == 0) {
        result[branch*34] = rank | (inconsistent ? 0x80000000u : 0u);
        result[branch*34+33] = inconsistent ? witness : 0;
    }
}
