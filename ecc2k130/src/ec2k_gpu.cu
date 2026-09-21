/*
 * ec2k_gpu.cu - the ECC2K-130 Pollard rho GPU client.
 *
 *   ec2k-gpu bench   [--steps S] [--launches L] [--threads T]
 *   ec2k-gpu walk    --run-id R [--dp-weight W] [--dp-file F] [--verify N] ...
 *   ec2k-gpu check   [--rounds N]          (host only: arithmetic vs the model)
 *
 * One process drives one device.  The kernel (include/packedkernels.cuh) is
 * the packed GF(2^131) table walk imported from github.com/aburan28/crypto:
 * one walk per thread-slot, five 32-bit words per coordinate, products on the
 * carry-less multiplier (clmad, sm_80+, CUDA 13.3+), one batched inversion
 * per 16 slots.  ecc2k130/README.md gives the measured rate and how it was
 * reached; this file is only the host that feeds it.
 *
 * What the host does per launch: run the walk kernel for `steps` steps over
 * every lane, read back the distinguished points it found (a lane that finds
 * one marks itself dead), append them to the corpus, re-walk the first
 * `--verify` of them on the golden model in fpga/model, and revive the dead
 * lanes from their incremented seeds.  Reports are 64-byte records: seed,
 * iteration count, x, y -- so a report is checkable by anyone who knows P and
 * Q, and a collision is two records with the same (x, y) up to Frobenius and
 * negation under different seeds, which `ec2k merge` in fpga/host finds on
 * the 32-byte record it shares with the FPGA core (this client writes both).
 *
 * The base and target points come from seeds (--p-seed, --q-seed): the
 * published challenge points belong in a campaign definition, not here, and
 * a run against the challenge needs only to pass them in.
 */
#include "hostcheck.h"

#include <cuda_runtime.h>

#include <stdlib.h>
#include <string.h>
#include <time.h>

#include <algorithm>
#include <string>
#include <vector>

#include "../include/packedkernels.cuh"

#define CUDA_CHECK(call)                                                                           \
    do {                                                                                           \
        cudaError_t err_ = (call);                                                                 \
        if (err_ != cudaSuccess) {                                                                 \
            fprintf(stderr, "CUDA error at %s:%d: %s\n", __FILE__, __LINE__,                       \
                    cudaGetErrorString(err_));                                                     \
            exit(3);                                                                               \
        }                                                                                          \
    } while (0)

using namespace ec2k_gpu;
using eccPacked131::P131;

namespace
{

struct Options {
    std::string cmd;
    int threads = 0; // 0: automatic, one wave of resident blocks
    int steps = 1024;
    int launches = 32;
    int dpWeight = EC2K_DP_WEIGHT;
    unsigned dpCap = 1u << 18;
    unsigned runId = 1;
    unsigned long long maxIters = 0;
    int verify = 0;
    int rounds = 64;
    int device = 0;
    uint64_t pSeed = 1, qSeed = 2;
    std::string dpFile, dpFile32;
};

int usage()
{
    fprintf(stderr,
            "usage: ec2k-gpu <bench|walk|check> [options]\n"
            "  --steps S        iterations per launch (default 1024)\n"
            "  --launches L     launches (default 32; 0 = run until interrupted)\n"
            "  --threads T      worker threads (default: automatic, multiple of 256)\n"
            "  --dp-weight W    distinguished when HW(x) <= W (default %d; bench: none)\n"
            "  --dp-cap N       report buffer capacity per launch (default 262144)\n"
            "  --run-id R       16-bit run id; distinct runs never share a trail\n"
            "  --max-iters N    restart a lane that walked N steps without a report\n"
            "  --verify N       re-walk the first N reports on the golden model\n"
            "  --dp-file F      append 64-byte (seed, iters, x, y) records to F\n"
            "  --dp-file32 F    append fpga/host-compatible 32-byte (seed, orbit-min x) records\n"
            "  --p-seed S, --q-seed S   the base and target points, from seeds (1, 2)\n"
            "  --rounds N       check: random inputs per routine (default 64)\n"
            "  --device D       CUDA device index\n",
            EC2K_DP_WEIGHT);
    return 2;
}

const char *opt(int argc, char **argv, const char *name)
{
    for (int i = 2; i + 1 < argc; i++)
        if (!strcmp(argv[i], name)) return argv[i + 1];
    return nullptr;
}

unsigned long long optU64(int argc, char **argv, const char *name, unsigned long long def)
{
    const char *v = opt(argc, argv, name);
    return v ? strtoull(v, nullptr, 0) : def;
}

double now()
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

/* ---- the device engine ------------------------------------------------- */

struct Engine {
    WalkParams<unsigned> P{};
    unsigned *fieldBlob = nullptr;
    unsigned *twConsts = nullptr;
    size_t fieldWords = 0;

