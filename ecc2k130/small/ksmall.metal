// ksmall.metal - Pollard rho on a small Koblitz curve y^2 + xy = x^3 + a x^2 + 1
// over F_2^M, walking the ECC2K-130 iteration R -> R + sigma^j(R).
//
// run.py prepends a prelude that defines the degree and field (M, NW, kTerms),
// the batch size, the distinguished-point cutoff, the normal-basis rows
// (kNormal), the start-point bases (kBaseX/Y, kQX/Y) and the arithmetic
// switches below.  The kernel is generic in M <= 127.
//
// j = J_BASE + (HW/2 mod 8), where HW is the Hamming weight of x in a normal
// basis.  HW is invariant under Frobenius and negation, so the walk is a walk
// on classes {+-sigma^i R} and gains the sqrt(2M) of ECC2K-130.  A point is
// distinguished when HW <= DPW.  Each lane counts how many times it took each
// j; the point is then prod (1+lambda^j)^count_j (u P + Q), so the host needs
// no scalar arithmetic in the walk.
//
// Arithmetic switches (each 0 or 1; run.py bench compares them):
//   KS_KARA    Karatsuba products (6 32x32 carry-less products at NW=3, 9 at
//              NW=4) instead of schoolbook (9, 16).  Apple GPUs have no
//              carry-less multiply; each 32x32 product is 16 masked integer
//              multiplies.
//   KS_TABLES  normal-basis conversion by 4-bit tables in threadgroup memory
//              instead of M row parities.  With it, sigma^j and the long
//              squaring runs of the inversion are a rotation of the
//              normal-basis vector between two table conversions instead of
//              repeated squaring.
//   KS_SQR32   squaring spreads bits in 32-bit halves instead of emulated
//              64-bit shifts.
//   KS_FROBTAB sigma^j(x, y) by normal-basis rotation and table conversions
//              instead of 2j squarings.  Squarings are cheaper at a fixed j,
//              but j differs across a SIMD group, which then runs the
//              largest j's squarings; the tables cost the same for every j.
//   KS_CLMUL   the 32x32 carry-less product: 0 as ulong products of masked
//              operands, 1 as explicit 32-bit mul/mulhi pairs, 2 as three
//              16x16 products (Karatsuba) of 3-bit-spaced masks, 27 32-bit
//              multiplies instead of 32.

#ifndef KS_KARA
#define KS_KARA 1
#endif
#ifndef KS_TABLES
#define KS_TABLES 1
#endif
#ifndef KS_SQR32
#define KS_SQR32 1
#endif
// Multi-squarings of at least this many steps go through the normal basis.
#ifndef KS_ROT_MIN
#define KS_ROT_MIN 8
#endif
#ifndef KS_FROBTAB
#define KS_FROBTAB 1
#endif
#ifndef KS_CLMUL
#define KS_CLMUL 2
#endif

#define NCHUNK ((M + 3) / 4)
#define TBL (NCHUNK * 16 * NW) // uints per conversion table

struct F { uint w[NW]; };

struct Args {
    uint lanes;
    uint steps;
    uint dpCap;
    uint seedStride;
    uint maxTrail;
    uint pad[3];
};

struct DpRec {
    ulong seed;
    uint steps;
    uint lane;
    uint counts[J_COUNT];
    uint x[4];
    uint y[4];
    uint nb[4];
};

// --- products ---------------------------------------------------------------

