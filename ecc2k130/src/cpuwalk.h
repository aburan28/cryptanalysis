// cpuwalk.h - the packed table walk on the host's cores.
//
// The same walk as include/packedkernels.cuh, written for a CPU: the seed
// schedule, the table and the inversion are the device's own headers compiled
// as host code, and the step is src/f131.h, the same arithmetic and the same
// selection on 64-bit limbs.  What differs is what a CPU wants differently.
//
//   - Elements are three 64-bit limbs, not five 32-bit words: 53 ns an
//     iteration on an M4 Pro core against 127 on the packed routines.
//   - The state is stored limb by limb -- lane i's limb 0 at x0[i], its limb 1
//     at x1[i] -- so that N consecutive lanes load as three vector registers,
//     and on x86-64 the five products, the squaring and the conversion of a
//     step run N lanes at a time on the vector carry-less multiplier
//     (src/f131x.h: N = 8 on AVX-512, 4 on AVX2, 2 on SSE), and the
//     selection N lanes at a time on the bit planes of the labels, as the
//     model computes it, instead of through f131.h's byte tables.  The tag,
//     the addend's loads and the rare lane that reports stay scalar.
//   - A batch is `batch` lanes sharing one inversion by Montgomery's trick,
//     512 by default on the scalar path and 2048 on the vector path, against
//     the device's 16: a core has no register budget to respect, the inversion
//     is about 700 ns against a lane's step, and a batch of state (x, y,
//     prefix product, denominator, history: 104 bytes a lane, plus the byte
//     scratch) sits in cache beside the selection tables.
//   - A step is a sequence of loops over the batch, not a loop of steps over
//     lanes: a lane's selection and its place in the inversion chain are
//     dependency chains much longer than their instruction counts, and a core
//     only stays full when neighbouring lanes' chains overlap.  The chain is
//     cut into K interleaved chains (lane i in chain i mod K) so that no
//     product waits on the lane before it; on the vector path K is N lanes
//     times ECC_F131_CHAIN_VECTORS, and each vector register of accumulators
//     advances N chains at once.
//   - The denominator d = x + x_T is stored by the forward pass rather than
//     rebuilt from the step tag (ECC_TABLE_TAG_DENOM): that knob buys back
//     device memory traffic a cache does not charge for.
//   - A lane that reports restarts in the same step from its next seed,
//     instead of idling until the launch ends and a revive kernel runs.  The
//     report is the device's: (seed, steps since the start point, x, y).
//   - Work is handed out in slices of at most 64 steps of one batch, to
//     whichever worker is free, so performance and efficiency cores both stay
//     busy to the end of a launch without the slow ones gating it.  A batch is
//     advanced by one worker at a time; which worker and in what order does
//     not change any lane's trail, which depends only on its seed.
//
// Every product is exact field arithmetic, so the chain count, the vector
// width and the batch size change the order of the multiplications and
// nothing else: a lane's trail is a function of its seed alone.
// src/cputest.cpp holds this engine to the golden model: start points, every
// lane's state after a run against a re-walk from its seed, every report, and
// the independence of the reports from the geometry.
#pragma once

#include "client.h"
#include "f131.h"
#include "f131x.h"

#include <stdlib.h>

#include <atomic>
#include <memory>
#include <mutex>
#include <thread>

// Vector registers of chain accumulators on the vector path: K = N lanes
// times this.  Two keeps two independent products in flight per lane group,
// which covers a product's latency on the cores measured so far; one is the
// shorter prefix at small batches.
#ifndef ECC_F131_CHAIN_VECTORS
#    define ECC_F131_CHAIN_VECTORS 2
#endif

