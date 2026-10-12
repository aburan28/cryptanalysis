#include "cryptanalysis/ca_curve.h"
#include <errno.h>
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

static double wall_ms(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return 1000.0 * (double)t.tv_sec + (double)t.tv_nsec / 1000000.0;
}

static int parse_u64(const char *text, uint64_t *value)
{
    char *end = NULL;
    if (!text || !*text || *text == '-') return 0;
    errno = 0;
    unsigned long long parsed = strtoull(text, &end, 0);
    if (errno || !end || *end) return 0;
    *value = (uint64_t)parsed;
    return 1;
}

int main(int argc, char **argv)
{
    const int print_target = argc > 1 && !strcmp(argv[1], "--print-target");
    const int public_target = argc > 1 && !strcmp(argv[1], "--public-target");
    const char *name = print_target || public_target ?
        (argc > 2 ? argv[2] : "") : (argc > 1 ? argv[1] : "j0-37");
    uint64_t repetitions_u64 = 1;
    uint64_t scalar_input = UINT64_C(0x5d2e739b4c1);
    uint64_t walk_seed = UINT64_C(20261002);
    uint64_t input_x = 0, input_y = 0;
    if (print_target) {
        if (argc != 4 || !parse_u64(argv[3], &scalar_input)) return 5;
    } else if (public_target) {
        if (argc != 7 || !parse_u64(argv[3], &repetitions_u64) ||
            !parse_u64(argv[4], &input_x) || !parse_u64(argv[5], &input_y) ||
            !parse_u64(argv[6], &walk_seed)) return 5;
    } else {
        if (argc > 2 && !parse_u64(argv[2], &repetitions_u64)) return 5;
        if (argc > 3 && !parse_u64(argv[3], &scalar_input)) return 5;
        if (argc > 4 && !parse_u64(argv[4], &walk_seed)) return 5;
    }
    if (repetitions_u64 < 1 || repetitions_u64 > 1000) return 5;
    const int repetitions = (int)repetitions_u64;
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
    if (public_target) {
        uint64_t input_words[4] = {input_x, input_y, 0, 0};
        ca_elem subgroup_check;
        if (!ca_group_encode(&g, &target, input_words) ||
            ca_group_is_identity(&g, &target)) return 6;
        ca_group_mul(&g, &subgroup_check, &target, n, NULL);
        if (!ca_group_is_identity(&g, &subgroup_check)) return 6;
    } else {
        if (fixture_scalar == 0) return 6;
        ca_group_mul(&g, &target, &gen, fixture_scalar, NULL);
    }
    uint64_t words[4], base_words[4];
    ca_group_decode(&g, words, &target);
    ca_group_decode(&g, base_words, &gen);
    if (print_target) {
        printf("curve=%s p=%" PRIu64 " b=%" PRIu64 " order=%" PRIu64
               " base_x=%" PRIu64 " base_y=%" PRIu64
               " target_x=%" PRIu64 " target_y=%" PRIu64
               " fixture_scalar=%" PRIu64 "\n",
               name, p, b, n, base_words[0], base_words[1],
               words[0], words[1], fixture_scalar);
        return 0;
    }
    char fixture_text[32];
    if (public_target) {
        snprintf(fixture_text, sizeof(fixture_text), "unknown");
    } else {
        snprintf(fixture_text, sizeof(fixture_text), "%" PRIu64, fixture_scalar);
    }
    for (int i = 0; i < repetitions; i++) {
        ca_stats st = {0};
        uint64_t found = 0;
        double cpu_start = cpu_ms();
        double wall_start = wall_ms();
        ca_status rc = ca_curve_solve(&g, &gen, &target, walk_seed,
                                      &found, NULL, &st);
        ca_elem replay;
        ca_group_mul(&g, &replay, &gen, found, NULL);
        int verified = rc == CA_OK && ca_group_equal(&g, &replay, &target) &&
                       (public_target || found == fixture_scalar);
        double online_ms = wall_ms() - wall_start;
        double online_cpu_ms = cpu_ms() - cpu_start;
        printf("curve=%s run=%d p=%" PRIu64 " b=%" PRIu64 " order=%" PRIu64
               " base_x=%" PRIu64 " base_y=%" PRIu64
               " target_x=%" PRIu64 " target_y=%" PRIu64
               " fixture_scalar=%s found=%" PRIu64
               " seed=%" PRIu64 " online_ms=%.6f cpu_ms=%.6f solver_ms=%.6f ops=%" PRIu64
               " dp_entries=%" PRIu64 " bytes_peak=%" PRIu64
               " verified=%d\n",
               name, i + 1, p, b, n, base_words[0], base_words[1],
               words[0], words[1], fixture_text, found, walk_seed,
               online_ms, online_cpu_ms, st.seconds * 1000.0,
               st.group_ops, st.table_entries, st.bytes_peak, verified);
        if (!verified) return 4;
    }
    return 0;
}
