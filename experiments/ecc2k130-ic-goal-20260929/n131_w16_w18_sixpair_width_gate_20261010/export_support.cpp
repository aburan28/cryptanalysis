// Enumerate nested polynomial W15..W18 rational masks and orbit-folded unions.
#define main unused_w23_geometry_main
#define seed_member unused_w23_seed_member
#include "../../koblitz-s5-invariant-20260924/lowpoly_w23_geometry.cpp"
#undef seed_member
#undef main

#include <array>
#include <chrono>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

constexpr std::array<int, 6> ROTATIONS{0, 13, 26, 39, 52, 65};

bool member_width(Fe value, int degree) {
    return value.lo && !(value.lo & 1) &&
           value.lo < (uint64_t(1) << (degree + 1)) &&
           !value.mid && !value.hi;
}

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("usage: export_support output-directory");
        const std::string output(argv[1]);
        std::array<std::ofstream, 4> streams;
        for (int index = 0; index < 4; ++index) {
            streams[index].open(output + "/support_w" + std::to_string(15 + index) + ".tsv");
            if (!streams[index]) throw std::runtime_error("cannot open support TSV");
        }
        const Fe one{1, 0, 0};
        const Fe trace_linear_mask = trace_mask();
        for (int bit = 1; bit <= 18; ++bit)
            if (trace_bit(field_bit(bit), trace_linear_mask))
                throw std::runtime_error("W18 basis trace is nonzero");
        std::array<uint64_t, 4> rational{}, canonical{}, union_x{};
        Fe w{0, 0, 0};
        uint32_t previous_gray = 0;
        const auto began = std::chrono::steady_clock::now();
        for (uint32_t ordinal = 1; ordinal < (uint32_t(1) << 18); ++ordinal) {
            const uint32_t mask = ordinal ^ (ordinal >> 1);
            const uint32_t changed = mask ^ previous_gray;
            if (!changed || changed & (changed - 1))
                throw std::runtime_error("invalid Gray step");
            w = xored(w, field_bit(__builtin_ctz(changed) + 1));
            previous_gray = mask;
            if (!member_width(w, 18) || w.lo >> 1 != mask)
                throw std::runtime_error("source mask/field mismatch");
            const Fe reciprocal = inverse(w);
            if (!(mul(w, reciprocal) == one))
                throw std::runtime_error("source inversion mismatch");
            if (trace_bit(reciprocal, trace_linear_mask)) continue;
            std::array<uint32_t, 4> minimum{};
            std::array<std::array<bool, 131>, 4> positions{};
            for (int index = 0; index < 4; ++index)
                minimum[index] = UINT32_MAX;
            Fe conjugate = w;
            for (int shift = 0; shift < 131; ++shift) {
                for (int index = 0; index < 4; ++index) {
                    if (member_width(conjugate, 15 + index)) {
                        minimum[index] = std::min(minimum[index],
                                                   uint32_t(conjugate.lo >> 1));
                        positions[index][shift] = true;
                    }
                }
                conjugate = square(conjugate);
            }
            if (!(conjugate == w))
                throw std::runtime_error("Frobenius orbit did not close");
            for (int index = 0; index < 4; ++index) {
                const int degree = 15 + index;
                if (mask >= (uint32_t(1) << degree)) continue;
                if (minimum[index] == UINT32_MAX)
                    throw std::runtime_error("rational mask missing orbit representative");
                ++rational[index];
                streams[index] << mask << ' ' << minimum[index] << '\n';
                if (mask != minimum[index]) continue;
                ++canonical[index];
                std::array<bool, 131> union_positions{};
                for (int shift = 0; shift < 131; ++shift)
                    if (positions[index][shift])
                        for (int rotation : ROTATIONS)
                            union_positions[(shift + rotation) % 131] = true;
                for (bool present : union_positions) union_x[index] += present;
            }
        }
        for (auto& stream : streams) {
            stream.close();
            if (!stream) throw std::runtime_error("support TSV write failed");
        }
        const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now() - began).count();
        std::ofstream receipt(output + "/support_receipt.json");
        if (!receipt) throw std::runtime_error("cannot open support receipt");
        receipt << "{\"status\":\"COMPLETE_NESTED_W15_W18_SUPPORT\",\"elapsed_ns\":"
                << elapsed << ",\"widths\":[";
        for (int index = 0; index < 4; ++index) {
            if (index) receipt << ',';
            receipt << "{\"degree\":" << 15 + index
                    << ",\"rational_masks\":" << rational[index]
                    << ",\"folded_columns_K\":" << canonical[index]
                    << ",\"six_rotation_union_x\":" << union_x[index]
                    << ",\"actual_projected_factor_base_B\":" << 2*union_x[index]
                    << '}';
        }
        receipt << "]}\n";
        receipt.close();
        if (!receipt) throw std::runtime_error("support receipt write failed");
        for (int index = 0; index < 4; ++index)
            std::cout << "W" << 15 + index << " rational=" << rational[index]
                      << " K=" << canonical[index] << " B=" << 2*union_x[index] << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