    size_t laneCount() const { return size_t(P.threads) * ECC_BATCH; }

    static int autoThreads(int device)
    {
        cudaDeviceProp prop;
        CUDA_CHECK(cudaGetDeviceProperties(&prop, device));
        int blocks = 0;
        CUDA_CHECK(cudaOccupancyMaxActiveBlocksPerMultiprocessor(
            &blocks, eccPacked131::walk, ECC_THREADS, eccPacked131::TW_SHARED_BYTES));
        if (blocks < 1) blocks = 1;
        size_t threads = size_t(prop.multiProcessorCount) * ECC_THREADS * blocks;
        threads -= threads % 256;
        printf("device: %s, %d SMs, %d block(s) of %d threads resident per SM, %zu threads\n",
               prop.name, prop.multiProcessorCount, blocks, ECC_THREADS, threads);
        return int(threads);
    }

    void setup(const Options &o, const HostTable &table)
    {
        if (eccPacked131::TW_SHARED_BYTES > 48 * 1024)
            CUDA_CHECK(cudaFuncSetAttribute(eccPacked131::walk,
                                            cudaFuncAttributeMaxDynamicSharedMemorySize,
                                            int(eccPacked131::TW_SHARED_BYTES)));
        P.threads = o.threads;
        P.steps = o.steps;
        P.dpWeight = o.dpWeight;
        P.runId = o.runId;
        P.maxIters = o.maxIters;
        P.iterBase = 0;
        P.dpCap = o.dpCap;

        // x, y and the prefix chain in one contiguous allocation so that one
        // L2 access-policy window covers them.  Compact storage: 16-byte low
        // records plus a tail-byte plane per 256-thread tile.
        fieldWords = eccPacked131::compactPhysicalFieldWords(size_t(P.threads));
        const size_t bytes = fieldWords * sizeof(unsigned);
        CUDA_CHECK(cudaMalloc(&fieldBlob, bytes * 3));
        CUDA_CHECK(cudaMemset(fieldBlob, 0, bytes * 3));
        P.x = fieldBlob;
        P.y = fieldBlob + fieldWords;
        P.pchain = fieldBlob + 2 * fieldWords;
        persist(fieldBlob, bytes * 3);

        CUDA_CHECK(cudaMalloc(&P.dead, laneCount() * sizeof(unsigned)));
        CUDA_CHECK(cudaMalloc(&P.seed, laneCount() * sizeof(unsigned long long)));
        CUDA_CHECK(cudaMalloc(&P.startIter, laneCount() * sizeof(unsigned long long)));
        CUDA_CHECK(cudaMalloc(&P.hist, laneCount() * sizeof(unsigned long long)));
        CUDA_CHECK(cudaMalloc(&P.dp, size_t(P.dpCap) * sizeof(DpRecord)));
        CUDA_CHECK(cudaMalloc(&P.dpCount, 4 * sizeof(unsigned)));
        CUDA_CHECK(cudaMemset(P.dpCount, 0, 4 * sizeof(unsigned)));

        const std::vector<uint32_t> consts = table.deviceConsts();
        CUDA_CHECK(cudaMalloc(&twConsts, consts.size() * sizeof(uint32_t)));
        CUDA_CHECK(cudaMemcpy(twConsts, consts.data(), consts.size() * sizeof(uint32_t),
                              cudaMemcpyHostToDevice));
        P.twConsts = twConsts;

        // The start-point terms sigma^i(P) and the target Q, in the normal
        // basis: the init kernel adds them with the ONB arithmetic.
        P131 ox[128], oy[128];
        for (int i = 0; i < 128; ++i) {
            ox[i] = toPacked(table.orbitP[i].x);
            oy[i] = toPacked(table.orbitP[i].y);
        }
        const P131 qx = toPacked(table.Q.x), qy = toPacked(table.Q.y);
        CUDA_CHECK(cudaMemcpyToSymbol(eccPacked131::orbitX, ox, sizeof(ox)));
        CUDA_CHECK(cudaMemcpyToSymbol(eccPacked131::orbitY, oy, sizeof(oy)));
        CUDA_CHECK(cudaMemcpyToSymbol(eccPacked131::targetX, &qx, sizeof(qx)));
        CUDA_CHECK(cudaMemcpyToSymbol(eccPacked131::targetY, &qy, sizeof(qy)));

        cudaFuncAttributes attrs;
        CUDA_CHECK(cudaFuncGetAttributes(&attrs, eccPacked131::walk));
        printf("kernel: %d registers/thread, %zu local bytes/thread, %zu dynamic shared "
               "bytes/block, batch %d, block %d x %d\n",
               attrs.numRegs, attrs.localSizeBytes, eccPacked131::TW_SHARED_BYTES, ECC_BATCH,
               ECC_THREADS, ECC_MINBLOCKS);
        init(false, 0);
    }

