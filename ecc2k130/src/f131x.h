// f131x.h - f131.h's arithmetic on several lanes at once, in SIMD registers.
//
// A step's five products and its squaring are the same instructions on every
// lane of a batch, and the engine already runs them in independent chains
// (cpuwalk.h): nothing in one lane's product depends on another's.  So the
// limbs of N lanes are held side by side in one vector register each -- N
// lanes' limb 0 in one register, their limb 1 in another, their 3-bit limb 2
// in a third -- and f131.h's routines run unchanged on those registers: a
// 64-bit shift of a limb is a per-element shift, an xor of two limbs is a
// vector xor, and the reduction, the squaring's spread and the conversion
// network are written once, over a vector type, for any N.
//
// What differs by width is the 64 x 64 -> 128 carry-less multiply.  x86-64's
// PCLMULQDQ multiplies one chosen 64-bit half of each 128-bit lane of its two
// operands, so the N products of a limb pair come out of two instructions --
// one for the even elements (imm 0x00), one for the odd (0x11) -- as
// [lo, hi] pairs that an unpacklo/unpackhi sort back into a `lo` and a `hi`
// register.  N is 2 on PCLMULQDQ alone (SSE), 4 with VPCLMULQDQ on AVX2, 8
// with VPCLMULQDQ on AVX-512.  The product keeps f131.h's Karatsuba on the two
// full limbs and takes the four cross products of the 3-bit limbs through the
// multiplier too (eight instructions for N lanes), where f131.h's scalar
// path shifts and masks: a vector shift-and-mask is five times the
// instructions of a multiply here, and the multiplier's port has them to
// spare.
//
// This header selects itself only on x86-64 with a hardware multiplier; the
// scalar path of f131.h stays what AArch64 (PMULL) and the software product
// run.  ECC_F131_LANES=1 forces the scalar engine on any host, and
// ECC_F131_LANES=2 or 4 narrows the vectors on a host that could take 8,
// which is how all three widths are held to f131.h (src/cputest.cpp) and
// measured on one core.
#pragma once

#include "f131.h"

#ifndef ECC_F131_LANES
#    if ECC_HOST_CLMUL && defined(__x86_64__) && defined(__AVX512F__) && defined(__AVX512BW__) && \
        defined(__VPCLMULQDQ__)
#        define ECC_F131_LANES 8
#    elif ECC_HOST_CLMUL && defined(__x86_64__) && defined(__AVX2__) && defined(__VPCLMULQDQ__)
#        define ECC_F131_LANES 4
#    elif ECC_HOST_CLMUL && defined(__x86_64__) && defined(__PCLMUL__) && defined(__SSE2__)
#        define ECC_F131_LANES 2
#    else
#        define ECC_F131_LANES 1
#    endif
#endif

#if ECC_F131_LANES != 1 && ECC_F131_LANES != 2 && ECC_F131_LANES != 4 && ECC_F131_LANES != 8
#    error "ECC_F131_LANES must be 1, 2, 4 or 8"
#endif
#if ECC_F131_LANES > 1 && !(ECC_HOST_CLMUL && defined(__x86_64__))
#    error "ECC_F131_LANES > 1 needs x86-64 with a hardware carry-less multiplier"
#endif

#if ECC_F131_LANES > 1

#    include <immintrin.h>