namespace ec2k_cpu
{

using namespace ec2k_client;
using eccPacked131::P131;
using f131::F131;

inline int weight131(const P131 &a)
{
    const uint64_t lo = a.v[0] | (uint64_t(a.v[1]) << 32), hi = a.v[2] | (uint64_t(a.v[3]) << 32);
    return __builtin_popcountll(lo) + __builtin_popcountll(hi) + __builtin_popcount(a.v[4] & 7u);
}

// 1/a in the polynomial basis, through the normal-basis Itoh-Tsujii chain.
inline P131 invPolynomial131(const P131 &a)
{
    using namespace eccPacked131;
    return toPolynomial131(inv131(fromPolynomial131(a)));
}

// Field elements stored limb by limb: lane i is (w0[i], w1[i], w2[i]).  Each
// limb array is 64-byte aligned, so a vector of N lanes at a multiple of N
// loads from one cache line when the batch is a multiple of N.
class Slab
{
  public:
    uint64_t *w0 = nullptr, *w1 = nullptr, *w2 = nullptr;

    Slab() {}
    Slab(const Slab &) = delete;
    Slab &operator=(const Slab &) = delete;
    ~Slab() { free(mem_); }
    void alloc(size_t lanes)
    {
        free(mem_);
        const size_t stride = (lanes * sizeof(uint64_t) + 63) & ~size_t(63);
        mem_ = aligned_alloc(64, stride ? 3 * stride : 64);
        if (!mem_) abort();
        memset(mem_, 0, stride ? 3 * stride : 64);
        w0 = reinterpret_cast<uint64_t *>(mem_);
        w1 = reinterpret_cast<uint64_t *>(reinterpret_cast<char *>(mem_) + stride);
        w2 = reinterpret_cast<uint64_t *>(reinterpret_cast<char *>(mem_) + 2 * stride);
    }
    F131 get(size_t i) const { return F131{{w0[i], w1[i], w2[i]}}; }
    void set(size_t i, const F131 &a)
    {
        w0[i] = a.w[0];
        w1[i] = a.w[1];
        w2[i] = a.w[2];
    }

  private:
    void *mem_ = nullptr;
};

struct Geometry {
    int workers = 0;                         // 0: one per core
    int batch = 0;                           // 0: CpuEngine::kDefaultBatch lanes per inversion
    int chunks = 0;                          // 0: two batches per worker
    int sliceSteps = 64;                     // steps of one batch handed to a worker at a time
    unsigned guardPeriod = ECC_GUARD_PERIOD; // --max-iters is evaluated once in this many steps
};

class CpuEngine
{
  public:
    static const int kLanes = ECC_F131_LANES; // lanes per vector register
    // Interleaved inversion chains: on the scalar path four, whose accumulators
    // the compiler keeps in registers; on the vector path a register of
    // accumulators per N lanes, ECC_F131_CHAIN_VECTORS of them.
    static const int kChains = kLanes > 1 ? kLanes *ECC_F131_CHAIN_VECTORS : 4;
    // Lanes per inversion when neither the options nor the geometry say.  The
    // vector path's lane step is short enough that the batch's fixed cost (the
    // inversion and the 3(K-1) scalar products that peel the K chains) shows:
    // 2048 lanes of state is about 270 KB, which sits in a core's L2, and on a
    // 4-vCPU Sapphire Rapids VM the client ran 117 M it/s at 512 and 126 M at
    // 2048 (uncontrolled host; the figures are exploratory).  The scalar path
    // keeps the 512 it was tuned at on an M4 Pro.
    static const int kDefaultBatch = kLanes > 1 ? 2048 : 512;

