#include <stdint.h>

/* GF(2^53) with reduction polynomial x^53 + x^6 + x^2 + x + 1. */
uint64_t gf53_mul(uint64_t a, uint64_t b) {
    uint64_t result = 0;
    while (b) {
        if (b & 1) result ^= a;
        b >>= 1;
        a <<= 1;
        if (a & (UINT64_C(1) << 53))
            a ^= (UINT64_C(1) << 53) | UINT64_C(0x47);
    }
    return result;
}
