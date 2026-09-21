// walk.metal - the packed table walk as Metal compute kernels.
//
// scripts/mslgen.py puts this file after the packed GF(2^131) headers, so the
// field arithmetic (mulPolynomial131, squarePolynomial131, inv131, the basis
// conversions) and the selection (twSelectHist, twAddend) below are the ones
// every other client runs; only the loop around them is written here.  It is
// the two-pass walk of include/packedkernels.cuh: a thread owns ECC_BATCH
// lanes and shares one inversion between them, a lane that reaches a
// distinguished point writes a 64-byte report and marks itself dead, and the
// host revives dead lanes between launches.  Apple GPUs have no carry-less
// multiplier, so products are the generated masked-multiply form.
//
// State is lane-major (lane = thread * ECC_BATCH + slot): five words per
// coordinate, in the polynomial basis.

using namespace eccPacked131;

struct DpRecord {
    ulong seed;
    ulong iters;
    ulong x[3];
    ulong y[3];
};

struct WalkArgs {
    uint threads;
    uint steps;
    int dpWeight;
    uint dpCap;
    ulong iterBase;
    ulong maxIters; // 0 disables the overdue guard
    uint guardPeriod;
    uint pad;
};

static inline P131 loadLane(const device uint *p, uint lane)
{
    P131 a;
    for (int i = 0; i < 5; ++i) a.v[i] = p[lane * 5u + uint(i)];
    return a;
}
static inline void storeLane(device uint *p, uint lane, P131 a)
{
    for (int i = 0; i < 5; ++i) p[lane * 5u + uint(i)] = a.v[i];
}
static inline int weight131(P131 a)
{
    return int(popcount(a.v[0]) + popcount(a.v[1]) + popcount(a.v[2]) + popcount(a.v[3]) +
               popcount(a.v[4] & 7u));
}
static inline void limbsOf(P131 a, thread ulong *out)
{
    out[0] = ulong(a.v[0]) | (ulong(a.v[1]) << 32);
    out[1] = ulong(a.v[2]) | (ulong(a.v[3]) << 32);
    out[2] = ulong(a.v[4] & 7u);
}