    CpuEngine(const HostTable &table, const Options &o, bool bench, Geometry g = Geometry())
        : consts_(table.deviceConsts()), dpWeight_(bench ? -1 : o.dpWeight), maxIters_(o.maxIters),
          runId_(o.runId), guardPeriod_(g.guardPeriod ? g.guardPeriod : 1u)
    {
        using namespace eccPacked131;
        const unsigned cores = std::thread::hardware_concurrency();
        workers_ =
            g.workers > 0 ? g.workers : (o.workers > 0 ? o.workers : (cores ? int(cores) : 1));
        batch_ = g.batch > 0 ? g.batch : (o.batch > 0 ? o.batch : kDefaultBatch);
        chunks_ = g.chunks > 0 ? g.chunks : (o.chunks > 0 ? o.chunks : 2 * workers_);
        sliceSteps_ = g.sliceSteps > 0 ? g.sliceSteps : 64;

        for (int i = 0; i < 128; ++i) {
            orbitX_[i] = toPolynomial131(toPacked(table.orbitP[i].x));
            orbitY_[i] = toPolynomial131(toPacked(table.orbitP[i].y));
        }
        targetX_ = toPolynomial131(toPacked(table.Q.x));
        targetY_ = toPolynomial131(toPacked(table.Q.y));
#if ECC_F131_LANES > 1
        select_.build(consts_.data());
#endif

        const size_t lanes = laneCount();
        x_.alloc(lanes);
        y_.alloc(lanes);
        w_.alloc(lanes);
        d_.alloc(lanes);
        hist_.assign(lanes, ECC_HIST_EMPTY);
        seed_.resize(lanes);
        start_.assign(lanes, 0);
        now_.assign(size_t(chunks_), 0);
        ready_.assign(size_t(chunks_), 0);
        busy_.reset(new std::atomic<bool>[size_t(chunks_)]);
        for (int c = 0; c < chunks_; ++c) busy_[c].store(false);
    }

    size_t laneCount() const { return size_t(chunks_) * size_t(batch_); }
    const char *name() const { return "cpu"; }
    std::string describe() const
    {
        char buf[200];
        snprintf(buf, sizeof(buf),
                 ",\"workers\":%d,\"batch\":%d,\"chunks\":%d,\"hostClmul\":%d,\"vectorLanes\":%d,"
                 "\"chains\":%d",
                 workers_, batch_, chunks_, ECC_HOST_CLMUL, kLanes, kChains);
        return buf;
    }
    int workers() const { return workers_; }
    int batch() const { return batch_; }
    int chunks() const { return chunks_; }

    // Advance every batch by `steps` steps in total (a batch another worker
    // holds is passed over for the next free one, so under contention the
    // steps are spread unevenly; their number is exact).
    void launch(int steps, std::vector<DpRecord> *out, LaunchCounts *counts)
    {
        const int rounds = (steps + sliceSteps_ - 1) / sliceSteps_;
        const long total = long(chunks_) * rounds;
        std::atomic<long> next(0);
        std::mutex mu;
        auto body = [&]() {
            Local local;
            for (;;) {
                const long s = next.fetch_add(1);
                if (s >= total) break;
                const int round = int(s / chunks_);
                const int len = int((long long)steps * (round + 1) / rounds -
                                    (long long)steps * round / rounds);
                int c = int(s % chunks_);
                while (busy_[c].exchange(true)) c = c + 1 == chunks_ ? 0 : c + 1;
                runSlice(c, len, &local);
                busy_[c].store(false);
            }
            std::lock_guard<std::mutex> lock(mu);
            out->insert(out->end(), local.reports.begin(), local.reports.end());
            counts->restarts += local.restarts;
            counts->exhausted = counts->exhausted || local.exhausted;
        };
        std::vector<std::thread> pool;
        for (int i = 1; i < workers_; ++i) pool.emplace_back(body);
        body();
        for (std::thread &t : pool) t.join();
        counts->iterations += (unsigned long long)laneCount() * (unsigned long long)steps;
    }

    // The start point of a seed, Q + the sigma^i(P) its PRF bits select, in
    // the polynomial basis: what packedkernels.cuh's init kernel computes.
    void startPoint(unsigned long long seed, P131 *xp, P131 *yp) const
    {
        using namespace eccPacked131;
        const unsigned long long c0 = eccPrf(seed, 0), c1 = eccPrf(seed, 1);
        P131 x = targetX_, y = targetY_;
        for (int i = 0; i < 128; ++i) {
            if ((((i < 64 ? c0 >> i : c1 >> (i - 64))) & 1) == 0) continue;
            const P131 d = add131(x, orbitX_[i]), e = add131(y, orbitY_[i]);
            const P131 lambda = mulPolynomial131(e, invPolynomial131(d));
            const P131 nx = add131(add131(squarePolynomial131(lambda), lambda), d);
            y = add131(add131(mulPolynomial131(lambda, add131(x, nx)), nx), y);
            x = nx;
        }
        *xp = x;
        *yp = y;
    }