#if KS_CLMUL == 1
static inline ulong clmul32(uint x, uint y)
{
    uint x0 = x & 0x11111111u, x1 = x & 0x22222222u, x2 = x & 0x44444444u, x3 = x & 0x88888888u;
    uint y0 = y & 0x11111111u, y1 = y & 0x22222222u, y2 = y & 0x44444444u, y3 = y & 0x88888888u;
    uint l0 = (x0 * y0) ^ (x1 * y3) ^ (x2 * y2) ^ (x3 * y1);
    uint l1 = (x0 * y1) ^ (x1 * y0) ^ (x2 * y3) ^ (x3 * y2);
    uint l2 = (x0 * y2) ^ (x1 * y1) ^ (x2 * y0) ^ (x3 * y3);
    uint l3 = (x0 * y3) ^ (x1 * y2) ^ (x2 * y1) ^ (x3 * y0);
    uint h0 = mulhi(x0, y0) ^ mulhi(x1, y3) ^ mulhi(x2, y2) ^ mulhi(x3, y1);
    uint h1 = mulhi(x0, y1) ^ mulhi(x1, y0) ^ mulhi(x2, y3) ^ mulhi(x3, y2);
    uint h2 = mulhi(x0, y2) ^ mulhi(x1, y1) ^ mulhi(x2, y0) ^ mulhi(x3, y3);
    uint h3 = mulhi(x0, y3) ^ mulhi(x1, y2) ^ mulhi(x2, y1) ^ mulhi(x3, y0);
    uint lo = (l0 & 0x11111111u) | (l1 & 0x22222222u) | (l2 & 0x44444444u) | (l3 & 0x88888888u);
    uint hi = (h0 & 0x11111111u) | (h1 & 0x22222222u) | (h2 & 0x44444444u) | (h3 & 0x88888888u);
    return ulong(lo) | (ulong(hi) << 32);
}
#elif KS_CLMUL == 2
// 16x16 -> 31 bits.  Operand bits in one residue class mod 3 number at most
// six, so a digit's sum is <= 6 and never carries into the next 3-bit digit.
static inline uint clmul16(uint x, uint y)
{
    uint x0 = x & 0x9249u, x1 = x & 0x2492u, x2 = x & 0x4924u;
    uint y0 = y & 0x9249u, y1 = y & 0x2492u, y2 = y & 0x4924u;
    uint z0 = (x0 * y0) ^ (x1 * y2) ^ (x2 * y1);
    uint z1 = (x0 * y1) ^ (x1 * y0) ^ (x2 * y2);
    uint z2 = (x0 * y2) ^ (x1 * y1) ^ (x2 * y0);
    return (z0 & 0x49249249u) | (z1 & 0x92492492u) | (z2 & 0x24924924u);
}
static inline ulong clmul32(uint x, uint y)
{
    uint a0 = x & 0xFFFFu, a1 = x >> 16, b0 = y & 0xFFFFu, b1 = y >> 16;
    uint p0 = clmul16(a0, b0), p2 = clmul16(a1, b1);
    uint p1 = clmul16(a0 ^ a1, b0 ^ b1) ^ p0 ^ p2;
    uint lo = p0 ^ (p1 << 16), hi = p2 ^ (p1 >> 16);
    return ulong(lo) | (ulong(hi) << 32);
}
#else
static inline ulong clmul32(uint x, uint y)
{
    ulong x0 = x & 0x11111111u, x1 = x & 0x22222222u, x2 = x & 0x44444444u, x3 = x & 0x88888888u;
    ulong y0 = y & 0x11111111u, y1 = y & 0x22222222u, y2 = y & 0x44444444u, y3 = y & 0x88888888u;
    ulong z0 = (x0 * y0) ^ (x1 * y3) ^ (x2 * y2) ^ (x3 * y1);
    ulong z1 = (x0 * y1) ^ (x1 * y0) ^ (x2 * y3) ^ (x3 * y2);
    ulong z2 = (x0 * y2) ^ (x1 * y1) ^ (x2 * y0) ^ (x3 * y3);
    ulong z3 = (x0 * y3) ^ (x1 * y2) ^ (x2 * y1) ^ (x3 * y0);
    return (z0 & 0x1111111111111111ul) | (z1 & 0x2222222222222222ul) |
           (z2 & 0x4444444444444444ul) | (z3 & 0x8888888888888888ul);
}
#endif

static inline void acc64(thread uint *c, int w, ulong p)
{
    c[w] ^= uint(p);
    c[w + 1] ^= uint(p >> 32);
}

// 64x64 -> 128 as three 32x32 products.
static inline void kara2(uint a0, uint a1, uint b0, uint b1, thread ulong &lo, thread ulong &mid, thread ulong &hi)
{
    ulong p0 = clmul32(a0, b0), p2 = clmul32(a1, b1);
    ulong p1 = clmul32(a0 ^ a1, b0 ^ b1) ^ p0 ^ p2;
    lo = p0 ^ (p1 << 32);
    hi = p2 ^ (p1 >> 32);
    mid = 0;
}