namespace f131x
{

using f131::F131;

// The vector of N 64-bit limbs, as the compiler's own vector type so that the
// shifts, ands and xors of f131.h read the same over it.
template <int N> struct Limbs;
template <> struct Limbs<2> {
    typedef uint64_t V __attribute__((vector_size(16)));
    typedef __m128i M;
};
template <> struct Limbs<4> {
    typedef uint64_t V __attribute__((vector_size(32)));
    typedef __m256i M;
};
template <> struct Limbs<8> {
    typedef uint64_t V __attribute__((vector_size(64)));
    typedef __m512i M;
};

#    define F131X_INLINE inline __attribute__((always_inline))

// The N-lane carry-less multiply: lo and hi halves of a[i] * b[i].
template <int N>
F131X_INLINE void clmul(typename Limbs<N>::V a, typename Limbs<N>::V b, typename Limbs<N>::V *lo,
                        typename Limbs<N>::V *hi);

template <>
F131X_INLINE void clmul<2>(Limbs<2>::V a, Limbs<2>::V b, Limbs<2>::V *lo, Limbs<2>::V *hi)
{
    const __m128i e = _mm_clmulepi64_si128((__m128i)a, (__m128i)b, 0x00),
                  o = _mm_clmulepi64_si128((__m128i)a, (__m128i)b, 0x11);
    *lo = (Limbs<2>::V)_mm_unpacklo_epi64(e, o);
    *hi = (Limbs<2>::V)_mm_unpackhi_epi64(e, o);
}
#    if ECC_F131_LANES >= 4
template <>
F131X_INLINE void clmul<4>(Limbs<4>::V a, Limbs<4>::V b, Limbs<4>::V *lo, Limbs<4>::V *hi)
{
    const __m256i e = _mm256_clmulepi64_epi128((__m256i)a, (__m256i)b, 0x00),
                  o = _mm256_clmulepi64_epi128((__m256i)a, (__m256i)b, 0x11);
    *lo = (Limbs<4>::V)_mm256_unpacklo_epi64(e, o);
    *hi = (Limbs<4>::V)_mm256_unpackhi_epi64(e, o);
}
#    endif
#    if ECC_F131_LANES >= 8
template <>
F131X_INLINE void clmul<8>(Limbs<8>::V a, Limbs<8>::V b, Limbs<8>::V *lo, Limbs<8>::V *hi)
{
    const __m512i e = _mm512_clmulepi64_epi128((__m512i)a, (__m512i)b, 0x00),
                  o = _mm512_clmulepi64_epi128((__m512i)a, (__m512i)b, 0x11);
    *lo = (Limbs<8>::V)_mm512_unpacklo_epi64(e, o);
    *hi = (Limbs<8>::V)_mm512_unpackhi_epi64(e, o);
}
#    endif

// N field elements, limb by limb.
template <int N> struct F131x {
    typedef typename Limbs<N>::V V;
    V w0, w1, w2;

    F131X_INLINE static V splat(uint64_t x)
    {
        V v;
        for (int i = 0; i < N; ++i) v[i] = x;
        return v;
    }
    // Lanes i..i+N-1 of a limb-sliced array (unaligned; the engine aligns its
    // arrays, and a batch that is not a multiple of N still loads correctly).
    F131X_INLINE static V loadLimb(const uint64_t *p)
    {
        V v;
        memcpy(&v, p, sizeof(v));
        return v;
    }
    F131X_INLINE static void storeLimb(uint64_t *p, V v) { memcpy(p, &v, sizeof(v)); }
    F131X_INLINE static F131x load(const uint64_t *w0, const uint64_t *w1, const uint64_t *w2)
    {
        return F131x{loadLimb(w0), loadLimb(w1), loadLimb(w2)};
    }
    F131X_INLINE void store(uint64_t *o0, uint64_t *o1, uint64_t *o2) const
    {
        storeLimb(o0, w0);
        storeLimb(o1, w1);
        storeLimb(o2, w2);
    }
    F131X_INLINE F131 lane(int i) const { return F131{{w0[i], w1[i], w2[i]}}; }
    F131X_INLINE void setLane(int i, const F131 &a)
    {
        w0[i] = a.w[0];
        w1[i] = a.w[1];
        w2[i] = a.w[2];
    }
};

template <int N> F131X_INLINE F131x<N> add(const F131x<N> &a, const F131x<N> &b)
{
    return F131x<N>{a.w0 ^ b.w0, a.w1 ^ b.w1, a.w2 ^ b.w2};
}

// f131::reduce, limb for limb, over N lanes.
template <int N> F131X_INLINE F131x<N> reduce(const typename Limbs<N>::V h[5])
{
    typedef typename Limbs<N>::V V;
    const V d0 = (h[2] >> 3) | (h[3] << 61), d1 = (h[3] >> 3) | (h[4] << 61),
            d2 = (h[4] >> 3) & F131x<N>::splat(3u);
    const V r0 = d0 ^ (d0 >> 1) ^ (d1 << 63) ^ (d0 >> 3) ^ (d1 << 61);
    const V r1 = d1 ^ (d1 >> 1) ^ (d2 << 63) ^ (d1 >> 3) ^ (d2 << 61);
    const V r2 = d2 ^ (d2 >> 1);
    const V q0 = d0 ^ (r0 >> 1) ^ (r1 << 63) ^ (r0 >> 9) ^ (r1 << 55) ^ (r0 >> 25) ^ (r1 << 39) ^
                 (r0 >> 57) ^ (r1 << 7) ^ (r1 >> 57) ^ (r2 << 7);
    const V q1 = d1 ^ (r1 >> 1) ^ (r2 << 63) ^ (r1 >> 9) ^ (r2 << 55) ^ (r1 >> 25) ^ (r2 << 39) ^
                 (r1 >> 57) ^ (r2 << 7);
    const V q2 = d2 ^ (r2 >> 1);
    const V t0 = q0 ^ (q0 << 2) ^ (q0 << 3);
    const V t1 = q1 ^ (q1 << 2) ^ (q0 >> 62) ^ (q1 << 3) ^ (q0 >> 61);
    const V t2 = q2 ^ (q2 << 2) ^ (q1 >> 62) ^ (q2 << 3) ^ (q1 >> 61);
    F131x<N> out;
    out.w0 = h[0] ^ t0;
    out.w1 = h[1] ^ t1 ^ t0 ^ (t0 << 32) ^ (t0 << 48) ^ (t0 << 56) ^ (q0 << 60);
    out.w2 = (h[2] ^ t2 ^ t1 ^ (t0 >> 32) ^ (t0 >> 16) ^ (t0 >> 8) ^ t0 ^ (q0 >> 4)) &
             F131x<N>::splat(7u);
    return out;
}

// The unreduced product, five limbs: Karatsuba on the two full limbs, the
// 3-bit limbs' cross terms through the multiplier as well (each is a 64 x 3
// product whose high half is below 4), and their 3 x 3 product by shifts.
template <int N>
F131X_INLINE void product(const F131x<N> &a, const F131x<N> &b, typename Limbs<N>::V h[5])
{
    typedef typename Limbs<N>::V V;
    V l0, l1, h0, h1, m0, m1;
    clmul<N>(a.w0, b.w0, &l0, &l1);
    clmul<N>(a.w1, b.w1, &h0, &h1);
    clmul<N>(a.w0 ^ a.w1, b.w0 ^ b.w1, &m0, &m1);
    m0 ^= l0 ^ h0;
    m1 ^= l1 ^ h1;
    V x0, x1, y0, y1, u0, u1, v0, v1;
    clmul<N>(a.w2, b.w0, &x0, &x1);
    clmul<N>(b.w2, a.w0, &y0, &y1);
    clmul<N>(a.w2, b.w1, &u0, &u1);
    clmul<N>(b.w2, a.w1, &v0, &v1);
    const V a2 = a.w2, b2 = b.w2;
    const V top = (b2 & (V{} - (a2 & F131x<N>::splat(1u)))) ^
                  ((b2 << 1) & (V{} - ((a2 >> 1) & F131x<N>::splat(1u)))) ^
                  ((b2 << 2) & (V{} - ((a2 >> 2) & F131x<N>::splat(1u))));
    h[0] = l0;
    h[1] = l1 ^ m0;
    h[2] = h0 ^ m1 ^ x0 ^ y0;
    h[3] = h1 ^ x1 ^ y1 ^ u0 ^ v0;
    h[4] = u1 ^ v1 ^ top;
}

template <int N> F131X_INLINE F131x<N> mul(const F131x<N> &a, const F131x<N> &b)
{
    typename Limbs<N>::V h[5];
    product<N>(a, b, h);
    return reduce<N>(h);
}

// The square: the multiplier spreads each full limb, the 3-bit limb by shifts.
template <int N> F131X_INLINE F131x<N> sqr(const F131x<N> &a)
{
    typedef typename Limbs<N>::V V;
    V h[5];
    clmul<N>(a.w0, a.w0, &h[0], &h[1]);
    clmul<N>(a.w1, a.w1, &h[2], &h[3]);
    h[4] = (a.w2 & F131x<N>::splat(1u)) | ((a.w2 & F131x<N>::splat(2u)) << 1) |
           ((a.w2 & F131x<N>::splat(4u)) << 2);
    return reduce<N>(h);
}

// f131::fromPolynomial over N lanes.
template <int N> F131X_INLINE F131x<N> fromPolynomial(const F131x<N> &a)
{
    typedef typename Limbs<N>::V V;
#    define F131X_C(x) F131x<N>::splat(x)
    V w0 = a.w0, w1 = a.w1;
    const V w2 = a.w2;
    w0 ^= w1 & F131X_C(0xffffffff00000000ull);
    w0 ^= ((w0 >> 32) | (w1 << 32)) & F131X_C(0xffff0000ffff0000ull);
    w1 ^= ((w1 >> 32) | (w2 << 32)) & F131X_C(0x00000000ffff0000ull);
    w0 ^= ((w0 >> 16) | (w1 << 48)) & F131X_C(0xff00ff00ff00ff00ull);
    w1 ^= ((w1 >> 16) | (w2 << 48)) & F131X_C(0x0000ff00ff00ff00ull);
    w0 ^= ((w0 >> 8) | (w1 << 56)) & F131X_C(0xf0f0f0f0f0f0f0f0ull);
    w1 ^= ((w1 >> 8) | (w2 << 56)) & F131X_C(0x00f0f0f0f0f0f0f0ull);
    w0 ^= ((w0 >> 4) | (w1 << 60)) & F131X_C(0xccccccccccccccccull);
    w1 ^= ((w1 >> 4) | (w2 << 60)) & F131X_C(0x4cccccccccccccccull);
    w0 ^= ((w0 >> 2) | (w1 << 62)) & F131X_C(0xaaaaaaaaaaaaaaaaull);
    w1 ^= ((w1 >> 2) | (w2 << 62)) & F131X_C(0xaaaaaaaaaaaaaaaaull);
    const V sign = V{} - (w0 & F131X_C(1u));
    return F131x<N>{((w0 >> 1) | (w1 << 63)) ^ sign, ((w1 >> 1) | (w2 << 63)) ^ sign,
                    ((w2 >> 1) ^ sign) & F131X_C(7u)};
#    undef F131X_C
}

#    undef F131X_INLINE

} // namespace f131x

#endif // ECC_F131_LANES > 1
