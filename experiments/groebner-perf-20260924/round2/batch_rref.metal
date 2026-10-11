#include <metal_stdlib>
using namespace metal;

// One threadgroup per independent GF(2) matrix. The caller proves that the
// entire padded matrix fits in the supplied dynamic threadgroup allocation.
// Every row is owned by one lane during elimination, so its pivot bit is
// consumed before that lane overwrites it. No signature information is used.
struct BatchParams { uint rows, cols, words, count; };
kernel void batch_rref(device const uint* input [[buffer(0)]],
                       device uint* output [[buffer(1)]],
                       device uint* ranks [[buffer(2)]],
                       constant BatchParams& p [[buffer(3)]],
                       threadgroup uint* a [[threadgroup(0)]],
                       uint t [[thread_index_in_threadgroup]],
                       uint nt [[threads_per_threadgroup]],
                       uint lane [[thread_index_in_simdgroup]],
                       uint simd [[simdgroup_index_in_threadgroup]],
                       uint width [[threads_per_simdgroup]],
                       uint matrix [[threadgroup_position_in_grid]]) {
    if (matrix >= p.count) return;
    const uint size = p.rows * p.words;
    const uint base = matrix * size;
    const uint stride = p.words+1; // avoid power-of-two shared-memory bank conflicts
    for (uint i=t; i<size; i+=nt) a[(i/p.words)*stride+i%p.words] = input[base+i];
    threadgroup uint candidates[32];
    uint rank=0;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint col=0; col<p.cols && rank<p.rows; ++col) {
        uint mine=p.rows;
        for (uint row=rank+t; row<p.rows; row+=nt)
            if ((a[row*stride+col/32] >> (col%32)) & 1u) mine=min(mine,row);
        mine=simd_min(mine);
        if (lane==0) candidates[simd]=mine;
        threadgroup_barrier(mem_flags::mem_threadgroup);
        uint pivot=p.rows;
        for(uint group=0;group<nt/width;++group) pivot=min(pivot,candidates[group]);
        if (pivot==p.rows) {
            // Protect candidate reads before the next iteration overwrites them.
            threadgroup_barrier(mem_flags::mem_threadgroup);
            continue;
        }
        for (uint word=t; word<p.words; word+=nt) {
            uint v=a[rank*stride+word];
            a[rank*stride+word]=a[pivot*stride+word];
            a[pivot*stride+word]=v;
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint row=t; row<p.rows; row+=nt) {
            if (row==rank || !((a[row*stride+col/32]>>(col%32))&1u)) continue;
            for (uint word=col/32; word<p.words; ++word)
                a[row*stride+word]^=a[rank*stride+word];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        ++rank;
    }
    for (uint i=t; i<size; i+=nt) output[base+i]=a[(i/p.words)*stride+i%p.words];
    if (t==0) ranks[matrix]=rank;
}
