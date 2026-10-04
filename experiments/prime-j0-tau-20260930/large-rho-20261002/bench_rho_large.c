#include "cryptanalysis/ca_curve.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static double cpu_ms(void)
{
    struct timespec t;
    clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t);
    return 1000.0 * (double)t.tv_sec + (double)t.tv_nsec / 1000000.0;
}

int main(int argc, char **argv)
{
    const char *name = argc > 1 ? argv[1] : "j0-37";
    int repetitions = argc > 2 ? atoi(argv[2]) : 1;
    if (repetitions < 1 || repetitions > 1000) return 5;
    const uint64_t scalar_input = argc > 3 ? strtoull(argv[3], NULL, 0)
                                           : UINT64_C(0x5d2e739b4c1);
    const uint64_t walk_seed = argc > 4 ? strtoull(argv[4], NULL, 0)
                                          : UINT64_C(20261002);
    const uint64_t p = UINT64_C(2305843009213693951);
    uint64_t b, n;
    if (!strcmp(name, "j0-37")) {
        b = 11;
        n = UINT64_C(157632877033);
    } else if (!strcmp(name, "j0-36")) {
        b = 5;
        n = UINT64_C(51131959441);
    } else if (!strcmp(name, "j0-46")) {
        b = 13;
        n = UINT64_C(42111239174233);
    } else return 1;
    ca_group g;
    ca_curve_info info;
    if (ca_curve_group(&g, p, 0, b, n, &info) != CA_OK ||
        info.endo != CA_CURVE_ENDO_J0) return 2;
    ca_elem gen, target;
    if (ca_group_find_generator(&g, &gen, 1) != CA_OK) return 3;
    const uint64_t fixture_scalar = scalar_input % n;
    ca_group_mul(&g, &target, &gen, fixture_scalar, NULL);
    uint64_t words[4], base_words[4];
    ca_group_decode(&g, words, &target);
    ca_group_decode(&g, base_words, &gen);
    for (int i = 0; i < repetitions; i++) {
        ca_stats st = {0};
        uint64_t found = 0;
        double cpu_start = cpu_ms();
        ca_status rc = ca_curve_solve(&g, &gen, &target, walk_seed,
                                      &found, NULL, &st);
        double solve_cpu_ms = cpu_ms() - cpu_start;
        ca_elem replay;
        ca_group_mul(&g, &replay, &gen, found, NULL);
        int verified = rc == CA_OK && found == fixture_scalar &&
                       ca_group_equal(&g, &replay, &target);
        printf("curve=%s run=%d p=%" PRIu64 " b=%" PRIu64 " order=%" PRIu64
               " base_x=%" PRIu64 " base_y=%" PRIu64
               " target_x=%" PRIu64 " target_y=%" PRIu64
               " fixture_scalar=%" PRIu64 " found=%" PRIu64
               " seed=%" PRIu64 " online_ms=%.6f cpu_ms=%.6f ops=%" PRIu64
               " dp_entries=%" PRIu64 " bytes_peak=%" PRIu64
               " verified=%d\n",
               name, i + 1, p, b, n, base_words[0], base_words[1],
               words[0], words[1], fixture_scalar, found, walk_seed,
               st.seconds * 1000.0, solve_cpu_ms,
               st.group_ops, st.table_entries, st.bytes_peak, verified);
        if (!verified) return 4;
    }
    return 0;
}
