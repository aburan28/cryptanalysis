#include "../build/live-22b-baseline/include/curveparams.h"
#include "../build/live-22b-baseline/include/packed131.h"
#ifdef GOAL22_DIVSTEPS
#include "divsteps_inverse.h"
#define goal22BinaryInverse goal22DivstepsInverse
#elif defined(GOAL22_WINDOW)
#include "binary_inverse_window.h"
#define goal22BinaryInverse goal22WindowInverse
#else
#include "binary_inverse.h"
#endif
#include <cstdio>
using namespace eccPacked131;
using R = Ref<CfgF131>;
int main() {
    uint32_t state = 131;
    auto next = [&]() { state ^= state << 13; state ^= state >> 17; state ^= state << 5; return state; };
    for (int test = 0; test < 1133; ++test) {
        P131 a = {{next(), next(), next(), next(), next() & 7u}};
        if (test < 131) { a = P131{}; a.v[test / 32] = 1u << (test % 32); }
        if (test == 131) a = P131{};
        if (test == 132) a = P131{{~0u, ~0u, ~0u, ~0u, 7u}};
        const P131 got = goal22BinaryInverse(a);
        if (got.v[4] & ~7u) return 2;
        const P131 normal = fromPolynomial131(a);
        unsigned long long limbs[3] = {normal.v[0] | (uint64_t(normal.v[1]) << 32),
            normal.v[2] | (uint64_t(normal.v[3]) << 32), normal.v[4]};
        const auto expected = R::inv(R::fromLimbs(limbs));
        const P131 gotNormal = fromPolynomial131(got);
        for (int i = 0; i < 5; ++i) {
            if (gotNormal.v[i] != uint32_t(expected.v[i / 2] >> (32 * (i & 1)))) {
                std::printf("FAIL independent inverse comparison at case %d word %d\n", test, i);
                return 1;
            }
        }
    }
    std::puts("PASS 1133 binary inversions: all 131 basis inputs, zero, dense edge, 1000 random; independent Ref<CfgF131>");
}