    // Keep the walk state resident in L2: on the RTX PRO 6000 the persisting
    // window is 80 MiB and x/y/pchain at the automatic thread count is 78.5 MB.
    static void persist(void *base, size_t bytes)
    {
        int device = 0, maxPersist = 0;
        CUDA_CHECK(cudaGetDevice(&device));
        CUDA_CHECK(
            cudaDeviceGetAttribute(&maxPersist, cudaDevAttrMaxPersistingL2CacheSize, device));
        if (maxPersist <= 0) {
            printf("L2 persist window: not supported on this device\n");
            return;
        }
        CUDA_CHECK(cudaDeviceSetLimit(cudaLimitPersistingL2CacheSize, size_t(maxPersist)));
        CUDA_CHECK(cudaCtxResetPersistingL2Cache());
        cudaAccessPolicyWindow window = {};
        window.base_ptr = base;
        window.num_bytes = std::min(bytes, size_t(maxPersist));
        window.hitRatio = 1.0f;
        window.hitProp = cudaAccessPropertyPersisting;
        window.missProp = cudaAccessPropertyStreaming;
        cudaStreamAttrValue attr = {};
        attr.accessPolicyWindow = window;
        CUDA_CHECK(cudaStreamSetAttribute(0, cudaStreamAttributeAccessPolicyWindow, &attr));
        printf("L2 persist window: %zu of %zu state bytes, cap %d\n", window.num_bytes, bytes,
               maxPersist);
    }

    // (Re)seed the lanes for walks that begin at global step `iterBase`, the
    // base of the next launch: a report's iteration count is measured from it.
    void init(bool reseed, unsigned long long iterBase)
    {
        P.iterBase = iterBase;
        const int blocks = int((laneCount() + ECC_THREADS - 1) / ECC_THREADS);
        eccPacked131::init<<<blocks, ECC_THREADS>>>(P, reseed);
        CUDA_CHECK(cudaGetLastError());
    }

    void launch(unsigned long long iterBase)
    {
        P.iterBase = iterBase;
        eccPacked131::walk<<<(P.threads + ECC_THREADS - 1) / ECC_THREADS, ECC_THREADS,
                             eccPacked131::TW_SHARED_BYTES>>>(P, nullptr);
        CUDA_CHECK(cudaGetLastError());
    }

    // Reports of the last launch; counts[1] overdue restarts, counts[2] a lane
    // whose 16-bit restart counter is exhausted.
    void fetch(std::vector<DpRecord> &out, unsigned counts[3])
    {
        CUDA_CHECK(cudaDeviceSynchronize());
        CUDA_CHECK(cudaMemcpy(counts, P.dpCount, 3 * sizeof(unsigned), cudaMemcpyDeviceToHost));
        const unsigned n = std::min(counts[0], P.dpCap);
        out.resize(n);
        if (n)
            CUDA_CHECK(
                cudaMemcpy(out.data(), P.dp, size_t(n) * sizeof(DpRecord), cudaMemcpyDeviceToHost));
        if (counts[0] || counts[1] || counts[2])
            CUDA_CHECK(cudaMemset(P.dpCount, 0, 3 * sizeof(unsigned)));
    }

