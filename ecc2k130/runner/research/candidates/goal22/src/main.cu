// ECC2K-130 client: Pollard rho with the Frobenius-based iteration function,
// bitsliced over the permuted type-II optimal normal basis.
//
// Build as CUDA (nvcc/clang) or as plain C++ with -DECC_NO_CUDA; the walk code
// is identical in both cases, only the word width differs (32 bits on the
// device, 64 on the host).
#include <signal.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>

#include <algorithm>
#include <string>
#include <vector>

#include "../include/curveparams.h"
#include "../include/kernel.h"
#include "../include/solver.h"
#include "../include/durable.h"

#ifndef ECC_NO_CUDA
#include <cuda_runtime.h>
#define CUDA_CHECK(x)                                                                   \
    do {                                                                                \
        cudaError_t e_ = (x);                                                           \
        if (e_ != cudaSuccess) {                                                        \
            fprintf(stderr, "CUDA error at %s:%d: %s\n", __FILE__, __LINE__,            \
                    cudaGetErrorString(e_));                                            \
            exit(2);                                                                    \
        }                                                                               \
    } while (0)
typedef unsigned int DeviceWord;
#endif

#ifdef _OPENMP
#include <omp.h>
#endif



// Set by SIGINT/SIGTERM so a run stopped by its deadline still checkpoints.
// Without it every timed run throws away the walks in flight, which for this
// workload is about a quarter of the whole computation.
static volatile sig_atomic_t gStop = 0;
static void onStop(int) { gStop = 1; }

// A corpus record: the seed that produced the point, and the canonical
// representative of its orbit, which is the collision key.  Fixed 32 bytes so
// the file can be appended to, reloaded and merged without parsing.
struct DpFileRecord {
    unsigned long long seed;
    unsigned long long canon[3];
};
static_assert(sizeof(DpFileRecord) == 32, "corpus records must remain 32 bytes");

static double nowSeconds() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

struct Options {
    int curve = 131;
    int threads = 0;
    int blocks = 0;
    int steps = 64;
    int dpWeight = -1;
    long launches = 0;
    int instance = -1;
    unsigned runId = 1;
    u64 maxIters = 0;
    bool bench = false;
    bool packed = false;
    bool preferL1 = false;
    bool test = false;
    bool polyBasis = false;
    bool selfCheck = false;
    bool refEngine = false;
    unsigned dpCap = 1u << 16;
    int device = 0;
    int verify = 8;
    std::string dpFile;
    std::vector<std::string> loadFiles;
    unsigned long long loadMax = 0;
    std::string ckptFile;
    double ckptSeconds = 300.0;
};


// Checkpoint layout: a header naming the configuration the state belongs to,
// then the walk arrays (packed coordinates use normal basis on disk).
// A checkpoint is only loadable back into the same
// curve, thread count, batch and lane width, so a resumed run continues exactly
// the walks it left off rather than silently starting new ones.
struct CkptHeader {
    char magic[8];
    unsigned version;
    unsigned m;
    unsigned threads;
    unsigned batch;
    unsigned lanes;
    unsigned runId;
    unsigned long long iterBase;
};

static bool ckptHeaderMatches(const CkptHeader &h, int m, int threads, int batch, int lanes,
                              unsigned runId, unsigned version = 1u) {
    return memcmp(h.magic, "ECC2K130", 8) == 0 && h.version == version && h.m == (unsigned)m &&
           h.threads == (unsigned)threads && h.batch == (unsigned)batch &&
           h.lanes == (unsigned)lanes && h.runId == runId;
}

// Refuse a checkpoint whose payload is not exactly the size this configuration
// writes, and leave the file positioned after the header if it is.  A file cut
// short by a container that died mid-write has a perfectly good header, and
// reading it would leave half the walks restored and half still at their start
// points -- a state no run ever occupied. Such checkpoints must be rejected.
static bool ckptPayloadIsWhole(FILE *f, size_t payload) {
    if (fseek(f, 0, SEEK_END) != 0) return false;
    const long total = ftell(f);
    if (total < 0 || (unsigned long)total != sizeof(CkptHeader) + payload) return false;
    return fseek(f, (long)sizeof(CkptHeader), SEEK_SET) == 0;
}

// ---------------------------------------------------------------------------
// host backend
// ---------------------------------------------------------------------------
template <class Cfg>
struct HostEngine {
    typedef ECC_HOST_WORD W;
    typedef Kernel<Cfg, W> K;
    static const int M = Cfg::M;
    static const int LANES = WordTraits<W>::LANES;
    static const int BATCH = ECC_BATCH;

    std::vector<W> x, y, pchain, dead;
    std::vector<u64> seed, startIter;

    // Present so runCurve can size either backend the same way; on the host the
    // count is one walk thread per core and main has already worked it out.
    static int autoThreads(int) {
#ifdef _OPENMP
        return omp_get_max_threads();
#else
        return 1;
#endif
    }
    std::vector<DpRecord> dp;
    unsigned dpCount[3] = {0, 0, 0};
    bool restartPending = false;
    WalkParams<W> P;
    std::vector<u64> px, py, qx, qy;

    void setup(const Options &o, const unsigned long long *cpx, const unsigned long long *cpy,
               const unsigned long long *cqx, const unsigned long long *cqy) {
        const size_t T = (size_t)o.threads;
        x.assign(T * BATCH * M, 0);
        y.assign(T * BATCH * M, 0);
        pchain.assign(T * BATCH * M, 0);
        dead.assign(T * BATCH, 0);
        seed.assign(T * BATCH * LANES, 0);
        startIter.assign(T * BATCH * LANES, 0);
        dp.assign(o.dpCap, DpRecord());
        px.assign(cpx, cpx + 3);
        py.assign(cpy, cpy + 3);
        qx.assign(cqx, cqx + 3);
        qy.assign(cqy, cqy + 3);
        P.threads = o.threads;
        P.steps = o.steps;
        P.dpWeight = o.dpWeight;
        P.runId = o.runId;
        P.maxIters = o.maxIters;
        P.iterBase = 0;
        P.x = x.data();
        P.y = y.data();
        P.pchain = pchain.data();
        P.seed = seed.data();
        P.startIter = startIter.data();
        P.dead = dead.data();
        P.dp = dp.data();
        P.dpCount = dpCount;
        P.dpCap = o.dpCap;
        P.consts.px = px.data();
        P.consts.py = py.data();
        P.consts.qx = qx.data();
        P.consts.qy = qy.data();
        const WalkParams<W> pp = P;
#ifdef _OPENMP
#pragma omp parallel for schedule(static)
#endif
        for (int t = 0; t < o.threads; ++t) K::init(t, pp);
    }

    void launch(u64 iterBase) {
        P.iterBase = iterBase;
        const WalkParams<W> pp = P;
#ifdef _OPENMP
#pragma omp parallel for schedule(static)
#endif
        for (int t = 0; t < pp.threads; ++t) K::run(t, pp);
    }

    // revive the lanes that reported during the last launch
    void reseed(u64 iterBase) {
        P.iterBase = iterBase;
        const WalkParams<W> pp = P;
#ifdef _OPENMP
#pragma omp parallel for schedule(static)
#endif
        for (int t = 0; t < pp.threads; ++t) K::reseed(t, pp);
    }

    void synchronize() const {}

    unsigned fetch(std::vector<DpRecord> &out) {
        const unsigned n = dpCount[0];
        const bool exhausted = dpCount[2] != 0;
        restartPending = dpCount[1] != 0;
        const unsigned m = n < P.dpCap ? n : P.dpCap;
        out.assign(dp.begin(), dp.begin() + m);
        dpCount[0] = dpCount[1] = dpCount[2] = 0;
        return exhausted ? ECC_SEED_EXHAUSTED : n;
    }

    bool save(const char *path, u64 iterBase, unsigned runId) const {
        const std::string tmp = std::string(path) + ".tmp";
        FILE *f = fopen(tmp.c_str(), "wb");
        if (!f) return false;
        CkptHeader h;
        memcpy(h.magic, "ECC2K130", 8);
        h.version = 1u;
        h.m = (unsigned)M;
        h.threads = (unsigned)P.threads;
        h.batch = (unsigned)BATCH;
        h.lanes = (unsigned)LANES;
        h.runId = runId;
        h.iterBase = iterBase;
        bool ok = fwrite(&h, sizeof h, 1, f) == 1;
        ok = ok && fwrite(x.data(), sizeof(W), x.size(), f) == x.size();
        ok = ok && fwrite(y.data(), sizeof(W), y.size(), f) == y.size();
        ok = ok && fwrite(dead.data(), sizeof(W), dead.size(), f) == dead.size();
        ok = ok && fwrite(seed.data(), sizeof(u64), seed.size(), f) == seed.size();
        ok = ok && fwrite(startIter.data(), sizeof(u64), startIter.size(), f) == startIter.size();
        ok = ok && durableFlush(f);
        if (fclose(f) != 0) ok = false;
        if (!ok) { remove(tmp.c_str()); return false; }
        // rename last so a checkpoint is either the old one or the new one,
        // never a half-written file
        return rename(tmp.c_str(), path) == 0 && syncParent(path);
    }

