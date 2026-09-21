// Rotated product trees with private right-branch inverses and fewer barriers.
#pragma once
namespace eccPacked131 {
template<int WARPS>
__device__ __forceinline__ void goal22GroupBarrier() {
    const int id = 1 + int(threadIdx.x) / (32 * WARPS);
    asm volatile("barrier.sync %0, %1;" :: "r"(id), "n"(32 * WARPS) : "memory");
}
template<int WARPS>
__device__ __noinline__ P131 goal22CollectiveInverse(P131 input) {
    static_assert(WARPS == 2 || WARPS == 4 || WARPS == 8 || WARPS == 16);
    static_assert(ECC_THREADS % (32 * WARPS) == 0);
    constexpr int LEVELS = WARPS == 2 ? 1 : WARPS == 4 ? 2 : WARPS == 8 ? 3 : 4;
    __shared__ uint32_t values[5 * ECC_THREADS];
    const int physicalWarp = int(threadIdx.x) / 32;
    const int group = physicalWarp / WARPS;
    const int rotation = group / (WARPS < 4 ? 4 / WARPS : 1);
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
            // Only a following tree level needs this stored product.
            if (level + 1 < LEVELS) {
#pragma unroll
                for (int i = 0; i < 5; ++i) values[i * ECC_THREADS + tid] = acc.v[i];
            }
        }
        if (level + 1 < LEVELS) goal22GroupBarrier<WARPS>();
    }
    bool privateInverse = (warp & (WARPS - 1)) == WARPS - 1;
    if (privateInverse) acc = toPolynomial131(inv131(fromPolynomial131(acc)));
    // The root immediately splits its inverse. Other warps wait at the
    // first downward barrier; no one consumes a shared root inverse.
#pragma unroll
    for (int level = LEVELS - 1; level >= 0; --level) {
        const int width = 1 << (level + 1), offset = 32 << level;
        if ((warp & (width - 1)) == width - 1) {
            P131 parent = acc, left;
#pragma unroll
            for (int i = 0; i < 5; ++i) {
                if (!privateInverse) parent.v[i] = values[i * ECC_THREADS + tid];
                left.v[i] = values[i * ECC_THREADS + tid - offset];
            }
            const PolynomialPair inverse = mulPolynomialPair131(parent, right[level], left);
#pragma unroll
            for (int i = 0; i < 5; ++i) values[i * ECC_THREADS + tid - offset] = inverse.first.v[i];
            acc = inverse.second;
            privateInverse = true;
        }
        goal22GroupBarrier<WARPS>();
    }
    P131 out = acc;
    if (!privateInverse) {
#pragma unroll
        for (int i = 0; i < 5; ++i) out.v[i] = values[i * ECC_THREADS + tid];
    }
    // A later call first writes only the caller's own slot, after its read.
    // Its initial barrier precedes any cross-warp write. Thus another final
    // barrier is unnecessary even when calls follow each other immediately.
    return zero ? P131{{0, 0, 0, 0, 0}} : out;
}
} // namespace eccPacked131
