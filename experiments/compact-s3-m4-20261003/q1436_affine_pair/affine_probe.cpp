// Native affine-pair replay independent of CaDiCaL.
#include "affine_pair.hpp"

#include <fstream>
#include <iostream>
#include <string>

int main(int argc, char **argv) {
    try {
        q1420::require(argc == 3, "usage: affine_probe FIELD CASES");
        q1420::Field field(argv[1]);
        q1432::CachedSpan cache(field);
        std::ifstream input(argv[2]);
        q1420::require(bool(input), "affine cases missing");
        std::string magic;
        int count = 0;
        input >> magic >> count;
        q1420::require(magic == "Q1436AFFINE1" && count > 0 &&
                        count <= 4096, "bad affine-case header");
        const int weight = field.n == 53 ? 3 : 5;
        for (int i = 0; i < count; ++i) {
            std::string encoded[5];
            for (auto &part : encoded) {
                input >> part;
                q1420::require(bool(input), "short affine-case input");
            }
            q1420::Counts before = field.counts;
            auto result = q1436::check(
                cache, q1420::parse_hex(encoded[0]),
                q1420::parse_hex(encoded[1]),
                q1420::parse_hex(encoded[2]),
                q1420::parse_hex(encoded[3]),
                q1420::parse_hex(encoded[4]), weight, 65536);
            std::cout << "{\"index\":" << i
                      << ",\"feasible\":" << (result.feasible ? "true" : "false")
                      << ",\"unique\":" << (result.unique ? "true" : "false")
                      << ",\"a_options\":" << result.a_options
                      << ",\"b_free\":" << result.b_free
                      << ",\"inconsistent_options\":"
                      << result.inconsistent_options
                      << ",\"overweight_options\":"
                      << result.overweight_options
                      << ",\"rank_deficient_options\":"
                      << result.rank_deficient_options
                      << ",\"exact_solutions\":"
                      << result.exact_solutions
                      << ",\"coefficient_columns\":"
                      << result.coefficient_columns
                      << ",\"xor_ops\":" << result.xor_ops
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
        q1420::require(!(input >> extra), "extra affine-case input");
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