    bool restore(const char *path, u64 *iterBase, unsigned runId) {
        FILE *f = fopen(path, "rb");
        if (!f) return false;
        CkptHeader h;
        const size_t payload = (x.size() + y.size() + dead.size()) * sizeof(W) +
                               (seed.size() + startIter.size()) * sizeof(u64);
        bool ok = fread(&h, sizeof h, 1, f) == 1 &&
                  ckptHeaderMatches(h, M, P.threads, BATCH, LANES, runId) &&
                  ckptPayloadIsWhole(f, payload);
        ok = ok && fread(x.data(), sizeof(W), x.size(), f) == x.size();
        ok = ok && fread(y.data(), sizeof(W), y.size(), f) == y.size();
        ok = ok && fread(dead.data(), sizeof(W), dead.size(), f) == dead.size();
        ok = ok && fread(seed.data(), sizeof(u64), seed.size(), f) == seed.size();
        ok = ok && fread(startIter.data(), sizeof(u64), startIter.size(), f) == startIter.size();
        fclose(f);
        if (ok) *iterBase = h.iterBase;
        return ok;
    }

    const char *name() const { return "cpu"; }
    bool needsReseed() const { return restartPending; }
    u64 walksPerLaunch() const { return (u64)P.threads * BATCH * LANES; }
};

// ---------------------------------------------------------------------------
// reference backend
// ---------------------------------------------------------------------------
// A scalar engine on the reference arithmetic, walking with whichever
// iteration the build selects.  It exists to run the whole pipeline -- seeds,
// distinguished points, collision, resolution -- on the toy curves with a
// handful of walks, where the planted logarithm says whether the walk and its
// resolver agree and the iteration count can be compared between walks on
// identical seeds.  Under ECC_WALK_TABLE it is the only non-packed engine, the
// bitsliced kernels implementing sigma^j + 1 only; otherwise --ref selects it.
// It is slow; it checkpoints so that the campaign's certification suite can
// exercise resume on it.
template <class Cfg>
struct RefEngine {
    typedef Ref<Cfg> R;
    typedef typename R::Point Point;
    static const int M = Cfg::M;
    static const int BATCH = ECC_BATCH;
    struct Lane { Point p; u64 seed, startIter, hist; unsigned dead; };

    std::vector<Lane> lanes;
    std::vector<DpRecord> dp;
    unsigned dpCount[3] = {0, 0, 0};
    bool restartPending = false;
    const Solver<Cfg> *sol = nullptr;
    int threads = 0, steps = 0, dpWeight = 0;
    unsigned runId = 0, dpCap = 0;
    u64 maxIters = 0;

    static int autoThreads(int) {
#ifdef _OPENMP
        return omp_get_max_threads();
#else
        return 1;
#endif
    }
    void start(size_t id, u64 seed, u64 iterBase) {
        Lane &l = lanes[id];
        l.seed = seed;
        l.p = R::startPoint(seed, sol->basis, sol->target, 0, sol->ell, sol->spow);
        l.startIter = iterBase;
        l.hist = ECC_HIST_EMPTY;
        l.dead = 0;
    }
    void setup(const Options &o, const unsigned long long *, const unsigned long long *,
               const unsigned long long *, const unsigned long long *) {
        threads = o.threads; steps = o.steps; dpWeight = o.dpWeight; runId = o.runId;
        maxIters = o.maxIters; dpCap = o.dpCap;
        lanes.resize(size_t(threads) * BATCH);
        dp.assign(o.dpCap, DpRecord());
#ifdef _OPENMP
#pragma omp parallel for schedule(static)
#endif
        for (long id = 0; id < (long)lanes.size(); ++id) start(id, eccSeedFor(runId, id), 0);
    }
    void launch(u64 iterBase) {
#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic, 16)
#endif
        for (long id = 0; id < (long)lanes.size(); ++id) {
            Lane &l = lanes[id];
            for (int step = 0; step < steps && !l.dead; ++step) {
                const u64 now = iterBase + step;
                const int hw = R::weight(l.p.x);
                if (hw <= dpWeight) {
                    if ((l.seed & 0xffffull) == 0xffffull) eccAtomicInc(dpCount + 2);
                    const unsigned dest = eccAtomicInc(dpCount);
                    if (dest < dpCap) {
                        DpRecord rec;
                        rec.seed = l.seed;
                        rec.iters = now - l.startIter;
                        for (int i = 0; i < 3; ++i) { rec.x[i] = l.p.x.v[i]; rec.y[i] = l.p.y.v[i]; }
                        dp[dest] = rec;
                    }
                    l.dead = 1;
                    break;
                }
                if (maxIters && now % ECC_GUARD_PERIOD == 0 && now - l.startIter >= maxIters) {
                    if ((l.seed & 0xffffull) == 0xffffull) eccAtomicInc(dpCount + 2);
                    l.dead = 1;
                    eccAtomicInc(dpCount + 1);
                    break;
                }
#if ECC_WALK_TABLE
                l.p = sol->walk.step(l.p, hw, &l.hist, 0, 0, sol->ell, sol->spow);
#else
                l.p = R::step(l.p, hw);
#endif
            }
        }
    }
    void reseed(u64 iterBase) {
#ifdef _OPENMP
#pragma omp parallel for schedule(static)
#endif
        for (long id = 0; id < (long)lanes.size(); ++id)
            if (lanes[id].dead) start(id, lanes[id].seed + 1, iterBase);
        restartPending = false;
    }
    void synchronize() const {}
    unsigned fetch(std::vector<DpRecord> &out) {
        const unsigned n = dpCount[0];
        const bool exhausted = dpCount[2] != 0;
        restartPending = dpCount[1] != 0;
        const unsigned m = n < dpCap ? n : dpCap;
        out.assign(dp.begin(), dp.begin() + m);
        dpCount[0] = dpCount[1] = dpCount[2] = 0;
        return exhausted ? ECC_SEED_EXHAUSTED : n;
    }
    // One fixed-width record per lane: both coordinates as three words each,
    // the seed, the start iteration, the cycle history and the dead flag.  The
    // header's lane width is 1 and its version 2, so a bitsliced checkpoint of
    // the same curve and thread count is refused rather than misread.
    static const size_t LANE_WORDS = 3 + 3 + 1 + 1 + 1 + 1;
    static const unsigned CKPT_VERSION = 2u;
    void pack(std::vector<u64> &buf) const {
        buf.resize(lanes.size() * LANE_WORDS);
        for (size_t id = 0; id < lanes.size(); ++id) {
            const Lane &l = lanes[id];
            u64 *w = &buf[id * LANE_WORDS];
            for (int i = 0; i < 3; ++i) { w[i] = l.p.x.v[i]; w[3 + i] = l.p.y.v[i]; }
            w[6] = l.seed; w[7] = l.startIter; w[8] = l.hist; w[9] = l.dead;
        }
    }
    void unpack(const std::vector<u64> &buf) {
        for (size_t id = 0; id < lanes.size(); ++id) {
            Lane &l = lanes[id];
            const u64 *w = &buf[id * LANE_WORDS];
            for (int i = 0; i < 3; ++i) { l.p.x.v[i] = w[i]; l.p.y.v[i] = w[3 + i]; }
            l.seed = w[6]; l.startIter = w[7]; l.hist = w[8]; l.dead = (unsigned)w[9];
        }
    }
    bool save(const char *path, u64 iterBase, unsigned runId) const {
        const std::string tmp = std::string(path) + ".tmp";
        FILE *f = fopen(tmp.c_str(), "wb");
        if (!f) return false;
        CkptHeader h;
        memcpy(h.magic, "ECC2K130", 8);
        h.version = CKPT_VERSION;
        h.m = (unsigned)M;
        h.threads = (unsigned)threads;
        h.batch = (unsigned)BATCH;
        h.lanes = 1u;
        h.runId = runId;
        h.iterBase = iterBase;
        std::vector<u64> buf;
        pack(buf);
        bool ok = fwrite(&h, sizeof h, 1, f) == 1;
        ok = ok && fwrite(buf.data(), sizeof(u64), buf.size(), f) == buf.size();
        ok = ok && durableFlush(f);
        if (fclose(f) != 0) ok = false;
        if (!ok) { remove(tmp.c_str()); return false; }
        return rename(tmp.c_str(), path) == 0 && syncParent(path);
    }
    bool restore(const char *path, u64 *iterBase, unsigned runId) {
        FILE *f = fopen(path, "rb");
        if (!f) return false;
        CkptHeader h;
        std::vector<u64> buf(lanes.size() * LANE_WORDS);
        bool ok = fread(&h, sizeof h, 1, f) == 1 &&
                  ckptHeaderMatches(h, M, threads, BATCH, 1, runId, CKPT_VERSION) &&
                  ckptPayloadIsWhole(f, buf.size() * sizeof(u64));
        ok = ok && fread(buf.data(), sizeof(u64), buf.size(), f) == buf.size();
        fclose(f);
        if (!ok) return false;
        unpack(buf);
        *iterBase = h.iterBase;
        return true;
    }
    const char *name() const { return ECC_WALK_TABLE ? "reference-table-walk" : "reference"; }
    bool needsReseed() const { return restartPending; }
    u64 walksPerLaunch() const { return (u64)lanes.size(); }
};