    // A lane as a report would describe it now: for the tests.
    DpRecord laneRecord(size_t lane) const
    {
        using namespace eccPacked131;
        DpRecord rec;
        rec.seed = seed_[lane];
        rec.iters = now_[lane / size_t(batch_)] - start_[lane];
        memcpy(rec.x, f131::fromPolynomial(x_.get(lane)).w, sizeof(rec.x));
        memcpy(rec.y, f131::fromPolynomial(y_.get(lane)).w, sizeof(rec.y));
        return rec;
    }
    bool laneReady(size_t lane) const { return ready_[lane / size_t(batch_)] != 0; }

  private:
    struct Local {
        std::vector<DpRecord> reports;
        unsigned long long restarts = 0;
        bool exhausted = false;
        // The selection's intermediates for one batch: normal-basis x (limb by
        // limb), weight, phase, sign.
        Slab xn;
        std::vector<unsigned char> hw, k, eps;
        int batch = 0;
        void scratch(int b)
        {
            if (batch == b) return;
            batch = b;
            xn.alloc((size_t)b);
            hw.resize((size_t)b);
            k.resize((size_t)b);
            eps.resize((size_t)b);
        }
    };

    void seedLane(size_t lane, unsigned long long seed, unsigned long long now)
    {
        seed_[lane] = seed;
        start_[lane] = now;
        hist_[lane] = ECC_HIST_EMPTY;
        P131 xp, yp;
        startPoint(seed, &xp, &yp);
        x_.set(lane, f131::fromPacked(xp));
        y_.set(lane, f131::fromPacked(yp));
    }

    // The rare path of the forward pass: the lane is at a distinguished point
    // or has outrun --max-iters.  Report the former, then restart the lane from
    // its next seed until it stands on a point it may step from.
    void revive(size_t lane, unsigned long long now, bool guard, Local *local)
    {
        using namespace eccPacked131;
        for (;;) {
            const F131 xn = f131::fromPolynomial(x_.get(lane));
            const bool dp = f131::weight(xn) <= dpWeight_;
            if (!dp && !(guard && now - start_[lane] >= maxIters_)) return;
            if (dp) {
                DpRecord rec;
                rec.seed = seed_[lane];
                rec.iters = now - start_[lane];
                memcpy(rec.x, xn.w, sizeof(rec.x));
                memcpy(rec.y, f131::fromPolynomial(y_.get(lane)).w, sizeof(rec.y));
                local->reports.push_back(rec);
            } else {
                local->restarts++;
            }
            // The low 16 bits of a seed count the lane's restarts; past that
            // it would run into its neighbour's trails, and the run must end.
            if ((seed_[lane] & 0xFFFFull) == 0xFFFFull) {
                local->exhausted = true;
                return;
            }
            seedLane(lane, seed_[lane] + 1, now);
        }
    }

    // One batch's lanes, as the limb arrays of its state and scratch.
    struct Batch {
        uint64_t *X0, *X1, *X2, *Y0, *Y1, *Y2, *W0, *W1, *W2, *D0, *D1, *D2;
        uint64_t *XN0, *XN1, *XN2;
        F131 X(int i) const { return F131{{X0[i], X1[i], X2[i]}}; }
        F131 Y(int i) const { return F131{{Y0[i], Y1[i], Y2[i]}}; }
        F131 W(int i) const { return F131{{W0[i], W1[i], W2[i]}}; }
        F131 D(int i) const { return F131{{D0[i], D1[i], D2[i]}}; }
        F131 XN(int i) const { return F131{{XN0[i], XN1[i], XN2[i]}}; }
        void setX(int i, const F131 &a) const { X0[i] = a.w[0], X1[i] = a.w[1], X2[i] = a.w[2]; }
        void setY(int i, const F131 &a) const { Y0[i] = a.w[0], Y1[i] = a.w[1], Y2[i] = a.w[2]; }
        void setW(int i, const F131 &a) const { W0[i] = a.w[0], W1[i] = a.w[1], W2[i] = a.w[2]; }
        void setD(int i, const F131 &a) const { D0[i] = a.w[0], D1[i] = a.w[1], D2[i] = a.w[2]; }
        void setXN(int i, const F131 &a) const
        {
            XN0[i] = a.w[0], XN1[i] = a.w[1], XN2[i] = a.w[2];
        }
    };

