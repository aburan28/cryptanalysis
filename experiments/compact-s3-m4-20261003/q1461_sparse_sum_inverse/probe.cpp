// Q1461: compare exact sparse-sum inversion with direct pair enumeration.
#include "sparse_sum.hpp"

#include <chrono>
#include <iostream>
#include <set>
#include <string>
#include <utility>
#include <vector>

using q1420::U128;

std::vector<U128> direct_options(const q1461::Leaf &leaf,
                                 int n, int weight) {
    std::vector<int> free;
    for (int bit = 0; bit < n; ++bit)
        if (!(leaf.fixed >> bit & 1)) free.push_back(bit);
    int slack = weight - q1461::weight(leaf.ones);
    std::vector<U128> result;
    auto visit = [&](auto &&self, int start, int left, U128 x) -> void {
        if (!left) {
            if (x) result.push_back(x);
            return;
        }
        for (int i = start; i <= int(free.size()) - left; ++i)
            self(self, i + 1, left - 1, x | (U128(1) << free[i]));
    };
    for (int size = 0; size <= std::min(slack, int(free.size())); ++size)
        visit(visit, 0, size, leaf.ones);
    return result;
}

std::set<std::pair<U128, U128>> direct_pairs(
    q1420::Field &field, int weight, q1461::Leaf first,
    q1461::Leaf second, U128 midpoint, uint64_t cap,
    uint64_t &pair_candidates) {
    auto a_options = direct_options(first, field.n, weight);
    auto b_options = direct_options(second, field.n, weight);
    pair_candidates = a_options.size() * b_options.size();
    q1420::require(pair_candidates <= cap,
                    "direct validation pair domain exceeds cap");
    std::set<std::pair<U128, U128>> found;
    U128 m = field.to_poly(midpoint);
    std::vector<U128> liftable_a, liftable_b;
    for (U128 a : a_options)
        if (q1422::curve_lifts(field, a)) liftable_a.push_back(a);
    for (U128 b : b_options)
        if (q1422::curve_lifts(field, b)) liftable_b.push_back(b);
    for (U128 a : liftable_a) {
        U128 ap = field.to_poly(a);
        for (U128 b : liftable_b) {
            if (field.evaluate_s3(ap, field.to_poly(b), m) == 0)
                found.insert({a, b});
        }
    }
    return found;
}

int main(int argc, char **argv) {
    try {
        q1420::require(argc == 5,
                        "usage: probe FIELD WEIGHT SUM_CAP PAIR_CAP < states");
        q1420::Field field(argv[1]);
        int weight = std::stoi(argv[2]);
        uint64_t sum_cap = std::stoull(argv[3]);
        uint64_t pair_cap = std::stoull(argv[4]);
        auto start = std::chrono::steady_clock::now();
        q1461::SparseSumInverse inverse(field, weight);
        auto setup_end = std::chrono::steady_clock::now();
        auto setup_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            setup_end - start).count();
        std::cout << "{\"kind\":\"setup\",\"degree_n\":" << field.n
                  << ",\"field_mul_calls\":" << field.counts.mul
                  << ",\"field_sqr_calls\":" << field.counts.sqr
                  << ",\"field_inv_calls\":" << field.counts.inv
                  << ",\"wall_ns_exploratory\":" << setup_ns << "}\n";
        std::string cell;
        int index, pair;
        std::string mid_hex, af_hex, ao_hex, bf_hex, bo_hex;
        while (std::cin >> cell >> index >> pair >> mid_hex >> af_hex >>
               ao_hex >> bf_hex >> bo_hex) {
            U128 mid = q1420::parse_hex(mid_hex);
            q1461::Leaf first{q1420::parse_hex(af_hex),
                               q1420::parse_hex(ao_hex)};
            q1461::Leaf second{q1420::parse_hex(bf_hex),
                                q1420::parse_hex(bo_hex)};
            field.counts = {};
            auto before_kernel = std::chrono::steady_clock::now();
            auto result = inverse.check(first, second, mid, sum_cap);
            auto after_kernel = std::chrono::steady_clock::now();
            auto kernel_ns = std::chrono::duration_cast<
                std::chrono::nanoseconds>(after_kernel - before_kernel).count();
            auto kernel_counts = field.counts;
            uint64_t direct_candidates = 0;
            field.counts = {};
            auto before_direct = std::chrono::steady_clock::now();
            auto direct = direct_pairs(field, weight, first, second, mid,
                                       pair_cap, direct_candidates);
            auto after_direct = std::chrono::steady_clock::now();
            auto direct_ns = std::chrono::duration_cast<
                std::chrono::nanoseconds>(after_direct - before_direct).count();
            auto direct_counts = field.counts;
            q1420::require(!result.skipped, "sum inversion unexpectedly skipped");
            q1420::require(result.pairs == direct,
                            "sum inversion disagrees with direct enumeration");
            std::cout << "{\"kind\":\"state\",\"cell\":\"" << cell
                      << "\",\"state_index\":" << index
                      << ",\"pair\":" << pair
                      << ",\"mid_onb_hex\":\"" << mid_hex
                      << "\",\"sum_candidate_count\":"
                      << result.sum_candidate_bound
                      << ",\"sums_visited\":" << result.sums_visited
                      << ",\"trace_rejections\":"
                      << result.trace_rejections
                      << ",\"fixed_bit_rejections\":"
                      << result.fixed_bit_rejections
                      << ",\"linear_solutions\":"
                      << result.linear_solutions
                      << ",\"sparse_rejections\":"
                      << result.sparse_rejections
                      << ",\"lift_rejections\":"
                      << result.lift_rejections
                      << ",\"verified_pairs\":"
                      << result.verified_pairs
                      << ",\"basis_xors\":" << result.basis_xors
                      << ",\"elimination_xors\":"
                      << result.elimination_xors
                      << ",\"pair_candidates\":" << direct_candidates
                      << ",\"kernel_mul_calls\":" << kernel_counts.mul
                      << ",\"kernel_sqr_calls\":" << kernel_counts.sqr
                      << ",\"kernel_inv_calls\":" << kernel_counts.inv
                      << ",\"direct_mul_calls\":" << direct_counts.mul
                      << ",\"direct_sqr_calls\":" << direct_counts.sqr
                      << ",\"direct_inv_calls\":" << direct_counts.inv
                      << ",\"kernel_wall_ns_exploratory\":" << kernel_ns
                      << ",\"direct_wall_ns_exploratory\":" << direct_ns
                      << ",\"witness_pairs\":[";
            size_t written = 0;
            for (const auto &[a, b] : result.pairs) {
                if (written++) std::cout << ',';
                std::cout << "[\"" << q1420::hex(a) << "\",\""
                          << q1420::hex(b) << "\"]";
            }
            std::cout << "]}\n";
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