#ifndef ECC_NO_CUDA
// ---------------------------------------------------------------------------
// device backend
// ---------------------------------------------------------------------------
template <class Cfg>
struct CudaEngine {
    typedef DeviceWord W;
    static const int M = Cfg::M;
    static const int LANES = WordTraits<W>::LANES;
    static const int BATCH = ECC_BATCH;
    WalkParams<W> P;
    std::vector<DpRecord> staging;
    bool restartPending = false;

    // Bytes of device memory one walk thread needs: x, y and pchain are a field
    // element per slot, plus the per-lane bookkeeping.
    static size_t bytesPerThread() {
        return (size_t)BATCH * M * sizeof(W) * 3
             + (size_t)BATCH * sizeof(W)
             + (size_t)BATCH * LANES * sizeof(u64) * 2;
    }

    // How many threads actually fill this device.
    //
    // The old answer was SMs * ECC_THREADS * 2, which divides back to exactly
    // two blocks per SM no matter what the build asked for -- so a kernel
    // compiled for four resident blocks launched half of them, paid the
    // register cut that buys the fourth block, and got no occupancy for it.
    // Ask the driver instead: cudaOccupancyMaxActiveBlocksPerMultiprocessor
    // reports what ptxas's register allocation actually admits for this exact
    // kernel, so the launch tracks the build.
    //
    // One wave is the right size.  Every thread runs the same number of steps,
    // so a second wave adds no work-stealing, only memory.
    static int autoThreads(int device) {
        cudaDeviceProp prop;
        CUDA_CHECK(cudaGetDeviceProperties(&prop, device));
        int perSm = 0;
        CUDA_CHECK(cudaOccupancyMaxActiveBlocksPerMultiprocessor(
            &perSm, eccWalkKernel<Cfg, W>, ECC_THREADS, 0));
        if (perSm < 1) perSm = 1;
        long long want = (long long)prop.multiProcessorCount * ECC_THREADS * perSm;
        // Each thread carries BATCH field elements three times over, which at
        // batch 32 is about 50 KB; a full wave at high occupancy can ask for
        // more than the card has.  Leave a quarter free for the DP buffer and
        // the driver, and shrink to whole blocks rather than failing to malloc.
        size_t freeB = 0, totalB = 0;
        CUDA_CHECK(cudaMemGetInfo(&freeB, &totalB));
        const size_t budget = freeB - freeB / 4;
        const long long fits = (long long)(budget / bytesPerThread());
        long long got = want < fits ? want : fits;
        got -= got % ECC_THREADS;
        if (got < ECC_THREADS) got = ECC_THREADS;
        printf("device: %s, %d SMs, %d block(s) of %d threads resident per SM\n",
               prop.name, prop.multiProcessorCount, perSm, (int)ECC_THREADS);
        printf("launch: %lld threads (%lld blocks), %.1f GB of walk state%s\n",
               got, got / ECC_THREADS,
               got * (double)bytesPerThread() / (1024.0 * 1024.0 * 1024.0),
               got < want ? "  [capped by device memory]" : "");
        return (int)got;
    }

    void setup(const Options &o, const unsigned long long *cpx, const unsigned long long *cpy,
               const unsigned long long *cqx, const unsigned long long *cqy) {
        const size_t T = (size_t)o.threads;
        const size_t fw = T * BATCH * M * sizeof(W);
        const size_t lw = T * BATCH * LANES * sizeof(u64);
        CUDA_CHECK(cudaMalloc(&P.x, fw));
        CUDA_CHECK(cudaMalloc(&P.y, fw));
        CUDA_CHECK(cudaMalloc(&P.pchain, fw));
        CUDA_CHECK(cudaMalloc(&P.dead, T * BATCH * sizeof(W)));
        CUDA_CHECK(cudaMemset(P.dead, 0, T * BATCH * sizeof(W)));
        CUDA_CHECK(cudaMalloc(&P.seed, lw));
        CUDA_CHECK(cudaMalloc(&P.startIter, lw));
        CUDA_CHECK(cudaMalloc(&P.dp, (size_t)o.dpCap * sizeof(DpRecord)));
        CUDA_CHECK(cudaMalloc(&P.dpCount, 3 * sizeof(unsigned)));
        CUDA_CHECK(cudaMemset(P.dpCount, 0, 3 * sizeof(unsigned)));
        cudaFuncAttributes attrs;
        CUDA_CHECK(cudaFuncGetAttributes(&attrs, eccWalkKernel<Cfg, W>));
        cudaDeviceProp prop;
        CUDA_CHECK(cudaGetDeviceProperties(&prop, o.device));
        printf("kernel: %d SMs, %d registers/thread, %zu local bytes/thread, "
               "%zu shared bytes/block, stream Karatsuba %d, prefer L1 %d\n",
               prop.multiProcessorCount, attrs.numRegs, attrs.localSizeBytes,
               attrs.sharedSizeBytes, (int)ECC_STREAM_KARAT, (int)o.preferL1);
        unsigned long long *dk;
        CUDA_CHECK(cudaMalloc(&dk, 12 * sizeof(u64)));
        u64 hk[12];
        memcpy(hk + 0, cpx, 3 * sizeof(u64));
        memcpy(hk + 3, cpy, 3 * sizeof(u64));
        memcpy(hk + 6, cqx, 3 * sizeof(u64));
        memcpy(hk + 9, cqy, 3 * sizeof(u64));
        CUDA_CHECK(cudaMemcpy(dk, hk, sizeof hk, cudaMemcpyHostToDevice));
        P.consts.px = dk;
        P.consts.py = dk + 3;
        P.consts.qx = dk + 6;
        P.consts.qy = dk + 9;
        P.threads = o.threads;
        P.steps = o.steps;
        P.dpWeight = o.dpWeight;
        P.runId = o.runId;
        P.maxIters = o.maxIters;
        P.iterBase = 0;
        P.dpCap = o.dpCap;
        staging.resize(o.dpCap);
        const int blocks = (o.threads + ECC_THREADS - 1) / ECC_THREADS;
        eccInitKernel<Cfg, W><<<blocks, ECC_THREADS, 0, 0>>>(P);
        CUDA_CHECK(cudaGetLastError());
        CUDA_CHECK(cudaDeviceSynchronize());
    }

    void launch(u64 iterBase) {
        P.iterBase = iterBase;
        const int blocks = (P.threads + ECC_THREADS - 1) / ECC_THREADS;
        eccWalkKernel<Cfg, W><<<blocks, ECC_THREADS, 0, 0>>>(P);
        CUDA_CHECK(cudaGetLastError());
    }

    void reseed(u64 iterBase) {
        P.iterBase = iterBase;
        const int blocks = (P.threads + ECC_THREADS - 1) / ECC_THREADS;
        eccReseedKernel<Cfg, W><<<blocks, ECC_THREADS, 0, 0>>>(P);
        CUDA_CHECK(cudaGetLastError());
    }

    void synchronize() const { CUDA_CHECK(cudaDeviceSynchronize()); }

    unsigned fetch(std::vector<DpRecord> &out) {
        CUDA_CHECK(cudaDeviceSynchronize());
        unsigned counts[3] = {0, 0, 0};
        CUDA_CHECK(cudaMemcpy(counts, P.dpCount, sizeof counts, cudaMemcpyDeviceToHost));
        const unsigned n = counts[0];
        restartPending = counts[1] != 0;
        const unsigned m = n < P.dpCap ? n : P.dpCap;
        out.resize(m);
        if (m) CUDA_CHECK(cudaMemcpy(out.data(), P.dp, (size_t)m * sizeof(DpRecord), cudaMemcpyDeviceToHost));
        if (n || restartPending || counts[2]) CUDA_CHECK(cudaMemset(P.dpCount, 0, sizeof counts));
        return counts[2] ? ECC_SEED_EXHAUSTED : n;
    }

    virtual ~CudaEngine() = default;
    virtual size_t fieldCount() const { return (size_t)P.threads * BATCH * M; }
    // Device field allocations may include physical-layout padding. Checkpoint
    // headers and payload sizes continue to use the logical fieldCount().
    virtual size_t physicalFieldCount() const { return fieldCount(); }
    size_t slotCount() const { return (size_t)P.threads * BATCH; }
    virtual size_t laneCount() const { return (size_t)P.threads * BATCH * LANES; }
    virtual unsigned checkpointVersion() const { return 1u; }
    virtual int checkpointLanes() const { return LANES; }
    // Backends may use a different coordinate representation on the device.
    // These hooks preserve the checkpoint representation without touching
    // live device state; the default backend already stores checkpoint words.
    virtual void exportCheckpointField(std::vector<W> &) const {}
    virtual void importCheckpointField(std::vector<W> &) const {}
    // Per-lane 64-bit arrays in the checkpoint, in order: seed, startIter,
    // and whatever a backend adds (the table walk's step history).
    virtual int laneArrayCount() const { return 2; }
    virtual u64 *laneArray(int i) const { return i ? P.startIter : P.seed; }
    virtual void readCheckpointDead(std::vector<W> &v) const {
        CUDA_CHECK(cudaMemcpy(v.data(), P.dead, v.size()*sizeof(W), cudaMemcpyDeviceToHost));
    }
    virtual void writeCheckpointDead(const std::vector<W> &v) {
        CUDA_CHECK(cudaMemcpy(P.dead, v.data(), v.size()*sizeof(W), cudaMemcpyHostToDevice));
    }
    virtual void readCheckpointLane(int i, std::vector<u64> &v) const {
        CUDA_CHECK(cudaMemcpy(v.data(), laneArray(i), v.size()*sizeof(u64), cudaMemcpyDeviceToHost));
    }
    virtual void writeCheckpointLane(int i, const std::vector<u64> &v) {
        CUDA_CHECK(cudaMemcpy(laneArray(i), v.data(), v.size()*sizeof(u64), cudaMemcpyHostToDevice));
    }


