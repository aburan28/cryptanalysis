// Q1466 post-result audit: replay a wide no-chain state with the separate
// serial Q1420 S3 root oracle. No Q1458 batched-root code is used here.
#include "../q1420_root_theory/root_field.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <iostream>
#include <set>
#include <string>
#include <vector>

using q1420::U128;

struct Leaf {
    U128 fixed = 0, ones = 0;
};

std::vector<U128> options(const Leaf &leaf, int n, int weight) {
    q1420::require(!(leaf.ones & ~leaf.fixed), "one outside fixed mask");
    q1420::require((leaf.fixed >> n) == 0, "fixed mask exceeds field");
    int used = __builtin_popcountll(uint64_t(leaf.ones)) +
               __builtin_popcountll(uint64_t(leaf.ones >> 64));
    q1420::require(used <= weight, "leaf exceeds weight bound");
    std::vector<int> free;
    for (int i = 0; i < n; ++i)
        if (!(leaf.fixed >> i & 1)) free.push_back(i);
    std::vector<U128> out;
    auto visit = [&](auto &&self, int start, int left, U128 x) -> void {
        if (!left) {
            if (x) out.push_back(x);
            return;
        }
        for (int i = start; i <= int(free.size()) - left; ++i)
            self(self, i + 1, left - 1, x | (U128(1) << free[i]));
    };
    for (int size = 0; size <= std::min(weight - used, int(free.size()));
         ++size)
        visit(visit, 0, size, leaf.ones);
    return out;
}

int main(int argc, char **argv) {
    try {
        q1420::require(argc == 12,
                        "usage: serial_audit FIELD WEIGHT TARGET 8_LEAF_MASKS");
        auto begin = std::chrono::steady_clock::now();
        q1420::Field field(argv[1]);
        int weight = std::stoi(argv[2]);
        U128 target = q1420::parse_hex(argv[3]);
        q1420::require(target != 0 && target <= field.mask,
                        "invalid target x");
        std::array<Leaf, 4> leaves;
        std::array<std::vector<U128>, 4> domains;
        for (int i = 0; i < 4; ++i) {
            leaves[i] = {q1420::parse_hex(argv[4 + 2 * i]),
                         q1420::parse_hex(argv[5 + 2 * i])};
            domains[i] = options(leaves[i], field.n, weight);
        }
        uint64_t pair0 = uint64_t(domains[0].size()) * domains[1].size();
        uint64_t pair1 = uint64_t(domains[2].size()) * domains[3].size();
        q1420::require(pair0 <= 250000 && pair1 <= 250000,
                        "pair domain exceeds audit cap");
        std::array<std::set<U128>, 2> mids;
        for (int side = 0; side < 2; ++side)
            for (U128 a : domains[2 * side])
                for (U128 b : domains[2 * side + 1]) {
                    auto roots = field.roots_onb(a, b);
                    mids[side].insert(roots.begin(), roots.end());
                }
        uint64_t final_roots = 0, hits = 0;
        for (U128 u : mids[0]) {
            std::vector<U128> partners;
            if (u) partners = field.roots_onb(u, target);
            else partners = {field.to_onb(field.inv(field.to_poly(target)))};
            final_roots += partners.size();
            for (U128 v : partners) hits += mids[1].count(v);
        }
        auto seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - begin).count();
        std::cout << "{\"pair_candidates\":[" << pair0 << ',' << pair1
                  << "],\"midpoint_cardinalities\":[" << mids[0].size()
                  << ',' << mids[1].size() << "]"
                  << ",\"final_root_values\":" << final_roots
                  << ",\"x_only_chain_hits\":" << hits
                  << ",\"field_mul_calls\":" << field.counts.mul
                  << ",\"field_sqr_calls\":" << field.counts.sqr
                  << ",\"field_inv_calls\":" << field.counts.inv
                  << ",\"serial_root_calls\":" << field.counts.roots
                  << ",\"wall_seconds_exploratory\":" << seconds
                  << "}\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
