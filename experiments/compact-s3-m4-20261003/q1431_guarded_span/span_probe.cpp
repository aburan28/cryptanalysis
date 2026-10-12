// Replay frozen or synthetic partial-pair span cases without CaDiCaL.
#include "span_filter.hpp"

#include <fstream>
#include <iostream>
#include <string>

int main(int argc, char **argv) {
    try {
        q1420::require(argc == 3, "usage: span_probe FIELD CASES");
        q1420::Field field(argv[1]);
        std::ifstream input(argv[2]);
        q1420::require(bool(input), "span cases missing");
        std::string magic;
        int count = 0;
        input >> magic >> count;
        q1420::require(magic == "Q1431SPAN1" && count > 0 && count <= 4096,
                        "bad span-case header");
        for (int i = 0; i < count; ++i) {
            std::string encoded[5];
            for (auto &part : encoded) {
                input >> part;
                q1420::require(bool(input), "short span-case input");
            }
            q1420::Counts before = field.counts;
            auto result = q1431::check(
                field, q1420::parse_hex(encoded[0]),
                q1420::parse_hex(encoded[1]),
                q1420::parse_hex(encoded[2]),
                q1420::parse_hex(encoded[3]),
                q1420::parse_hex(encoded[4]));
            std::cout << "{\"index\":" << i
                      << ",\"feasible\":"
                      << (result.feasible ? "true" : "false")
                      << ",\"rank\":" << result.rank
                      << ",\"linear_columns\":"
                      << result.linear_columns
                      << ",\"bilinear_columns\":"
                      << result.bilinear_columns
                      << ",\"field_mul_calls\":"
                      << field.counts.mul - before.mul
                      << ",\"field_sqr_calls\":"
                      << field.counts.sqr - before.sqr
                      << ",\"field_inv_calls\":"
                      << field.counts.inv - before.inv << "}\n";
        }
        std::string extra;
        q1420::require(!(input >> extra), "extra span-case input");
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
