// Independent direct-mask and x([4]P) audit of nested W15..W18 support.
#define main unused_w23_geometry_main
#define seed_member unused_w23_seed_member
#include "../../koblitz-s5-invariant-20260924/lowpoly_w23_geometry.cpp"
#undef seed_member
#undef main

#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

constexpr std::array<int, 6> ROTATIONS{0, 13, 26, 39, 52, 65};

bool in_width(Fe value, int d) {
    return value.lo && !(value.lo & 1) &&
           value.lo < (uint64_t(1) << (d + 1)) &&
           !value.mid && !value.hi;
}

bool less_fe(const Fe& a, const Fe& b) {
    if (a.hi != b.hi) return a.hi < b.hi;
    if (a.mid != b.mid) return a.mid < b.mid;
    return a.lo < b.lo;
}

struct Row { uint32_t mask, column; };

std::vector<Row> read_rows(const std::string& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open support TSV");
    std::vector<Row> rows;
    Row row{};
    while (input >> row.mask >> row.column) rows.push_back(row);
    if (!input.eof()) throw std::runtime_error("malformed support TSV");
    return rows;
}

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("usage: verify_native support-directory");
        const std::string dir(argv[1]);
        const Fe trace_linear_mask = trace_mask();
        std::array<std::vector<Row>, 4> sources;
        std::array<std::vector<bool>, 4> present;
        for (int index = 0; index < 4; ++index) {
            int d = 15 + index;
            sources[index] = read_rows(dir + "/support_w" + std::to_string(d) + ".tsv");
            present[index].resize(uint32_t(1) << d);
            for (const Row& row : sources[index]) {
                if (!row.mask || row.mask >= present[index].size() ||
                    present[index][row.mask])
                    throw std::runtime_error("duplicate or invalid source mask");
                present[index][row.mask] = true;
            }
        }
        uint64_t rational_checks = 0;
        for (uint32_t mask = 1; mask < (uint32_t(1) << 18); ++mask) {
            Fe w{uint64_t(mask) << 1, 0, 0};
            const bool rational = !trace_bit(inverse(w), trace_linear_mask);
            for (int index = 0; index < 4; ++index)
                if (mask < present[index].size()) {
                    if (present[index][mask] != rational)
                        throw std::runtime_error("source rationality mismatch");
                    ++rational_checks;
                }
        }
        std::ofstream receipt(dir + "/native_audit_result.json");
        if (!receipt) throw std::runtime_error("cannot open native audit receipt");
        receipt << "{\"status\":\"PASS_DIRECT_MASK_AND_PROJECTED_X_AUDIT\","
                << "\"rationality_checks\":" << rational_checks << ",\"widths\":[";
        for (int index = 0; index < 4; ++index) {
            int d = 15 + index;
            std::vector<Fe> projected;
            projected.reserve(sources[index].size() * ROTATIONS.size());
            uint64_t column_checks = 0;
            for (const Row& row : sources[index]) {
                Fe w{uint64_t(row.mask) << 1, 0, 0};
                uint32_t minimum = std::numeric_limits<uint32_t>::max();
                Fe conjugate = w;
                for (int shift = 0; shift < 131; ++shift) {
                    if (in_width(conjugate, d))
                        minimum = std::min(minimum, uint32_t(conjugate.lo >> 1));
                    conjugate = square(conjugate);
                }
                if (minimum != row.column)
                    throw std::runtime_error("Frobenius canonical column mismatch");
                ++column_checks;
                const Fe x = inverse(w);
                const Fe x2 = xored(square(x), square(w));
                if (x2 == Fe{0, 0, 0})
                    throw std::runtime_error("exceptional doubled x coordinate");
                const Fe x2_squared = square(x2);
                const Fe x4 = xored(x2_squared, inverse(x2_squared));
                Fe rotated = x4;
                for (int shift = 0; shift <= ROTATIONS.back(); ++shift) {
                    if (std::find(ROTATIONS.begin(), ROTATIONS.end(), shift) != ROTATIONS.end())
                        projected.push_back(rotated);
                    rotated = square(rotated);
                }
            }
            std::sort(projected.begin(), projected.end(), less_fe);
            projected.erase(std::unique(projected.begin(), projected.end(),
                                        [](const Fe& a, const Fe& b) { return a == b; }),
                            projected.end());
            if (index) receipt << ',';
            receipt << "{\"degree\":" << d
                    << ",\"rational_masks\":" << sources[index].size()
                    << ",\"column_checks\":" << column_checks
                    << ",\"unique_projected_x\":" << projected.size()
                    << ",\"actual_projected_factor_base_B\":"
                    << 2*projected.size() << '}';
            std::cout << "W" << d << " projected B=" << 2*projected.size() << '\n';
        }
        receipt << "]}\n";
        receipt.close();
        if (!receipt) throw std::runtime_error("native audit receipt write failed");
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
