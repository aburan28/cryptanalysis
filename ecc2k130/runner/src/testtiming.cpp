// Deterministic timing regression: exercise the real search loop with a fake
// asynchronous backend. No arithmetic kernels or collision solver are run.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <time.h>
#include <unistd.h>

static long timingSeconds = 0;
static int timingClockGettime(clockid_t, struct timespec *ts) {
    ts->tv_sec = timingSeconds;
    ts->tv_nsec = 0;
    return 0;
}

#define ECC_NO_CUDA
#define clock_gettime timingClockGettime
#define main unusedClientMain
#ifndef ECC_TIMING_SOURCE
#define ECC_TIMING_SOURCE "main.cu"
#endif
#include ECC_TIMING_SOURCE
#undef main
#undef clock_gettime

struct PendingEngine {
    bool restart;
    bool pending = false;
    int launches = 0, reseeds = 0, syncs = 0, saves = 0;

    void launch(u64) { ++launches; ++timingSeconds; }
    unsigned fetch(std::vector<DpRecord> &out) {
        ++timingSeconds;
        out.clear();
        return 0;
    }
    bool needsReseed() const { return restart; }
    void reseed(u64) { ++reseeds; pending = true; }
    void synchronize() {
        ++syncs;
        if (pending) timingSeconds += 2;
        pending = false;
    }
    bool restore(const char *, u64 *iterBase, unsigned) {
        *iterBase = 40;
        return true;
    }
    bool save(const char *, u64, unsigned) {
        ++saves;
        synchronize();
        return true;
    }
    u64 walksPerLaunch() const { return 4000000; }
};

static bool timingCase(bool restart, bool checkpoint, bool stopped) {
    timingSeconds = 0;
    gStop = stopped;
    Options options;
    options.steps = 2;
    options.launches = stopped ? 3 : 1;
    options.verify = 0;
    if (checkpoint) options.ckptFile = "synthetic-checkpoint";
    PendingEngine engine{restart};
    Solver<CfgF23> unusedSolver;

    FILE *capture = tmpfile();
    if (!capture) return false;
    fflush(stdout);
    const int savedStdout = dup(fileno(stdout));
    if (savedStdout < 0 || dup2(fileno(capture), fileno(stdout)) < 0) return false;
    const int result = runSearch<CfgF23>(options, engine, unusedSolver, nullptr);
    fflush(stdout);
    if (dup2(savedStdout, fileno(stdout)) < 0) return false;
    close(savedStdout);
    rewind(capture);
    std::string output;
    char chunk[1024];
    for (size_t n; (n = fread(chunk, 1, sizeof chunk, capture));) output.append(chunk, n);
    fclose(capture);
    gStop = 0;

    const char *expected = restart ? "finished: 2.000 M it/s" : "finished: 4.000 M it/s";
    const bool ok = result == 0 && engine.launches == 1 && !engine.pending &&
                    engine.reseeds == int(restart) && engine.saves == int(checkpoint) &&
                    engine.syncs == 1 + int(checkpoint) &&
                    timingSeconds == (restart ? 4 : 2) &&
                    output.find(expected) != std::string::npos;
    if (!ok) {
        fprintf(stderr, "timing mismatch: restart=%d checkpoint=%d stopped=%d "
                "pending=%d syncs=%d clock=%ld\n%s", restart, checkpoint, stopped,
                engine.pending, engine.syncs, timingSeconds, output.c_str());
    }
    return ok;
}

int main() {
    HostEngine<CfgF23> host;
    host.synchronize();
    if (!timingCase(false, false, false) || !timingCase(true, false, false) ||
        !timingCase(true, true, false) || !timingCase(true, false, true)) return 1;
    puts("PASS: final timing waits for pending reseeds; no-reseed, checkpoint/resume, "
         "and interrupted-run controls retain their counts");
}
