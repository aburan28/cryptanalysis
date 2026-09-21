/*
 * cputest.cpp - the CPU walker (cpuwalk.h) against the golden model.
 *
 * hosttest.cpp holds the packed arithmetic to fpga/model under the CUDA
 * client's knobs.  This is the same for the CPU client: its knobs
 * (cpuknobs.h), its carry-less multiplier (hostclmul.h, or the software
 * product when the build has none), and then the engine itself --
 *
 *   - the host multiplier against a bit-serial product, on the operands a
 *     table-driven or masked implementation gets wrong first;
 *   - the 64-bit-limb hot path (f131.h) against the packed routines: product,
 *     squaring, reduction, conversion, selection with histories that fire
 *     the cycle rule, addend;
 *   - the engine's start points against the model's;
 *   - after a run with reports, --max-iters restarts and several workers,
 *     every lane where a re-walk from its seed on the model puts it, and
 *     every report re-walked the same way;
 *   - the reports of a run do not depend on how its lanes were cut into
 *     batches, nor on how many workers advanced them.
 */
#include "cpuwalk.h"
#include "f131.h"

#include <algorithm>

using namespace ec2k_cpu;

namespace
{

uint64_t splitmix(uint64_t *state)
{
    uint64_t z = (*state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

void checkClmul(CheckResult *cr)
{
    static const uint64_t edges[] = {0,
                                     1,
                                     2,
                                     0x8000000000000000ull,
                                     0xFFFFFFFFFFFFFFFFull,
                                     0x00000000FFFFFFFFull,
                                     0xFFFFFFFF00000000ull,
                                     0x5555555555555555ull,
                                     0xAAAAAAAAAAAAAAAAull,
                                     0x8000000000000001ull};
    const int nEdges = int(sizeof(edges) / sizeof(edges[0]));
    uint64_t rng = 0x13198A2E03707344ULL;
    for (int i = 0; i < nEdges * nEdges + 2000; ++i) {
        const uint64_t a = i < nEdges * nEdges ? edges[i / nEdges] : splitmix(&rng);
        const uint64_t b = i < nEdges * nEdges ? edges[i % nEdges] : splitmix(&rng);
        uint64_t lo = 0, hi = 0;
        for (int k = 0; k < 64; ++k)
            if ((b >> k) & 1) {
                lo ^= a << k;
                if (k) hi ^= a >> (64 - k);
            }
        const uint32_t aw[2] = {uint32_t(a), uint32_t(a >> 32)},
                       bw[2] = {uint32_t(b), uint32_t(b >> 32)};
        uint32_t r[4];
        eccPacked131::clmul64(r, aw, bw);
        cr->note((r[0] | (uint64_t(r[1]) << 32)) == lo && (r[2] | (uint64_t(r[3]) << 32)) == hi,
                 "clmul64 == bit-serial carry-less product");
    }
}

// The 64-bit-limb hot path (f131.h) against the packed routines it restates,
// which hostcheck.cpp holds to the golden model.
void checkF131(const HostTable &table, CheckResult *cr)
{
    using namespace eccPacked131;
    const std::vector<uint32_t> consts = table.deviceConsts();
    uint64_t rng = 0x082EFA98EC4E6C89ULL;
    for (int i = 0; i < 4000; ++i) {
        ec2k_fe fa, fb;
        randomFe(&fa, &rng);
        randomFe(&fb, &rng);
        if (i < 3) fa.w[0] = fa.w[1] = fa.w[2] = (i == 1) ? 0 : ~0ull, fa.w[2] &= 7u;
        const P131 a = toPacked(fa), b = toPacked(fb);
        const f131::F131 A = f131::fromPacked(a), B = f131::fromPacked(b);
        const auto eq = [](const f131::F131 &x, const P131 &y) {
            const P131 t = f131::toPacked(x);
            return memcmp(t.v, y.v, sizeof(y.v)) == 0 && x.w[2] < 8;
        };
        cr->note(eq(f131::mul(A, B), mulPolynomial131(a, b)), "f131 mul == packed product");
        cr->note(eq(f131::sqr(A), squarePolynomial131(a)), "f131 sqr == packed squaring");
        cr->note(eq(f131::fromPolynomial(A), fromPolynomial131(a)), "f131 conversion == packed");
        cr->note(f131::weight(A) == weight131(a), "f131 weight == packed");
        // the reduction alone, on limbs no product would produce
        uint32_t h[9];
        uint64_t H[5];
        for (int k = 0; k < 9; ++k) h[k] = uint32_t(splitmix(&rng));
        for (int k = 0; k < 5; ++k) H[k] = h[2 * k] | (k < 4 ? uint64_t(h[2 * k + 1]) << 32 : 0);
        cr->note(eq(f131::reduce(H), reducePolynomial131(h)), "f131 reduce == packed reduction");
    }
    for (int i = 0; i < 1500; ++i) {
        ec2k_pt pt;
        ec2k_point_from_seed(&pt, 9000 + (uint64_t)i);
        const P131 xn = toPacked(pt.x), xp = toPolynomial131(xn),
                   yp = toPolynomial131(toPacked(pt.y));
        const unsigned flipped = referenceTag(table, pt, ECC_HIST_EMPTY) ^ ECC_TAG_EPS;
        unsigned long long hist =
            i % 3 == 0 ? ECC_HIST_EMPTY
            : i % 3 == 1
                ? eccHistPush(ECC_HIST_EMPTY, flipped)
                : eccHistPush(eccHistPush(eccHistPush(ECC_HIST_EMPTY, 0x1123u), flipped), 0x0123u);
        unsigned long long h1 = hist, h2 = hist;
        const int hw = weight131(xn);
        const unsigned want = twSelect(xn, yp, hw, &h1, consts.data());
        const unsigned got =
            f131::select(f131::fromPacked(xn), f131::fromPacked(yp), hw, &h2, consts.data());
        cr->note(got == want && h1 == h2, "f131 select == twSelect");
        cr->note(want == referenceTag(table, pt, hist), "and both == the reference tag");
        P131 d, e;
        f131::F131 D, E;
        twAddend(want, xp, yp, consts.data(), &d, &e);
        f131::addend(want, f131::fromPacked(xp), f131::fromPacked(yp), consts.data(), &D, &E);
        const P131 dd = f131::toPacked(D), ee = f131::toPacked(E);
        cr->note(memcmp(dd.v, d.v, 20) == 0 && memcmp(ee.v, e.v, 20) == 0,
                 "f131 addend == twAddend");
    }
}

void checkStartPoints(const HostTable &table, CheckResult *cr)
{
    Options o;
    const CpuEngine e(table, o, true);
    for (int i = 0; i < 8; ++i) {
        const unsigned long long seed = eccSeedFor(5u, 1000ull * (unsigned long long)i) + (i & 3);
        ec2k_pt want;
        if (!startPoint(table, seed, &want)) continue;
        eccPacked131::P131 xp, yp;
        e.startPoint(seed, &xp, &yp);
        cr->note(sameFe(fromPacked(eccPacked131::fromPolynomial131(xp)), want.x) &&
                     sameFe(fromPacked(eccPacked131::fromPolynomial131(yp)), want.y),
                 "engine start point == golden start point");
    }
}

// A run with everything that can happen to a lane happening often: reports
// (weight 52 is about one point in a hundred), overdue restarts, several
// workers contending for a few batches, a batch size no chain count divides.
void checkEngine(const HostTable &table, CheckResult *cr)
{
    Options o;
    o.dpWeight = 52;
    o.maxIters = 40;
    o.runId = 11;
    Geometry g;
    g.workers = 3;
    g.batch = 13;
    g.chunks = 5;
    g.sliceSteps = 7;
    g.guardPeriod = 16;
    CpuEngine e(table, o, false, g);
    std::vector<DpRecord> reports;
    LaunchCounts counts;
    for (int l = 0; l < 3; ++l) e.launch(50, &reports, &counts);
    cr->note(counts.iterations == 3ull * 50ull * e.laneCount(), "iterations are counted exactly");
    cr->note(!counts.exhausted, "no lane exhausted its restart counter");
    cr->note(!reports.empty(), "a relaxed weight produces reports");
    cr->note(counts.restarts > 0, "--max-iters restarts overdue lanes");
    int rewalked = 0;
    for (const DpRecord &r : reports) {
        rewalked += rewalk(table, r, nullptr) ? 1 : 0;
        ec2k_fe x;
        x.w[0] = r.x[0];
        x.w[1] = r.x[1];
        x.w[2] = r.x[2];
        cr->note((int)ec2k_fe_weight(&x) <= o.dpWeight, "a report is a distinguished point");
    }
    cr->note(rewalked == (int)reports.size(), "every report re-walks on the golden model");
    int lanesOk = 0, lanesSeen = 0;
    for (size_t lane = 0; lane < e.laneCount(); ++lane) {
        if (!e.laneReady(lane)) continue;
        lanesSeen++;
        lanesOk += rewalk(table, e.laneRecord(lane), nullptr) ? 1 : 0;
    }
    cr->note(lanesSeen == (int)e.laneCount(), "every batch was advanced");
    cr->note(lanesOk == lanesSeen, "every lane is where the golden model puts its seed");
}

std::vector<DpRecord> reportsOf(const HostTable &table, int workers, int batch, int chunks)
{
    Options o;
    o.dpWeight = 50;
    o.runId = 12;
    Geometry g;
    g.workers = workers;
    g.batch = batch;
    g.chunks = chunks;
    g.sliceSteps = 60; // one slice per launch: every batch takes exactly the launch's steps
    CpuEngine e(table, o, false, g);
    std::vector<DpRecord> reports;
    LaunchCounts counts;
    for (int l = 0; l < 2; ++l) e.launch(60, &reports, &counts);
    std::sort(reports.begin(), reports.end(), [](const DpRecord &a, const DpRecord &b) {
        return a.seed != b.seed ? a.seed < b.seed : a.iters < b.iters;
    });
    return reports;
}

void checkGeometryIndependence(const HostTable &table, CheckResult *cr)
{
    const std::vector<DpRecord> a = reportsOf(table, 1, 12, 4), b = reportsOf(table, 1, 8, 6),
                                c = reportsOf(table, 4, 16, 3);
    cr->note(!a.empty(), "the geometry comparison has reports to compare");
    const auto same = [](const std::vector<DpRecord> &p, const std::vector<DpRecord> &q) {
        return p.size() == q.size() &&
               (p.empty() || memcmp(p.data(), q.data(), p.size() * sizeof(DpRecord)) == 0);
    };
    cr->note(same(a, b), "reports do not depend on the batch size");
    cr->note(same(a, c), "reports do not depend on the workers");
}

} // namespace

int main(int argc, char **argv)
{
    const int rounds = argc > 1 ? atoi(argv[1]) : 64;
    ec2k_pt P, Q;
    ec2k_point_from_seed(&P, 1);
    ec2k_point_from_seed(&Q, 2);
    HostTable *table = new HostTable;
    table->build(P, Q);

    CheckResult cr = crossCheck(*table, rounds, 0x243F6A8885A308D3ULL);
    checkClmul(&cr);
    checkF131(*table, &cr);
    checkStartPoints(*table, &cr);
    checkEngine(*table, &cr);
    checkGeometryIndependence(*table, &cr);

    delete table;
    if (cr.failures) {
        fprintf(stderr, "FAILED: %d of %d checks\n", cr.failures, cr.checks);
        return 1;
    }
    printf("{\"status\":\"ok\",\"checks\":%d,\"rounds\":%d,\"hostClmul\":%d}\n", cr.checks, rounds,
           ECC_HOST_CLMUL);
    return 0;
}
