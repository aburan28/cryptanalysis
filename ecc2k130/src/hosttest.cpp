/*
 * hosttest.cpp - the packed GF(2^131) arithmetic against the golden model,
 * on the CPU, with no CUDA toolkit and no GPU.
 *
 * This is the check CI runs.  It compiles the same headers the GPU kernel is
 * built from as host code and holds every routine the walk uses to
 * fpga/model/ecc2k130.c: field multiply, square, inverse, the Frobenius
 * powers, the polynomial-basis conversions and products, the table walk's
 * selection and addend, and a few dozen steps of the walk itself.  Then it
 * re-walks synthetic reports, including one that must fail, because a check
 * that cannot fail is not a check.
 */
#include "hostcheck.h"

#include <stdlib.h>

using namespace ec2k_gpu;

int main(int argc, char **argv)
{
    const int rounds = argc > 1 ? atoi(argv[1]) : 64;
    ec2k_pt P, Q;
    ec2k_point_from_seed(&P, 1);
    ec2k_point_from_seed(&Q, 2);
    HostTable *table = new HostTable;
    table->build(P, Q);

    CheckResult cr = crossCheck(*table, rounds, 0x243F6A8885A308D3ULL);

    /* A report the reference produces must re-walk; the same record with one
     * coordinate bit flipped, or under another seed, must not. */
    for (int i = 0; i < 4; ++i) {
        const unsigned long long seed = eccSeedFor(9u, (unsigned long long)i);
        ec2k_pt r;
        if (!startPoint(*table, seed, &r)) continue;
        unsigned long long hist = ECC_HIST_EMPTY;
        const unsigned long long iters = 50 + 17ull * (unsigned long long)i;
        bool ok = true;
        for (unsigned long long k = 0; k < iters && ok; ++k) ok = referenceStep(*table, &r, &hist);
        if (!ok) continue;
        DpRecord rec;
        rec.seed = seed;
        rec.iters = iters;
        toLimbs(r.x, rec.x);
        toLimbs(r.y, rec.y);
        cr.note(rewalk(*table, rec, nullptr), "reference report re-walks");
        DpRecord bad = rec;
        bad.y[1] ^= 1ull << 17;
        cr.note(!rewalk(*table, bad, nullptr), "a corrupted report is rejected");
        bad = rec;
        bad.seed ^= 1ull << 16;
        cr.note(!rewalk(*table, bad, nullptr), "a report under another seed is rejected");
    }

    delete table;
    if (cr.failures) {
        fprintf(stderr, "FAILED: %d of %d checks\n", cr.failures, cr.checks);
        return 1;
    }
    printf("{\"status\":\"ok\",\"checks\":%d,\"rounds\":%d}\n", cr.checks, rounds);
    return 0;
}
