#include "cryptanalysis/ca_curve.h"
#include <inttypes.h>
#include <stdio.h>
#include <time.h>

static double now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return 1000.0 * (double)ts.tv_sec + (double)ts.tv_nsec / 1000000.0;
}

static uint64_t next_key(uint64_t *state)
{
    uint64_t x = *state;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    *state = x;
    return x;
}

int main(void)
{
    const char *names[] = {"glv-j0-26", "glv-j0-32", "j0-56"};
    for (size_t ci = 0; ci < 3; ci++) {
        uint64_t p, a, b, n;
        if (ci == 2) {
            p = UINT64_C(2305843009213693951);
            a = 0;
            b = 7;
            n = UINT64_C(53624256071278747);
        } else if (ca_curve_by_name(names[ci], &p, &a, &b, &n) != CA_OK) return 1;
        ca_group g;
        if (ca_curve_group(&g, p, a, b, n, NULL) != CA_OK) return 1;
        ca_elem gen;
        if (ca_group_find_generator(&g, &gen, 1) != CA_OK) return 1;
        enum { COUNT = 20000 };
        uint64_t keys[COUNT];
        uint64_t seed = 20260930 + ci;
        for (size_t i = 0; i < COUNT; i++) keys[i] = next_key(&seed) % n;
        for (int round = 0; round < 3; round++) {
            double times[4];
            uint64_t checks[4] = {0, 0, 0, 0};
            for (int method = 0; method < 4; method++) {
                double t0 = now_ms();
                for (size_t i = 0; i < COUNT; i++) {
                    ca_elem out;
                    if (method == 0) ca_group_mul(&g, &out, &gen, keys[i], NULL);
                    else if (method == 1) {
                        if (!ca_ec_mul_tau2(&g, &out, &gen, keys[i], NULL, NULL)) return 2;
                    } else if (method == 2) {
                        if (!ca_ec_mul_tau4(&g, &out, &gen, keys[i], NULL, NULL)) return 2;
                    } else if (!ca_ec_mul_tau4_tripling(&g, &out, &gen, keys[i],
                                                         NULL, NULL, NULL)) return 2;
                    checks[method] ^= ca_group_hash(&g, &out);
                }
                times[method] = now_ms() - t0;
            }
            if (checks[0] != checks[1] || checks[0] != checks[2] ||
                checks[0] != checks[3]) return 3;
            printf("%s round=%d count=%d affine_ms=%.3f tau2_ms=%.3f tau4_ms=%.3f tau4_tripling_ms=%.3f checksum=%" PRIu64 "\n",
                   names[ci], round + 1, COUNT, times[0], times[1], times[2],
                   times[3], checks[0]);
        }
    }
    return 0;
}
