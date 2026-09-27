#include <metal_stdlib>
using namespace metal;

struct Params { uint equations, blocks, mask_lo, mask_hi; };
constant uint TILE = 4096;

// A group transforms one equation/tile in 32 KiB of shared memory. The host
// launches complete groups, including when the active tile is smaller.
kernel void zeta_tiles(device const uint2* coefficients [[buffer(0)]],
                       device uint2* values [[buffer(1)]],
                       constant Params& p [[buffer(3)]],
                       uint group [[threadgroup_position_in_grid]],
                       uint tid [[thread_index_in_threadgroup]],
                       uint threads [[threads_per_threadgroup]]) {
    threadgroup uint2 tile[TILE];
    const uint width = min(p.blocks, TILE);
    const uint tiles = (p.blocks + TILE - 1) / TILE;
    const uint equation = group / tiles, part = group % tiles;
    if (equation >= p.equations) return; // Uniform for the entire group.
    const uint base = equation * p.blocks + part * TILE;
    for (uint j = tid; j < width; j += threads) tile[j] = coefficients[base+j];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride = 1; stride < width; stride <<= 1) {
        for (uint pair = tid; pair < width/2; pair += threads) {
            const uint lower = (pair/stride)*(2*stride) + pair%stride;
            tile[lower+stride] ^= tile[lower];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    for (uint j = tid; j < width; j += threads) values[base+j] = tile[j];
}

// Combine the at most four high tiles for nvars <= 20 while intersecting
// equations. This keeps the complete truth evaluation at two dispatches.
kernel void tiled_intersect(device const uint2* values [[buffer(1)]],
                            device uint2* roots [[buffer(2)]],
                            constant Params& p [[buffer(3)]],
                            uint block [[thread_position_in_grid]]) {
    if (block >= p.blocks) return;
    const uint high = block/TILE, low = block%TILE;
    uint2 zero = uint2(p.mask_lo, p.mask_hi);
    for (uint equation = 0; equation < p.equations; ++equation) {
        uint subset = high;
        uint2 value = uint2(0);
        do {
            value ^= values[equation*p.blocks + subset*TILE + low];
            if (!subset) break;
            subset = (subset-1)&high;
        } while (true);
        zero &= ~value;
    }
    roots[block] = zero;
}
