// Batched walk driver shared by the CUDA kernel and the CPU backend.
//
// State layout is structure-of-arrays indexed by thread so that lanes of a warp
// touch consecutive words:
//
//     x[(slot * M + word) * threads + tid]
//
// Only x, y and the Montgomery product chain move through memory each
// iteration; the addition denominators are recomputed in pass 2 from three
// stored weight bits.
#pragma once

#include "walk.h"

// How far to unroll a loop that is M words wide.  Fully unrolling one asks
// ptxas to keep all 131 values live at once and it spills them: full unroll
// costs 9820 bytes of spill traffic in the walk kernel against 4784 at any
// factor of 16 or more, measured with ptxas at batch 32, threads 128,
// minBlocks 2.  16 is the smallest factor that reaches that plateau.
#ifndef ECC_BATCH
#define ECC_BATCH 16
#endif

#ifndef ECC_GUARD_PERIOD
#define ECC_GUARD_PERIOD 4096
#endif

template <class W>
struct WalkParams {
    int threads;
    int steps;
    int dpWeight;
    unsigned runId;
    unsigned long long maxIters;      // 0 disables the cycle guard
    unsigned long long iterBase;
    W *x;
    W *y;
    W *pchain;
    unsigned long long *seed;         // one per lane
    unsigned long long *startIter;    // one per lane
    W *dead;                          // one word per slot: lanes awaiting a restart
    DpRecord *dp;
    unsigned *dpCount;                // report count, restart count, exhausted seed flag
    unsigned dpCap;
    CurveConsts consts;
    // Table walk only (tablewalk.h): the last four step tags of every lane,
    // and the flat constant buffer packedtablewalk.cuh copies to shared memory.
    unsigned long long *hist;
    const unsigned *twConsts;
};

ECC_HD unsigned eccAtomicInc(unsigned *p) {
#if defined(__CUDA_ARCH__)
    return atomicAdd(p, 1u);
#elif defined(_OPENMP) || defined(ECC_HOST_ATOMIC)
    return __sync_fetch_and_add(p, 1u);
#else
    unsigned v = *p;
    *p = v + 1;
    return v;
#endif
}

template <class Cfg, class W>
struct Kernel {
    typedef Walk<Cfg, W> WK;
    typedef typename Cfg::template Field<W> F;
    static const int M = Cfg::M;
    static const int LANES = WordTraits<W>::LANES;
    static const int HWBITS = Cfg::HWBITS;
    static const int BATCH = ECC_BATCH;

    static ECC_HD size_t fieldIndex(int slot, int word, int tid, int threads) {
        return ((size_t)(slot * M + word) * (size_t)threads) + (size_t)tid;
    }
    static ECC_HD size_t laneIndex(int slot, int lane, int tid, int threads) {
        return ((size_t)(slot * LANES + lane) * (size_t)threads) + (size_t)tid;
    }

    static ECC_HD void load(const W *src, int slot, int tid, int threads, W *dst) {
ECC_WIDE_UNROLL_PRAGMA
        for (int i = 0; i < M; ++i) dst[i] = src[fieldIndex(slot, i, tid, threads)];
    }
    static ECC_HD void store(W *dst, int slot, int tid, int threads, const W *src) {
ECC_WIDE_UNROLL_PRAGMA
        for (int i = 0; i < M; ++i) dst[fieldIndex(slot, i, tid, threads)] = src[i];
    }

    // ---- start every walk of this thread ------------------------------
    static ECC_HD void init(int tid, const WalkParams<W> &P) {
        W x[M], y[M];
        unsigned long long seeds[LANES];
        for (int slot = 0; slot < BATCH; ++slot) {
            for (int lane = 0; lane < LANES; ++lane) {
                const unsigned long long walkIndex =
                    ((unsigned long long)tid * BATCH + slot) * LANES + lane;
                seeds[lane] = eccSeedFor(P.runId, walkIndex);
                P.seed[laneIndex(slot, lane, tid, P.threads)] = seeds[lane];
                P.startIter[laneIndex(slot, lane, tid, P.threads)] = 0;
            }
            WK::startPoint(seeds, P.consts, x, y);
            store(P.x, slot, tid, P.threads, x);
            store(P.y, slot, tid, P.threads, y);
            P.dead[(size_t)slot * (size_t)P.threads + (size_t)tid] = ECC_ZERO;
        }
    }

