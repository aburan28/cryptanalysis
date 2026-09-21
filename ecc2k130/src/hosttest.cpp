/*
 * hosttest.cpp - the packed GF(2^131) arithmetic against the golden model,
 * on the CPU, with no CUDA toolkit and no GPU.
 *
 *   hosttest [ROUNDS] [KAT]
 *
 * This is the check CI runs.  It compiles the same headers the GPU kernel is
 * built from as host code and holds every routine the walk uses to
 * fpga/model/ecc2k130.c: field multiply, square, inverse, the Frobenius
 * powers, the polynomial-basis conversions and products, the walk's
 * selection, and a few dozen steps of the walk itself.  Then it re-walks
 * synthetic reports, including ones that must fail, because a check that
 * cannot fail is not a check.
 *
 * For the campaign's sigma walk it also checks the challenge points and the
 * known answers in KAT (tests/campaign-kat.hex): records the campaign's own
 * client wrote, which the model must reproduce byte for byte from their
 * seeds.  That is the test that a point this client reports is a point of
 * that campaign.
 */
#include "hostcheck.h"

#include <stdlib.h>

using namespace ec2k_gpu;

#if !ECC_WALK_TABLE
namespace
{

int hexNibble(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

// P and Q are Certicom's points: on the curve, of prime order n, and distinct
// from the points the tests below would otherwise be built from.
void checkChallenge(CheckResult &cr)
{
    ec2k_pt P, Q, z;
    challengePoints(&P, &Q);
    cr.note(ec2k_on_curve(&P) && ec2k_on_curve(&Q), "challenge points are on the curve");
    ec2k_pt_mul(&z, &P, SUBGROUP_ORDER, 3);
    cr.note(z.inf != 0, "[n]P = O");
    ec2k_pt_mul(&z, &Q, SUBGROUP_ORDER, 3);
    cr.note(z.inf != 0, "[n]Q = O");
}

// Walk every known answer's seed from the challenge points to its first point
// of weight <= 46 and compare the 32-byte record.
void checkKnownAnswers(CheckResult &cr, const char *path)
{
    FILE *f = fopen(path, "r");
    cr.note(f != nullptr, "known-answer file opens");
    if (!f) return;
    ec2k_pt P, Q;
    challengePoints(&P, &Q);
    HostWalk *walk = new HostWalk;
    walk->build(P, Q);
    char line[256];
    int records = 0, matched = 0;
    while (fgets(line, sizeof(line), f)) {
        if (line[0] == '#' || line[0] == '\n') continue;
        uint8_t want[EC2K_RECORD_BYTES];
        bool parsed = true;
        for (int i = 0; i < EC2K_RECORD_BYTES && parsed; ++i) {
            const int hi = hexNibble(line[2 * i]), lo = hexNibble(line[2 * i + 1]);
            parsed = hi >= 0 && lo >= 0;
            want[i] = (uint8_t)(hi << 4 | lo);
        }
        cr.note(parsed, "known answer parses");
        if (!parsed) continue;
        unsigned long long seed = 0;
        for (int i = 0; i < 8; ++i) seed |= (unsigned long long)want[i] << (8 * i);
        DpRecord rec;
        uint8_t got[EC2K_RECORD_BYTES];
        const bool walked = referenceReport(*walk, seed, 46, 1ull << 24, &rec);
        if (walked) campaignRecord(got, rec);
        const bool same = walked && memcmp(got, want, sizeof(got)) == 0;
        cr.note(same, "known answer: the model walks the seed to the campaign client's record");
        records++;
        matched += same;
    }
    fclose(f);
    delete walk;
    cr.note(records >= 32, "known-answer file has its records");
    printf("known answers: %d of %d records reproduced from the challenge points\n", matched,
           records);
}

} // namespace
#endif

int main(int argc, char **argv)
{
    const int rounds = argc > 1 ? atoi(argv[1]) : 64;
    ec2k_pt P, Q;
    ec2k_point_from_seed(&P, 1);
    ec2k_point_from_seed(&Q, 2);
    HostWalk *walk = new HostWalk;
    walk->build(P, Q);

    CheckResult cr = crossCheck(*walk, rounds, 0x243F6A8885A308D3ULL);

    /* A report the reference produces must re-walk; the same record with one
     * coordinate bit flipped, or under another seed, must not. */
    for (int i = 0; i < 4; ++i) {
        const unsigned long long seed = eccSeedFor(9u, (unsigned long long)i);
        ec2k_pt r;
        if (!startPoint(*walk, seed, &r)) continue;
        unsigned long long hist = HIST_START;
        const unsigned long long iters = 50 + 17ull * (unsigned long long)i;
        bool ok = true;
        for (unsigned long long k = 0; k < iters && ok; ++k) ok = referenceStep(*walk, &r, &hist);
        if (!ok) continue;
        DpRecord rec;
        rec.seed = seed;
        rec.iters = iters;
        toLimbs(r.x, rec.x);
        toLimbs(r.y, rec.y);
        cr.note(rewalk(*walk, rec, nullptr), "reference report re-walks");
        DpRecord bad = rec;
        bad.y[1] ^= 1ull << 17;
        cr.note(!rewalk(*walk, bad, nullptr), "a corrupted report is rejected");
        bad = rec;
        bad.seed ^= 1ull << 16;
        cr.note(!rewalk(*walk, bad, nullptr), "a report under another seed is rejected");
    }
    delete walk;

#if !ECC_WALK_TABLE
    checkChallenge(cr);
    if (argc > 2)
        checkKnownAnswers(cr, argv[2]);
    else
        cr.note(false, "the sigma walk's test needs the known-answer file (hosttest ROUNDS KAT)");
#endif

    if (cr.failures) {
        fprintf(stderr, "FAILED: %d of %d checks\n", cr.failures, cr.checks);
        return 1;
    }
    printf("{\"status\":\"ok\",\"checks\":%d,\"rounds\":%d}\n", cr.checks, rounds);
    return 0;
}