    bool save(const char *path, u64 iterBase, unsigned runId) const {
        CUDA_CHECK(cudaDeviceSynchronize());
        const std::string tmp = std::string(path) + ".tmp";
        FILE *f = fopen(tmp.c_str(), "wb");
        if (!f) return false;
        CkptHeader h;
        memcpy(h.magic, "ECC2K130", 8);
        h.version = checkpointVersion();
        h.m = (unsigned)M;
        h.threads = (unsigned)P.threads;
        h.batch = (unsigned)BATCH;
        h.lanes = (unsigned)checkpointLanes();
        h.runId = runId;
        h.iterBase = iterBase;
        bool ok = fwrite(&h, sizeof h, 1, f) == 1;
        std::vector<W> fbuf;
        std::vector<W> sbuf(slotCount());
        std::vector<u64> lbuf(laneCount());
        const W *fields[2] = {P.x, P.y};
        for (int i = 0; i < 2 && ok; ++i) {
            // Export may resize staging to the logical checkpoint field size.
            // Restore the physical transfer length independently for X and Y.
            fbuf.resize(physicalFieldCount());
            CUDA_CHECK(cudaMemcpy(fbuf.data(), fields[i], fbuf.size() * sizeof(W), cudaMemcpyDeviceToHost));
            exportCheckpointField(fbuf);
            if (fbuf.size() != fieldCount()) { ok = false; break; }
            ok = fwrite(fbuf.data(), sizeof(W), fbuf.size(), f) == fbuf.size();
        }
        if (ok) {
            readCheckpointDead(sbuf);
            ok = fwrite(sbuf.data(), sizeof(W), sbuf.size(), f) == sbuf.size();
        }
        for (int i = 0; i < laneArrayCount() && ok; ++i) {
            readCheckpointLane(i, lbuf);
            ok = fwrite(lbuf.data(), sizeof(u64), lbuf.size(), f) == lbuf.size();
        }
        ok = ok && durableFlush(f);
        if (fclose(f) != 0) ok = false;
        if (!ok) { remove(tmp.c_str()); return false; }
        return rename(tmp.c_str(), path) == 0 && syncParent(path);
    }

    bool restore(const char *path, u64 *iterBase, unsigned runId) {
        FILE *f = fopen(path, "rb");
        if (!f) return false;
        CkptHeader h;
        const size_t payload = (2 * fieldCount() + slotCount()) * sizeof(W) +
                               size_t(laneArrayCount()) * laneCount() * sizeof(u64);
        bool ok = fread(&h, sizeof h, 1, f) == 1 &&
                  ckptHeaderMatches(h, M, P.threads, BATCH, checkpointLanes(), runId, checkpointVersion()) &&
                  ckptPayloadIsWhole(f, payload);
        if (!ok) { fclose(f); return false; }
        std::vector<W> fbuf(fieldCount());
        std::vector<W> sbuf(slotCount());
        std::vector<u64> lbuf(laneCount());
        W *fields[2] = {P.x, P.y};
        for (int i = 0; i < 2 && ok; ++i) {
            // Import may expand staging into a padded physical field.
            fbuf.resize(fieldCount());
            ok = fread(fbuf.data(), sizeof(W), fbuf.size(), f) == fbuf.size();
            if (ok) {
                importCheckpointField(fbuf);
                if (fbuf.size() != physicalFieldCount()) { ok = false; break; }
                CUDA_CHECK(cudaMemcpy(fields[i], fbuf.data(), fbuf.size() * sizeof(W), cudaMemcpyHostToDevice));
            }
        }
        if (ok) {
            ok = fread(sbuf.data(), sizeof(W), sbuf.size(), f) == sbuf.size();
            if (ok) writeCheckpointDead(sbuf);
        }
        for (int i = 0; i < laneArrayCount() && ok; ++i) {
            ok = ok && fread(lbuf.data(), sizeof(u64), lbuf.size(), f) == lbuf.size();
            if (ok) writeCheckpointLane(i, lbuf);
        }
        fclose(f);
        if (ok) *iterBase = h.iterBase;
        return ok;
    }

    const char *name() const { return "cuda"; }
    bool needsReseed() const { return restartPending; }
    u64 walksPerLaunch() const { return (u64)P.threads * BATCH * LANES; }
};
#include "../include/packedengine.cuh"
#endif

// ---------------------------------------------------------------------------
// validation
// ---------------------------------------------------------------------------
static int gFail = 0;
static void report(const char *what, bool ok) {
    printf("  %-46s %s\n", what, ok ? "ok" : "FAILED");
    if (!ok) gFail++;
}

struct Rng {
    u64 s;
    explicit Rng(u64 seed) : s(seed ? seed : 1) {}
    u64 next() {
        s ^= s << 13;
        s ^= s >> 7;
        s ^= s << 17;
        return s;
    }
};

template <class Cfg>
static typename Ref<Cfg>::Elem randomElem(Rng &rng) {
    typename Ref<Cfg>::Elem e = Ref<Cfg>::zero();
    for (int i = 0; i < Cfg::M; ++i)
        if (rng.next() & 1) Ref<Cfg>::setBit(e, i);
    return e;
}

// random point of order l on y^2 + xy = x^3 + 1
template <class Cfg>
static typename Ref<Cfg>::Point randomPoint(Rng &rng, const U192 &ell) {
    typedef Ref<Cfg> R;
    for (;;) {
        const typename R::Elem x = randomElem<Cfg>(rng);
        if (R::isZero(x)) continue;
        const typename R::Elem c = R::add(x, R::inv(R::mul(x, x)));
        if (R::trace(c)) continue;
        const typename R::Elem z = R::halfTrace(c);
        typename R::Point p = R::make(x, R::mul(x, z));
        if (!R::onCurve(p)) continue;
        p = R::dbl(R::dbl(p));
        if (p.inf) continue;
        if (!R::scalarMul(p, ell).inf) continue;
        return p;
    }
}

template <class Cfg>
static void testField(Rng &rng) {
    typedef Ref<Cfg> R;
    typedef ECC_HOST_WORD W;
    typedef typename Cfg::template Field<W> F;
    const int M = Cfg::M;
    const int LANES = WordTraits<W>::LANES;
    std::vector<typename R::Elem> a(LANES), b(LANES);
    std::vector<W> ba(M, ECC_ZERO), bb(M, ECC_ZERO), bc(M, ECC_ZERO), bd(M, ECC_ZERO);
    for (int l = 0; l < LANES; ++l) {
        a[l] = randomElem<Cfg>(rng);
        b[l] = randomElem<Cfg>(rng);
        F::setLane(ba.data(), l, a[l].v);
        F::setLane(bb.data(), l, b[l].v);
    }
    bool okMul = true, okSqr = true, okInv = true, okHw = true, okSig = true;
    F::mul(ba.data(), bb.data(), bc.data());
    for (int l = 0; l < LANES; ++l) {
        typename R::Elem got;
        F::getLane(bc.data(), l, got.v);
        if (!(got == R::mul(a[l], b[l]))) okMul = false;
    }
    F::sqr(ba.data(), bc.data());
    for (int l = 0; l < LANES; ++l) {
        typename R::Elem got;
        F::getLane(bc.data(), l, got.v);
        if (!(got == R::sqr(a[l]))) okSqr = false;
    }
    F::inv(ba.data(), bc.data());
    for (int l = 0; l < LANES; ++l) {
        typename R::Elem got;
        F::getLane(bc.data(), l, got.v);
        if (!R::isZero(a[l]) && !(got == R::inv(a[l]))) okInv = false;
    }
    F::sigmaRun(ba.data(), 7, bc.data());
    for (int l = 0; l < LANES; ++l) {
        typename R::Elem got;
        F::getLane(bc.data(), l, got.v);
        if (!(got == R::sigma(a[l], 7))) okSig = false;
    }
    std::vector<W> hb(Cfg::HWBITS > 4 ? Cfg::HWBITS : 4, ECC_ZERO);
    Cfg::hamming(ba.data(), hb.data());
    for (int l = 0; l < LANES; ++l) {
        int got = 0;
        for (int i = 0; i < Cfg::HWBITS; ++i) got |= laneBit<W>(hb[i], l) << i;
        if (got != R::weight(a[l])) okHw = false;
    }
    report("bitsliced multiply matches reference", okMul);
    report("bitsliced squaring matches reference", okSqr);
    report("bitsliced inversion matches reference", okInv);
    report("bitsliced sigma^7 matches reference", okSig);
    report("bitsliced Hamming weight matches reference", okHw);
}

