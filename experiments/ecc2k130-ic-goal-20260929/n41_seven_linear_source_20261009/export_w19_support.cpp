// Exact rational W19 masks, signed-Frobenius aliases, and seven-slot base union.
#define main unused_w23_geometry_main
#define seed_member unused_w23_seed_member
#include "../../koblitz-s5-invariant-20260924/lowpoly_w23_geometry.cpp"
#undef seed_member
#undef main

#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>

constexpr int DEGREE = 19;
constexpr std::array<int, 7> ROTATIONS{0, 18, 36, 54, 72, 90, 108};
bool member_w19(Fe value) {
    return value.lo && !(value.lo & 1) &&
           value.lo < (uint64_t(1) << (DEGREE + 1)) &&
           !value.mid && !value.hi;
}

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: export_w19 support.tsv receipt.json");
        constexpr uint32_t population = (uint32_t(1) << DEGREE) - 1;
        const Fe one{1,0,0};
        Fe trace_linear_mask = trace_mask();
        for (int bit = 1; bit <= DEGREE; ++bit)
            if (trace_bit(field_bit(bit), trace_linear_mask))
                throw std::runtime_error("W19 basis trace is nonzero");
        std::ofstream support(argv[1]);
        if (!support) throw std::runtime_error("cannot open support output");
        auto began = std::chrono::steady_clock::now();
        uint64_t rational = 0, canonical = 0, direct_overlap = 0;
        uint64_t union_seeds = 0, reciprocal_overlap = 0;
        Fe w{0,0,0};
        uint32_t previous_gray = 0;
        for (uint32_t ordinal = 1; ordinal <= population; ++ordinal) {
            uint32_t mask = ordinal ^ (ordinal >> 1);
            uint32_t changed = mask ^ previous_gray;
            if (!changed || changed & (changed-1)) throw std::runtime_error("invalid Gray step");
            w = xored(w,field_bit(__builtin_ctz(changed)+1));
            previous_gray = mask;
            if (!member_w19(w) || w.lo >> 1 != mask)
                throw std::runtime_error("seed mask/field mismatch");
            Fe reciprocal = inverse(w);
            if (!(mul(w,reciprocal) == one)) throw std::runtime_error("inverse mismatch");
            if (trace_bit(reciprocal,trace_linear_mask)) continue;
            ++rational;
            uint32_t minimum = mask;
            std::array<bool,131> positions{};
            Fe conjugate = w;
            int members = 0;
            for (int shift = 0; shift < 131; ++shift) {
                if (member_w19(conjugate)) {
                    uint32_t other = uint32_t(conjugate.lo >> 1);
                    minimum = std::min(minimum,other);
                    positions[shift] = true;
                    ++members;
                }
                conjugate = square(conjugate);
            }
            if (!(conjugate == w) || members == 0)
                throw std::runtime_error("Frobenius orbit did not close");
            direct_overlap += uint64_t(members-1);
            support << mask << ' ' << minimum << '\n';
            if (mask == minimum) {
                ++canonical;
                std::array<bool,131> union_positions{};
                for (int shift = 0; shift < 131; ++shift)
                    if (positions[shift])
                        for (int rotation : ROTATIONS)
                            union_positions[(shift+rotation)%131] = true;
                union_seeds += std::count(union_positions.begin(),union_positions.end(),true);
            }
            for (int shift = 0; shift <= 65; ++shift) {
                reciprocal_overlap += member_w19(reciprocal);
                reciprocal = square(reciprocal);
            }
        }
        support.close();
        if (rational != 262390 || canonical != 262151 ||
            direct_overlap != 486 || reciprocal_overlap != 0)
            throw std::runtime_error("W19 independent geometry count mismatch");
        uint64_t elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now()-began).count();
        std::ofstream receipt(argv[2]);
        if (!receipt) throw std::runtime_error("cannot open receipt");
        receipt << "{\"status\":\"COMPLETE\",\"rational_masks\":" << rational
                << ",\"folded_columns_K\":" << canonical
                << ",\"direct_overlap_incidence\":" << direct_overlap
                << ",\"reciprocal_overlap\":" << reciprocal_overlap
                << ",\"seven_rotation_union_seed_count\":" << union_seeds
                << ",\"actual_subgroup_factor_base_points_B\":" << 2*union_seeds
                << ",\"elapsed_ns\":" << elapsed << "}\n";
        std::cout << "COMPLETE rational=" << rational << " K=" << canonical
                  << " B=" << 2*union_seeds << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