    // Lanes that have walked longer than maxIters without reporting.  Cold: it
    // runs once every ECC_GUARD_PERIOD steps, and inlining a 32-iteration loop
    // of global loads into the hot body costs registers on every step.
    static ECC_BIG W overdueLanes(int tid, int slot, const WalkParams<W> &P,
                                  unsigned long long now) {
        W dp = ECC_ZERO;
        for (int lane = 0; lane < LANES; ++lane) {
            const size_t li = laneIndex(slot, lane, tid, P.threads);
            if (now - P.startIter[li] >= P.maxIters) dp |= laneMask<W>(lane);
        }
        return dp;
    }

    // Report every lane flagged in `mask` and mark it for restart.  Restarting
    // is deferred to the reseed kernel: computing a fresh start point needs 128
    // point additions, and keeping that call chain out of the hot kernel is
    // worth 5.8 KB of per-thread stack frame.  A marked lane keeps walking, but
    // its reports are suppressed until it is revived.
    static ECC_BIG void handleDistinguished(int tid, int slot, W mask, const WalkParams<W> &P,
                                           unsigned long long now, const W *x, const W *y) {
        for (int lane = 0; lane < LANES; ++lane) {
            if (!laneBit(mask, lane)) continue;
            const size_t li = laneIndex(slot, lane, tid, P.threads);
            DpRecord rec;
            rec.seed = P.seed[li];
            if ((rec.seed & 0xffffull) == 0xffffull) eccAtomicInc(P.dpCount + 2);
            rec.iters = now - P.startIter[li];
            F::getLane(x, lane, rec.x);
            F::getLane(y, lane, rec.y);
            const unsigned slotIdx = eccAtomicInc(P.dpCount);
            if (slotIdx < P.dpCap) P.dp[slotIdx] = rec;
        }
    }

    // ---- revive every marked lane (rare; launched between walk kernels) ----
    static ECC_HD void reseed(int tid, const WalkParams<W> &P) {
        W x[M], y[M];
        unsigned long long seeds[LANES];
        for (int slot = 0; slot < BATCH; ++slot) {
            const size_t di = (size_t)slot * (size_t)P.threads + (size_t)tid;
            const W mask = P.dead[di];
            if (mask == ECC_ZERO) continue;
            load(P.x, slot, tid, P.threads, x);
            load(P.y, slot, tid, P.threads, y);
            for (int lane = 0; lane < LANES; ++lane) {
                const size_t li = laneIndex(slot, lane, tid, P.threads);
                unsigned long long sd = P.seed[li];
                if (laneBit(mask, lane)) {
                    sd += 1;
                    P.seed[li] = sd;
                    P.startIter[li] = P.iterBase;
                }
                seeds[lane] = sd;
            }
            WK::reseedLanes(mask, seeds, P.consts, x, y);
            store(P.x, slot, tid, P.threads, x);
            store(P.y, slot, tid, P.threads, y);
            P.dead[di] = ECC_ZERO;
        }
    }