    // Stage 1 of a step: the normal-basis x of every lane into XN and its
    // weight into HW, N lanes at a time; then, lane by lane, the test for the
    // rare lane that reports or is overdue, which is revived in place.
    void convertBatch(const Batch &b, int B, size_t base, unsigned long long now, bool guard,
                      const unsigned long long *S, unsigned char *HW, Local *local)
    {
        int i = 0;
#if ECC_F131_LANES > 1
        typedef f131x::F131x<kLanes> FX;
        for (; i + kLanes <= B; i += kLanes) {
            const FX xn = f131x::fromPolynomial<kLanes>(FX::load(b.X0 + i, b.X1 + i, b.X2 + i));
            xn.store(b.XN0 + i, b.XN1 + i, b.XN2 + i);
            f131x::storeBytes<kLanes>(f131x::popcnt<kLanes>(xn.w0) + f131x::popcnt<kLanes>(xn.w1) +
                                          f131x::popcnt<kLanes>(xn.w2),
                                      HW + i);
        }
#endif
        for (; i < B; ++i) {
            const F131 xn = f131::fromPolynomial(b.X(i));
            b.setXN(i, xn);
            HW[i] = (unsigned char)f131::weight(xn);
        }
        for (i = 0; i < B; ++i) {
            if (__builtin_expect(HW[i] <= dpWeight_ || (guard && now - S[i] >= maxIters_), 0)) {
                revive(base + i, now, guard, local);
                const F131 xn = f131::fromPolynomial(b.X(i));
                b.setXN(i, xn);
                HW[i] = (unsigned char)f131::weight(xn);
            }
        }
    }

    // Stages 2 to 4: the phase into KK and the sign into EPS of every lane,
    // from XN and the polynomial-basis y.  N lanes at a time on the bit planes
    // of L (f131x.h), lane by lane through f131.h's byte tables for the tail.
    void selectBatch(const Batch &b, int B, const unsigned char *HW, unsigned char *KK,
                     unsigned char *EPS) const
    {
        const uint32_t *tw = consts_.data();
        int i = 0;
#if ECC_F131_LANES > 1
        typedef f131x::F131x<kLanes> FX;
        // G vectors a call, interleaved (f131x.h), then one at a time.
        const int G = f131x::kSelectGroup;
        for (; i + G * kLanes <= B; i += G * kLanes) {
            FX xn[G], yp[G];
            typename FX::V hw[G], k[G], eps[G];
            for (int g = 0; g < G; ++g) {
                const int j = i + g * kLanes;
                xn[g] = FX::load(b.XN0 + j, b.XN1 + j, b.XN2 + j);
                yp[g] = FX::load(b.Y0 + j, b.Y1 + j, b.Y2 + j);
            }
            f131x::select<kLanes, G>(xn, yp, select_, hw, k, eps);
            for (int g = 0; g < G; ++g) {
                f131x::storeBytes<kLanes>(k[g], KK + i + g * kLanes);
                f131x::storeBytes<kLanes>(eps[g], EPS + i + g * kLanes);
            }
        }
        for (; i + kLanes <= B; i += kLanes) {
            typename FX::V hw, k, eps;
            f131x::select<kLanes>(FX::load(b.XN0 + i, b.XN1 + i, b.XN2 + i),
                                  FX::load(b.Y0 + i, b.Y1 + i, b.Y2 + i), select_, &hw, &k, &eps);
            f131x::storeBytes<kLanes>(k, KK + i);
            f131x::storeBytes<kLanes>(eps, EPS + i);
        }
#endif
        // Stage by stage over the tail as well: one lane's selection is a
        // dependency chain three times longer than its instruction count
        // warrants (f131.h), so each stage gets its own loop.
        for (int j = i; j < B; ++j) KK[j] = (unsigned char)f131::selectPhase(b.XN(j), HW[j], tw);
        for (int j = i; j < B; ++j)
            EPS[j] =
                (unsigned char)f131::coordinate(b.Y(j), f131::selectPivot(b.XN(j), KK[j], tw), tw);
    }