template <class Cfg>
static void testOrbit(Rng &rng, const Solver<Cfg> &sol) {
    typedef Ref<Cfg> R;
    const U192 &ell = sol.ell;
    bool okFrob = true, okNeg = true, okWeight = true, okTrace = true;
#if ECC_WALK_TABLE
    if (!TableWalk<Cfg>::applicable()) {
        printf("  %-46s (table walk needs a type-II normal basis)\n", "  ... not applicable for GF(2^m) in a polynomial basis");
        return;
    }
    // The table walk's class covariance rests on three identities of the
    // coordinate functions (tablewalk.h); check them, then the step itself
    // with an empty history and with a history that trips the cycle rule.
    bool okPhase = true, okEpsFrob = true, okEpsNeg = true, okTables = sol.walk.consts.consistent();
    for (int t = 0; t < 64; ++t) {
        const typename R::Point p = randomPoint<Cfg>(rng, ell);
        const int hw = R::weight(p.x);
        const int c = 1 + (int)(rng.next() % (Cfg::M - 1));
        const typename R::Point pc = R::frob(p, c), pn = R::neg(p);
        const typename R::Elem xn = R::nbCoords(p.x), yn = R::nbCoords(p.y);
        const typename R::Elem xc = R::nbCoords(pc.x), yc = R::nbCoords(pc.y), ynn = R::nbCoords(pn.y);
        const int k = sol.walk.phase(xn, hw), kc = sol.walk.phase(xc, hw);
        if (kc != (k + c) % Cfg::M) okPhase = false;
        if (sol.walk.negationBit(xc, yc, kc) != sol.walk.negationBit(xn, yn, k)) okEpsFrob = false;
        if (sol.walk.negationBit(xn, ynn, k) != 1 - sol.walk.negationBit(xn, yn, k)) okEpsNeg = false;
        u64 h0 = ECC_HIST_EMPTY, h1 = h0, h2 = h0;
        const typename R::Point f = sol.walk.step(p, hw, &h0, 0, 0, ell, sol.spow);
        if (!R::eq(sol.walk.step(pc, R::weight(pc.x), &h1, 0, 0, ell, sol.spow), R::frob(f, c))) okFrob = false;
        if (!R::eq(sol.walk.step(pn, R::weight(pn.x), &h2, 0, 0, ell, sol.spow), R::neg(f))) okNeg = false;
        // Trails meeting as R and sigma^c(-R) carry conjugate histories; the
        // cycle rule must fire for both or neither.
        const unsigned tag = unsigned(h0 & 0xFFFF);
        const u64 undo = eccHistPush(ECC_HIST_EMPTY, tag ^ ECC_TAG_EPS);
        const u64 undoC = eccHistPush(ECC_HIST_EMPTY, unsigned(h1 & 0xFFFF) ^ ECC_TAG_EPS);
        const u64 undoN = eccHistPush(ECC_HIST_EMPTY, unsigned(h2 & 0xFFFF) ^ ECC_TAG_EPS);
        u64 g0 = undo, g1 = undoC, g2 = undoN;
        const typename R::Point fa = sol.walk.step(p, hw, &g0, 0, 0, ell, sol.spow);
        if (R::eq(fa, f)) okFrob = false;   // the rule did not fire
        if (!R::eq(sol.walk.step(pc, R::weight(pc.x), &g1, 0, 0, ell, sol.spow), R::frob(fa, c))) okFrob = false;
        if (!R::eq(sol.walk.step(pn, R::weight(pn.x), &g2, 0, 0, ell, sol.spow), R::neg(fa))) okNeg = false;
        if (R::weight(pc.x) != hw) okWeight = false;
        if (R::trace(p.x) != 0) okTrace = false;
    }
    report("coordinate logarithm table is a bijection", okTables);
    report("Frobenius phase advances by one under sigma", okPhase);
    report("negation bit is sigma-invariant", okEpsFrob);
    report("negation bit flips under negation", okEpsNeg);
#else
    for (int t = 0; t < 8; ++t) {
        const typename R::Point p = randomPoint<Cfg>(rng, ell);
        const int hw = R::weight(p.x);
        const typename R::Point f = R::step(p, hw);
        const int c = (int)(rng.next() % Cfg::M);
        const typename R::Point pc = R::frob(p, c);
        if (!R::eq(R::step(pc, R::weight(pc.x)), R::frob(f, c))) okFrob = false;
        const typename R::Point pn = R::neg(p);
        if (!R::eq(R::step(pn, R::weight(pn.x)), R::neg(f))) okNeg = false;
        if (R::weight(pc.x) != hw) okWeight = false;
        if (R::trace(p.x) != 0) okTrace = false;
    }
#endif
    report("iteration commutes with Frobenius", okFrob);
    report("iteration commutes with negation", okNeg);
    report("weight is constant on an orbit", okWeight);
    report("subgroup x-coordinates have even weight", okTrace);
}

template <class Cfg>
static void testStartPoint(Rng &rng, Solver<Cfg> &sol) {
    typedef Ref<Cfg> R;
    typedef ECC_HOST_WORD W;
    typedef typename Cfg::template Field<W> F;
    typedef Walk<Cfg, W> WK;
    const int M = Cfg::M;
    const int LANES = WordTraits<W>::LANES;
    std::vector<u64> seeds(LANES);
    for (int l = 0; l < LANES; ++l) seeds[l] = rng.next();
    std::vector<W> x(M, ECC_ZERO), y(M, ECC_ZERO);
    CurveConsts K;
    K.px = sol.basis.x.v;
    K.py = sol.basis.y.v;
    K.qx = sol.target.x.v;
    K.qy = sol.target.y.v;
    WK::startPoint(seeds.data(), K, x.data(), y.data());
    // The reference is the slow path here, so a handful of lanes is plenty.
    const int CHECK = LANES < 16 ? LANES : 16;
    bool ok = true, okAlpha = true;
    int skipped = 0;
    for (int l = 0; l < CHECK; ++l) {
        typename R::Elem gx, gy;
        F::getLane(x.data(), l, gx.v);
        F::getLane(y.data(), l, gy.v);
        U192 alpha;
        bool degenerate = false;
        const typename R::Point want =
            R::startPoint(seeds[l], sol.basis, sol.target, &alpha, sol.ell, sol.spow, &degenerate);
        if (!(gx == want.x) || !(gy == want.y)) ok = false;
        // start = [alpha] P + Q.  The client adds without special cases, so
        // this identity only holds while no two summands share an abscissa.
        // That needs a birthday collision among a few hundred points, so it
        // never happens on the challenge curves and does on a toy field.
        if (degenerate) {
            ++skipped;
            continue;
        }
        const typename R::Point chk = R::addPt(R::scalarMul(sol.basis, alpha), sol.target);
        if (!R::eq(chk, want)) okAlpha = false;
    }
    report("bitsliced start point matches reference", ok);
    report("tracked start scalar reproduces the point", okAlpha);
    if (skipped)
        printf("  %-46s %d of %d lanes (degenerate addition on a toy field)\n",
               "  ... not applicable for", skipped, CHECK);
}

template <class Cfg>
static void testSolveAlgebra(Rng &rng, const Solver<Cfg> &base) {
    typedef Ref<Cfg> R;
    // Plant a discrete log of our own, synthesise two walks that meet with
    // known exponents, and check the solver recovers it.
    Solver<Cfg> sol = base;
    U192 knownK = u192_zero();
    knownK.v[0] = rng.next();
    knownK.v[1] = rng.next();
    knownK = mod_reduce(knownK, sol.ell);
    if (u192_is_zero(knownK)) knownK = u192_from(7);
    sol.target = R::scalarMul(sol.basis, knownK);
    bool ok = true;
    auto randomScalar = [&]() {
        U192 r = u192_zero();
        r.v[0] = rng.next();
        r.v[1] = rng.next() & 0xFFFF;
        return mod_reduce(r, sol.ell);
    };
    for (int t = 0; t < 4 && ok; ++t) {
        typename Solver<Cfg>::WalkResult A, B;
        A.ok = B.ok = true;
        // Endpoints are a P + b Q.  The sigma^j + 1 walk has b = mu, a product
        // of (1 + s^j); the table walk's b is an arbitrary residue.
#if ECC_WALK_TABLE
        A.b = randomScalar();
        B.b = randomScalar();
#else
        for (int j = 0; j < 8; ++j) {
            A.counts[j] = rng.next() % 7;
            B.counts[j] = rng.next() % 7;
        }
        A.b = sol.multiplier(A.counts);
        B.b = sol.multiplier(B.counts);
#endif
        B.a = randomScalar();
        const int c = (int)(rng.next() % Cfg::M);
        const int eps = (rng.next() & 1) ? 1 : -1;
        U192 sc = sol.spow[c];
        if (eps < 0) sc = mod_neg(sc, sol.ell);
        // choose a_A so that  a_A + b_A k = eps s^c (a_B + b_B k)
        const U192 rhs = mod_mul(sc, mod_add(B.a, mod_mul(B.b, knownK, sol.ell), sol.ell), sol.ell);
        A.a = mod_sub(rhs, mod_mul(A.b, knownK, sol.ell), sol.ell);
        A.endPoint = R::addPt(R::scalarMul(sol.basis, A.a), R::scalarMul(sol.target, A.b));
        B.endPoint = R::addPt(R::scalarMul(sol.basis, B.a), R::scalarMul(sol.target, B.b));
        if (!R::eq(A.endPoint, eps > 0 ? R::frob(B.endPoint, c) : R::neg(R::frob(B.endPoint, c)))) {
            ok = false;
            break;
        }
        U192 got;
        std::string why;
        if (!sol.solve(A, B, &got, &why) || !u192_eq(got, knownK)) ok = false;
    }
    report("collision solver recovers a known discrete log", ok);
}

