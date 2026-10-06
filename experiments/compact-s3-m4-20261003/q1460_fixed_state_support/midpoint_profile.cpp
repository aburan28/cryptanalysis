// Q1460: exact midpoint sets for bounded, archived four-leaf states.
#include "../q1422_leaf_lift_gate/lift_gate.hpp"
#include "../q1458_batch_roots/batch_roots.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <set>
#include <string>
#include <utility>
#include <vector>

using q1420::U128;

struct Leaf {
    U128 fixed = 0;
    U128 ones = 0;
};

std::vector<U128> options(const Leaf &leaf, int n, int weight) {
    q1420::require((leaf.fixed & ~((U128(1) << n) - 1)) == 0 &&
                    (leaf.ones & ~leaf.fixed) == 0,
                    "invalid partial leaf");
    int slack = weight - __builtin_popcountll(uint64_t(leaf.ones)) -
                __builtin_popcountll(uint64_t(leaf.ones >> 64));
    q1420::require(slack >= 0, "leaf exceeds weight bound");
    std::vector<int> free;
    for (int bit = 0; bit < n; ++bit)
        if (!(leaf.fixed >> bit & 1)) free.push_back(bit);
    std::vector<U128> result;
    auto visit = [&](auto &&self, int start, int left, U128 value) -> void {
        if (!left) {
            if (value) result.push_back(value);
            return;
        }
        for (int i = start; i <= int(free.size()) - left; ++i)
            self(self, i + 1, left - 1, value | (U128(1) << free[i]));
    };
    for (int size = 0; size <= std::min(slack, int(free.size())); ++size)
        visit(visit, 0, size, leaf.ones);
    return result;
}

struct PairProfile {
    uint64_t candidates = 0;
    uint64_t root_values = 0;
    std::set<U128> distinct;
};

PairProfile profile_pair(q1420::Field &field,
                         const std::vector<U128> &left,
                         const std::vector<U128> &right,
                         q1458::BatchStats &batch) {
    std::vector<std::pair<U128, U128>> inputs;
    inputs.reserve(left.size() * right.size());
    for (U128 a : left)
        for (U128 b : right) inputs.emplace_back(a, b);
    auto roots = q1458::roots_onb(field, inputs, batch);
    PairProfile result;
    result.candidates = inputs.size();
    for (const auto &row : roots) {
        result.root_values += row.size();
        result.distinct.insert(row.begin(), row.end());
    }
    return result;
}

int main(int argc, char **argv) {
    try {
        q1420::require(argc == 3,
                        "usage: midpoint_profile FIELD WEIGHT < states.txt");
        q1420::Field field(argv[1]);
        int weight = std::stoi(argv[2]);
        q1420::require(weight > 0 && weight < field.n, "invalid weight");
        std::string cell, mode;
        int state = 0;
        while (std::cin >> cell >> state >> mode) {
            q1420::require(mode == "raw" || mode == "lift",
                            "unknown midpoint mode");
            std::array<Leaf, 4> leaves;
            for (auto &leaf : leaves) {
                std::string fixed, ones;
                std::cin >> fixed >> ones;
                q1420::require(bool(std::cin), "short state row");
                leaf.fixed = q1420::parse_hex(fixed);
                leaf.ones = q1420::parse_hex(ones);
            }
            field.counts = {};
            std::array<std::vector<U128>, 4> domains;
            std::array<uint64_t, 4> raw_counts{};
            for (size_t i = 0; i < 4; ++i) {
                domains[i] = options(leaves[i], field.n, weight);
                raw_counts[i] = domains[i].size();
                q1420::require(raw_counts[i] <= 4096,
                                "archived leaf domain exceeds cap");
                if (mode == "lift") {
                    std::vector<U128> filtered;
                    for (U128 x : domains[i])
                        if (q1422::curve_lifts(field, x))
                            filtered.push_back(x);
                    domains[i] = std::move(filtered);
                }
            }
            q1420::Counts lift_counts = field.counts;
            field.counts = {};
            q1458::BatchStats batch{};
            auto first = profile_pair(field, domains[0], domains[1], batch);
            auto second = profile_pair(field, domains[2], domains[3], batch);
            q1420::require(first.candidates <= 4096 &&
                            second.candidates <= 4096,
                            "archived pair domain exceeds cap");
            uint64_t m0 = first.distinct.size(), m1 = second.distinct.size();
            uint64_t support_bound = 2 * m0 * m1;
            std::cout << "{\"cell\":\"" << cell << "\",\"state_index\":"
                      << state << ",\"mode\":\"" << mode
                      << "\",\"raw_leaf_counts\":[";
            for (size_t i = 0; i < 4; ++i) {
                if (i) std::cout << ',';
                std::cout << raw_counts[i];
            }
            std::cout << "],\"leaf_counts\":[";
            for (size_t i = 0; i < 4; ++i) {
                if (i) std::cout << ',';
                std::cout << domains[i].size();
            }
            std::cout << "],\"pair_candidates\":[" << first.candidates
                      << ',' << second.candidates << "]"
                      << ",\"pair_root_values\":[" << first.root_values
                      << ',' << second.root_values << "]"
                      << ",\"midpoint_cardinalities\":[" << m0 << ','
                      << m1 << "]"
                      << ",\"zero_midpoints\":["
                      << first.distinct.count(0) << ','
                      << second.distinct.count(0) << "]"
                      << ",\"target_x_support_upper_bound\":"
                      << support_bound
                      << ",\"lift_mul_calls\":" << lift_counts.mul
                      << ",\"lift_sqr_calls\":" << lift_counts.sqr
                      << ",\"lift_inv_calls\":" << lift_counts.inv
                      << ",\"root_mul_calls\":" << field.counts.mul
                      << ",\"root_sqr_calls\":" << field.counts.sqr
                      << ",\"root_inv_calls\":" << field.counts.inv
                      << ",\"inverse_batches\":" << batch.inverse_batches
                      << ",\"batch_denominators\":" << batch.denominators
                      << "}\n";
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
