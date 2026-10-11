// Batch polynomial inverses across whole warps using a product tree.
// Each warp lane remains an independent tree; no walk points are combined.
#pragma once
namespace eccPacked131 {
template<int WARPS>
__device__ __noinline__ P131 goal22CollectiveInverse(P131 input) {
    static_assert(WARPS == 2 || WARPS == 4 || WARPS == 8 || WARPS == 16);
    static_assert(ECC_THREADS % (32 * WARPS) == 0);
    constexpr int LEVELS = WARPS == 2 ? 1 : WARPS == 4 ? 2 : WARPS == 8 ? 3 : 4;
    __shared__ uint32_t values[5 * ECC_THREADS];
    const int tid = threadIdx.x, warp = tid / 32;
    const bool zero = !(input.v[0] | input.v[1] | input.v[2] | input.v[3] | input.v[4]);
    P131 acc = zero ? P131{{1, 0, 0, 0, 0}} : input;
    P131 right[LEVELS];
#pragma unroll
    for (int i = 0; i < 5; ++i) values[i * ECC_THREADS + tid] = acc.v[i];
    __syncthreads();
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
        __syncthreads();
    }
    if ((warp & (WARPS - 1)) == WARPS - 1) {
        acc = toPolynomial131(inv131(fromPolynomial131(acc)));
#pragma unroll
        for (int i = 0; i < 5; ++i) values[i * ECC_THREADS + tid] = acc.v[i];
    }
    __syncthreads();
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
        __syncthreads();
    }
    P131 out;
#pragma unroll
    for (int i = 0; i < 5; ++i) out.v[i] = values[i * ECC_THREADS + tid];
    // All readers must finish before another call may reuse the scratch.
    __syncthreads();
    return zero ? P131{{0, 0, 0, 0, 0}} : out;
}
} // namespace eccPacked131
