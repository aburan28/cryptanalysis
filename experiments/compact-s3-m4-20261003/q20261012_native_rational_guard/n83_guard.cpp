// Exact N83 rational-x test via the existing native polynomial-basis kernel.
#define main q1496_unused_pair_stage_main
#include "native_n83_pairs.cpp"
#undef main

static unsigned trace_pb(F x) {
    static const std::array<U, 2> mask = [] {
        std::array<U, 2> result{};
        for (unsigned i = 0; i < N; ++i) {
            U lo = eccF83::Z_TO_ONB[i][0];
            U hi = eccF83::Z_TO_ONB[i][1];
            unsigned trace = unsigned((__builtin_popcountll(lo) +
                                       __builtin_popcountll(hi)) & 1);
            if (trace) result[i >> 6] |= U(1) << (i & 63);
        }
        return result;
    }();
    return unsigned((__builtin_popcountll(x.a & mask[0]) +
                     __builtin_popcountll(x.b & mask[1])) & 1);
}

static bool rational_mask(V coords) {
    if (!coords || (coords >> N)) return false;
    unsigned weight = unsigned(__builtin_popcountll(U(coords)) +
                               __builtin_popcountll(U(coords >> 64)));
    if (weight > 5) return false;
    F x = onb_to_pb(coords);
    return trace_pb(inv(x)) == (weight & 1);
}

extern "C" int q1496_pair_usable(U a_lo, U a_hi, U b_lo, U b_hi) {
    V a = V(a_lo) | (V(a_hi) << 64);
    V b = V(b_lo) | (V(b_hi) << 64);
    try {
        return rational_mask(a) && rational_mask(b) ? 1 : 0;
    } catch (...) {
        return -1;
    }
}

#ifdef Q1496_TEST_MAIN
int main(int argc, char **argv) {
    if (argc != 3) return 64;
    V a = parse_hex(argv[1]);
    V b = parse_hex(argv[2]);
    int result = q1496_pair_usable(U(a), U(a >> 64), U(b), U(b >> 64));
    std::cout << result << '\n';
    return result < 0 ? 65 : 0;
}
#endif
