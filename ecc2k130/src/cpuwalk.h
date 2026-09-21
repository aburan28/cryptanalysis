// cpuwalk.h - the packed table walk on the host's cores.
//
// The same walk as include/packedkernels.cuh, written for a CPU: the field
// routines, the selection (twSelect, twAddend) and the seed schedule are the
// device's own headers compiled as host code, so what differs is only what a
// CPU wants differently.
//
//   - A batch is `batch` lanes sharing one inversion by Montgomery's trick,
//     512 by default against the device's 16: a core has no register budget to
//     respect, the inversion is about 600 ns against 127 ns for a lane's step,
//     and 512 lanes of state (x, y, prefix product, denominator, history: 88
//     bytes each) sit in L1 beside the selection tables.
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
// src/cputest.cpp holds this engine to the golden model: start points, every
// lane's state after a run against a re-walk from its seed, every report, and
// the independence of the reports from the geometry.
#pragma once

#include "client.h"

#include <atomic>
#include <memory>
#include <mutex>
#include <thread>

namespace ec2k_cpu
{

using namespace ec2k_client;
using eccPacked131::P131;

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

struct Geometry {
    int workers = 0;                         // 0: one per core
    int batch = 0;                           // 0: 512 lanes per inversion
    int chunks = 0;                          // 0: two batches per worker
    int sliceSteps = 64;                     // steps of one batch handed to a worker at a time
    unsigned guardPeriod = ECC_GUARD_PERIOD; // --max-iters is evaluated once in this many steps
};

class CpuEngine
{
  public:
    CpuEngine(const HostTable &table, const Options &o, bool bench, Geometry g = Geometry())
        : consts_(table.deviceConsts()), dpWeight_(bench ? -1 : o.dpWeight), maxIters_(o.maxIters),
          runId_(o.runId), guardPeriod_(g.guardPeriod ? g.guardPeriod : 1u)
    {
        using namespace eccPacked131;
        const unsigned cores = std::thread::hardware_concurrency();
        workers_ =
            g.workers > 0 ? g.workers : (o.workers > 0 ? o.workers : (cores ? int(cores) : 1));
        batch_ = g.batch > 0 ? g.batch : (o.batch > 0 ? o.batch : 512);
        chunks_ = g.chunks > 0 ? g.chunks : (o.chunks > 0 ? o.chunks : 2 * workers_);
        sliceSteps_ = g.sliceSteps > 0 ? g.sliceSteps : 64;

        for (int i = 0; i < 128; ++i) {
            orbitX_[i] = toPolynomial131(toPacked(table.orbitP[i].x));
            orbitY_[i] = toPolynomial131(toPacked(table.orbitP[i].y));
        }
        targetX_ = toPolynomial131(toPacked(table.Q.x));
        targetY_ = toPolynomial131(toPacked(table.Q.y));

        const size_t lanes = laneCount();
        x_.resize(lanes);
        y_.resize(lanes);
        w_.resize(lanes);
        d_.resize(lanes);
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
        char buf[160];
        snprintf(buf, sizeof(buf), ",\"workers\":%d,\"batch\":%d,\"chunks\":%d,\"hostClmul\":%d",
                 workers_, batch_, chunks_, ECC_HOST_CLMUL);
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
        toLimbs(fromPacked(fromPolynomial131(x_[lane])), rec.x);
        toLimbs(fromPacked(fromPolynomial131(y_[lane])), rec.y);
        return rec;
    }
    bool laneReady(size_t lane) const { return ready_[lane / size_t(batch_)] != 0; }

  private:
    static const int kChains = 4;
    struct Local {
        std::vector<DpRecord> reports;
        unsigned long long restarts = 0;
        bool exhausted = false;
    };

    void seedLane(size_t lane, unsigned long long seed, unsigned long long now)
    {
        seed_[lane] = seed;
        start_[lane] = now;
        hist_[lane] = ECC_HIST_EMPTY;
        startPoint(seed, &x_[lane], &y_[lane]);
    }

