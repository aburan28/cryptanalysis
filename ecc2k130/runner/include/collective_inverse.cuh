// Batch polynomial inverses across whole warps using a product tree.
// Each warp lane remains an independent tree; no walk points are combined.
#pragma once
#include "collective_root_policy.h"
#ifndef ECC_COLLECTIVE_WARPS
#define ECC_COLLECTIVE_WARPS 4
#endif
#ifndef ECC_STATIC_GROUP_BARRIERS
#define ECC_STATIC_GROUP_BARRIERS 0
#endif
#if ECC_COLLECTIVE_WARPS != 0 && ECC_COLLECTIVE_WARPS != 2 && ECC_COLLECTIVE_WARPS != 4 && ECC_COLLECTIVE_WARPS != 8 && ECC_COLLECTIVE_WARPS != 16
#error "ECC_COLLECTIVE_WARPS must be 0, 2, 4, 8 or 16"
#endif
namespace eccPacked131 {
#if ECC_STATIC_GROUP_BARRIERS
template<int WARPS,int ID=1>
__device__ __forceinline__ void goal30StaticGroupBarrier(int group){
    static_assert(ECC_THREADS/(32*WARPS)<=15,"barrier zero is reserved for the block");
    if constexpr(ID<=ECC_THREADS/(32*WARPS)){
        if(group==ID-1){
            asm volatile("barrier.sync %0, %1;" :: "n"(ID),"n"(32*WARPS) : "memory");
        }else goal30StaticGroupBarrier<WARPS,ID+1>(group);
    }
}
#endif
template<int WARPS>
__device__ __forceinline__ void goal22GroupBarrier() {
    // Barrier zero belongs to the walk's ordinary block synchronization.
    // Every group owns a distinct ID and consists of complete warps.
#if ECC_STATIC_GROUP_BARRIERS
    goal30StaticGroupBarrier<WARPS>(int(threadIdx.x)/(32*WARPS));
#else
    const int id = 1 + int(threadIdx.x) / (32 * WARPS);
    asm volatile("barrier.sync %0, %1;" :: "r"(id), "n"(32 * WARPS) : "memory");
#endif
}
template<int WARPS>
__device__ __noinline__ P131 goal22CollectiveInverse(P131 input) {
    static_assert(WARPS == 2 || WARPS == 4 || WARPS == 8 || WARPS == 16);
    static_assert(ECC_THREADS % (32 * WARPS) == 0);
    constexpr int LEVELS = WARPS == 2 ? 1 : WARPS == 4 ? 2 : WARPS == 8 ? 3 : 4;
    __shared__ uint32_t values[5 * ECC_THREADS];
    // Rotate logical warp identities within each physical barrier group.
    // This changes the reduction tree's placement, never its field result.
    const int physicalWarp = int(threadIdx.x) / 32;
    const int group = physicalWarp / WARPS;
    // With two-warp groups, rotate every pair of groups so roots visit
    // all four relative warp positions rather than alternating two of them.
    const int rotation = collectiveRootRotation<WARPS>(group,unsigned(blockIdx.x));
    const int logicalWarp = (physicalWarp % WARPS + rotation) % WARPS;
    const int warp = group * WARPS + logicalWarp;
    const int tid = warp * 32 + int(threadIdx.x) % 32;
    const bool zero = !(input.v[0] | input.v[1] | input.v[2] | input.v[3] | input.v[4]);
    P131 acc = zero ? P131{{1, 0, 0, 0, 0}} : input;
    P131 right[LEVELS];
#pragma unroll
    for (int i = 0; i < 5; ++i) values[i * ECC_THREADS + tid] = acc.v[i];
    goal22GroupBarrier<WARPS>();
#pragma unroll
    for (int level = 0; level < LEVELS; ++level) {
        const int width = 1 << (level + 1), offset = 32 << level;
        if ((warp & (width - 1)) == width - 1) {
            right[level] = acc;
            P131 left;
#pragma unroll
            for (int i = 0; i < 5; ++i) left.v[i] = values[i * ECC_THREADS + tid - offset];
            acc = mulPolynomial131(left, acc);
#pragma unroll
            for (int i = 0; i < 5; ++i) values[i * ECC_THREADS + tid] = acc.v[i];
        }
        goal22GroupBarrier<WARPS>();
    }
    if ((warp & (WARPS - 1)) == WARPS - 1) {
        acc = toPolynomial131(inv131(fromPolynomial131(acc)));
#pragma unroll
        for (int i = 0; i < 5; ++i) values[i * ECC_THREADS + tid] = acc.v[i];
    }
    goal22GroupBarrier<WARPS>();
#pragma unroll
    for (int level = LEVELS - 1; level >= 0; --level) {
        const int width = 1 << (level + 1), offset = 32 << level;
        if ((warp & (width - 1)) == width - 1) {
            P131 parent, left;
#pragma unroll
            for (int i = 0; i < 5; ++i) {
                parent.v[i] = values[i * ECC_THREADS + tid];
                left.v[i] = values[i * ECC_THREADS + tid - offset];
            }
            const PolynomialPair inverse = mulPolynomialPair131(parent, right[level], left);
#pragma unroll
            for (int i = 0; i < 5; ++i) {
                values[i * ECC_THREADS + tid - offset] = inverse.first.v[i];
                values[i * ECC_THREADS + tid] = inverse.second.v[i];
            }
        }
        goal22GroupBarrier<WARPS>();
    }
    P131 out;
#pragma unroll
    for (int i = 0; i < 5; ++i) out.v[i] = values[i * ECC_THREADS + tid];
    // All readers must finish before another call may reuse the scratch.
    goal22GroupBarrier<WARPS>();
    return zero ? P131{{0, 0, 0, 0, 0}} : out;
}
__device__ __forceinline__ P131 batchInverse131(P131 input, int workers) {
#if ECC_COLLECTIVE_WARPS
    if ((blockIdx.x + 1) * blockDim.x <= workers)
        return goal22CollectiveInverse<ECC_COLLECTIVE_WARPS>(input);
#endif
    return toPolynomial131(inv131(fromPolynomial131(input)));
}
} // namespace eccPacked131
