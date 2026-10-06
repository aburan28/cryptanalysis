#include <metal_stdlib>
using namespace metal;

struct Parameters { uint branches, features, equations; };

// One complete linearized branch per SIMD group. All lane permutations and
// collectives execute uniformly, including rank-deficient and empty rows.
kernel void quadratic_branches(device const uint4* columns [[buffer(0)]],
                               device uint* result [[buffer(1)]],
                               constant Parameters& p [[buffer(2)]],
                               uint group [[threadgroup_position_in_grid]],
                               ushort simd [[simdgroup_index_in_threadgroup]],
                               ushort lane [[thread_index_in_simdgroup]]) {
    uint branch = group * 4 + simd;
    if (branch >= p.branches) return; // Uniform for the whole SIMD group.
    uint base = branch * (p.features + 1);
    uint row = 0;
    if (lane < p.equations) {
        for (uint j = 0; j < p.features; ++j)
            row |= ((columns[base+j+1].x >> lane) & 1u) << j;
        row |= ((columns[base].x >> lane) & 1u) << p.features;
    }
    uint rank = 0;
    for (uint j = 0; j < p.features; ++j) {
        uint bit = 1u << j;
        uint chosen = simd_min((lane >= rank && (row & bit)) ? uint(lane) : 32u);
        if (chosen < 32) {
            uint pivot = simd_shuffle(row, ushort(chosen));
            uint displaced = simd_shuffle(row, ushort(rank));
            if (lane == rank) row = pivot;
            else {
                if (lane == chosen) row = displaced;
                if (row & bit) row ^= pivot;
            }
            ++rank;
        }
    }
    bool inconsistent = simd_any(row == (1u << p.features));
    result[branch*33+1+lane] = row;
    if (lane == 0) result[branch*33] = rank | (inconsistent ? 0x80000000u : 0u);
}
