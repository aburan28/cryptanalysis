// The walks behind the client's distinguished points, one orbit at a time.
//
// The client records only (seed, canonical endpoint) per distinguished point,
// which is all a collision needs.  This tool walks seeds with the reference
// implementation -- the same start-point derivation, iteration function and
// distinguishing test the client verifies its own reports against under
// --verify -- and prints every orbit a walk passes through on its way to its
// distinguished point.  scripts/site/walk_forest.py reads that and draws the
// forest the trails form, for the campaign status page.
//
// Two modes, one output format:
//
//   --corpus F        replay the records in the client's --dp-file F.  A trail
//                     whose last orbit is not the one the record names is an
//                     error, not a drawing.
//   --generate        walk the client's own seed schedule for --run-id R,
//                     lanes 0 .. --walks-1, exactly as the client would, but
//                     without stopping at the first collision the way a
//                     search does.  On a curve small enough to draw, a search
//                     solves within its first launch, so its corpus holds only
//                     the handful of walks reported before that; this mode
//                     keeps every lane's first walk.  --check-corpus F then
//                     holds the trails to the client's real records: every
//                     record in F for a generated seed must end on the orbit
//                     the replay reached, and the count of records checked is
//                     printed in the header.  --corpus-out F writes the
//                     generated endpoints in the client's 32-byte record
//                     format, so the client can --load them.
//
//   --sample          the challenge curve.  The reference walks a few thousand
//                     steps a second, so this mode drives the client's own
//                     bitsliced kernel instead, walks every seed at most --cap
//                     steps, keeps the trails that reach their distinguished
//                     point inside that, samples each every --every steps plus
//                     its endpoint, and names every orbit by a hash prefix, so
//                     the output can be published where the orbits themselves
//                     cannot.  Seeds come from --corpus (each endpoint must be
//                     the orbit its record names) or --run-id/--walks.
//
// Build:  make trailforest            (plain C++, no GPU)
// Usage:  build/trailforest --curve 23 --instance 0 --corpus dps.bin [--max N] > trails.txt
//         build/trailforest --curve 23 --instance 0 --generate --run-id 1 --walks 40 \
//                           --check-corpus dps.bin --corpus-out forest.bin > trails.txt
//         build/trailforest --curve 131 --dp-weight 34 --sample --corpus dps.bin \
//                           --cap 65536 --every 512 --hashes-out forest.hashes > trails.txt
//
// Output, one record per line:
//
//   # curve 23 instance 0 dp-weight 7 mode generate run-id 1 walks 40 checked 3
//   walk <seed hex> <steps> <orbit0> <orbit1> ... <orbitN>
//
// where each orbit is the canonical representative of the x-coordinate's
// orbit under Frobenius (the collision key the store uses), as hex, and the
// last orbit on the line is the distinguished one.  <steps> is the number of
// iterations, so a line carries <steps> + 1 orbits.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#include <string>
#include <vector>

#include "../include/curveparams.h"
#include "../include/kernel.h"
#include "../include/solver.h"

#include <unordered_map>

struct DpFileRecord {
    unsigned long long seed;
    unsigned long long canon[3];
};
static_assert(sizeof(DpFileRecord) == 32, "corpus records must remain 32 bytes");

struct Options {
    int curve = 23;
    int instance = -1;
    int dpWeight = -1;
    bool polyBasis = false;
    bool generate = false;
    bool sample = false;
    unsigned runId = 1;
    unsigned long long walks = 40;
    unsigned long long max = 0;
    unsigned long long skip = 0;
    unsigned long long maxIters = 1ull << 32;
    unsigned long long every = 1024;
    unsigned long long cap = 1ull << 20;
    std::string corpus;
    std::string checkCorpus;
    std::string corpusOut;
    std::string hashesOut;
};