static inline void product(thread uint *c, const thread F &a, const thread F &b)
{
    for (int i = 0; i < 2 * NW + 1; ++i) c[i] = 0;
#if KS_KARA && NW == 1
    acc64(c, 0, clmul32(a.w[0], b.w[0]));
#elif KS_KARA && NW == 2
    ulong lo, mid, hi;
    kara2(a.w[0], a.w[1], b.w[0], b.w[1], lo, mid, hi);
    acc64(c, 0, lo);
    acc64(c, 2, hi);
#elif KS_KARA && NW == 3
    ulong p00 = clmul32(a.w[0], b.w[0]), p11 = clmul32(a.w[1], b.w[1]), p22 = clmul32(a.w[2], b.w[2]);
    ulong p01 = clmul32(a.w[0] ^ a.w[1], b.w[0] ^ b.w[1]) ^ p00 ^ p11;
    ulong p02 = clmul32(a.w[0] ^ a.w[2], b.w[0] ^ b.w[2]) ^ p00 ^ p22;
    ulong p12 = clmul32(a.w[1] ^ a.w[2], b.w[1] ^ b.w[2]) ^ p11 ^ p22;
    acc64(c, 0, p00);
    acc64(c, 1, p01);
    acc64(c, 2, p02 ^ p11);
    acc64(c, 3, p12);
    acc64(c, 4, p22);
#elif KS_KARA && NW == 4
    ulong l0, lm, l1, h0, hm, h1, m0, mm, m1;
    kara2(a.w[0], a.w[1], b.w[0], b.w[1], l0, lm, l1);
    kara2(a.w[2], a.w[3], b.w[2], b.w[3], h0, hm, h1);
    kara2(a.w[0] ^ a.w[2], a.w[1] ^ a.w[3], b.w[0] ^ b.w[2], b.w[1] ^ b.w[3], m0, mm, m1);
    m0 ^= l0 ^ h0;
    m1 ^= l1 ^ h1;
    acc64(c, 0, l0);
    acc64(c, 2, l1 ^ m0);
    acc64(c, 4, h0 ^ m1);
    acc64(c, 6, h1);
#else
    for (int i = 0; i < NW; ++i)
        for (int j = 0; j < NW; ++j) acc64(c, i + j, clmul32(a.w[i], b.w[j]));
#endif
}

// --- reduction ----------------------------------------------------------------

static inline void xorAt(thread uint *c, uint t, int pos)
{
    int w = pos >> 5, s = pos & 31;
    c[w] ^= t << s;
    if (s) c[w + 1] ^= t >> (32 - s);
}

// c has 2*NW+1 words; bits >= M are folded with x^M = sum x^kTerms[k].
// Every middle term is <= M - 33, so a fold never lands in the word being folded.
static inline F reduce(thread uint *c)
{
    for (int i = 2 * NW - 1; i >= 0; --i) {
        int lo = 32 * i;
        if (lo + 32 <= M) break;
        uint t;
        int pos;
        if (lo >= M) {
            t = c[i];
            c[i] = 0;
            pos = lo;
        } else {
            int s = M - lo;
            t = c[i] >> s;
            c[i] &= (1u << s) - 1u;
            pos = M;
        }
        for (int k = 0; k < NTERMS; ++k) xorAt(c, t, pos - M + kTerms[k]);
    }
    F r;
    for (int i = 0; i < NW; ++i) r.w[i] = c[i];
    return r;
}

static inline F fmul(F a, F b)
{
    uint c[2 * NW + 1];
    product(c, a, b);
    return reduce(c);
}

static inline uint spread16(uint x)
{
    x = (x | (x << 8)) & 0x00FF00FFu;
    x = (x | (x << 4)) & 0x0F0F0F0Fu;
    x = (x | (x << 2)) & 0x33333333u;
    x = (x | (x << 1)) & 0x55555555u;
    return x;
}

static inline ulong spread32(uint x)
{
    ulong v = x;
    v = (v | (v << 16)) & 0x0000FFFF0000FFFFul;
    v = (v | (v << 8)) & 0x00FF00FF00FF00FFul;
    v = (v | (v << 4)) & 0x0F0F0F0F0F0F0F0Ful;
    v = (v | (v << 2)) & 0x3333333333333333ul;
    v = (v | (v << 1)) & 0x5555555555555555ul;
    return v;
}

