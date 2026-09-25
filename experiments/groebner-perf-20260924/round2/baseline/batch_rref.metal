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
                       uint matrix [[threadgroup_position_in_grid]]) {
    if (matrix >= p.count) return;
    const uint size = p.rows * p.words;
    const uint base = matrix * size;
    for (uint i=t; i<size; i+=nt) a[i] = input[base+i];
    threadgroup atomic_uint best;
    uint rank=0;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint col=0; col<p.cols && rank<p.rows; ++col) {
        if (t==0) atomic_store_explicit(&best, p.rows, memory_order_relaxed);
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint row=rank+t; row<p.rows; row+=nt)
            if ((a[row*p.words+col/32] >> (col%32)) & 1u)
                atomic_fetch_min_explicit(&best, row, memory_order_relaxed);
        threadgroup_barrier(mem_flags::mem_threadgroup);
        const uint pivot=atomic_load_explicit(&best, memory_order_relaxed);
        if (pivot==p.rows) continue;
        for (uint word=t; word<p.words; word+=nt) {
            uint v=a[rank*p.words+word];
            a[rank*p.words+word]=a[pivot*p.words+word];
            a[pivot*p.words+word]=v;
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        for (uint row=t; row<p.rows; row+=nt) {
            if (row==rank || !((a[row*p.words+col/32]>>(col%32))&1u)) continue;
            for (uint word=col/32; word<p.words; ++word)
                a[row*p.words+word]^=a[rank*p.words+word];
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
        ++rank;
    }
    for (uint i=t; i<size; i+=nt) output[base+i]=a[i];
    if (t==0) ranks[matrix]=rank;
}