    ~Engine()
    {
        cudaFree(fieldBlob);
        cudaFree(twConsts);
        cudaFree(P.dead);
        cudaFree(P.seed);
        cudaFree(P.startIter);
        cudaFree(P.hist);
        cudaFree(P.dp);
        cudaFree(P.dpCount);
    }
};

/* ---- the corpus ---------------------------------------------------------- */

struct Corpus {
    FILE *f64 = nullptr, *f32 = nullptr;
    unsigned long long written = 0;
    bool failed = false;

    bool open(const Options &o)
    {
        if (!o.dpFile.empty() && !(f64 = fopen(o.dpFile.c_str(), "ab"))) return false;
        if (!o.dpFile32.empty() && !(f32 = fopen(o.dpFile32.c_str(), "ab"))) return false;
        return true;
    }
    void append(const std::vector<DpRecord> &recs)
    {
        for (const DpRecord &r : recs) {
            if (f64 && fwrite(&r, sizeof(r), 1, f64) != 1) failed = true;
            if (f32) {
                // The FPGA core's record: seed, then the Frobenius-orbit
                // minimum of x, which is the negation- and Frobenius-class
                // invariant `ec2k merge` compares.
                ec2k_record rec;
                rec.seed = r.seed;
                ec2k_fe x;
                x.w[0] = r.x[0];
                x.w[1] = r.x[1];
                x.w[2] = r.x[2];
                ec2k_orbit_min(&rec.x, &x);
                uint8_t buf[EC2K_RECORD_BYTES];
                ec2k_record_encode(buf, &rec);
                if (fwrite(buf, 1, sizeof(buf), f32) != sizeof(buf)) failed = true;
            }
            written++;
        }
        if (f64) fflush(f64);
        if (f32) fflush(f32);
    }
    ~Corpus()
    {
        if (f64) fclose(f64);
        if (f32) fclose(f32);
    }
};

/* ---- commands ------------------------------------------------------------ */

int cmdCheck(const Options &o, const HostTable &table)
{
    const CheckResult cr = crossCheck(table, o.rounds, 0x243F6A8885A308D3ULL);
    if (cr.failures) {
        fprintf(stderr, "FAILED: %d of %d checks\n", cr.failures, cr.checks);
        return 1;
    }
    printf("{\"status\":\"ok\",\"checks\":%d,\"rounds\":%d}\n", cr.checks, o.rounds);
    return 0;
}

int cmdRun(Options o, const HostTable &table, bool bench)
{
    CUDA_CHECK(cudaSetDevice(o.device));
    if (o.threads <= 0) o.threads = Engine::autoThreads(o.device);
    if (o.threads % 256) {
        fprintf(stderr, "--threads must be a multiple of 256 (compact state tiles)\n");
        return 2;
    }
    if (bench) o.dpWeight = -1; // no lane ever reports
    Engine e;
    e.setup(o, table);
    Corpus corpus;
    if (!bench && !corpus.open(o)) {
        fprintf(stderr, "cannot open the corpus file for appending\n");
        return 1;
    }
    printf("walks: %d threads x %d slots = %zu, %d steps per launch, dp weight %d, run id %u\n",
           o.threads, ECC_BATCH, e.laneCount(), o.steps, o.dpWeight, o.runId);

    CUDA_CHECK(cudaDeviceSynchronize());
    const double t0 = now();
    unsigned long long iterations = 0, reports = 0, verified = 0, badReports = 0, restarts = 0,
                       dropped = 0;
    std::vector<DpRecord> recs;
    for (int l = 0; o.launches == 0 || l < o.launches; ++l) {
        e.launch(iterations / e.laneCount());
        unsigned counts[3] = {0, 0, 0};
        e.fetch(recs, counts);
        iterations += e.laneCount() * (unsigned long long)o.steps;
        reports += recs.size();
        restarts += counts[1];
        if (counts[0] > o.dpCap) dropped += counts[0] - o.dpCap;
        if (counts[2]) {
            fprintf(stderr, "a lane exhausted its 16-bit restart counter; use a new run id\n");
            return 1;
        }
        for (size_t i = 0; i < recs.size() && verified < (unsigned long long)o.verify; ++i) {
            verified++;
            if (!rewalk(table, recs[i], nullptr)) {
                badReports++;
                fprintf(stderr, "report does not re-walk: seed %llu, %llu iterations\n",
                        recs[i].seed, recs[i].iters);
            }
        }
        if (!bench) corpus.append(recs);
        if (!recs.empty() || counts[1]) e.init(true, iterations / e.laneCount());
        const double dt = now() - t0;
        if (bench || (l & 7) == 7 || (o.launches && l + 1 == o.launches))
            printf("  %7.1f s  %10.3f M it/s  %llu iterations  %llu dp  %llu restarts  %llu "
                   "dropped\n",
                   dt, dt > 0 ? (double)iterations / dt / 1e6 : 0.0, iterations, reports, restarts,
                   dropped);
    }
    CUDA_CHECK(cudaDeviceSynchronize());
    const double dt = now() - t0;
    if (corpus.failed) {
        fprintf(stderr, "writing the corpus failed\n");
        return 1;
    }
    printf("{\"status\":\"%s\",\"cmd\":\"%s\",\"iterations\":%llu,\"seconds\":%.3f,"
           "\"iterationsPerSecond\":%.0f,\"reports\":%llu,\"verified\":%llu,\"badReports\":%llu,"
           "\"restarts\":%llu,\"dropped\":%llu,\"threads\":%d,\"batch\":%d,\"steps\":%d,"
           "\"dpWeight\":%d,\"runId\":%u}\n",
           badReports ? "mismatch" : "ok", bench ? "bench" : "walk", iterations, dt,
           dt > 0 ? (double)iterations / dt : 0.0, reports, verified, badReports, restarts, dropped,
           o.threads, ECC_BATCH, o.steps, o.dpWeight, o.runId);
    return badReports ? 1 : 0;
}

} // namespace