    // One inversion serves the K chains whose running products are prod[]:
    // invert the product of their products and peel each chain's inverse off,
    // 3(K - 1) products.
    static void invertChains(const F131 *prod, int K, F131 *inv)
    {
        using namespace eccPacked131;
        F131 upTo[kChains];
        upTo[0] = prod[0];
        for (int j = 1; j < K; ++j) upTo[j] = f131::mul(upTo[j - 1], prod[j]);
        F131 rest = f131::fromPacked(invPolynomial131(f131::toPacked(upTo[K - 1])));
        for (int j = K - 1; j > 0; --j) {
            inv[j] = f131::mul(rest, upTo[j - 1]);
            rest = f131::mul(rest, prod[j]);
        }
        inv[0] = rest;
    }

    // Stages 5 and 6: Montgomery's trick over the batch as kChains interleaved
    // chains (lane i in chain i mod K; W_i becomes e_i times the denominators
    // before it in its chain, so that no product waits on the lane before it),
    // one inversion, then lambda_i = e_i / d_i back down each chain and the
    // additions, which depend on nothing but their own lane.
    void chainsAndAdd(const Batch &b, int B)
    {
        if (B <= 0) return;
        const int K = B < kChains ? B : kChains;
        int i = 0;
#if ECC_F131_LANES > 1
        typedef f131x::F131x<kLanes> FX;
        const int V = ECC_F131_CHAIN_VECTORS;
        if (K == kChains) {
            // Chain c runs in lane c % N of vector c / N, and stays there: the
            // ragged end of the batch and the peel work on the lanes in place.
            FX pv[V];
            for (int v = 0; v < V; ++v)
                pv[v] = FX::load(b.D0 + v * kLanes, b.D1 + v * kLanes, b.D2 + v * kLanes);
            for (i = kChains; i + kChains <= B; i += kChains) {
                for (int v = 0; v < V; ++v) {
                    const int j = i + v * kLanes;
                    const FX w = FX::load(b.W0 + j, b.W1 + j, b.W2 + j),
                             d = FX::load(b.D0 + j, b.D1 + j, b.D2 + j);
                    f131x::mul<kLanes>(pv[v], w).store(b.W0 + j, b.W1 + j, b.W2 + j);
                    pv[v] = f131x::mul<kLanes>(pv[v], d);
                }
            }
            const int tail = i; // lanes from here on are the ragged end of the batch
            for (; i < B; ++i) {
                FX &p = pv[(i - tail) / kLanes];
                const int l = (i - tail) % kLanes;
                const F131 q = p.lane(l);
                b.setW(i, f131::mul(q, b.W(i)));
                p.setLane(l, f131::mul(q, b.D(i)));
            }
            // One inversion serves the K chains, by Montgomery's trick twice
            // more: across the V vectors, N chains at a time, then across the
            // N lanes of the last vector in f131.h.  Chain by chain the peel
            // would be 2(K - 1) scalar products, most of them one dependency
            // chain (254 at the default geometry, 15 ns each here: an eighth
            // of the step); this way it is 2(V - 1) vector products and
            // 2(N - 1) scalar ones.
            FX up[V];
            up[0] = pv[0];
            for (int v = 1; v < V; ++v) up[v] = f131x::mul<kLanes>(up[v - 1], pv[v]);
            F131 lp[kLanes], li[kLanes];
            for (int l = 0; l < kLanes; ++l) lp[l] = up[V - 1].lane(l);
            invertChains(lp, kLanes, li);
            FX iv[V], rest;
            for (int l = 0; l < kLanes; ++l) rest.setLane(l, li[l]);
            for (int v = V - 1; v > 0; --v) {
                iv[v] = f131x::mul<kLanes>(rest, up[v - 1]);
                rest = f131x::mul<kLanes>(rest, pv[v]);
            }
            iv[0] = rest;
            // Back down each chain, lambda_i = e_i / d_i into W.
            for (i = B - 1; i >= tail; --i) {
                FX &q = iv[(i - tail) / kLanes];
                const int l = (i - tail) % kLanes;
                const F131 r = q.lane(l);
                b.setW(i, f131::mul(r, b.W(i)));
                q.setLane(l, f131::mul(r, b.D(i)));
            }
            for (i = tail - kChains; i >= kChains; i -= kChains) {
                for (int v = 0; v < V; ++v) {
                    const int j = i + v * kLanes;
                    const FX w = FX::load(b.W0 + j, b.W1 + j, b.W2 + j),
                             d = FX::load(b.D0 + j, b.D1 + j, b.D2 + j);
                    f131x::mul<kLanes>(iv[v], w).store(b.W0 + j, b.W1 + j, b.W2 + j);
                    iv[v] = f131x::mul<kLanes>(iv[v], d);
                }
            }
            for (int v = 0; v < V; ++v) {
                const int j = v * kLanes;
                f131x::mul<kLanes>(iv[v], FX::load(b.W0 + j, b.W1 + j, b.W2 + j))
                    .store(b.W0 + j, b.W1 + j, b.W2 + j);
            }
        } else
#endif
        {
            F131 prod[kChains];
            for (i = 0; i < K; ++i) prod[i] = b.D(i);
#if ECC_F131_LANES == 1
            if (K == kChains) {
                // The running products as four locals: through prod[i % K]
                // each chain would pay a store and a load per lane on its
                // critical path, 4.5 ns an iteration here.
                F131 p0 = prod[0], p1 = prod[1], p2 = prod[2], p3 = prod[3];
                for (; i + kChains <= B; i += kChains) {
                    b.setW(i, f131::mul(p0, b.W(i)));
                    p0 = f131::mul(p0, b.D(i));
                    b.setW(i + 1, f131::mul(p1, b.W(i + 1)));
                    p1 = f131::mul(p1, b.D(i + 1));
                    b.setW(i + 2, f131::mul(p2, b.W(i + 2)));
                    p2 = f131::mul(p2, b.D(i + 2));
                    b.setW(i + 3, f131::mul(p3, b.W(i + 3)));
                    p3 = f131::mul(p3, b.D(i + 3));
                }
                prod[0] = p0, prod[1] = p1, prod[2] = p2, prod[3] = p3;
            }
#endif
            const int tail = i; // lanes from here on are the ragged end of the batch
            for (; i < B; ++i) {
                const F131 p = prod[i % K];
                b.setW(i, f131::mul(p, b.W(i)));
                prod[i % K] = f131::mul(p, b.D(i));
            }
            F131 inv[kChains];
            invertChains(prod, K, inv);
            // Back down each chain, lambda_i = e_i / d_i into W.
            for (i = B - 1; i >= tail; --i) {
                const F131 v = inv[i % K];
                b.setW(i, f131::mul(v, b.W(i)));
                inv[i % K] = f131::mul(v, b.D(i));
            }
#if ECC_F131_LANES == 1
            if (K == kChains) {
                F131 v0 = inv[0], v1 = inv[1], v2 = inv[2], v3 = inv[3];
                for (i = tail - kChains; i >= K; i -= kChains) {
                    b.setW(i + 3, f131::mul(v3, b.W(i + 3)));
                    v3 = f131::mul(v3, b.D(i + 3));
                    b.setW(i + 2, f131::mul(v2, b.W(i + 2)));
                    v2 = f131::mul(v2, b.D(i + 2));
                    b.setW(i + 1, f131::mul(v1, b.W(i + 1)));
                    v1 = f131::mul(v1, b.D(i + 1));
                    b.setW(i, f131::mul(v0, b.W(i)));
                    v0 = f131::mul(v0, b.D(i));
                }
                inv[0] = v0, inv[1] = v1, inv[2] = v2, inv[3] = v3;
            }
#endif
            for (i = 0; i < K; ++i) b.setW(i, f131::mul(inv[i], b.W(i)));
        }
        // The additions: x' = lambda^2 + lambda + d, y' = lambda (x + x') + x' + y.
        i = 0;
#if ECC_F131_LANES > 1
        for (; i + kLanes <= B; i += kLanes) {
            const FX lambda = FX::load(b.W0 + i, b.W1 + i, b.W2 + i),
                     d = FX::load(b.D0 + i, b.D1 + i, b.D2 + i),
                     x = FX::load(b.X0 + i, b.X1 + i, b.X2 + i),
                     y = FX::load(b.Y0 + i, b.Y1 + i, b.Y2 + i);
            const FX nx =
                f131x::add<kLanes>(f131x::add<kLanes>(f131x::sqr<kLanes>(lambda), lambda), d);
            const FX ny = f131x::add<kLanes>(
                f131x::add<kLanes>(f131x::mul<kLanes>(lambda, f131x::add<kLanes>(x, nx)), nx), y);
            nx.store(b.X0 + i, b.X1 + i, b.X2 + i);
            ny.store(b.Y0 + i, b.Y1 + i, b.Y2 + i);
        }
#endif
        for (; i < B; ++i) {
            const F131 lambda = b.W(i), d = b.D(i), x = b.X(i);
            const F131 nx = f131::add(f131::add(f131::sqr(lambda), lambda), d);
            b.setY(i, f131::add(f131::add(f131::mul(lambda, f131::add(x, nx)), nx), b.Y(i)));
            b.setX(i, nx);
        }
    }

