// Vectorized low limbs plus a byte tail in grouped inversion scratch.
// Each warp lane remains an independent tree; no walk points are combined.
#pragma once
namespace eccPacked131 {
// Each stored value is a reduced polynomial field element (top in 0..7).
__device__ __forceinline__ P131 goal22GroupLoad(const uint4 *low, const unsigned char *top, int tid) {
    const uint4 v = low[tid];
    return P131{{v.x, v.y, v.z, v.w, unsigned(top[tid])}};
}
__device__ __forceinline__ void goal22GroupStore(uint4 *low, unsigned char *top, int tid, P131 v) {
    low[tid] = uint4{v.v[0], v.v[1], v.v[2], v.v[3]};
    top[tid] = static_cast<unsigned char>(v.v[4]);
}
template<int WARPS>
__device__ __forceinline__ void goal22GroupBarrier() {
    // Barrier zero belongs to the walk's ordinary block synchronization.
    // Every group owns a distinct ID and consists of complete warps.
    const int id = 1 + int(threadIdx.x) / (32 * WARPS);
    asm volatile("barrier.sync %0, %1;" :: "r"(id), "n"(32 * WARPS) : "memory");
}
template<int WARPS>
__device__ __noinline__ P131 goal22CollectiveInverse(P131 input) {
    static_assert(WARPS == 2 || WARPS == 4 || WARPS == 8 || WARPS == 16);
    static_assert(ECC_THREADS % (32 * WARPS) == 0);
    constexpr int LEVELS = WARPS == 2 ? 1 : WARPS == 4 ? 2 : WARPS == 8 ? 3 : 4;
    __shared__ uint4 low[ECC_THREADS];
    __shared__ unsigned char top[ECC_THREADS];
    // Rotate logical warp identities within each physical barrier group.
    // This changes the reduction tree's placement, never its field result.
    const int physicalWarp = int(threadIdx.x) / 32;
    const int group = physicalWarp / WARPS;
    // With two-warp groups, rotate every pair of groups so roots visit
    // all four relative warp positions rather than alternating two of them.
    const int rotation = group / (WARPS < 4 ? 4 / WARPS : 1);
    const int logicalWarp = (physicalWarp % WARPS + rotation) % WARPS;
    const int warp = group * WARPS + logicalWarp;
    const int tid = warp * 32 + int(threadIdx.x) % 32;
    const bool zero = !(input.v[0] | input.v[1] | input.v[2] | input.v[3] | input.v[4]);
    P131 acc = zero ? P131{{1, 0, 0, 0, 0}} : input;
    P131 right[LEVELS];
    goal22GroupStore(low, top, tid, acc);
    goal22GroupBarrier<WARPS>();
#pragma unroll
    for (int level = 0; level < LEVELS; ++level) {
        const int width = 1 << (level + 1), offset = 32 << level;
        if ((warp & (width - 1)) == width - 1) {
            right[level] = acc;
            const P131 left = goal22GroupLoad(low, top, tid - offset);
            acc = mulPolynomial131(left, acc);
            goal22GroupStore(low, top, tid, acc);
        }
        goal22GroupBarrier<WARPS>();
    }
    if ((warp & (WARPS - 1)) == WARPS - 1) {
        acc = toPolynomial131(inv131(fromPolynomial131(acc)));
        goal22GroupStore(low, top, tid, acc);
    }
    goal22GroupBarrier<WARPS>();
#pragma unroll
    for (int level = LEVELS - 1; level >= 0; --level) {
        const int width = 1 << (level + 1), offset = 32 << level;
        if ((warp & (width - 1)) == width - 1) {
            const P131 parent = goal22GroupLoad(low, top, tid);
            const P131 left = goal22GroupLoad(low, top, tid - offset);
            const PolynomialPair inverse = mulPolynomialPair131(parent, right[level], left);
            goal22GroupStore(low, top, tid - offset, inverse.first);
            goal22GroupStore(low, top, tid, inverse.second);
        }
        goal22GroupBarrier<WARPS>();
    }
    const P131 out = goal22GroupLoad(low, top, tid);
    // All readers must finish before another call may reuse the scratch.
    goal22GroupBarrier<WARPS>();
    return zero ? P131{{0, 0, 0, 0, 0}} : out;
}
} // namespace eccPacked131
