#include <metal_stdlib>
using namespace metal;

// Specialized once for the invariant coefficient layout. No equation data or
// target-dependent value is a function constant.
constant uint STRIDE [[function_constant(0)]];
struct Parameters { uint branches, bit; };

kernel void producer_stage(device uint *values [[buffer(0)]],
                           constant Parameters &p [[buffer(1)]],
                           uint index [[thread_position_in_grid]]) {
    if (index >= (p.branches / 2) * STRIDE) return;
    const uint pair = index / STRIDE, feature = index % STRIDE;
    const uint lower = (pair & (p.bit - 1)) | ((pair & ~(p.bit - 1)) << 1);
    values[(lower | p.bit) * STRIDE + feature] ^= values[lower * STRIDE + feature];
}

// Sixteen rows by sixteen features; all lanes cross every barrier, including
// feature padding and the unused rows of very small tables. Fuse up to four
// ascending branch stages without further device-memory round trips.
kernel void producer_low_tile(device uint *values [[buffer(0)]],
                              constant Parameters &p [[buffer(1)]],
                              uint lane [[thread_index_in_threadgroup]],
                              uint2 group [[threadgroup_position_in_grid]]) {
    threadgroup uint tile[256];
    const uint local_row = lane >> 4, feature = group.y * 16 + (lane & 15);
    const uint row = group.x * 16 + local_row;
    const bool active = row < p.branches && feature < STRIDE;
    tile[lane] = active ? values[row * STRIDE + feature] : 0;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint bit = 1; bit < min(p.branches, 16u); bit <<= 1) {
        uint next = tile[lane];
        if (local_row & bit) next ^= tile[lane - bit * 16];
        threadgroup_barrier(mem_flags::mem_threadgroup);
        tile[lane] = next;
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (active) values[row * STRIDE + feature] = tile[lane];
}
