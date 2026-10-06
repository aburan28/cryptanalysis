#include <metal_stdlib>
using namespace metal;

struct Params { uint universe, lanes, low_width, high_width; };
constant uint LOW_TILE = 4096;
constant uint HIGH_BATCH = 32;

// Each lane contains 32 original equation coefficients, not assignment bits.
kernel void coefficient_low(device const uint* coefficients [[buffer(0)]],
                            device uint* partial [[buffer(1)]],
                            constant Params& p [[buffer(3)]],
                            uint group [[threadgroup_position_in_grid]],
                            uint tid [[thread_index_in_threadgroup]],
                            uint threads [[threads_per_threadgroup]]) {
    threadgroup uint tile[LOW_TILE];
    const uint lane = group/p.high_width, high = group%p.high_width;
    if (lane >= p.lanes) return;
    const uint base = lane*p.universe + high*p.low_width;
    for (uint j=tid; j<p.low_width; j+=threads) tile[j] = coefficients[base+j];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride=1; stride<p.low_width; stride<<=1) {
        for (uint pair=tid; pair<p.low_width/2; pair+=threads) {
            const uint lower = (pair/stride)*(2*stride) + pair%stride;
            tile[lower+stride] ^= tile[lower];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    for (uint j=tid; j<p.low_width; j+=threads) partial[base+j] = tile[j];
}

// Transform high coordinates explicitly: no exponentially growing subset gather.
// A group owns 32 adjacent low coordinates and at most 256 high coordinates.
kernel void coefficient_high(device uint* values [[buffer(0)]],
                             device const uint* partial [[buffer(1)]],
                             constant Params& p [[buffer(3)]],
                             uint group [[threadgroup_position_in_grid]],
                             uint tid [[thread_index_in_threadgroup]],
                             uint threads [[threads_per_threadgroup]]) {
    threadgroup uint tile[256*HIGH_BATCH];
    const uint batches = p.low_width/HIGH_BATCH;
    const uint lane = group/batches, low_base = (group%batches)*HIGH_BATCH;
    if (lane >= p.lanes) return;
    const uint count = p.high_width*HIGH_BATCH;
    for (uint j=tid; j<count; j+=threads)
        tile[j] = partial[lane*p.universe + (j/HIGH_BATCH)*p.low_width + low_base+j%HIGH_BATCH];
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride=1; stride<p.high_width; stride<<=1) {
        for (uint pair=tid; pair<count/2; pair+=threads) {
            const uint high_pair = pair/HIGH_BATCH, low = pair%HIGH_BATCH;
            const uint lower = (high_pair/stride)*(2*stride) + high_pair%stride;
            tile[(lower+stride)*HIGH_BATCH+low] ^= tile[lower*HIGH_BATCH+low];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    for (uint j=tid; j<count; j+=threads)
        values[lane*p.universe + (j/HIGH_BATCH)*p.low_width + low_base+j%HIGH_BATCH] = tile[j];
}

// Two 32-bit root words are the little-endian 64-bit word used by the frozen
// independent basis proof. Out-of-domain padding is always zero, even for n<6.
kernel void coefficient_roots(device const uint* values [[buffer(0)]],
                              device const uint* partial [[buffer(1)]],
                              device uint* roots [[buffer(2)]],
                              constant Params& p [[buffer(3)]],
                              uint word [[thread_position_in_grid]]) {
    const uint words = 2*((p.universe+63)/64);
    if (word >= words) return;
    uint result = 0;
    for (uint bit=0; bit<32 && word*32+bit<p.universe; ++bit) {
        const uint assignment = word*32+bit;
        uint value = 0;
        for (uint lane=0; lane<p.lanes; ++lane)
            value |= p.high_width == 1 ? partial[lane*p.universe+assignment]
                                      : values[lane*p.universe+assignment];
        if (!value) result |= 1u<<bit;
    }
    roots[word] = result;
}
