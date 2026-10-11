#include <metal_stdlib>
using namespace metal;
struct Params { uint equations, blocks, mask_lo, mask_hi; };

// For each equation and high assignment, directly XOR the truth words of
// monomials whose high masks are subsets of that assignment. No solver roots,
// transform values or pivot information enter this computation.
kernel void gather_truth(device const uint2* coefficients [[buffer(0)]],
                         device uint2* values [[buffer(1)]],
                         constant Params& p [[buffer(3)]],
                         uint index [[thread_position_in_grid]]) {
    if (index >= p.equations*p.blocks) return;
    uint row=index/p.blocks, assignment=index%p.blocks;
    uint subset=assignment;
    uint2 value=uint2(0);
    do {
        value ^= coefficients[row*p.blocks+subset];
        if (!subset) break;
        subset=(subset-1)&assignment;
    } while (true);
    values[index]=value;
}

kernel void intersect_zeros(device const uint2* values [[buffer(1)]],
                            device uint2* roots [[buffer(2)]],
                            constant Params& p [[buffer(3)]],
                            uint block [[thread_position_in_grid]]) {
    if (block >= p.blocks) return;
    uint2 zero=uint2(p.mask_lo,p.mask_hi);
    for (uint row=0;row<p.equations;++row) zero &= ~values[row*p.blocks+block];
    roots[block]=zero;
}