    void runSlice(int c, int steps, Local *local)
    {
        using namespace eccPacked131;
        const size_t base = size_t(c) * size_t(batch_);
        const int B = batch_;
        unsigned long long *__restrict H = &hist_[base];
        const unsigned long long *S = &start_[base];
        const uint32_t *tw = consts_.data();
        unsigned long long now = now_[size_t(c)];
        if (!ready_[size_t(c)]) {
            for (int i = 0; i < B; ++i) seedLane(base + i, eccSeedFor(runId_, base + i), now);
            ready_[size_t(c)] = 1;
        }
        local->scratch(B);
        const Batch b = {x_.w0 + base, x_.w1 + base, x_.w2 + base, y_.w0 + base, y_.w1 + base,
                         y_.w2 + base, w_.w0 + base, w_.w1 + base, w_.w2 + base, d_.w0 + base,
                         d_.w1 + base, d_.w2 + base, local->xn.w0, local->xn.w1, local->xn.w2};
        unsigned char *__restrict HW = local->hw.data(), *__restrict KK = local->k.data(),
                                  *__restrict EPS = local->eps.data();
        for (int s = 0; s < steps && !local->exhausted; ++s, ++now) {
            const bool guard = maxIters_ && now % guardPeriod_ == 0;
            // The selection: the normal-basis x, its weight and the rare lane
            // that reports or is overdue; then the phase and the sign.
            convertBatch(b, B, base, now, guard, S, HW, local);
            selectBatch(b, B, HW, KK, EPS);
            // The tag, with the cycle rule and the history, and with it the
            // addend: d = x + x_T into D, e = y + y_T into W.
            for (int i = 0; i < B; ++i) {
                const unsigned tag = f131::tagOf(HW[i], KK[i], EPS[i], &H[i]);
                F131 d, e;
                f131::addend(tag, b.X(i), b.Y(i), tw, &d, &e);
                b.setD(i, d);
                b.setW(i, e);
            }
            chainsAndAdd(b, B);
        }
        now_[size_t(c)] = now;
    }

    const std::vector<uint32_t> consts_;
#if ECC_F131_LANES > 1
    f131x::SelectConsts select_;
#endif
    const int dpWeight_;
    const unsigned long long maxIters_;
    const unsigned runId_;
    const unsigned guardPeriod_;
    int workers_, batch_, chunks_, sliceSteps_;
    P131 orbitX_[128], orbitY_[128], targetX_, targetY_;
    Slab x_, y_, w_, d_;
    std::vector<unsigned long long> hist_, seed_, start_, now_;
    std::vector<char> ready_;
    std::unique_ptr<std::atomic<bool>[]> busy_;
};

} // namespace ec2k_cpu
