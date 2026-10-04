#include <metal_stdlib>
using namespace metal;

struct Parameters {
    uint branches, slices, lanes, bit;
    uint variables, lane_shift, low_bits;
};

// XOR zeta transform of the CHECKER's freshly scattered original coefficients.
// Within one stage, every destination is distinct and no source is a
// destination. Separate tracked compute passes order successive stages.
// Two uint lanes represent a uint64 coefficient without 64-bit GPU arithmetic.
kernel void independent_subset_stage(device uint *values [[buffer(0)]],
                                     constant Parameters &p [[buffer(1)]],
                                     uint tid [[thread_position_in_grid]])
{
    const uint pairs = p.branches / 2;
    if (tid >= p.slices * pairs * p.lanes) return;
    const uint lane = tid % p.lanes;
    const uint pair = (tid / p.lanes) % pairs;
    const uint slice = tid / (pairs * p.lanes);
    const uint low = slice * p.branches + (pair / p.bit) * (2 * p.bit) + pair % p.bit;
    values[(low + p.bit) * p.lanes + lane] ^= values[low * p.lanes + lane];
}

// The dimensions are powers of two. Express that invariant explicitly rather
// than asking the GPU to divide by dynamic uniform values for every XOR.
kernel void independent_subset_stage_bits(device uint *values [[buffer(0)]],
                                          constant Parameters &p [[buffer(1)]],
                                          uint tid [[thread_position_in_grid]])
{
    const uint pairs = p.branches / 2;
    if (tid >= p.slices * pairs * p.lanes) return;
    const uint lane = tid & (p.lanes - 1);
    const uint logical = tid >> p.lane_shift;
    const uint pair = logical & (pairs - 1);
    const uint slice = logical >> (p.variables - 1);
    const uint low = slice * p.branches + ((pair & ~(p.bit - 1)) << 1) + (pair & (p.bit - 1));
    values[((low + p.bit) << p.lane_shift) + lane] ^= values[(low << p.lane_shift) + lane];
}

// A full SIMD group participates, including padded threads. Each 32-bit lane
// holds its coefficient through all local butterflies. 64-bit coefficients
// occupy two lanes and never XOR their high and low halves together.
kernel void independent_subset_low(device uint *values [[buffer(0)]],
                                   constant Parameters &p [[buffer(1)]],
                                   uint tid [[thread_position_in_grid]])
{
    const uint count = p.slices * p.branches * p.lanes;
    uint value = tid < count ? values[tid] : 0;
    for (uint bit = 1u << (p.low_bits - 1); bit; bit >>= 1) {
        const uint distance = bit << p.lane_shift;
        const uint other = simd_shuffle(value, ushort((tid & 31u) ^ distance));
        if (tid & distance) value ^= other;
    }
    if (tid < count) values[tid] = value;
}