static inline F fsqr(F a)
{
    uint c[2 * NW + 1];
    for (int i = 0; i < NW; ++i) {
#if KS_SQR32
        c[2 * i] = spread16(a.w[i] & 0xFFFFu);
        c[2 * i + 1] = spread16(a.w[i] >> 16);
#else
        ulong s = spread32(a.w[i]);
        c[2 * i] = uint(s);
        c[2 * i + 1] = uint(s >> 32);
#endif
    }
    c[2 * NW] = 0;
    return reduce(c);
}

static inline F fsqrn(F a, int n)
{
    for (int i = 0; i < n; ++i) a = fsqr(a);
    return a;
}

static inline F fadd(F a, F b)
{
    for (int i = 0; i < NW; ++i) a.w[i] ^= b.w[i];
    return a;
}

static inline bool fzero(F a)
{
    uint o = 0;
    for (int i = 0; i < NW; ++i) o |= a.w[i];
    return o == 0;
}

static inline F fone()
{
    F r;
    for (int i = 0; i < NW; ++i) r.w[i] = 0;
    r.w[0] = 1;
    return r;
}

static inline int fweight(F a)
{
    int hw = 0;
    for (int i = 0; i < NW; ++i) hw += int(popcount(a.w[i]));
    return hw;
}

// --- normal basis ---------------------------------------------------------------

// Coordinates by row parities: bit i is parity(kNormal[i] & x).
static inline F nbRows(F x)
{
    F r;
    for (int i = 0; i < NW; ++i) r.w[i] = 0;
    for (int row = 0; row < M; ++row) {
        uint acc = 0;
        for (int i = 0; i < NW; ++i) acc ^= kNormal[row][i] & x.w[i];
        r.w[row >> 5] |= (popcount(acc) & 1u) << (row & 31);
    }
    return r;
}

static inline int nbWeightRows(F x)
{
    int hw = 0;
    for (int row = 0; row < M; ++row) {
        uint acc = 0;
        for (int i = 0; i < NW; ++i) acc ^= kNormal[row][i] & x.w[i];
        hw += int(popcount(acc) & 1u);
    }
    return hw;
}

// A linear map by 4-bit tables: T[(chunk * 16 + nibble) * NW + word] is the
// image of nibble << (4 chunk).  run.py builds one table for polynomial ->
// normal and one for normal -> polynomial.
template <typename T>
static inline F tmap(T t, F x)
{
    F r;
    for (int i = 0; i < NW; ++i) r.w[i] = 0;
    for (int c = 0; c < NCHUNK; ++c) {
        uint nib = (x.w[c >> 3] >> ((c & 7) * 4)) & 15u;
        T e = t + (uint(c) * 16u + nib) * uint(NW);
        for (int i = 0; i < NW; ++i) r.w[i] ^= e[i];
    }
    return r;
}

// Rotate an M-bit normal-basis vector left by k (0 <= k < M): x -> x^(2^k).
static inline F nbRot(F v, int k)
{
    uint e[2 * NW + 1];
    for (int i = 0; i < 2 * NW + 1; ++i) e[i] = 0;
    for (int i = 0; i < NW; ++i) e[i] = v.w[i];
    const int mw = M >> 5, bs = M & 31;
    for (int i = 0; i < NW; ++i) {
        e[i + mw] |= v.w[i] << bs;
        if (bs) e[i + mw + 1] |= v.w[i] >> (32 - bs);
    }
    // out bit i = v bit (i - k mod M) = e bit (i - k + M)
    const int base = M - k;
    const int w0 = base >> 5, sh = base & 31;
    F r;
    for (int i = 0; i < NW; ++i) {
        uint lo = e[w0 + i], hi = e[w0 + i + 1];
        r.w[i] = sh ? ((lo >> sh) | (hi << (32 - sh))) : lo;
    }
    if (M & 31) r.w[NW - 1] &= (1u << (M & 31)) - 1u;
    return r;
}

// x^(2^n)
template <typename T>
static inline F fsqrnT(F a, int n, T to, T from)
{
#if KS_TABLES
    if (n >= KS_ROT_MIN) return tmap(from, nbRot(tmap(to, a), n));
#endif
    return fsqrn(a, n);
}