kernel void walk(constant WalkArgs &a [[buffer(0)]], device uint *X [[buffer(1)]],
                 device uint *Y [[buffer(2)]], device ulong *hist [[buffer(3)]],
                 const device ulong *seed [[buffer(4)]],
                 const device ulong *startIter [[buffer(5)]], device uint *dead [[buffer(6)]],
                 device DpRecord *dp [[buffer(7)]], device atomic_uint *counts [[buffer(8)]],
                 const device uint *tw [[buffer(9)]], uint tid [[thread_position_in_grid]])
{
    if (tid >= a.threads) return;
    const uint base = tid * uint(ECC_BATCH);
    P131 W[ECC_BATCH], D[ECC_BATCH];
    for (uint step = 0; step < a.steps; ++step) {
        const ulong now = a.iterBase + ulong(step);
        const bool guard = a.maxIters != 0 && now % ulong(a.guardPeriod) == 0;
        // Forward pass: report, select the addend, multiply the denominators up.
        P131 prod;
        for (uint slot = 0; slot < uint(ECC_BATCH); ++slot) {
            const uint lane = base + slot;
            const P131 xp = loadLane(X, lane), yp = loadLane(Y, lane);
            const P131 xn = fromPolynomial131(xp);
            const int hw = weight131(xn);
            if (!dead[lane]) {
                if (hw <= a.dpWeight) {
                    if ((seed[lane] & 0xFFFFul) == 0xFFFFul)
                        atomic_fetch_add_explicit(counts + 2, 1u, memory_order_relaxed);
                    const uint dest = atomic_fetch_add_explicit(counts, 1u, memory_order_relaxed);
                    if (dest < a.dpCap) {
                        DpRecord rec;
                        rec.seed = seed[lane];
                        rec.iters = now - startIter[lane];
                        limbsOf(xn, rec.x);
                        limbsOf(fromPolynomial131(yp), rec.y);
                        dp[dest] = rec;
                    }
                    dead[lane] = 1u;
                } else if (guard && now - startIter[lane] >= a.maxIters) {
                    if ((seed[lane] & 0xFFFFul) == 0xFFFFul)
                        atomic_fetch_add_explicit(counts + 2, 1u, memory_order_relaxed);
                    dead[lane] = 1u;
                    atomic_fetch_add_explicit(counts + 1, 1u, memory_order_relaxed);
                }
            }
            ulong h = hist[lane];
            const uint tag = twSelectHist(xn, yp, hw, &h, tw);
            hist[lane] = h;
            P131 d, e;
            twAddend(tag, xp, yp, tw, &d, &e);
            D[slot] = d;
            if (slot) {
                const PolynomialPair pair = mulPolynomialPair131(prod, e, d);
                W[slot] = pair.first;
                prod = pair.second;
            } else {
                W[0] = e;
                prod = d;
            }
        }
        P131 inv = toPolynomial131(inv131(fromPolynomial131(prod)));
        // Reverse pass: lambda = e / d, then the affine addition.
        for (int slot = ECC_BATCH - 1; slot >= 0; --slot) {
            const uint lane = base + uint(slot);
            const P131 x = loadLane(X, lane), y = loadLane(Y, lane), d = D[slot];
            P131 lambda;
            if (slot) {
                const PolynomialPair pair = mulPolynomialPair131(inv, d, W[slot]);
                inv = pair.first;
                lambda = pair.second;
            } else {
                lambda = mulPolynomial131(inv, W[0]);
            }
            const P131 nx = add131(add131(squarePolynomial131(lambda), lambda), d);
            const P131 ny = add131(add131(mulPolynomial131(lambda, add131(x, nx)), nx), y);
            storeLane(X, lane, nx);
            storeLane(Y, lane, ny);
        }
    }
}

// Every routine the walk kernel calls, on inputs the host chooses, so that
// src/metaltest.mm can hold what this GPU computes to what the host computes
// (which src/cputest.cpp holds to the golden model).  Per case, in: a, b
// (normal basis), a curve point x, y (normal basis) and a step history;
// out: the words listed in metaltest.mm's SelfOut.
#define SELF_IN  22u
#define SELF_OUT 53u
kernel void selftest(const device uint *in [[buffer(0)]], device uint *out [[buffer(1)]],
                     const device uint *tw [[buffer(2)]], constant uint &cases [[buffer(3)]],
                     uint id [[thread_position_in_grid]])
{
    if (id >= cases) return;
    const device uint *c = in + id * SELF_IN;
    device uint *o = out + id * SELF_OUT;
    P131 a, b, px, py;
    for (int i = 0; i < 5; ++i) {
        a.v[i] = c[i];
        b.v[i] = c[5 + i];
        px.v[i] = c[10 + i];
        py.v[i] = c[15 + i];
    }
    ulong h = ulong(c[20]) | (ulong(c[21]) << 32);
    const P131 qa = toPolynomial131(a), qb = toPolynomial131(b);
    const P131 r[8] = {mul131(a, b),
                       sqr131(a),
                       inv131(a),
                       qa,
                       fromPolynomial131(qa),
                       mulPolynomial131(qa, qb),
                       squarePolynomial131(qa),
                       mulPolynomialPair131(qa, qb, qa).second};
    for (int k = 0; k < 8; ++k)
        for (int i = 0; i < 5; ++i) o[k * 5 + i] = r[k].v[i];
    const P131 xp = toPolynomial131(px), yp = toPolynomial131(py);
    const uint tag = twSelectHist(px, yp, weight131(px), &h, tw);
    P131 d, e;
    twAddend(tag, xp, yp, tw, &d, &e);
    o[40] = tag;
    o[41] = uint(h);
    o[42] = uint(h >> 32);
    for (int i = 0; i < 5; ++i) {
        o[43 + i] = d.v[i];
        o[48 + i] = e.v[i];
    }
}