    // The rare path of the forward pass: the lane is at a distinguished point
    // or has outrun --max-iters.  Report the former, then restart the lane from
    // its next seed until it stands on a point it may step from.
    void revive(size_t lane, unsigned long long now, bool guard, Local *local)
    {
        using namespace eccPacked131;
        for (;;) {
            const P131 xn = fromPolynomial131(x_[lane]);
            const bool dp = weight131(xn) <= dpWeight_;
            if (!dp && !(guard && now - start_[lane] >= maxIters_)) return;
            if (dp) {
                DpRecord rec;
                rec.seed = seed_[lane];
                rec.iters = now - start_[lane];
                toLimbs(fromPacked(xn), rec.x);
                toLimbs(fromPacked(fromPolynomial131(y_[lane])), rec.y);
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

    void runSlice(int c, int steps, Local *local)
    {
        using namespace eccPacked131;
        const size_t base = size_t(c) * size_t(batch_);
        const int B = batch_;
        P131 *__restrict X = &x_[base], *__restrict Y = &y_[base], *__restrict W = &w_[base],
                         *__restrict D = &d_[base];
        unsigned long long *__restrict H = &hist_[base];
        const unsigned long long *S = &start_[base];
        const uint32_t *tw = consts_.data();
        unsigned long long now = now_[size_t(c)];
        if (!ready_[size_t(c)]) {
            for (int i = 0; i < B; ++i) seedLane(base + i, eccSeedFor(runId_, base + i), now);
            ready_[size_t(c)] = 1;
        }
        const int K = B < kChains ? B : kChains;
        for (int s = 0; s < steps && !local->exhausted; ++s, ++now) {
            const bool guard = maxIters_ && now % guardPeriod_ == 0;
            // Selection: each lane's addend, d = x + x_T into D and e = y + y_T
            // into W.
            for (int i = 0; i < B; ++i) {
                P131 xn = fromPolynomial131(X[i]);
                int hw = weight131(xn);
                if (__builtin_expect(hw <= dpWeight_ || (guard && now - S[i] >= maxIters_), 0)) {
                    revive(base + i, now, guard, local);
                    xn = fromPolynomial131(X[i]);
                    hw = weight131(xn);
                }
                const unsigned tag = twSelect(xn, Y[i], hw, &H[i], tw);
                twAddend(tag, X[i], Y[i], tw, &D[i], &W[i]);
            }
            // Montgomery's trick, as K interleaved chains: lane i belongs to
            // chain i mod K, and W_i becomes e_i times the denominators before
            // it in its chain, so that no product waits on the lane before it.
            // (Measured on an M4 Pro this is neutral -- the products are bound
            // by instruction count, not by the chain -- and it costs 3(K - 1)
            // products a step; it is what lets a wider core or a leaner product
            // overlap lanes.)
            P131 prod[kChains];
            for (int i = 0; i < K; ++i) prod[i] = D[i];
            for (int i = K; i < B; ++i) {
                const PolynomialPair pair = mulPolynomialPair131(prod[i % K], W[i], D[i]);
                W[i] = pair.first;
                prod[i % K] = pair.second;
            }
            // One inversion serves the K chains: invert the product of their
            // products and peel each chain's inverse off, 3(K - 1) products.
            P131 inv[kChains], upTo[kChains];
            upTo[0] = prod[0];
            for (int j = 1; j < K; ++j) upTo[j] = mulPolynomial131(upTo[j - 1], prod[j]);
            P131 rest = invPolynomial131(upTo[K - 1]);
            for (int j = K - 1; j > 0; --j) {
                inv[j] = mulPolynomial131(rest, upTo[j - 1]);
                rest = mulPolynomial131(rest, prod[j]);
            }
            inv[0] = rest;
            // Back down each chain: lambda_i = e_i / d_i, then the addition.
            for (int i = B - 1; i >= 0; --i) {
                const P131 x = X[i], y = Y[i], d = D[i];
                P131 lambda;
                if (i >= K) {
                    const PolynomialPair pair = mulPolynomialPair131(inv[i % K], d, W[i]);
                    inv[i % K] = pair.first;
                    lambda = pair.second;
                } else {
                    lambda = mulPolynomial131(inv[i], W[i]);
                }
                const P131 nx = add131(add131(squarePolynomial131(lambda), lambda), d);
                const P131 ny = add131(add131(mulPolynomial131(lambda, add131(x, nx)), nx), y);
                X[i] = nx;
                Y[i] = ny;
            }
        }
        now_[size_t(c)] = now;
    }

    const std::vector<uint32_t> consts_;
    const int dpWeight_;
    const unsigned long long maxIters_;
    const unsigned runId_;
    const unsigned guardPeriod_;
    int workers_, batch_, chunks_, sliceSteps_;
    P131 orbitX_[128], orbitY_[128], targetX_, targetY_;
    std::vector<P131> x_, y_, w_, d_;
    std::vector<unsigned long long> hist_, seed_, start_, now_;
    std::vector<char> ready_;
    std::unique_ptr<std::atomic<bool>[]> busy_;
};

} // namespace ec2k_cpu