// ---------------------------------------------------------------------------
// search loop
// ---------------------------------------------------------------------------
template <class Cfg, class Engine>
static int runSearch(const Options &o, Engine &eng, Solver<Cfg> &sol, const U192 *knownK) {
    typedef Ref<Cfg> R;
    std::vector<DpRecord> recs;
    u64 iterBase = 0;
    u64 totalDp = 0, lost = 0, verified = 0, verifyBudget = (u64)(o.verify < 0 ? 0 : o.verify);
    CorpusOutput output;
    if (eng.walksPerLaunch() >= ECC_SEED_EXHAUSTED) {
        fprintf(stderr, "too many walks for the report counter or seed namespace\n");
        return 1;
    }
    if (!o.dpFile.empty() && !output.openFile(o.dpFile, sizeof(DpFileRecord))) {
        fprintf(stderr, "persistence failure: cannot lock/open aligned regular corpus %s\n", o.dpFile.c_str());
        return 8;
    }

    // Reload every corpus file first, so a collision against work done by an
    // earlier run or another worker is found the moment it happens rather than
    // only by an offline merge.
    size_t reloaded = 0;
    std::vector<std::string> corpus = o.loadFiles;
    if (!o.dpFile.empty()) corpus.push_back(o.dpFile);

    // The dp file is normally also named by --load, and two --load flags can
    // reach one corpus through different paths.  Reading a file twice costs
    // time and reports a misleading count; the second pass is all duplicates.
    for (size_t ci = 0; ci < corpus.size(); ++ci) {
        char *real = realpath(corpus[ci].c_str(), 0);
        if (!real) continue;
        corpus[ci] = real;
        free(real);
    }
    std::sort(corpus.begin(), corpus.end());
    corpus.erase(std::unique(corpus.begin(), corpus.end()), corpus.end());

    // Newest first, so that a --load-max cap keeps the most recent work rather
    // than whichever file sorts first by name.  A store entry costs far more
    // than the 32 bytes it occupies on disk, so an unbounded reload is what
    // ends a long collection run: the corpus grows every pass, and without a
    // cap each pass tries to hold every point every earlier pass ever wrote.
    // What the cap gives up is finding a collision in process; the corpus is
    // still complete on disk, and the offline merge still finds it there.
    std::sort(corpus.begin(), corpus.end(),
              [](const std::string &a, const std::string &b) {
                  struct stat sa, sb;
                  const bool oa = stat(a.c_str(), &sa) == 0, ob = stat(b.c_str(), &sb) == 0;
                  if (!oa || !ob) return oa > ob;
                  return sa.st_mtime > sb.st_mtime;
              });
    size_t skippedFiles = 0;
    for (size_t ci = 0; ci < corpus.size(); ++ci) {
        if (o.loadMax && reloaded >= o.loadMax) { skippedFiles = corpus.size() - ci; break; }
        FILE *in = fopen(corpus[ci].c_str(), "rb");
        struct stat inputStat;
        if (!in || fstat(fileno(in), &inputStat) != 0 || !S_ISREG(inputStat.st_mode) ||
            inputStat.st_size % sizeof(DpFileRecord) != 0) {
            if (in) fclose(in);
            fprintf(stderr, "persistence failure: missing, non-regular or truncated corpus %s\n", corpus[ci].c_str());
            return 8;
        }
        // A single --dp-file is append-only across passes, so the newest
        // records sit at the end.  When the remaining cap is smaller than
        // the file, start there rather than keeping the oldest prefix.
        if (o.loadMax && reloaded < o.loadMax && fseek(in, 0, SEEK_END) == 0) {
            const long sz = ftell(in);
            unsigned long long skip = 0;
            if (sz > 0) {
                const unsigned long long nrec = (unsigned long long)sz / sizeof(DpFileRecord);
                const unsigned long long remain = o.loadMax - (unsigned long long)reloaded;
                if (nrec > remain) skip = nrec - remain;
            }
            if (fseek(in, (long)(skip * sizeof(DpFileRecord)), SEEK_SET) != 0) rewind(in);
        }
        DpFileRecord fr;
        while (fread(&fr, sizeof fr, 1, in) == 1) {
            if (o.loadMax && reloaded >= o.loadMax) break;
            typename Solver<Cfg>::Key key;
            key.v[0] = fr.canon[0];
            key.v[1] = fr.canon[1];
            key.v[2] = fr.canon[2];
            typename Solver<Cfg>::Entry other;
            ++reloaded;
            if (!sol.insertKey(key, fr.seed, 0, &other)) continue;
            printf("collision found while reloading %s: seeds %016llx and %016llx\n",
                   corpus[ci].c_str(), (unsigned long long)fr.seed,
                   (unsigned long long)other.seed);
            const typename Solver<Cfg>::WalkResult A = sol.rewalk(fr.seed);
            const typename Solver<Cfg>::WalkResult B = sol.rewalk(other.seed);
            U192 k;
            std::string why;
            if (sol.solve(A, B, &k, &why)) {
                printf("  k = %s\n  verified [k]P == Q\n", u192_to_dec(k).c_str());
                if (knownK) printf("  matches the published solution: %s\n",
                                   u192_eq(k, *knownK) ? "yes" : "NO");
                fclose(in);
                return (knownK && !u192_eq(k, *knownK)) ? 4 : 0;
            }
            printf("  unusable (%s)\n", why.c_str());
        }
        const bool readFailed = ferror(in) != 0;
        fclose(in);
        if (readFailed) return 8;
    }
    if (reloaded) {
        printf("reloaded %zu points from %zu file(s), %zu distinct orbits\n",
               reloaded, corpus.size() - skippedFiles, sol.inserted);
        if (o.loadMax && reloaded >= o.loadMax)
            printf("  stopped at the --load-max %llu cap; %zu file(s) not read, "
                   "their collisions are left to the offline merge\n",
                   (unsigned long long)o.loadMax, skippedFiles);
    }

    // Resume the walks themselves.  Without this a restart abandons every walk
    // in flight, which at the usual cutoff is about a quarter of the whole run.
    if (!o.ckptFile.empty()) {
        if (eng.restore(o.ckptFile.c_str(), &iterBase, o.runId))
            printf("resumed from %s at iteration %llu\n", o.ckptFile.c_str(),
                   (unsigned long long)iterBase);
        else {
            struct stat existing;
            if (stat(o.ckptFile.c_str(), &existing) == 0 || errno != ENOENT) {
                fprintf(stderr, "checkpoint %s is incompatible or incomplete; use the matching backend/settings or a new checkpoint path\n", o.ckptFile.c_str());
                return 6;
            }
            printf("no checkpoint at %s, starting fresh\n", o.ckptFile.c_str());
        }
    }

    const u64 timedIterBase = iterBase;
    const double t0 = nowSeconds();
    double lastPrint = t0;
    double lastCkpt = t0;
    FILE *dpOut = output.file;
    for (long launch = 0; o.launches == 0 || launch < o.launches; ++launch) {
        eng.launch(iterBase);
        const unsigned n = eng.fetch(recs);
        iterBase += (u64)o.steps;
        if (n == ECC_SEED_EXHAUSTED) {
            fprintf(stderr, "SEED EXHAUSTED: refusing counter wrap into another walk; retire this run-id\n");
            return 9;
        }
        if (n > recs.size()) {
            fprintf(stderr, "DP OVERFLOW: %u reports, capacity %zu; checkpoint NOT advanced. Increase --dp-cap or lower --dp-weight.\n", n, recs.size());
            return 7;
        }
        if (n || eng.needsReseed()) eng.reseed(iterBase);
        totalDp += recs.size();
        for (size_t i = 0; i < recs.size(); ++i) {
            const DpRecord &rec = recs[i];
            if (verifyBudget) {
                --verifyBudget;
                const typename Solver<Cfg>::WalkResult w = sol.rewalk(rec.seed);
                const bool same = w.ok && w.iters == rec.iters &&
                                  w.endPoint.x == R::fromLimbs(rec.x) &&
                                  w.endPoint.y == R::fromLimbs(rec.y);
                if (!same) {
                    printf("MISMATCH: seed %016llx was not reproduced by the reference walk\n",
                           (unsigned long long)rec.seed);
                    return 3;
                }
                ++verified;
            }
            if (dpOut) {
                const typename R::Elem cx = R::canonical(R::fromLimbs(rec.x));
                DpFileRecord fr;
                fr.seed = rec.seed;
                fr.canon[0] = cx.v[0];
                fr.canon[1] = cx.v[1];
                fr.canon[2] = cx.v[2];
                if (fwrite(&fr, sizeof fr, 1, dpOut) != 1) {
                    fprintf(stderr, "persistence failure: corpus write; checkpoint NOT advanced\n");
                    return 8;
                }
            }
            typename Solver<Cfg>::Entry other;
            if (!sol.insert(rec, &other)) continue;
            printf("collision: seeds %016llx and %016llx meet after %llu and %llu steps\n",
                   (unsigned long long)rec.seed, (unsigned long long)other.seed,
                   (unsigned long long)rec.iters, (unsigned long long)other.iters);
            const double tr = nowSeconds();
            const typename Solver<Cfg>::WalkResult A = sol.rewalk(rec.seed);
            const typename Solver<Cfg>::WalkResult B = sol.rewalk(other.seed);
            U192 k;
            std::string why;
            if (!sol.solve(A, B, &k, &why)) {
                printf("  unusable (%s), continuing\n", why.c_str());
                continue;
            }
            printf("  recomputed both walks in %.2f s\n", nowSeconds() - tr);
            printf("  k = %s\n", u192_to_dec(k).c_str());
            printf("  verified [k]P == Q\n");
            if (knownK) printf("  matches the planted discrete log: %s\n",
                               u192_eq(k, *knownK) ? "yes" : "NO");
            const double el = nowSeconds() - t0;
            printf("  solved after %llu iterations of %llu walks in %.2f s (%llu distinguished points)\n",
                   (unsigned long long)iterBase, (unsigned long long)eng.walksPerLaunch(), el,
                   (unsigned long long)totalDp);
            if (!output.closeFile()) return 8;
            if (!o.ckptFile.empty() && !eng.save(o.ckptFile.c_str(), iterBase, o.runId)) return 8;
            return (knownK && !u192_eq(k, *knownK)) ? 4 : 0;
        }
        const double now = nowSeconds();
        // Flush reports and checkpoint on a timer, and always on the way out,
        // so a container stopped by its deadline loses seconds of work rather
        // than hours of it.
        const bool leaving = gStop || (o.launches && launch + 1 == o.launches);
        if (dpOut && (leaving || now - lastCkpt > o.ckptSeconds) && !durableFlush(dpOut)) {
            fprintf(stderr, "persistence failure: corpus flush; checkpoint NOT advanced\n");
            return 8;
        }
        if (!o.ckptFile.empty() && (leaving || now - lastCkpt > o.ckptSeconds)) {
            if (!eng.save(o.ckptFile.c_str(), iterBase, o.runId)) {
                fprintf(stderr, "persistence failure: checkpoint %s\n", o.ckptFile.c_str());
                return 8;
            }
            lastCkpt = now;
        }
        if (gStop) {
            printf("stopping: %llu iterations of %llu walks, %llu points reported\n",
                   (unsigned long long)iterBase, (unsigned long long)eng.walksPerLaunch(),
                   (unsigned long long)totalDp);
            break;
        }
        if (now - lastPrint > 2.0 || (o.launches && launch + 1 == o.launches)) {
            const double el = now - t0;
            const double it = (double)(iterBase - timedIterBase) * (double)eng.walksPerLaunch();
            printf("  %8.1f s  %10.3f M it/s  %10llu iterations  %8llu dp  %8llu stored"
                   "  %8llu dropped\n",
                   el, it / el / 1e6, (unsigned long long)it, (unsigned long long)totalDp,
                   (unsigned long long)sol.inserted, (unsigned long long)lost);
            fflush(stdout);
            lastPrint = now;
        }
    }
    // Include any final asynchronous reseed in the completed-run rate.
    eng.synchronize();
    const double el = nowSeconds() - t0;
    const double it = (double)(iterBase - timedIterBase) * (double)eng.walksPerLaunch();
    printf("  finished: %.3f M it/s, %llu distinguished points (%llu verified against the reference, %llu dropped)\n",
           it / el / 1e6, (unsigned long long)totalDp, (unsigned long long)verified, (unsigned long long)lost);
    if (!output.closeFile()) return 8;
    return 0;
}