// Itoh-Tsujii: b_k = a^(2^k - 1); a^-1 = b_(M-1)^2.
template <typename T>
static inline F finvT(F a, T to, T from)
{
    const int n = M - 1;
    int top = 31 - clz(uint(n));
    F b = a;
    int k = 1;
    for (int bit = top - 1; bit >= 0; --bit) {
        b = fmul(fsqrnT(b, k, to, from), b);
        k *= 2;
        if ((n >> bit) & 1) {
            b = fmul(fsqr(b), a);
            k += 1;
        }
    }
    return fsqr(b);
}

// --- lanes ----------------------------------------------------------------

static inline F loadF(const device uint *p, uint lane)
{
    F a;
    for (int i = 0; i < NW; ++i) a.w[i] = p[lane * NW + uint(i)];
    return a;
}

static inline void storeF(device uint *p, uint lane, F a)
{
    for (int i = 0; i < NW; ++i) p[lane * NW + uint(i)] = a.w[i];
}

static inline F constF(constant const uint *p)
{
    F a;
    for (int i = 0; i < NW; ++i) a.w[i] = p[i];
    return a;
}

static inline ulong splitmix64(ulong x)
{
    ulong z = x + 0x9E3779B97F4A7C15ul;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ul;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBul;
    return z ^ (z >> 31);
}

// Affine addition with x1 != x2; returns false when x1 == x2.
template <typename T>
static inline bool addDistinct(thread F &x1, thread F &y1, F x2, F y2, T to, T from)
{
    F dx = fadd(x1, x2);
    if (fzero(dx)) return false;
    F lam = fmul(fadd(y1, y2), finvT(dx, to, from));
    F x3 = fadd(fadd(fadd(fsqr(lam), lam), dx), constF(kCurveA));
    F y3 = fadd(fadd(fmul(lam, fadd(x1, x3)), x3), y1);
    x1 = x3;
    y1 = y3;
    return true;
}

// Q + sum_k sigma^(e_k)(B_k) with e_k = splitmix64(16 seed + k) mod M.
template <typename T>
static inline bool startPoint(ulong seed, thread F &x, thread F &y, T to, T from)
{
    x = constF(kQX);
    y = constF(kQY);
    for (int k = 0; k < KBASE; ++k) {
        int e = int(splitmix64(seed * 16ul + ulong(k)) % ulong(M));
        F bx = fsqrnT(constF(kBaseX[k]), e, to, from), by = fsqrnT(constF(kBaseY[k]), e, to, from);
        if (!addDistinct(x, y, bx, by, to, from)) return false;
    }
    return true;
}

// Normal-basis x, and sigma^j of (x, y) given the normal-basis x.
template <typename T>
static inline F toNormal(F x, T to)
{
#if KS_TABLES
    return tmap(to, x);
#else
    return nbRows(x);
#endif
}

template <typename T>
static inline void frobenius(F x, F y, F nbx, int j, thread F &sx, thread F &sy, T to, T from)
{
#if KS_TABLES && KS_FROBTAB
    sx = tmap(from, nbRot(nbx, j));
    sy = tmap(from, nbRot(tmap(to, y), j));
#else
    sx = fsqrn(x, j);
    sy = fsqrn(y, j);
#endif
}

#if KS_TABLES
#define TABLE_SETUP(tables, lid, tgs)                                              \
    threadgroup uint tgTables[2 * TBL];                                           \
    for (uint i_ = lid; i_ < 2u * TBL; i_ += tgs) tgTables[i_] = tables[i_];     \
    threadgroup_barrier(mem_flags::mem_threadgroup);                              \
    threadgroup const uint *to = tgTables, *from = tgTables + TBL;
#else
#define TABLE_SETUP(tables, lid, tgs) \
    const device uint *to = tables, *from = tables + TBL;
#endif

// --- the walk ---------------------------------------------------------------