int main(int argc, char **argv)
{
    if (argc < 2) return usage();
    Options o;
    o.cmd = argv[1];
    o.steps = (int)optU64(argc, argv, "--steps", (unsigned long long)o.steps);
    o.launches = (int)optU64(argc, argv, "--launches", (unsigned long long)o.launches);
    o.threads = (int)optU64(argc, argv, "--threads", 0);
    o.dpWeight = (int)optU64(argc, argv, "--dp-weight", (unsigned long long)o.dpWeight);
    o.dpCap = (unsigned)optU64(argc, argv, "--dp-cap", o.dpCap);
    o.runId = (unsigned)optU64(argc, argv, "--run-id", o.runId) & 0xFFFFu;
    o.maxIters = optU64(argc, argv, "--max-iters", 0);
    o.verify = (int)optU64(argc, argv, "--verify", 0);
    o.rounds = (int)optU64(argc, argv, "--rounds", (unsigned long long)o.rounds);
    o.device = (int)optU64(argc, argv, "--device", 0);
    o.pSeed = optU64(argc, argv, "--p-seed", 1);
    o.qSeed = optU64(argc, argv, "--q-seed", 2);
    if (const char *v = opt(argc, argv, "--dp-file")) o.dpFile = v;
    if (const char *v = opt(argc, argv, "--dp-file32")) o.dpFile32 = v;
    if (o.steps <= 0 || o.launches < 0 || o.dpCap == 0) return usage();

    ec2k_pt P, Q;
    ec2k_point_from_seed(&P, o.pSeed);
    ec2k_point_from_seed(&Q, o.qSeed);
    HostTable *table = new HostTable;
    table->build(P, Q);

    int rc;
    if (o.cmd == "check")
        rc = cmdCheck(o, *table);
    else if (o.cmd == "bench")
        rc = cmdRun(o, *table, true);
    else if (o.cmd == "walk")
        rc = cmdRun(o, *table, false);
    else
        rc = usage();
    delete table;
    return rc;
}