// ---------------------------------------------------------------------------
template <class Cfg>
static int runCurve(const Options &oIn, const unsigned long long *px, const unsigned long long *py,
                    const unsigned long long *qx, const unsigned long long *qy, const char *ellDec,
                    const char *sDec, int defaultW, const char *knownKDec) {
    Options o = oIn;
    if (o.dpWeight < 0) o.dpWeight = defaultW;
    Solver<Cfg> sol;
    sol.setup(px, py, qx, qy, ellDec, sDec, o.dpWeight,
              // Guards are checked on global ECC_GUARD_PERIOD boundaries.
              // A valid first DP may occur in the bounded overshoot window
              // after maxIters, so reference replay must include that window.
              o.maxIters ? o.maxIters + ECC_GUARD_PERIOD - 1 : (u64)1 << 40);
    std::string why;
    if (!sol.checkSetup(&why)) {
        printf("parameter check failed: %s\n", why.c_str());
        return 5;
    }
    U192 knownK;
    bool haveK = false;
    if (knownKDec) {
        knownK = u192_from_dec(knownKDec);
        haveK = true;
    }

    if (o.test) {
        printf("GF(2^%d), n = %d, l = %s\n", Cfg::M, Cfg::NRING, ellDec);
        report("published parameters are consistent", true);
        if (haveK) {
            // ECC2K-95: Harley's group published this in 1998
            report("published challenge solution satisfies [k]P == Q",
                   Ref<Cfg>::eq(Ref<Cfg>::scalarMul(sol.basis, knownK), sol.target));
        }
        Rng rng(0x1234567 + Cfg::M);
        testField<Cfg>(rng);
        testOrbit<Cfg>(rng, sol);
        testStartPoint<Cfg>(rng, sol);
        testSolveAlgebra<Cfg>(rng, sol);
        return 0;
    }

#ifndef ECC_NO_CUDA
    if (o.packed) {
        if constexpr (Cfg::M == 131) {
            PackedCudaEngine eng;
            eng.sol = &sol;
            if (o.threads <= 0) o.threads = eng.autoThreads(o.device);
            eng.setup(o, px, py, qx, qy);
            printf("backend %s: %d threads x %d slots x 1 lanes = %llu walks, dp weight %d, %d steps per launch\n",
                   eng.name(), o.threads, (int)ECC_BATCH, eng.walksPerLaunch(), o.dpWeight, o.steps);
            return runSearch<Cfg>(o, eng, sol, haveK ? &knownK : NULL);
        } else {
            fprintf(stderr, "--packed is supported only for GF(2^131)\n");
            return 1;
        }
    }
#endif
    if (ECC_WALK_TABLE || o.refEngine) {
        // The bitsliced kernels walk with sigma^j + 1; only the packed
        // GF(2^131) kernel and the reference implement the table walk.
        if (ECC_WALK_TABLE && !TableWalk<Cfg>::applicable()) {
            fprintf(stderr, "the table walk is defined on type-II normal-basis fields only\n");
            return 1;
        }
        RefEngine<Cfg> eng;
        eng.sol = &sol;
        if (o.threads <= 0) o.threads = eng.autoThreads(o.device);
        eng.setup(o, px, py, qx, qy);
        printf("backend %s: %d threads x %d slots x 1 lanes = %llu walks, dp weight %d, %d steps per launch\n",
               eng.name(), o.threads, (int)ECC_BATCH, (unsigned long long)eng.walksPerLaunch(), o.dpWeight, o.steps);
        return runSearch<Cfg>(o, eng, sol, haveK ? &knownK : NULL);
    }
#ifndef ECC_NO_CUDA
    CudaEngine<Cfg> eng;
    if (o.preferL1)
        CUDA_CHECK(cudaFuncSetCacheConfig(eccWalkKernel<Cfg, DeviceWord>, cudaFuncCachePreferL1));
#else
    HostEngine<Cfg> eng;
#endif
    if (o.threads <= 0) o.threads = eng.autoThreads(o.device);
    eng.setup(o, px, py, qx, qy);
    printf("backend %s: %d threads x %d slots x %d lanes = %llu walks, dp weight %d, %d steps per launch\n",
           eng.name(), o.threads, (int)ECC_BATCH, (int)WordTraits<typename decltype(eng)::W>::LANES,
           (unsigned long long)eng.walksPerLaunch(), o.dpWeight, o.steps);
    return runSearch<Cfg>(o, eng, sol, haveK ? &knownK : NULL);
}

