// Carryless-multiplication scaling benchmark for the tower multiplier in
// tower.c: CPU seconds of one clmul at doubling operand sizes.  Used by
// scripts/s10_level_53676929.py to extrapolate the cost of arithmetic in
// F_(2^(83 r)) for the l = 53676929 torsion field (r = 6709616).
//     clbench MAXWORDS
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include "tower.h"

int main(int argc, char **argv)
{
    size_t maxw = argc > 1 ? (size_t)atol(argv[1]) : 1068032;
    u64 s = 88172645463325252ull;
    for (size_t n = 8344; n <= maxw; n *= 2) {
        u64 *a = malloc(n * 8), *b = malloc(n * 8), *c = malloc(2 * n * 8);
        u64 *w = malloc((clmul_scratch_words(n) + 16) * 8);
        for (size_t j = 0; j < n; j++) {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            a[j] = s;
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            b[j] = s;
        }
        int reps = n < 100000 ? 10 : 1;
        clock_t c0 = clock();
        for (int r = 0; r < reps; r++) clmul(c, a, b, n, w);
        double cpu = (double)(clock() - c0) / CLOCKS_PER_SEC / reps;
        printf("{\"words\":%zu,\"cpu_seconds\":%.6f}\n", n, cpu);
        fflush(stdout);
        free(a);
        free(b);
        free(c);
        free(w);
    }
    return 0;
}
