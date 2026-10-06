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
// shifts, ands and xors of f131.h read the same over it; its signed twin for
// an arithmetic shift, and the intrinsics' type.
template <int N> struct Limbs;
template <> struct Limbs<2> {
    typedef uint64_t V __attribute__((vector_size(16)));
    typedef int64_t S __attribute__((vector_size(16)));
    typedef __m128i M;
};
template <> struct Limbs<4> {
    typedef uint64_t V __attribute__((vector_size(32)));
    typedef int64_t S __attribute__((vector_size(32)));
    typedef __m256i M;
};
template <> struct Limbs<8> {
    typedef uint64_t V __attribute__((vector_size(64)));
    typedef int64_t S __attribute__((vector_size(64)));
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

    // A scalar operand of a vector operator is broadcast, and compiles to the
    // one broadcast instruction; an element-by-element loop compiled to N
    // masked inserts.
    F131X_INLINE static V splat(uint64_t x)
    {
        const V zero = {};
        return zero | x;
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

/* ---- the selection, bitwise over N lanes ---------------------------------- */

// f131.h's selection is table lookups: 17 bytes for the phase sum, 17 for
// the pivot's maximum, a row of the coordinate table for the sign.  A vector
// register has no cheap lookup, but every one of those tables is a function
// of the labels L alone, and include/tablewalk.h's model computes the same
// selection from the bit planes of L (plane j has coordinate e set when bit
// j of L(e) is): the phase sum is sum_j 2^j |x & plane_j|, the mask L < k is
// a bitwise comparison of each coordinate's label with k, the pivot is a
// binary search down the planes for the set coordinate of largest L, and the
// sign is that coordinate of fromPolynomial(y), by linearity the parity the
// row would give.  That is popcounts, ands and compares, the same on every
// lane, so the selection runs here N lanes at a time with no lookup but one
// gather of HW^-1.

// The sum of the eight bytes of each element.
template <int N> F131X_INLINE typename Limbs<N>::V byteSum(typename Limbs<N>::V v);
template <> F131X_INLINE Limbs<2>::V byteSum<2>(Limbs<2>::V v)
{
    return (Limbs<2>::V)_mm_sad_epu8((__m128i)v, _mm_setzero_si128());
}
#    if ECC_F131_LANES >= 4
template <> F131X_INLINE Limbs<4>::V byteSum<4>(Limbs<4>::V v)
{
    return (Limbs<4>::V)_mm256_sad_epu8((__m256i)v, _mm256_setzero_si256());
}
#    endif
#    if ECC_F131_LANES >= 8
template <> F131X_INLINE Limbs<8>::V byteSum<8>(Limbs<8>::V v)
{
    return (Limbs<8>::V)_mm512_sad_epu8((__m512i)v, _mm512_setzero_si512());
}
#    endif

// Population count of each 64-bit element: the instruction where there is
// one (AVX-512 VPOPCNTDQ), else the bit-sliced count.
template <int N> F131X_INLINE typename Limbs<N>::V popcnt(typename Limbs<N>::V v)
{
    v = v - ((v >> 1) & F131x<N>::splat(0x5555555555555555ull));
    v = (v & F131x<N>::splat(0x3333333333333333ull)) +
        ((v >> 2) & F131x<N>::splat(0x3333333333333333ull));
    v = (v + (v >> 4)) & F131x<N>::splat(0x0f0f0f0f0f0f0f0full);
    return byteSum<N>(v);
}
#    if defined(__AVX512VPOPCNTDQ__)
#        if ECC_F131_LANES >= 8
template <> F131X_INLINE Limbs<8>::V popcnt<8>(Limbs<8>::V v)
{
    return (Limbs<8>::V)_mm512_popcnt_epi64((__m512i)v);
}
#        endif
#        if defined(__AVX512VL__)
#            if ECC_F131_LANES >= 4
template <> F131X_INLINE Limbs<4>::V popcnt<4>(Limbs<4>::V v)
{
    return (Limbs<4>::V)_mm256_popcnt_epi64((__m256i)v);
}
#            endif
template <> F131X_INLINE Limbs<2>::V popcnt<2>(Limbs<2>::V v)
{
    return (Limbs<2>::V)_mm_popcnt_epi64((__m128i)v);
}
#        endif
#    endif

// The low 32 bits of each element of a times those of b, as a 64-bit product.
template <int N> F131X_INLINE typename Limbs<N>::V mul32(typename Limbs<N>::V a, typename Limbs<N>::V b);
template <> F131X_INLINE Limbs<2>::V mul32<2>(Limbs<2>::V a, Limbs<2>::V b)
{
    return (Limbs<2>::V)_mm_mul_epu32((__m128i)a, (__m128i)b);
}
#    if ECC_F131_LANES >= 4
template <> F131X_INLINE Limbs<4>::V mul32<4>(Limbs<4>::V a, Limbs<4>::V b)
{
    return (Limbs<4>::V)_mm256_mul_epu32((__m256i)a, (__m256i)b);
}
#    endif
#    if ECC_F131_LANES >= 8
template <> F131X_INLINE Limbs<8>::V mul32<8>(Limbs<8>::V a, Limbs<8>::V b)
{
    return (Limbs<8>::V)_mm512_mul_epu32((__m512i)a, (__m512i)b);
}
#    endif

// t[idx[i]] for each element, t a table of 32-bit words.
template <int N> F131X_INLINE typename Limbs<N>::V gather32(const uint32_t *t, typename Limbs<N>::V idx);
template <> F131X_INLINE Limbs<2>::V gather32<2>(const uint32_t *t, Limbs<2>::V idx)
{
    const Limbs<2>::V r = {t[idx[0]], t[idx[1]]};
    return r;
}
#    if ECC_F131_LANES >= 4
template <> F131X_INLINE Limbs<4>::V gather32<4>(const uint32_t *t, Limbs<4>::V idx)
{
    return (Limbs<4>::V)_mm256_cvtepu32_epi64(
        _mm256_i64gather_epi32(reinterpret_cast<const int *>(t), (__m256i)idx, 4));
}
#    endif
#    if ECC_F131_LANES >= 8
template <> F131X_INLINE Limbs<8>::V gather32<8>(const uint32_t *t, Limbs<8>::V idx)
{
    return (Limbs<8>::V)_mm512_cvtepu32_epi64(_mm512_i64gather_epi32((__m512i)idx, t, 4));
}
#    endif

// p mod 131 for p below 2^16: the quotient by a reciprocal multiply (64036 =
// ceil(2^23 / 131); the error 108 p stays below 2^23 for p < 77672).
template <int N> F131X_INLINE typename Limbs<N>::V mod131(typename Limbs<N>::V p)
{
    typedef typename Limbs<N>::V V;
    const V q = mul32<N>(p, F131x<N>::splat(64036u)) >> 23;
    return p - ((q << 7) + (q << 1) + q);
}

// The low byte of each element, to out[0..N).
template <int N> F131X_INLINE void storeBytes(typename Limbs<N>::V v, unsigned char *out)
{
    for (int i = 0; i < N; ++i) out[i] = (unsigned char)v[i];
}

// The selection's constants in the form the vector stages read: the eight bit
// planes of L, limb by limb, from the shared constant buffer's L^-1 table, and
// its HW^-1 table in place.
struct SelectConsts {
    uint64_t plane[8][3];
    const uint32_t *inv;

    void build(const uint32_t *tw)
    {
        using namespace eccPacked131;
        const uint8_t *linv = reinterpret_cast<const uint8_t *>(tw) + 4 * TW_LINV_OFF;
        memset(plane, 0, sizeof(plane));
        for (int l = 0; l < 131; ++l) {
            const int e = linv[l];
            for (int j = 0; j < 8; ++j)
                if ((l >> j) & 1) plane[j][e >> 6] |= 1ull << (e & 63);
        }
        inv = tw + TW_INV_OFF;
    }
};

// HW(x), the phase k and the sign eps of N lanes -- f131::weight, selectPhase
// and coordinate(y, selectPivot(x, k)) -- from x in the normal basis and y in
// the polynomial basis.
template <int N>
F131X_INLINE void select(const F131x<N> &xn, const F131x<N> &yp, const SelectConsts &c,
                         typename Limbs<N>::V *hwOut, typename Limbs<N>::V *kOut,
                         typename Limbs<N>::V *epsOut)
{
    typedef typename Limbs<N>::V V;
#    define F131X_C(x) F131x<N>::splat(x)
    const V hw = popcnt<N>(xn.w0) + popcnt<N>(xn.w1) + popcnt<N>(xn.w2);
    // The phase sum, sum_e L(e) x_e = sum_j 2^j |x & plane_j|, below 131^2.
    V s = V{};
    for (int j = 0; j < 8; ++j)
        s += (popcnt<N>(xn.w0 & F131X_C(c.plane[j][0])) + popcnt<N>(xn.w1 & F131X_C(c.plane[j][1])) +
              popcnt<N>(xn.w2 & F131X_C(c.plane[j][2])))
             << j;
    const V k = mod131<N>(mul32<N>(mod131<N>(s), gather32<N>(c.inv, hw)));
    // The pivot's mask, the coordinates with L(e) < k: a bitwise comparison
    // of every coordinate's label with k, least significant bit first.  At
    // each bit, L < k so far if bit j of k is set and of L clear, or the two
    // agree and L < k already: the majority of (k_j, not L_j, so far), one
    // three-input logic instruction per limb.
    typedef typename Limbs<N>::S S;
    V lt0 = V{}, lt1 = V{}, lt2 = V{};
    for (int j = 0; j < 8; ++j) {
        const V kj = (V)((S)(k << (63 - j)) >> 63);
        const V n0 = F131X_C(~c.plane[j][0]), n1 = F131X_C(~c.plane[j][1]),
                n2 = F131X_C(~c.plane[j][2]);
        lt0 = (kj & n0) | (kj & lt0) | (n0 & lt0);
        lt1 = (kj & n1) | (kj & lt1) | (n1 & lt1);
        lt2 = (kj & n2) | (kj & lt2) | (n2 & lt2);
    }
    V p0 = xn.w0 & lt0, p1 = xn.w1 & lt1, p2 = xn.w2 & lt2;
    const V any = (V)((p0 | p1 | p2) != V{});
    p0 = (p0 & any) | (xn.w0 & ~any);
    p1 = (p1 & any) | (xn.w1 & ~any);
    p2 = (p2 & any) | (xn.w2 & ~any);
    // The set coordinate of largest L: down the planes, keep the candidates
    // with bit j of L set whenever there are any.  L is a bijection, so one
    // coordinate is left.
    for (int j = 7; j >= 0; --j) {
        const V t0 = p0 & F131X_C(c.plane[j][0]), t1 = p1 & F131X_C(c.plane[j][1]),
                t2 = p2 & F131X_C(c.plane[j][2]);
        const V nz = (V)((t0 | t1 | t2) != V{});
        p0 = (t0 & nz) | (p0 & ~nz);
        p1 = (t1 & nz) | (p1 & ~nz);
        p2 = (t2 & nz) | (p2 & ~nz);
    }
    // eps: that coordinate of y in the normal basis.
    const F131x<N> yn = fromPolynomial<N>(yp);
    *epsOut = (V)(((yn.w0 & p0) | (yn.w1 & p1) | (yn.w2 & p2)) != V{}) & F131X_C(1u);
    *hwOut = hw;
    *kOut = k;
#    undef F131X_C
}

#    undef F131X_INLINE

} // namespace f131x

#endif // ECC_F131_LANES > 1
