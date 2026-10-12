#include "cryptanalysis/ca_curve.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    const char *name = argc > 1 ? argv[1] : "glv-j0-32";
    int repetitions = argc > 2 ? atoi(argv[2]) : 12;
    if (repetitions < 1 || repetitions > 1000) return 5;
    uint64_t p, a, b, n;
    if (ca_curve_by_name(name, &p, &a, &b, &n) != CA_OK) return 1;
    ca_group g;
    if (ca_curve_group(&g, p, a, b, n, NULL) != CA_OK) return 2;
    ca_elem gen, target;
    if (ca_group_find_generator(&g, &gen, 1) != CA_OK) return 3;
    uint64_t fixture_scalar = UINT64_C(0x5d2e739b4c1) % n;
    ca_group_mul(&g, &target, &gen, fixture_scalar, NULL);
    uint64_t words[4];
    ca_group_decode(&g, words, &target);
    for (int i = 0; i < repetitions; i++) {
        ca_stats st = {0};
        uint64_t found = 0;
        ca_status rc = ca_curve_solve(&g, &gen, &target, 20260930, &found, NULL, &st);
        ca_elem replay;
        ca_group_mul(&g, &replay, &gen, found, NULL);
        int verified = rc == CA_OK && found == fixture_scalar &&
                       ca_group_equal(&g, &replay, &target);
        printf("curve=%s run=%d target_x=%" PRIu64 " target_y=%" PRIu64
               " seed=20260930 online_ms=%.6f ops=%" PRIu64 " verified=%d\n",
               name, i + 1, words[0], words[1], st.seconds * 1000.0,
               st.group_ops, verified);
        if (!verified) return 4;
    }
    return 0;
}
