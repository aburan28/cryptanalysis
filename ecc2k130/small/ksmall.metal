// ksmall.metal - Pollard rho on a small Koblitz curve y^2 + xy = x^3 + a x^2 + 1
// over F_2^M, walking the ECC2K-130 iteration R -> R + sigma^j(R).
//
// run.py prepends a prelude that defines the degree and field (M, NW, kTerms),
// the batch size, the distinguished-point cutoff, the normal-basis rows
// (kNormal) and the start-point bases (kBaseX/Y, kQX/Y).  The kernel is
// generic in M <= 127; nothing here is specific to one degree.
//
// j = J_BASE + (HW/2 mod 8), where HW is the Hamming weight of x in a normal
// basis.  HW is invariant under Frobenius and negation, so the walk is a walk
// on classes {+-sigma^i R} and gains the sqrt(2M) of ECC2K-130.  A point is
// distinguished when HW <= DPW.  Each lane counts how many times it took each
// j; the point is then prod (1+lambda^j)^count_j (u P + Q), so the host needs
// no scalar arithmetic in the walk.  Apple GPUs have no carry-less multiply:
// products use masked integer multiplies.

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

// --- field ----------------------------------------------------------------

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
    for (int i = 0; i < 2 * NW + 1; ++i) c[i] = 0;
    for (int i = 0; i < NW; ++i)
        for (int j = 0; j < NW; ++j) {
            ulong p = clmul32(a.w[i], b.w[j]);
            c[i + j] ^= uint(p);
            c[i + j + 1] ^= uint(p >> 32);
        }
    return reduce(c);
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
        ulong s = spread32(a.w[i]);
        c[2 * i] = uint(s);
        c[2 * i + 1] = uint(s >> 32);
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

// Itoh-Tsujii: b_k = a^(2^k - 1); a^-1 = b_(M-1)^2.
static inline F finv(F a)
{
    const int n = M - 1;
    int top = 31 - clz(uint(n));
    F b = a;
    int k = 1;
    for (int bit = top - 1; bit >= 0; --bit) {
        b = fmul(fsqrn(b, k), b);
        k *= 2;
        if ((n >> bit) & 1) {
            b = fmul(fsqr(b), a);
            k += 1;
        }
    }
    return fsqr(b);
}

// Coordinates in the normal basis; bit i is parity(kNormal[i] & x).
static inline int nbWeight(F x)
{
    int hw = 0;
    for (int r = 0; r < M; ++r) {
        uint acc = 0;
        for (int i = 0; i < NW; ++i) acc ^= kNormal[r][i] & x.w[i];
        hw += int(popcount(acc) & 1u);
    }
    return hw;
}

static inline void nbVector(F x, thread uint *out)
{
    for (int i = 0; i < 4; ++i) out[i] = 0;
    for (int r = 0; r < M; ++r) {
        uint acc = 0;
        for (int i = 0; i < NW; ++i) acc ^= kNormal[r][i] & x.w[i];
        out[r >> 5] |= (popcount(acc) & 1u) << (r & 31);
    }
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
static inline bool addDistinct(thread F &x1, thread F &y1, F x2, F y2)
{
    F dx = fadd(x1, x2);
    if (fzero(dx)) return false;
    F lam = fmul(fadd(y1, y2), finv(dx));
    F x3 = fadd(fadd(fadd(fsqr(lam), lam), dx), constF(kCurveA));
    F y3 = fadd(fadd(fmul(lam, fadd(x1, x3)), x3), y1);
    x1 = x3;
    y1 = y3;
    return true;
}

// Q + sum_k sigma^(e_k)(B_k) with e_k = splitmix64(16 seed + k) mod M.
static inline bool startPoint(ulong seed, thread F &x, thread F &y)
{
    x = constF(kQX);
    y = constF(kQY);
    for (int k = 0; k < KBASE; ++k) {
        int e = int(splitmix64(seed * 16ul + ulong(k)) % ulong(M));
        F bx = fsqrn(constF(kBaseX[k]), e), by = fsqrn(constF(kBaseY[k]), e);
        if (!addDistinct(x, y, bx, by)) return false;
    }
    return true;
}

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
                 uint tid [[thread_position_in_grid]])
{
    const uint base = tid * BATCH;
    if (base >= a.lanes) return;
    ulong steps = 0, starts = 0, abandoned = 0;

    for (int b = 0; b < BATCH; ++b) {
        uint lane = base + uint(b);
        if (trail[lane] != 0xffffffffu) continue;
        ulong seed = seeds[lane];
        F x, y;
        bool ok = startPoint(seed, x, y);
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
            int hw = nbWeight(x);
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
                        }
                        uint nb[4];
                        nbVector(x, nb);
                        for (int i2 = 0; i2 < 4; ++i2) r.nb[i2] = nb[i2];
                    }
                } else {
                    abandoned++;
                }
                seeds[lane] = seeds[lane] + a.seedStride;
                trail[lane] = 0xffffffffu;
                continue;
            }
            int j = J_BASE + ((hw >> 1) & (J_COUNT - 1));
            F sx = fsqrn(x, j), sy = fsqrn(loadF(Y, lane), j);
            storeF(SX, lane, sx);
            storeF(SY, lane, sy);
            counts[lane * J_COUNT + uint(j - J_BASE)] += 1u;
            acc = fmul(acc, fadd(x, sx));
            live |= 1u << b;
        }
        if (live == 0) break;
        F inv = finv(acc);
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
                     device uint *out [[buffer(1)]],        // per case: mul, sqr, inv, step x, step y, start x, start y, hw, j, ok
                     const device ulong *seedIn [[buffer(2)]],
                     constant uint &cases [[buffer(3)]],
                     uint tid [[thread_position_in_grid]])
{
    if (tid >= cases) return;
    F a = loadF(in, tid * 4 + 0), b = loadF(in, tid * 4 + 1);
    F px = loadF(in, tid * 4 + 2), py = loadF(in, tid * 4 + 3);
    uint o = tid * 7;
    storeF(out, o + 0, fmul(a, b));
    storeF(out, o + 1, fsqr(a));
    storeF(out, o + 2, finv(a));
    int hw = nbWeight(px);
    int j = J_BASE + ((hw >> 1) & (J_COUNT - 1));
    F x = px, y = py;
    bool ok1 = addDistinct(x, y, fsqrn(px, j), fsqrn(py, j));
    storeF(out, o + 3, x);
    storeF(out, o + 4, y);
    F sx, sy;
    bool ok2 = startPoint(seedIn[tid], sx, sy);
    storeF(out, o + 5, sx);
    storeF(out, o + 6, sy);
    device uint *tail = out + cases * 7 * NW + tid * 3;
    tail[0] = uint(hw);
    tail[1] = uint(j);
    tail[2] = (ok1 ? 1u : 0u) | (ok2 ? 2u : 0u);
}