kernel void walk(constant Args &a [[buffer(0)]],
                 device uint *X [[buffer(1)]],
                 device uint *Y [[buffer(2)]],
                 device uint *SX [[buffer(3)]],
                 device uint *SY [[buffer(4)]],
                 device ulong *seeds [[buffer(5)]],
                 device uint *trail [[buffer(6)]],   // steps so far; 0xffffffff = needs a start
                 device uint *counts [[buffer(7)]],  // lane * J_COUNT
                 device DpRec *dps [[buffer(8)]],
                 device atomic_uint *dpCount [[buffer(9)]],
                 device ulong *work [[buffer(10)]],  // per thread: walk steps, starts, abandons
                 const device uint *tables [[buffer(11)]],
                 uint tid [[thread_position_in_grid]],
                 uint lid [[thread_index_in_threadgroup]],
                 uint tgs [[threads_per_threadgroup]])
{
    TABLE_SETUP(tables, lid, tgs)
    const uint base = tid * BATCH;
    if (base >= a.lanes) return;
    ulong steps = 0, starts = 0, abandoned = 0;

    for (int b = 0; b < BATCH; ++b) {
        uint lane = base + uint(b);
        if (trail[lane] != 0xffffffffu) continue;
        ulong seed = seeds[lane];
        F x, y;
        bool ok = startPoint(seed, x, y, to, from);
        starts++;
        if (!ok) {
            seeds[lane] = seed + a.seedStride;
            continue;
        }
        storeF(X, lane, x);
        storeF(Y, lane, y);
        for (int j = 0; j < J_COUNT; ++j) counts[lane * J_COUNT + uint(j)] = 0;
        trail[lane] = 0;
    }

    for (uint s = 0; s < a.steps; ++s) {
        F pre[BATCH];
        F acc = fone();
        uint live = 0;
        for (int b = 0; b < BATCH; ++b) {
            uint lane = base + uint(b);
            pre[b] = acc;
            uint t = trail[lane];
            if (t == 0xffffffffu) continue;
            F x = loadF(X, lane);
            F nbx = toNormal(x, to);
            int hw = fweight(nbx);
            if (hw <= DPW || t >= a.maxTrail) {
                if (hw <= DPW) {
                    uint i = atomic_fetch_add_explicit(dpCount, 1u, memory_order_relaxed);
                    if (i < a.dpCap) {
                        device DpRec &r = dps[i];
                        r.seed = seeds[lane];
                        r.steps = t;
                        r.lane = lane;
                        for (int j = 0; j < J_COUNT; ++j) r.counts[j] = counts[lane * J_COUNT + uint(j)];
                        F y = loadF(Y, lane);
                        for (int i2 = 0; i2 < 4; ++i2) {
                            r.x[i2] = i2 < NW ? x.w[i2] : 0u;
                            r.y[i2] = i2 < NW ? y.w[i2] : 0u;
                            r.nb[i2] = i2 < NW ? nbx.w[i2] : 0u;
                        }
                    }
                } else {
                    abandoned++;
                }
                seeds[lane] = seeds[lane] + a.seedStride;
                trail[lane] = 0xffffffffu;
                continue;
            }
            int j = J_BASE + ((hw >> 1) & (J_COUNT - 1));
            F sx, sy;
            frobenius(x, loadF(Y, lane), nbx, j, sx, sy, to, from);
            storeF(SX, lane, sx);
            storeF(SY, lane, sy);
            counts[lane * J_COUNT + uint(j - J_BASE)] += 1u;
            acc = fmul(acc, fadd(x, sx));
            live |= 1u << b;
        }
        if (live == 0) break;
        F inv = finvT(acc, to, from);
        for (int b = BATCH - 1; b >= 0; --b) {
            if (!((live >> b) & 1u)) continue;
            uint lane = base + uint(b);
            F x = loadF(X, lane), y = loadF(Y, lane);
            F sx = loadF(SX, lane), sy = loadF(SY, lane);
            F dx = fadd(x, sx);
            F dinv = fmul(inv, pre[b]);
            inv = fmul(inv, dx);
            F lam = fmul(fadd(y, sy), dinv);
            F x3 = fadd(fadd(fadd(fsqr(lam), lam), dx), constF(kCurveA));
            F y3 = fadd(fadd(fmul(lam, fadd(x, x3)), x3), y);
            storeF(X, lane, x3);
            storeF(Y, lane, y3);
            trail[lane] += 1u;
            steps++;
        }
    }
    work[tid * 3 + 0] += steps;
    work[tid * 3 + 1] += starts;
    work[tid * 3 + 2] += abandoned;
}

// --- self-test: field ops, the step and start points against field.py -------

