#define main q1460_unused_main
#include "../q1460_fixed_state_support/midpoint_profile.cpp"
#undef main

int affine_rank(const std::set<U128>& values, int n) {
    if (values.empty()) return -1;
    U128 origin = *values.begin();
    std::array<U128, 128> pivots{};
    int rank = 0;
    for (U128 raw : values) {
        U128 value = raw ^ origin;
        while (value) {
            int bit = (value >> 64)
                ? 127 - __builtin_clzll(uint64_t(value >> 64))
                : 63 - __builtin_clzll(uint64_t(value));
            if (pivots[bit]) value ^= pivots[bit];
            else { pivots[bit] = value; ++rank; break; }
        }
        if (rank == n) break;
    }
    return rank;
}

int main(int argc, char** argv) {
    if (argc != 3) return 2;
    q1420::Field field(argv[1]);
    int weight = std::stoi(argv[2]);
    std::string cell, mode;
    int state;
    while (std::cin >> cell >> state >> mode) {
        if (mode != "raw") return 3;
        std::array<Leaf, 4> leaves;
        for (auto& leaf : leaves) {
            std::string fixed, ones;
            std::cin >> fixed >> ones;
            leaf.fixed = q1420::parse_hex(fixed);
            leaf.ones = q1420::parse_hex(ones);
        }
        std::array<std::vector<U128>, 4> domains;
        for (int i = 0; i < 4; ++i)
            domains[i] = options(leaves[i], field.n, weight);
        q1458::BatchStats batch{};
        auto left = profile_pair(field, domains[0], domains[1], batch);
        auto right = profile_pair(field, domains[2], domains[3], batch);
        q1420::require(left.candidates <= 4096 &&
                       right.candidates <= 4096,
                       "pair candidate count exceeds frozen cap");
        std::cout << "{\"cell\":\"" << cell << "\",\"state_index\":"
                  << state << ",\"pair_candidates\":["
                  << left.candidates << ',' << right.candidates
                  << "],\"midpoint_cardinalities\":["
                  << left.distinct.size() << ',' << right.distinct.size()
                  << "],\"affine_ranks\":["
                  << affine_rank(left.distinct, field.n) << ','
                  << affine_rank(right.distinct, field.n) << "]}\n";
    }
}