// ---------------------------------------------------------------------------
static void usage() {
    printf(
        "ecc2k130 - Pollard rho client for the Certicom ECC2K-130 challenge\n"
        "\n"
        "  --curve M        131 (ECC2K-130) or 97 (ECC2K-95); 83/41/23/19/13 are tests\n"
        "  --poly-basis     for curve 41, use the polynomial-basis backend\n"
        "  --instance I     use planted test instance I (small curves only)\n"
        "  --threads T      worker threads (device: total threads)\n"
        "  --steps S        iterations per launch (default 64)\n"
        "  --launches L     stop after L launches (0 = until solved)\n"
        "  --dp-weight W    distinguished point when the normal-basis weight is <= W\n"
        "  --max-iters N    restart a walk that has run N steps without a report\n"
        "  --run-id R       16-bit salt making seeds unique across processes\n"
        "  --verify N       recompute the first N reported points with the reference\n"
        "  --ref            walk on the scalar reference arithmetic (toy curves; slow)\n"
        "  --dp-file F      append distinguished points to F (binary, 32 bytes each)\n"
        "  --load F         preload a corpus file so collisions with earlier runs count\n"
        "  --load-max N     stop reloading after N points (0 = no limit), newest file first\n"
        "  --checkpoint F   save and resume walk state through F\n"
        "  --checkpoint-every S   seconds between checkpoints (default 300)\n"
        "  --bench          throughput only, no distinguished-point handling\n"
        "  --packed         packed CUDA backend for GF(2^131); one walk per slot\n"
        "  --prefer-l1      request more L1 cache for the CUDA walk kernel\n"
        "  --test           run the validation suite and exit\n"
        "  --device D       CUDA device index\n"
        "\n"
        "Build-time: ECC_BATCH=%d slots per thread, ECC_THREADS block size.\n",
        (int)ECC_BATCH);
}

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IOLBF, 0);   // stream progress when piped to a file
    signal(SIGINT, onStop);
    signal(SIGTERM, onStop);
    Options o;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        const char *nx = (i + 1 < argc) ? argv[i + 1] : NULL;
        if (a == "--curve" && nx) o.curve = atoi(argv[++i]);
        else if (a == "--instance" && nx) o.instance = atoi(argv[++i]);
        else if (a == "--threads" && nx) o.threads = atoi(argv[++i]);
        else if (a == "--steps" && nx) o.steps = atoi(argv[++i]);
        else if (a == "--launches" && nx) o.launches = atol(argv[++i]);
        else if (a == "--dp-weight" && nx) o.dpWeight = atoi(argv[++i]);
        else if (a == "--max-iters" && nx) o.maxIters = strtoull(argv[++i], NULL, 10);
        else if (a == "--run-id" && nx) o.runId = (unsigned)atoi(argv[++i]);
        else if (a == "--verify" && nx) o.verify = atoi(argv[++i]);
        else if (a == "--ref") o.refEngine = true;
        else if (a == "--dp-cap" && nx) o.dpCap = (unsigned)atoi(argv[++i]);
        else if (a == "--dp-file" && nx) o.dpFile = argv[++i];
        else if (a == "--load" && nx) o.loadFiles.push_back(argv[++i]);
        else if (a == "--load-max" && nx) o.loadMax = strtoull(argv[++i], 0, 10);
        else if (a == "--checkpoint" && nx) o.ckptFile = argv[++i];
        else if (a == "--checkpoint-every" && nx) o.ckptSeconds = atof(argv[++i]);
        else if (a == "--device" && nx) o.device = atoi(argv[++i]);
        else if (a == "--bench") o.bench = true;
        else if (a == "--packed") o.packed = true;
        else if (a == "--prefer-l1") o.preferL1 = true;
        else if (a == "--poly-basis") o.polyBasis = true;
        else if (a == "--test") o.test = true;
        else if (a == "--help" || a == "-h") { usage(); return 0; }
        else { printf("unknown option %s\n", a.c_str()); usage(); return 1; }
    }
    if (o.packed && (o.curve != 131 || o.polyBasis || o.test)) {
        fprintf(stderr, "--packed selects the GF(2^131) CUDA walk; use --verify for device report validation and make test-packed for host arithmetic\n");
        return 1;
    }
    if (o.runId > 65535 || o.steps <= 0 || o.launches < 0 || o.dpCap == 0 ||
        o.dpWeight < -1 || o.dpWeight > o.curve || !(o.ckptSeconds > 0) ||
        o.maxIters > ~u64(0) - (ECC_GUARD_PERIOD - 1)) {
        fprintf(stderr, "invalid run-id, launch, DP or checkpoint parameters\n");
        return 1;
    }
    // The device thread count is left at 0 here on purpose: it depends on the
    // register allocation of a kernel that is only instantiated once the curve
    // is known, so CudaEngine::autoThreads decides it in runCurve.
#ifdef ECC_NO_CUDA
    if (o.packed) { fprintf(stderr, "--packed requires the CUDA client\n"); return 1; }
    if (o.threads <= 0) {
#ifdef _OPENMP
        o.threads = omp_get_max_threads();
#else
        o.threads = 1;
#endif
    }
#endif
#ifndef ECC_NO_CUDA
    CUDA_CHECK(cudaSetDevice(o.device));
#endif
    if (o.bench) o.dpWeight = 0;

    if (o.test) {
        printf("ECC2K-130 validation suite\n");
        int rc = 0;
        rc |= runCurve<CfgF23>(o, eccF23::PX, eccF23::PY, eccF23::QX, eccF23::QY,
                               eccF23::ELL_DEC, eccF23::S_DEC, eccF23::DP_WEIGHT, NULL);
        rc |= runCurve<CfgF41>(o, eccF41::PX, eccF41::PY, eccF41::QX, eccF41::QY,
                               eccF41::ELL_DEC, eccF41::S_DEC, eccF41::DP_WEIGHT, NULL);
        rc |= runCurve<CfgF83>(o, eccF83::PX, eccF83::PY, eccF83::QX, eccF83::QY,
                               eccF83::ELL_DEC, eccF83::S_DEC, eccF83::DP_WEIGHT, NULL);
        rc |= runCurve<CfgF131>(o, eccF131::PX, eccF131::PY, eccF131::QX, eccF131::QY,
                                eccF131::ELL_DEC, eccF131::S_DEC, eccF131::DP_WEIGHT, NULL);
        rc |= runCurve<CfgP13>(o, eccP13::PX, eccP13::PY, eccP13::QX, eccP13::QY,
                               eccP13::ELL_DEC, eccP13::S_DEC, eccP13::DP_WEIGHT, NULL);
        rc |= runCurve<CfgP19>(o, eccP19::PX, eccP19::PY, eccP19::QX, eccP19::QY,
                               eccP19::ELL_DEC, eccP19::S_DEC, eccP19::DP_WEIGHT, NULL);
        rc |= runCurve<CfgP41>(o, eccP41::PX, eccP41::PY, eccP41::QX, eccP41::QY,
                               eccP41::ELL_DEC, eccP41::S_DEC, eccP41::DP_WEIGHT, NULL);
        rc |= runCurve<CfgP97>(o, eccP97::PX, eccP97::PY, eccP97::QX, eccP97::QY,
                               eccP97::ELL_DEC, eccP97::S_DEC, eccP97::DP_WEIGHT, eccP97::KNOWN_K);
        printf("%s (%d failures)\n", gFail ? "VALIDATION FAILED" : "all checks passed", gFail);
        return (rc || gFail) ? 1 : 0;
    }

#define ECC_DISPATCH(NS, CFG)                                                                 \
    do {                                                                                      \
        const unsigned long long *px = NS::PX, *py = NS::PY, *qx = NS::QX, *qy = NS::QY;       \
        const char *kk = NULL;                                                                 \
        if (o.instance >= 0 && o.instance < NS::NUM_INSTANCES) {                              \
            px = NS::INSTANCE_PX[o.instance];                                                  \
            py = NS::INSTANCE_PY[o.instance];                                                  \
            qx = NS::INSTANCE_QX[o.instance];                                                  \
            qy = NS::INSTANCE_QY[o.instance];                                                  \
            kk = NS::INSTANCE_K[o.instance];                                                   \
        } else if (o.instance >= 0) {                                                          \
            printf("curve %d has %d planted instances\n", o.curve, NS::NUM_INSTANCES);        \
            return 1;                                                                          \
        }                                                                                      \
        return runCurve<CFG>(o, px, py, qx, qy, NS::ELL_DEC, NS::S_DEC, NS::DP_WEIGHT, kk);   \
    } while (0)

    if (o.curve == 131) ECC_DISPATCH(eccF131, CfgF131);
    if (o.curve == 83) ECC_DISPATCH(eccF83, CfgF83);
    if (o.curve == 41 && !o.polyBasis) ECC_DISPATCH(eccF41, CfgF41);
    if (o.curve == 23) ECC_DISPATCH(eccF23, CfgF23);
    if (o.curve == 97) ECC_DISPATCH(eccP97, CfgP97);
    if (o.curve == 41 && o.polyBasis) ECC_DISPATCH(eccP41, CfgP41);
    if (o.curve == 19) ECC_DISPATCH(eccP19, CfgP19);
    if (o.curve == 13) ECC_DISPATCH(eccP13, CfgP13);
    printf("unsupported curve %d\n", o.curve);
    return 1;
}
