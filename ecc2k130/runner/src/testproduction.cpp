// Test the REAL host search/persistence code under deterministic I/O faults.
// Fault switches exist only in this translation unit, never the client binary.
#include <cstdio>
#include <cerrno>
#include <unistd.h>
#include <string>
static bool failWrite = false, failSync = false;
static size_t checkedFwrite(const void *p, size_t s, size_t n, FILE *f) {
    if (failWrite) { errno = ENOSPC; return 0; }
    return fwrite(p, s, n, f);
}
static int checkedFsync(int fd) {
    if (failSync) { errno = EIO; return -1; }
    return fsync(fd);
}
#ifndef ECC_NO_CUDA
#define ECC_NO_CUDA
#endif
#define main clientMain
#define fwrite checkedFwrite
#define fsync checkedFsync
#include "main.cu"
#undef fsync
#undef fwrite
#undef main

static void require(bool ok, const char *message) {
    if (!ok) { fprintf(stderr, "FAIL: %s\n", message); exit(1); }
}

static Solver<CfgF41> fixtureSolver() {
    Solver<CfgF41> s;
    s.setup(eccF41::PX, eccF41::PY, eccF41::QX, eccF41::QY,
            eccF41::ELL_DEC, eccF41::S_DEC, eccF41::DP_WEIGHT, 100000);
    return s;
}

struct FaultEngine {
    DpRecord rec{};
    unsigned count = 1;
    int saves = 0, reseeds = 0;
    bool syncFault = false;
    void launch(u64) { if (syncFault) failSync = true; }
    unsigned fetch(std::vector<DpRecord> &out) { out.assign(1, rec); return count; }
    bool needsReseed() const { return false; }
    void reseed(u64) { ++reseeds; }
    void synchronize() {}
    bool restore(const char *, u64 *it, unsigned) { *it = 0; return true; }
    bool save(const char *, u64, unsigned) { ++saves; return true; }
    u64 walksPerLaunch() const { return 1; }
};

int main(int argc, char **argv) {
    using R = Ref<CfgF41>;
    auto sol = fixtureSolver();
    // A known cross-run collision on the fixture instance.  The seeds depend
    // on the iteration function, the discrete log they resolve to does not.
#if ECC_WALK_TABLE
    const u64 a = 0x0002000001c30000ull, b = 0x0001000002740000ull;
#else
    const u64 a = 0x0002000048880000ull, b = 0x000100004cf60000ull;
#endif
    const auto A = sol.rewalk(a), B = sol.rewalk(b);
    require(A.ok && B.ok, "fixture endpoints reachable");
    const auto key = R::canonical(A.endPoint.x);
    require(key == R::canonical(B.endPoint.x), "fixture same orbit");
    U192 k; std::string why;
    require(sol.solve(A, B, &k, &why), "fixture scalar independently verified");
    require(u192_to_dec(k) == "369250562913", "fixture known discrete log");
    if (argc == 2 && std::string(argv[1]) == "--fixture") {
        printf("{\"curve\":41,\"weight\":%d,\"k\":\"%s\",\"seedA\":%llu,\"seedB\":%llu,"
               "\"key\":[%llu,%llu,%llu],\"iterations\":[%llu,%llu]}\n",
               sol.dpWeight, u192_to_dec(k).c_str(), a, b, key.v[0], key.v[1], key.v[2], A.iters, B.iters);
        return 0;
    }
    char pattern[] = "/tmp/ecc-production-XXXXXX";
    char *root = mkdtemp(pattern);
    require(root != nullptr, "temporary test directory");
    for (int mode = 0; mode < 4; ++mode) {
        Options o;
        o.steps = 1; o.launches = 1; o.verify = 0;
        o.dpFile = std::string(root) + "/case-" + std::to_string(mode) + ".bin";
        o.ckptFile = std::string(root) + "/fake.ck";
        FaultEngine engine;
        engine.rec.seed = a;
        engine.rec.iters = A.iters;
        memcpy(engine.rec.x, A.endPoint.x.v, sizeof engine.rec.x);
        memcpy(engine.rec.y, A.endPoint.y.v, sizeof engine.rec.y);
        engine.count = mode == 0 ? 2 : 1;
        failWrite = mode == 1;
        engine.syncFault = mode == 2;
        auto fresh = fixtureSolver();
        const int rc = runSearch<CfgF41>(o, engine, fresh, nullptr);
        failWrite = failSync = false;
        require(rc == (mode == 0 ? 7 : mode < 3 ? 8 : 0), "fault exit code");
        require(engine.saves == (mode == 3 ? 1 : 0), "no checkpoint after lost/uncommitted reports");
        require(mode != 0 || engine.reseeds == 0, "no reseed after report overflow");
    }
    // The baseline bitsliced cycle guard used to emit non-DPs. It must only
    // request a restart, just as the packed backend does.
    {
        Options o; o.threads = 1; o.steps = 1; o.dpWeight = 0;
        o.maxIters = 1; o.dpCap = 65536;
        HostEngine<CfgF41> eng;
        eng.setup(o, eccF41::PX, eccF41::PY, eccF41::QX, eccF41::QY);
        eng.launch(ECC_GUARD_PERIOD);
        std::vector<DpRecord> records;
        require(eng.fetch(records) == 0, "overdue walks are not distinguished points");
        require(eng.needsReseed(), "overdue walks request reseeding");
        eng.reseed(ECC_GUARD_PERIOD + 1);
        for (auto dead : eng.dead) require(dead == 0, "overdue walks revived");
        // A 16-bit restart counter must not bleed into another walk's seed.
        eng.seed[0] |= 0xffffull;
        eng.P.dpWeight = CfgF41::M;
        eng.launch(ECC_GUARD_PERIOD + 1);
        require(eng.fetch(records) == ECC_SEED_EXHAUSTED, "seed counter wrap rejected");
    }
    printf("PASS: deterministic collision fixture, overflow/write/fsync fault isolation, cycle guard\n");
}
