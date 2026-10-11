#define main archived_native_main
#include "/Volumes/SSD990/cryptanalysis/experiments/ecc2k130-ic-goal-20260929/n131_w15_rotated_fouratom_inverse_20261010/native.cpp"
#undef main
#include "field_fast.hpp"

#include <random>

int main() {
    Field field(131);
    std::mt19937_64 rng(20261011);
    const Fe special[] = {{0,0,0}, {1,0,0}, {~0ULL,~0ULL,7},
                          {0,0,4}, {0,0,7}, {0x2007,0,0}};
    uint64_t checked = 0;
    for (Fe a : special) for (Fe b : special) {
        if (!eq(field.mul(a,b), mul131_fast(a,b))) return 1;
        ++checked;
    }
    for (int i=0;i<10000;++i) {
        Fe a{rng(),rng(),rng()&7}, b{rng(),rng(),rng()&7};
        if (!eq(field.mul(a,b), mul131_fast(a,b))) {
            std::cerr << "mismatch at " << i << "\n";
            return 1;
        }
        ++checked;
    }
    std::cout << "PASS exact products=" << checked << "\n";
}