kernel void selftest(const device uint *in [[buffer(0)]],   // per case: a, b, px, py (NW each)
                     device uint *out [[buffer(1)]],        // per case: mul, sqr, inv, step x/y, start x/y, sqrn, nb
                     const device ulong *seedIn [[buffer(2)]],
                     constant uint &cases [[buffer(3)]],
                     const device uint *tables [[buffer(4)]],
                     uint tid [[thread_position_in_grid]],
                     uint lid [[thread_index_in_threadgroup]],
                     uint tgs [[threads_per_threadgroup]])
{
    TABLE_SETUP(tables, lid, tgs)
    if (tid >= cases) return;
    F a = loadF(in, tid * 4 + 0), b = loadF(in, tid * 4 + 1);
    F px = loadF(in, tid * 4 + 2), py = loadF(in, tid * 4 + 3);
    uint o = tid * 9;
    storeF(out, o + 0, fmul(a, b));
    storeF(out, o + 1, fsqr(a));
    storeF(out, o + 2, finvT(a, to, from));
    F nbx = toNormal(px, to);
    int hw = fweight(nbx);
    int j = J_BASE + ((hw >> 1) & (J_COUNT - 1));
    F sx, sy;
    frobenius(px, py, nbx, j, sx, sy, to, from);
    F x = px, y = py;
    bool ok1 = addDistinct(x, y, sx, sy, to, from);
    storeF(out, o + 3, x);
    storeF(out, o + 4, y);
    F stx, sty;
    bool ok2 = startPoint(seedIn[tid], stx, sty, to, from);
    storeF(out, o + 5, stx);
    storeF(out, o + 6, sty);
    storeF(out, o + 7, fsqrnT(a, int(tid % uint(M)), to, from));
    storeF(out, o + 8, nbx);
    device uint *tail = out + cases * 9 * NW + tid * 3;
    tail[0] = uint(hw);
    tail[1] = uint(j);
    tail[2] = (ok1 ? 1u : 0u) | (ok2 ? 2u : 0u);
}

// --- microbenchmark: dependent chains of one operation ---------------------------
// op 0 mul, 1 sqr, 2 inv, 3 normal basis (the walk's), 4 sigma^6 of a point,
// 5 one full walk step's field work without memory traffic.

kernel void microbench(constant uint &op [[buffer(0)]],
                       constant uint &iters [[buffer(1)]],
                       device uint *sink [[buffer(2)]],
                       const device uint *tables [[buffer(3)]],
                       uint tid [[thread_position_in_grid]],
                       uint lid [[thread_index_in_threadgroup]],
                       uint tgs [[threads_per_threadgroup]])
{
    TABLE_SETUP(tables, lid, tgs)
    F a, b;
    for (int i = 0; i < NW; ++i) {
        a.w[i] = uint(splitmix64(tid * 8u + uint(i)));
        b.w[i] = uint(splitmix64(tid * 8u + uint(i) + 4u));
    }
    if (M & 31) {
        a.w[NW - 1] &= (1u << (M & 31)) - 1u;
        b.w[NW - 1] &= (1u << (M & 31)) - 1u;
    }
    a.w[0] |= 1u;
    for (uint it = 0; it < iters; ++it) {
        switch (op) {
        case 0: a = fmul(a, b); break;
        case 1: a = fsqr(a); break;
        case 2: a = finvT(a, to, from); break;
        case 3: a = fadd(toNormal(a, to), b); break;
        case 4: {
            F sx, sy;
            frobenius(a, b, toNormal(a, to), 6, sx, sy, to, from);
            a = fadd(sx, b);
            b = fadd(sy, a);
            break;
        }
        default: {
            // nbx, weight, sigma^j, 3 batch products, lambda, lambda^2, y3.
            F nbx = toNormal(a, to);
            int j = J_BASE + ((fweight(nbx) >> 1) & (J_COUNT - 1));
            F sx, sy;
            frobenius(a, b, nbx, j, sx, sy, to, from);
            F dx = fadd(a, sx);
            F t = fmul(fmul(dx, b), fmul(b, a));
            F lam = fmul(fadd(b, sy), t);
            F x3 = fadd(fadd(fsqr(lam), lam), dx);
            b = fadd(fadd(fmul(lam, fadd(a, x3)), x3), b);
            a = x3;
            break;
        }
        }
    }
    for (int i = 0; i < NW; ++i) sink[tid * NW + uint(i)] = a.w[i] ^ b.w[i];
}
