// Independent exact-root comparison for Q1458's batched-inversion kernel.
#include "batch_roots.hpp"

#include <iostream>

using q1420::U128;

static U128 next_value(U128 &state, U128 mask) {
    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    U128 value = state & mask;
    return value ? value : 1;
}

int main(int argc, char **argv) {
    q1420::require(argc == 2, "usage: smoke_roots FIELD");
    q1420::Field serial(argv[1]), batched(argv[1]);
    for (int count : {1, 32, 512, 4096}) {
        U128 state = U128(0x1458) * U128(serial.n);
        std::vector<std::pair<U128, U128>> inputs;
        inputs.reserve(size_t(count));
        for (int i = 0; i < count; ++i) {
            U128 left = next_value(state, serial.mask);
            U128 right = (i % 17 == 0 ? left :
                          next_value(state, serial.mask));
            inputs.emplace_back(left, right);
        }
        q1458::BatchStats stats{};
        batched.counts = {};
        serial.counts = {};
        auto actual = q1458::roots_onb(batched, inputs, stats);
        q1420::require(actual.size() == inputs.size(),
                       "batch root cardinality mismatch");
        size_t no_root = 0, one_root = 0, two_roots = 0;
        for (size_t i = 0; i < inputs.size(); ++i) {
            auto expected = serial.roots_onb(inputs[i].first,
                                             inputs[i].second);
            q1420::require(actual[i] == expected,
                           "batch roots differ from serial oracle");
            if (actual[i].empty()) ++no_root;
            else if (actual[i].size() == 1) ++one_root;
            else if (actual[i].size() == 2) ++two_roots;
            else q1420::require(false, "too many S3 roots");
        }
        q1420::require(no_root + one_root + two_roots == inputs.size(),
                       "root status accounting mismatch");
        q1420::require(stats.root_inputs == inputs.size(),
                       "batch input accounting mismatch");
        q1420::require(batched.counts.roots == serial.counts.roots,
                       "batch root call accounting mismatch");
        q1420::require(batched.counts.inv == stats.inverse_batches,
                       "batch inverse accounting mismatch");
        std::cout << "{\"n\":" << serial.n
                  << ",\"inputs\":" << inputs.size()
                  << ",\"no_root\":" << no_root
                  << ",\"one_root\":" << one_root
                  << ",\"two_roots\":" << two_roots
                  << ",\"serial_inv\":" << serial.counts.inv
                  << ",\"batch_inv\":" << batched.counts.inv
                  << ",\"batch_denominators\":" << stats.denominators
                  << ",\"serial_mul\":" << serial.counts.mul
                  << ",\"batch_mul\":" << batched.counts.mul
                  << ",\"serial_sqr\":" << serial.counts.sqr
                  << ",\"batch_sqr\":" << batched.counts.sqr
                  << "}\n";
    }
}
