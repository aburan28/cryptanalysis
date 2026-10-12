// Native exact-tail replay, independent of CaDiCaL.
#include "bounded_tail.hpp"

#include <fstream>
#include <iostream>
#include <string>

int main(int argc, char **argv) {
    try {
        q1420::require(argc == 3, "usage: tail_probe FIELD CASES");
        q1420::Field field(argv[1]);
        q1432::CachedSpan cache(field);
        std::ifstream input(argv[2]);
        q1420::require(bool(input), "tail cases missing");
        std::string magic;
        int count = 0;
        input >> magic >> count;
        q1420::require(magic == "Q1435TAIL1" && count > 0 && count <= 4096,
                        "bad tail-case header");
        const int weight = field.n == 53 ? 3 : 5;
        for (int i = 0; i < count; ++i) {
            std::string encoded[5];
            for (auto &part : encoded) {
                input >> part;
                q1420::require(bool(input), "short tail-case input");
            }
            q1420::Counts before = field.counts;
            auto result = q1435::check(
                cache, q1420::parse_hex(encoded[0]),
                q1420::parse_hex(encoded[1]),
                q1420::parse_hex(encoded[2]),
                q1420::parse_hex(encoded[3]),
                q1420::parse_hex(encoded[4]), weight, 4096);
            std::cout << "{\"index\":" << i
                      << ",\"candidates\":" << result.candidates
                      << ",\"solutions\":" << result.solutions
                      << ",\"expansion_xor_ops\":"
                      << result.expansion_xor_ops
                      << ",\"unique_a_onb_hex\":\""
                      << q1420::hex(result.unique_a)
                      << "\",\"unique_b_onb_hex\":\""
                      << q1420::hex(result.unique_b)
                      << "\",\"field_mul_calls\":"
                      << field.counts.mul - before.mul
                      << ",\"field_sqr_calls\":"
                      << field.counts.sqr - before.sqr
                      << ",\"field_inv_calls\":"
                      << field.counts.inv - before.inv
                      << ",\"cache_payload_bytes_lower_bound\":"
                      << cache.payload_bytes_lower_bound() << "}\n";
        }
        std::string extra;
        q1420::require(!(input >> extra), "extra tail-case input");
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
