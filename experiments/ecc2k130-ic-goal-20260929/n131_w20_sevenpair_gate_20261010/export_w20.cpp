// Enumerate rational W20 masks, Frobenius columns, and seven-window geometry.
#define main unused_w23_geometry_main
#define seed_member unused_w23_seed_member
#include "../../koblitz-s5-invariant-20260924/lowpoly_w23_geometry.cpp"
#undef seed_member
#undef main

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

constexpr int DEGREE_W20 = 20;
constexpr std::array<int, 7> ROTATIONS_W20{0, 18, 36, 54, 72, 90, 108};

bool member_w20(Fe value) {
    return value.lo && !(value.lo & 1) &&
           value.lo < (uint64_t(1) << (DEGREE_W20 + 1)) &&
           !value.mid && !value.hi;
}

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("usage: export_w20 output-directory");
        const std::string output(argv[1]);
        std::ofstream table(output + "/support_w20.tsv");
        if (!table) throw std::runtime_error("cannot open support TSV");
        const Fe one{1, 0, 0};
        const Fe trace_linear_mask = trace_mask();
        for (int bit = 1; bit <= DEGREE_W20; ++bit)
            if (trace_bit(field_bit(bit), trace_linear_mask))
                throw std::runtime_error("W20 basis has nonzero trace");
        constexpr uint32_t population = (uint32_t(1) << DEGREE_W20) - 1;
        Fe w{0, 0, 0};
        uint32_t previous_gray = 0;
        uint64_t rational = 0, canonical = 0;
        uint64_t direct_overlap_incidence = 0, reciprocal_hits = 0;
        uint64_t fixed_window_union_w = 0, inverse_products = 0;
        const auto started = std::chrono::steady_clock::now();
        for (uint32_t ordinal = 1; ordinal <= population; ++ordinal) {
            const uint32_t mask = ordinal ^ (ordinal >> 1);
            const uint32_t changed = mask ^ previous_gray;
            if (!changed || changed & (changed - 1))
                throw std::runtime_error("invalid Gray step");
            w = xored(w, field_bit(__builtin_ctz(changed) + 1));
            previous_gray = mask;
            if (!member_w20(w) || w.lo >> 1 != mask)
                throw std::runtime_error("source mask/field mismatch");
            const Fe reciprocal = inverse(w);
            if (!(mul(w, reciprocal) == one))
                throw std::runtime_error("source inversion mismatch");
            ++inverse_products;
            const bool is_rational = !trace_bit(reciprocal, trace_linear_mask);
            if (is_rational) {
                ++rational;
                Fe rotated_reciprocal = reciprocal;
                for (int shift = 0; shift <= 65; ++shift) {
                    if (member_w20(rotated_reciprocal)) ++reciprocal_hits;
                    rotated_reciprocal = square(rotated_reciprocal);
                }
            }
            Fe conjugate = w;
            uint32_t minimum = std::numeric_limits<uint32_t>::max();
            int minimum_shift = -1;
            int members = 0;
            std::array<bool, 131> source_positions{};
            for (int shift = 0; shift < 131; ++shift) {
                if (shift && conjugate == w)
                    throw std::runtime_error("short nontrivial Frobenius orbit");
                if (member_w20(conjugate)) {
                    const uint32_t candidate = uint32_t(conjugate.lo >> 1);
                    source_positions[shift] = true;
                    ++members;
                    if (candidate < minimum) {
                        minimum = candidate;
                        minimum_shift = shift;
                    }
                }
                conjugate = square(conjugate);
            }
            if (!(conjugate == w) || !members || minimum_shift < 0)
                throw std::runtime_error("Frobenius orbit check failed");
            if (!is_rational) continue;
            direct_overlap_incidence += uint64_t(members - 1);
            const int relative_shift = (131 - minimum_shift) % 131;
            table << mask << ' ' << minimum << ' ' << relative_shift << '\n';
            if (mask != minimum) continue;
            ++canonical;
            std::array<bool, 131> union_positions{};
            for (int shift = 0; shift < 131; ++shift) {
                if (!source_positions[shift]) continue;
                for (int rotation : ROTATIONS_W20)
                    union_positions[(shift + rotation) % 131] = true;
            }
            fixed_window_union_w += std::count(union_positions.begin(),
                                                union_positions.end(), true);
        }
        table.close();
        if (!table) throw std::runtime_error("support TSV write failed");
        const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now() - started).count();
        std::ofstream receipt(output + "/export_receipt.json");
        if (!receipt) throw std::runtime_error("cannot open receipt");
        receipt << "{\n\"status\":\"COMPLETE_W20_GEOMETRY\","
                << "\n\"curve_id\":\"EC1N131Ckb1heb5f1998f20b\","
                << "\n\"source_dimension\":20,"
                << "\n\"nonzero_mask_population\":" << population
                << ",\n\"checked_inverse_products\":" << inverse_products
                << ",\n\"rational_masks\":" << rational
                << ",\n\"folded_columns_K\":" << canonical
                << ",\n\"direct_overlap_incidence\":" << direct_overlap_incidence
                << ",\n\"reciprocal_frobenius_hits\":" << reciprocal_hits
                << ",\n\"seven_window_union_distinct_w\":" << fixed_window_union_w
                << ",\n\"seven_window_usable_points_B\":";
        if (!reciprocal_hits) receipt << 2 * fixed_window_union_w;
        else receipt << "null";
        receipt << ",\n\"seven_window_rotations\":[";
        for (size_t i = 0; i < ROTATIONS_W20.size(); ++i) {
            if (i) receipt << ',';
            receipt << ROTATIONS_W20[i];
        }
        receipt << "],\n\"elapsed_wall_ns\":" << elapsed << "\n}\n";
        receipt.close();
        if (!receipt) throw std::runtime_error("receipt write failed");
        std::cout << "W20 rational=" << rational << " K=" << canonical
                  << " seven_B=" << 2 * fixed_window_union_w
                  << " reciprocal_hits=" << reciprocal_hits << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
