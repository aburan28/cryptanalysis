/* One public target, shared by the hash and coordinate orbit builds.
 * Curve/point construction is outside the timer. The interval starts before
 * target-dependent solver setup and ends after independent scalar replay. */
#include "cryptanalysis/ca_curve.h"
#include "ca_internal.h"

#include <inttypes.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef CA_RHO_J0_COORDINATE_ORBIT
#define ORBIT_ARM "coordinate"
#elif defined(CA_RHO_J0_FACTORED_HASH)
#define ORBIT_ARM "factored"
#else
#define ORBIT_ARM "hash"
#endif

int main(int argc, char **argv)
{
    int large = argc > 1 && strcmp(argv[1], "j0-56") == 0;
    int seed_arg = large ? 2 : 1;
    if (argc > seed_arg + 1) {
        fputs("usage: ca_rho_orbit_bench [j0-56] [walk-seed]\n", stderr);
        return 2;
    }
    const char *curve = large ? "j0-56" : "glv-j0-32";
    const uint64_t p = large ? UINT64_C(2305843009213693951) : UINT64_C(4294967377);
    const uint64_t b = large ? UINT64_C(7) : UINT64_C(15);
    const uint64_t order = large ? UINT64_C(53624256071278747) : UINT64_C(23729779);
    const uint64_t small_base[4] = {UINT64_C(481899190), UINT64_C(1998487369), 0, 0};
    const uint64_t small_target[4] = {UINT64_C(11525401), UINT64_C(2537560930), 0, 0};
    const uint64_t large_base[4] = {UINT64_C(1839617427631136375),
                                    UINT64_C(725584580046817702), 0, 0};
    const uint64_t large_target[4] = {UINT64_C(282423703968320088),
                                      UINT64_C(2098065311724316995), 0, 0};
    const uint64_t *base_words = large ? large_base : small_base;
    const uint64_t *target_words = large ? large_target : small_target;
    uint64_t seed = large ? UINT64_C(20261008) : UINT64_C(20261007);
    if (argc == seed_arg + 1) {
        char *end;
        errno = 0;
        unsigned long long parsed = strtoull(argv[seed_arg], &end, 10);
        if (errno || end == argv[seed_arg] || *end || parsed == 0) {
            fputs("walk-seed must be a positive decimal integer\n", stderr);
            return 2;
        }
        seed = (uint64_t)parsed;
    }
    ca_group g;
    ca_curve_info info;
    if (ca_curve_group(&g, p, 0, b, order, &info) != CA_OK ||
        info.endo != CA_CURVE_ENDO_J0 || info.aut_order != 6) {
        fputs("failed to prepare j0 group\n", stderr);
        return 2;
    }
    ca_elem base, target;
    if (!ca_group_encode(&g, &base, base_words) ||
        !ca_group_encode(&g, &target, target_words)) {
        fputs("invalid frozen point\n", stderr);
        return 2;
    }

    uint64_t scalar = 0, verify_ops = 0;
    ca_stats stats = {0};
    double start = ca_now();
    ca_status rc = ca_curve_solve(&g, &base, &target, seed, &scalar, NULL, &stats);
    ca_elem replay;
    if (rc == CA_OK) ca_group_mul(&g, &replay, &base, scalar, &verify_ops);
    int verified = rc == CA_OK && scalar < order && ca_group_equal(&g, &replay, &target);
    double online_ms = 1000.0 * (ca_now() - start);
    if (!verified) {
        fprintf(stderr, "rho solve or independent scalar replay failed: status=%d\n", (int)rc);
        return 1;
    }
    printf("arm=%s curve=%s base_x=%" PRIu64 " base_y=%" PRIu64
           " target_x=%" PRIu64 " target_y=%" PRIu64
           " seed=%" PRIu64 " scalar=%" PRIu64
           " online_ms=%.6f group_ops=%" PRIu64 " replay_ops=%" PRIu64
           " verified=1\n",
           ORBIT_ARM, curve, base_words[0], base_words[1], target_words[0], target_words[1],
           seed, scalar, online_ms, stats.group_ops, verify_ops);
    return 0;
}