// ---------------------------------------------------------------------------
// SHA-256, for naming orbits on the challenge curve without publishing them.
// ---------------------------------------------------------------------------
struct Sha256 {
    static inline unsigned rotr(unsigned x, int n) { return (x >> n) | (x << (32 - n)); }
    static void digest(const unsigned char *msg, size_t len, unsigned char out[32]) {
        static const unsigned K[64] = {
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
            0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
            0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
            0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
            0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
        unsigned h[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                         0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
        std::vector<unsigned char> m(msg, msg + len);
        m.push_back(0x80);
        while (m.size() % 64 != 56) m.push_back(0);
        const unsigned long long bits = (unsigned long long)len * 8;
        for (int i = 7; i >= 0; --i) m.push_back((unsigned char)(bits >> (8 * i)));
        for (size_t off = 0; off < m.size(); off += 64) {
            unsigned w[64];
            for (int i = 0; i < 16; ++i)
                w[i] = ((unsigned)m[off + 4 * i] << 24) | ((unsigned)m[off + 4 * i + 1] << 16) |
                       ((unsigned)m[off + 4 * i + 2] << 8) | (unsigned)m[off + 4 * i + 3];
            for (int i = 16; i < 64; ++i) {
                const unsigned s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
                const unsigned s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
                w[i] = w[i - 16] + s0 + w[i - 7] + s1;
            }
            unsigned a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
            for (int i = 0; i < 64; ++i) {
                const unsigned S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
                const unsigned ch = (e & f) ^ (~e & g);
                const unsigned t1 = hh + S1 + ch + K[i] + w[i];
                const unsigned S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
                const unsigned maj = (a & b) ^ (a & c) ^ (b & c);
                const unsigned t2 = S0 + maj;
                hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
            }
            h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
        }
        for (int i = 0; i < 8; ++i) {
            out[4 * i] = (unsigned char)(h[i] >> 24);
            out[4 * i + 1] = (unsigned char)(h[i] >> 16);
            out[4 * i + 2] = (unsigned char)(h[i] >> 8);
            out[4 * i + 3] = (unsigned char)h[i];
        }
    }
};

// An orbit's public name: the first 16 hex digits of SHA-256 over the canonical
// representative's 24 little-endian bytes.  On the challenge curve the orbit
// itself is a distinguished-point key, which the campaign never publishes; a
// 64-bit prefix of a hash of a 131-bit value names it without revealing it.
static std::string orbitName(const unsigned long long *canon3) {
    unsigned char bytes[24];
    for (int l = 0; l < 3; ++l)
        for (int i = 0; i < 8; ++i) bytes[8 * l + i] = (unsigned char)(canon3[l] >> (8 * i));
    unsigned char d[32];
    Sha256::digest(bytes, sizeof bytes, d);
    char hex[17];
    for (int i = 0; i < 8; ++i) snprintf(hex + 2 * i, 3, "%02x", d[i]);
    return std::string(hex, 16);
}

// The client's seed for lane `walkIndex` of run `runId` (walk.h, eccSeedFor):
// a finished lane continues at seed + 1, so the low 16 bits count restarts.
static unsigned long long seedFor(unsigned runId, unsigned long long walkIndex) {
    return ((unsigned long long)runId << 48) | ((walkIndex & 0xFFFFFFFFull) << 16);
}

static bool readCorpus(const std::string &path, std::vector<DpFileRecord> *recs) {
    FILE *in = fopen(path.c_str(), "rb");
    struct stat st;
    if (!in || fstat(fileno(in), &st) != 0 || st.st_size % sizeof(DpFileRecord) != 0) {
        if (in) fclose(in);
        fprintf(stderr, "cannot read corpus %s (missing, or not a whole number of 32-byte records)\n",
                path.c_str());
        return false;
    }
    recs->resize((size_t)(st.st_size / sizeof(DpFileRecord)));
    const bool ok = recs->empty() || fread(recs->data(), sizeof(DpFileRecord), recs->size(), in) == recs->size();
    fclose(in);
    if (!ok) fprintf(stderr, "short read on %s\n", path.c_str());
    return ok;
}

static void printHex(const unsigned long long *v) {
    // 192 bits, most significant limb first, leading zeros dropped past the
    // first digit so a small field does not print as 48 zeros.
    char buf[64];
    int n = snprintf(buf, sizeof buf, "%llx%016llx%016llx", v[2], v[1], v[0]);
    int i = 0;
    while (i < n - 1 && buf[i] == '0') ++i;
    fputs(buf + i, stdout);
}

template <class Cfg>
static int sampleWalks(const Options &o, const unsigned long long *px, const unsigned long long *py,
                       const unsigned long long *qx, const unsigned long long *qy, int w);

template <class Cfg>
static int run(const Options &o, const unsigned long long *px, const unsigned long long *py,
               const unsigned long long *qx, const unsigned long long *qy, const char *ellDec,
               const char *sDec, int defaultW) {
    typedef Ref<Cfg> R;
    const int w = o.dpWeight < 0 ? defaultW : o.dpWeight;
    if (o.sample) return sampleWalks<Cfg>(o, px, py, qx, qy, w);
    Solver<Cfg> sol;
    sol.setup(px, py, qx, qy, ellDec, sDec, w, o.maxIters);
    std::string why;
    if (!sol.checkSetup(&why)) {
        fprintf(stderr, "parameter check failed: %s\n", why.c_str());
        return 5;
    }

    // Walk one seed to its distinguished point, collecting every orbit.
    auto walk = [&](unsigned long long seed, std::vector<typename R::Elem> *orbits) -> bool {
        U192 alpha;
        typename R::Point p = R::startPoint(seed, sol.basis, sol.target, &alpha, sol.ell, sol.spow);
        orbits->clear();
        for (unsigned long long it = 0;; ++it) {
            orbits->push_back(R::canonical(p.x));
            const int hw = R::weight(p.x);
            if (hw <= w) return true;
            if (it >= o.maxIters) {
                fprintf(stderr, "seed %016llx did not reach a distinguished point within %llu steps\n",
                        seed, o.maxIters);
                return false;
            }
            p = R::step(p, hw);
        }
    };
    auto emit = [](unsigned long long seed, const std::vector<typename R::Elem> &orbits) {
        printf("walk %016llx %zu", seed, orbits.size() - 1);
        for (size_t k = 0; k < orbits.size(); ++k) {
            putchar(' ');
            printHex(orbits[k].v);
        }
        putchar('\n');
    };
    auto sameKey = [](const typename R::Elem &e, const DpFileRecord &rec) {
        return e.v[0] == rec.canon[0] && e.v[1] == rec.canon[1] && e.v[2] == rec.canon[2];
    };

    std::vector<typename R::Elem> orbits;

    if (o.generate) {
        // The header comes first, so the record count it reports has to be
        // known before any trail is printed; the walks are cheap enough to
        // keep.
        std::vector<unsigned long long> seeds;
        std::vector<std::vector<typename R::Elem> > trails;
        for (unsigned long long i = 0; i < o.walks; ++i) {
            const unsigned long long seed = seedFor(o.runId, i);
            if (!walk(seed, &orbits)) return 3;
            seeds.push_back(seed);
            trails.push_back(orbits);
        }
        size_t checked = 0;
        if (!o.checkCorpus.empty()) {
            std::vector<DpFileRecord> recs;
            if (!readCorpus(o.checkCorpus, &recs)) return 8;
            for (size_t r = 0; r < recs.size(); ++r) {
                for (size_t i = 0; i < seeds.size(); ++i) {
                    if (recs[r].seed != seeds[i]) continue;
                    if (!sameKey(trails[i].back(), recs[r])) {
                        fprintf(stderr, "seed %016llx: the client's record ends on an orbit the replay did not reach\n",
                                recs[r].seed);
                        return 3;
                    }
                    ++checked;
                }
            }
            if (!checked) {
                fprintf(stderr, "no record in %s carries a generated seed; nothing was checked\n",
                        o.checkCorpus.c_str());
                return 3;
            }
        }
        if (!o.corpusOut.empty()) {
            FILE *out = fopen(o.corpusOut.c_str(), "wb");
            if (!out) { fprintf(stderr, "cannot write %s\n", o.corpusOut.c_str()); return 8; }
            for (size_t i = 0; i < seeds.size(); ++i) {
                DpFileRecord fr;
                fr.seed = seeds[i];
                fr.canon[0] = trails[i].back().v[0];
                fr.canon[1] = trails[i].back().v[1];
                fr.canon[2] = trails[i].back().v[2];
                if (fwrite(&fr, sizeof fr, 1, out) != 1) { fprintf(stderr, "short write on %s\n", o.corpusOut.c_str()); return 8; }
            }
            fclose(out);
        }
        printf("# curve %d instance %d dp-weight %d mode generate run-id %u walks %llu checked %zu\n",
               o.curve, o.instance, w, o.runId, o.walks, checked);
        for (size_t i = 0; i < seeds.size(); ++i) emit(seeds[i], trails[i]);
        return 0;
    }

    std::vector<DpFileRecord> recs;
    if (!readCorpus(o.corpus, &recs)) return 8;
    const size_t first = (size_t)(o.skip < recs.size() ? o.skip : recs.size());
    size_t last = recs.size();
    if (o.max && first + o.max < last) last = first + (size_t)o.max;

    printf("# curve %d instance %d dp-weight %d mode replay records %zu skip %zu drawn %zu\n",
           o.curve, o.instance, w, recs.size(), first, last - first);
    for (size_t i = first; i < last; ++i) {
        const DpFileRecord &rec = recs[i];
        if (!walk(rec.seed, &orbits)) return 3;
        if (!sameKey(orbits.back(), rec)) {
            fprintf(stderr, "seed %016llx: the replayed walk ends at an orbit the corpus does not record\n",
                    rec.seed);
            return 3;
        }
        emit(rec.seed, orbits);
    }
    return 0;
}

// ---------------------------------------------------------------------------
// --sample: the client's own bitsliced walk, on the challenge curve
// ---------------------------------------------------------------------------
// The scalar reference walks a few thousand steps a second, which is fine on
// a test curve and hopeless against a 2^25 step trail.  This mode drives the
// same Kernel the client runs -- every lane of every slot at once -- so a
// batch of seeds is walked at the client's own rate.  Every seed gets --cap
// steps at most; the trails that reach their distinguished point inside the
// cap are kept, sampled once every --every steps plus their endpoint, and
// named by hash.  With --corpus the seeds are the client's records and each
// endpoint must be the orbit its record names; with --run-id/--walks they
// are the seed schedule.
template <class Cfg>
static int sampleWalks(const Options &o, const unsigned long long *px, const unsigned long long *py,
                       const unsigned long long *qx, const unsigned long long *qy, int w) {
    typedef ECC_HOST_WORD W;
    typedef Kernel<Cfg, W> K;
    typedef Walk<Cfg, W> WK;
    typedef typename Cfg::template Field<W> F;
    typedef Ref<Cfg> R;
    const int M = Cfg::M;
    const int LANES = WordTraits<W>::LANES;
    const int BATCH = ECC_BATCH;
    const size_t perThread = (size_t)BATCH * LANES;

    std::vector<unsigned long long> seeds;
    std::vector<DpFileRecord> recs;
    if (!o.corpus.empty()) {
        if (!readCorpus(o.corpus, &recs)) return 8;
        const size_t first = (size_t)(o.skip < recs.size() ? o.skip : recs.size());
        size_t last = recs.size();
        if (o.max && first + o.max < last) last = first + (size_t)o.max;
        recs.assign(recs.begin() + first, recs.begin() + last);
        for (size_t i = 0; i < recs.size(); ++i) seeds.push_back(recs[i].seed);
    } else {
        for (unsigned long long i = 0; i < o.walks; ++i) seeds.push_back(seedFor(o.runId, i));
    }
    if (seeds.empty()) { fprintf(stderr, "nothing to walk\n"); return 1; }
    if (o.every == 0 || o.cap == 0 || o.cap % o.every != 0 || o.every > 0x7fffffffull) {
        fprintf(stderr, "--cap must be a positive multiple of --every\n");
        return 1;
    }
    const int threads = (int)((seeds.size() + perThread - 1) / perThread);
    std::unordered_map<unsigned long long, size_t> indexOf;
    for (size_t i = 0; i < seeds.size(); ++i) {
        if (!indexOf.emplace(seeds[i], i).second) {
            fprintf(stderr, "seed %016llx appears twice\n", seeds[i]);
            return 1;
        }
    }

    // State, laid out exactly as HostEngine lays it out.
    std::vector<W> x((size_t)threads * BATCH * M, ECC_ZERO), y(x.size(), ECC_ZERO), pchain(x.size(), ECC_ZERO);
    std::vector<W> dead((size_t)threads * BATCH, ECC_ZERO);
    std::vector<unsigned long long> seedTab((size_t)threads * perThread, 0), startIter(seedTab.size(), 0);
    std::vector<DpRecord> dp(seeds.size() + 1);
    unsigned dpCount[3] = {0, 0, 0};
    std::vector<unsigned long long> cpx(px, px + 3), cpy(py, py + 3), cqx(qx, qx + 3), cqy(qy, qy + 3);
    WalkParams<W> P;
    P.threads = threads;
    P.steps = (int)o.every;
    P.dpWeight = w;
    P.runId = 0;
    P.maxIters = 0;
    P.iterBase = 0;
    P.x = x.data();
    P.y = y.data();
    P.pchain = pchain.data();
    P.seed = seedTab.data();
    P.startIter = startIter.data();
    P.dead = dead.data();
    P.dp = dp.data();
    P.dpCount = dpCount;
    P.dpCap = (unsigned)dp.size();
    P.consts.px = cpx.data();
    P.consts.py = cpy.data();
    P.consts.qx = cqx.data();
    P.consts.qy = cqy.data();

    // Kernel::init, but seeded from the list.  Lanes past the end of the list
    // walk a filler seed with their reports suppressed, which is what the
    // kernel's dead mask is for.
    for (int tid = 0; tid < threads; ++tid) {
        W xs[Cfg::M], ys[Cfg::M];
        unsigned long long laneSeeds[WordTraits<W>::LANES];
        for (int slot = 0; slot < BATCH; ++slot) {
            W filler = ECC_ZERO;
            for (int lane = 0; lane < LANES; ++lane) {
                const size_t index = ((size_t)tid * BATCH + slot) * LANES + lane;
                const bool real = index < seeds.size();
                laneSeeds[lane] = real ? seeds[index] : seedFor(0xFFFFu, index);
                P.seed[K::laneIndex(slot, lane, tid, threads)] = laneSeeds[lane];
                P.startIter[K::laneIndex(slot, lane, tid, threads)] = 0;
                if (!real) filler = filler | laneMask<W>(lane);
            }
            WK::startPoint(laneSeeds, P.consts, xs, ys);
            K::store(P.x, slot, tid, threads, xs);
            K::store(P.y, slot, tid, threads, ys);
            P.dead[(size_t)slot * threads + tid] = filler;
        }
    }

    struct Trail {
        bool finished = false;
        unsigned long long steps = 0;
        std::vector<typename R::Elem> samples;   // raw x every `every` steps, from step 0
        typename R::Elem end;
    };
    std::vector<Trail> trails(seeds.size());
    auto sampleAll = [&]() {
        W xs[Cfg::M];
        unsigned long long limbs[3];
        for (int tid = 0; tid < threads; ++tid) {
            for (int slot = 0; slot < BATCH; ++slot) {
                const size_t base = ((size_t)tid * BATCH + slot) * LANES;
                if (base >= seeds.size()) break;
                K::load(P.x, slot, tid, threads, xs);
                for (int lane = 0; lane < LANES && base + lane < seeds.size(); ++lane) {
                    Trail &t = trails[base + lane];
                    if (t.finished) continue;
                    F::getLane(xs, lane, limbs);
                    t.samples.push_back(R::fromLimbs(limbs));
                }
            }
        }
    };
    auto collect = [&]() {
        const unsigned n = dpCount[0] < P.dpCap ? dpCount[0] : P.dpCap;
        for (unsigned i = 0; i < n; ++i) {
            const DpRecord &rec = dp[i];
            auto it = indexOf.find(rec.seed);
            if (it == indexOf.end()) continue;   // a filler lane can never report, but be safe
            Trail &t = trails[it->second];
            if (t.finished) continue;
            t.finished = true;
            t.steps = rec.iters;
            t.end = R::fromLimbs(rec.x);
        }
        dpCount[0] = dpCount[1] = dpCount[2] = 0;
    };

    sampleAll();
    size_t finished = 0;
    unsigned long long now = 0;
    while (now < o.cap) {
        P.iterBase = now;
        for (int tid = 0; tid < threads; ++tid) K::run(tid, P);
        now += o.every;
        collect();
        finished = 0;
        for (size_t i = 0; i < trails.size(); ++i) finished += trails[i].finished ? 1 : 0;
        if (finished == trails.size()) break;
        sampleAll();
        fprintf(stderr, "\r%llu steps, %zu of %zu finished", now, finished, trails.size());
    }
    fprintf(stderr, "\n");

    // Every finished trail's samples run from step 0 in strides of `every`;
    // the ones taken after its distinguished point are dropped, and the
    // endpoint is appended unless it fell exactly on a stride.
    size_t checked = 0;
    std::vector<size_t> drawn;
    for (size_t i = 0; i < trails.size(); ++i) {
        Trail &t = trails[i];
        if (!t.finished) continue;
        const size_t keep = (size_t)(t.steps / o.every) + 1;
        if (t.samples.size() > keep) t.samples.resize(keep);
        if (t.steps % o.every != 0) t.samples.push_back(t.end);
        else t.samples.back() = t.end;
        if (!recs.empty()) {
            const typename R::Elem c = R::canonical(t.end);
            if (c.v[0] != recs[i].canon[0] || c.v[1] != recs[i].canon[1] || c.v[2] != recs[i].canon[2]) {
                fprintf(stderr, "seed %016llx: the replayed walk ends on an orbit the record does not name\n", seeds[i]);
                return 3;
            }
            ++checked;
        }
        drawn.push_back(i);
    }

    FILE *hashes = 0;
    if (!o.hashesOut.empty()) {
        hashes = fopen(o.hashesOut.c_str(), "w");
        if (!hashes) { fprintf(stderr, "cannot write %s\n", o.hashesOut.c_str()); return 8; }
    }
    printf("# curve %d instance %d dp-weight %d mode sample source %s every %llu cap %llu tried %zu drawn %zu checked %zu hash sha256-16\n",
           o.curve, o.instance, w, recs.empty() ? "schedule" : "corpus", o.every, o.cap,
           trails.size(), drawn.size(), checked);
    for (size_t k = 0; k < drawn.size(); ++k) {
        const Trail &t = trails[drawn[k]];
        printf("walk %zu %llu", drawn[k], t.steps);
        std::string last;
        for (size_t s = 0; s < t.samples.size(); ++s) {
            const typename R::Elem c = R::canonical(t.samples[s]);
            last = orbitName(c.v);
            printf(" %s", last.c_str());
        }
        putchar('\n');
        if (hashes) fprintf(hashes, "%zu %s\n", drawn[k], last.c_str());
    }
    if (hashes) fclose(hashes);
    return 0;
}

static void usage() {
    fprintf(stderr,
            "trailforest - replay the walks behind a corpus file, orbit by orbit\n"
            "\n"
            "  --curve M        131, 83, 41, 23 (normal basis) or 97, 41 --poly-basis, 19, 13\n"
            "  --poly-basis     for curve 41, the polynomial-basis parameters\n"
            "  --instance I     planted test instance I (small curves only)\n"
            "  --dp-weight W    the cutoff the corpus was collected at (default: the curve's)\n"
            "  --corpus F       replay the client's --dp-file F (32-byte records)\n"
            "  --skip K         skip the first K records\n"
            "  --max N          replay at most N records (0 = all)\n"
            "  --generate       walk the client's seed schedule instead of a corpus\n"
            "  --run-id R       16-bit run id whose seeds to walk (default 1)\n"
            "  --walks N        lanes 0 .. N-1 of that run, first walk each (default 40)\n"
            "  --check-corpus F hold generated trails to the client's records in F\n"
            "  --corpus-out F   write the generated endpoints as a corpus file\n"
            "  --max-iters N    give up on a walk after N steps (default 2^32)\n"
            "  --sample         walk with the client's bitsliced kernel instead of the\n"
            "                   reference, keep the walks that finish within --cap steps,\n"
            "                   sample them every --every steps and name orbits by hash;\n"
            "                   seeds from --corpus (checked) or --run-id/--walks\n"
            "  --every N        sample stride in --sample mode (default 1024)\n"
            "  --cap N          most steps a sampled walk may take (default 2^20)\n"
            "  --hashes-out F   write each drawn walk's endpoint name in --sample mode\n");
}

int main(int argc, char **argv) {
    Options o;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        const bool nx = i + 1 < argc;
        if (a == "--curve" && nx) o.curve = atoi(argv[++i]);
        else if (a == "--poly-basis") o.polyBasis = true;
        else if (a == "--instance" && nx) o.instance = atoi(argv[++i]);
        else if (a == "--dp-weight" && nx) o.dpWeight = atoi(argv[++i]);
        else if (a == "--corpus" && nx) o.corpus = argv[++i];
        else if (a == "--skip" && nx) o.skip = strtoull(argv[++i], 0, 10);
        else if (a == "--max" && nx) o.max = strtoull(argv[++i], 0, 10);
        else if (a == "--max-iters" && nx) o.maxIters = strtoull(argv[++i], 0, 10);
        else if (a == "--generate") o.generate = true;
        else if (a == "--run-id" && nx) o.runId = (unsigned)strtoul(argv[++i], 0, 10) & 0xFFFFu;
        else if (a == "--walks" && nx) o.walks = strtoull(argv[++i], 0, 10);
        else if (a == "--check-corpus" && nx) o.checkCorpus = argv[++i];
        else if (a == "--corpus-out" && nx) o.corpusOut = argv[++i];
        else if (a == "--sample") o.sample = true;
        else if (a == "--every" && nx) o.every = strtoull(argv[++i], 0, 10);
        else if (a == "--cap" && nx) o.cap = strtoull(argv[++i], 0, 10);
        else if (a == "--hashes-out" && nx) o.hashesOut = argv[++i];
        else { usage(); return 1; }
    }
    if (o.sample) {
        if (o.generate) { usage(); return 1; }
    } else if (o.corpus.empty() == !o.generate) { usage(); return 1; }

#define TF_DISPATCH(NS, CFG)                                                                  \
    do {                                                                                      \
        const unsigned long long *px = NS::PX, *py = NS::PY, *qx = NS::QX, *qy = NS::QY;       \
        if (o.instance >= 0 && o.instance < NS::NUM_INSTANCES) {                              \
            px = NS::INSTANCE_PX[o.instance];                                                  \
            py = NS::INSTANCE_PY[o.instance];                                                  \
            qx = NS::INSTANCE_QX[o.instance];                                                  \
            qy = NS::INSTANCE_QY[o.instance];                                                  \
        } else if (o.instance >= 0) {                                                          \
            fprintf(stderr, "curve %d has %d planted instances\n", o.curve, NS::NUM_INSTANCES); \
            return 1;                                                                          \
        }                                                                                      \
        return run<CFG>(o, px, py, qx, qy, NS::ELL_DEC, NS::S_DEC, NS::DP_WEIGHT);            \
    } while (0)

    if (o.curve == 131) TF_DISPATCH(eccF131, CfgF131);
    if (o.curve == 83) TF_DISPATCH(eccF83, CfgF83);
    if (o.curve == 41 && !o.polyBasis) TF_DISPATCH(eccF41, CfgF41);
    if (o.curve == 23) TF_DISPATCH(eccF23, CfgF23);
    if (o.curve == 97) TF_DISPATCH(eccP97, CfgP97);
    if (o.curve == 41 && o.polyBasis) TF_DISPATCH(eccP41, CfgP41);
    if (o.curve == 19) TF_DISPATCH(eccP19, CfgP19);
    if (o.curve == 13) TF_DISPATCH(eccP13, CfgP13);
    fprintf(stderr, "unsupported curve %d\n", o.curve);
    return 1;
}