    // ---- one full iteration over the batch ----------------------------
    static ECC_HD void run(int tid, const WalkParams<W> &P) {
        W x[M], y[M], t[M], u[M], prod[M], inv[M];
        W hb[HWBITS < 4 ? 4 : HWBITS];
        W jbits[BATCH][4];

#pragma unroll 1
        for (int step = 0; step < P.steps; ++step) {
            const unsigned long long now = P.iterBase + (unsigned long long)step;
            const bool guard = P.maxIters != 0 && (now % ECC_GUARD_PERIOD) == 0;

#pragma unroll 1
            for (int slot = 0; slot < BATCH; ++slot) {
                load(P.x, slot, tid, P.threads, x);
                const size_t di = (size_t)slot * (size_t)P.threads + (size_t)tid;
                WK::hamming(x, hb);
                W dp = WK::dpMask(hb, P.dpWeight);
                const W alreadyDead = P.dead[di];
                dp &= ~alreadyDead;
                if (dp != ECC_ZERO) {
                    load(P.y, slot, tid, P.threads, y);
                    handleDistinguished(tid, slot, dp, P, now, x, y);
                    P.dead[di] = alreadyDead | dp;
                }
                if (guard) {
                    const W overdue = overdueLanes(tid, slot, P, now) & ~P.dead[di];
                    if (overdue != ECC_ZERO) {
                        for (int lane = 0; lane < LANES; ++lane) {
                            const size_t li = laneIndex(slot, lane, tid, P.threads);
                            if (laneBit(overdue, lane) && (P.seed[li] & 0xffffull) == 0xffffull)
                                eccAtomicInc(P.dpCount + 2);
                        }
                        P.dead[di] |= overdue;
                        eccAtomicInc(P.dpCount + 1);
                    }
                }
                jbits[slot][1] = hb[1];
                jbits[slot][2] = hb[2];
                jbits[slot][3] = hb[3];
                WK::sigmaJ(x, jbits[slot], t);
                F::add(x, t, u);                       // u = d
                if (slot == 0) {
                    F::copy(prod, u);
                } else {
                    F::mul(prod, u, t);
                    F::copy(prod, t);
                }
                // The final product goes directly to inv; reverse traversal
                // only reads prefixes through BATCH-2.
                if (slot + 1 < BATCH) store(P.pchain, slot, tid, P.threads, prod);
            }

            F::inv(prod, inv);

#pragma unroll 1
            for (int slot = BATCH - 1; slot >= 0; --slot) {
                load(P.x, slot, tid, P.threads, x);
                load(P.y, slot, tid, P.threads, y);
                W d[M], e[M], ii[M], lam[M];
                WK::sigmaJ(x, jbits[slot], t);
                F::add(x, t, d);
                WK::sigmaJ(y, jbits[slot], t);
                F::add(y, t, e);
                if (slot > 0) {
                    load(P.pchain, slot - 1, tid, P.threads, u);
                    F::mul(inv, u, ii);
                    F::mul(inv, d, t);
                    F::copy(inv, t);
                } else {
                    F::copy(ii, inv);
                }
                F::mul(e, ii, lam);
                F::sqr(lam, t);
ECC_WIDE_UNROLL_PRAGMA
                for (int i = 0; i < M; ++i) t[i] = ECC_XOR3(t[i], lam[i], d[i]);   // x3
                F::add(x, t, u);
                F::mul(lam, u, e);
ECC_WIDE_UNROLL_PRAGMA
                for (int i = 0; i < M; ++i) y[i] = ECC_XOR3(e[i], t[i], y[i]);
                store(P.x, slot, tid, P.threads, t);
                store(P.y, slot, tid, P.threads, y);
            }
        }
    }
};

#if defined(__CUDACC__)
#ifndef ECC_SMEM_SPILL
#define ECC_SMEM_SPILL 0
#endif
// enable_smem_spilling is consumed by ptxas, not by the frontend, so the
// version that matters is the assembler's -- which the frontend cannot see.
// nvcc bundles its own, so gating on __CUDACC_VER_MAJOR__ is the right proxy
// there and 13 is the documented floor.  clang does not bundle one: autolab
// pairs it with whichever ptxas it was pointed at, and ptxas 12.9 was measured
// to accept the pragma and report the smem it moved the frame into.  Treating
// "not nvcc" as "too old" only blocked the offline search from seeing the knob
// at all, so let that path through and leave the nvcc floor exactly where it was.
#if ECC_SMEM_SPILL && defined(__CUDACC_VER_MAJOR__) && __CUDACC_VER_MAJOR__ < 13
#error "ECC_SMEM_SPILL requires nvcc from CUDA 13 or newer"
#endif
#ifndef ECC_THREADS
#define ECC_THREADS 128
#endif
// Occupancy knob.  With only a block-size bound, ptxas gives every thread the
// full 255 registers, which caps the machine at about 256 threads per SM.
// Asking for more resident blocks trades registers for occupancy; which side
// wins is a measurement, so it is a build parameter.
// 2 is free at 128 threads: 128 * 255 * 2 = 65280 registers, just inside the
// 65536 an SM has, so occupancy doubles without costing a single spill.  Going
// further trades registers for warps and has to be measured.
#ifndef ECC_MINBLOCKS
#define ECC_MINBLOCKS 2
#endif
#define ECC_BOUNDS __launch_bounds__(ECC_THREADS, ECC_MINBLOCKS)
template <class Cfg, class W>
__global__ void ECC_BOUNDS eccWalkKernel(WalkParams<W> P) {
#if ECC_SMEM_SPILL
    asm volatile (".pragma \"enable_smem_spilling\";");
#endif
    const int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= P.threads) return;
    Kernel<Cfg, W>::run(tid, P);
}
template <class Cfg, class W>
__global__ void ECC_BOUNDS eccInitKernel(WalkParams<W> P) {
    const int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= P.threads) return;
    Kernel<Cfg, W>::init(tid, P);
}
template <class Cfg, class W>
__global__ void ECC_BOUNDS eccReseedKernel(WalkParams<W> P) {
    const int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= P.threads) return;
    Kernel<Cfg, W>::reseed(tid, P);
}
#endif
