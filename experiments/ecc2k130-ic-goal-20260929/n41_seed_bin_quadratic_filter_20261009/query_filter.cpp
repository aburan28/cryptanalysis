// Exact public-point residual screening through seed-bin quadratic equations.
#define main unused_frozen_helper_main
#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
#undef main

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr int BINS = 3969;
constexpr int FEATURES = 821;
constexpr int FILTERS = 8;
constexpr int WORDS = 13;
constexpr int BLOCKS = (BINS + 63) / 64;
using Accumulator = std::array<uint64_t, FILTERS * BLOCKS>;
struct SeedPoint { Point point; uint8_t column, mask; };
struct PairState { Point point; uint32_t columns; uint16_t left, right; };

uint64_t elapsed(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
}
uint64_t peak_rss() {
    rusage usage{}; getrusage(RUSAGE_SELF, &usage);
#ifdef __APPLE__
    return uint64_t(usage.ru_maxrss);
#else
    return uint64_t(usage.ru_maxrss) * 1024;
#endif
}
uint64_t read_u64(std::ifstream& input) {
    uint64_t value = 0;
    for (int k = 0; k < 8; ++k) {
        int byte = input.get();
        if (byte < 0) throw std::runtime_error("truncated filter table");
        value |= uint64_t(byte) << (8 * k);
    }
    return value;
}
void write_u16(std::ofstream& out, uint16_t value) {
    out.put(char(value & 255)); out.put(char((value >> 8) & 255));
}

std::vector<PairState> pair_states(const std::vector<SeedPoint>& source) {
    if (source.size() != 64) throw std::runtime_error("source window size changed");
    std::vector<PairState> pairs;
    for (int i = 0; i < 64; ++i)
        for (int j = i + 1; j < 64; ++j) {
            if (source[i].column == source[j].column) continue;
            Point point = add(source[i].point, source[j].point);
            if (point.infinity) throw std::runtime_error("valid pair is identity");
            pairs.push_back({point,
                             (uint32_t(1) << source[i].column) |
                             (uint32_t(1) << source[j].column),
                             uint16_t(i), uint16_t(j)});
        }
    if (pairs.size() != 1956) throw std::runtime_error("pair domain size changed");
    return pairs;
}

std::vector<int> feature_list(uint64_t x) {
    if (x & 1 || x >> 41) throw std::runtime_error("residual x outside encoding");
    std::vector<int> active{0};
    std::array<int, 40> bits{};
    int count = 0;
    for (int bit = 1; bit <= 40; ++bit) if ((x >> bit) & 1) {
        bits[count++] = bit - 1;
        active.push_back(bit);
    }
    for (int a = 0; a < count; ++a)
        for (int b = a + 1; b < count; ++b) {
            const int i = bits[a], j = bits[b];
            active.push_back(41 + i * (79 - i) / 2 + j - i - 1);
        }
    return active;
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 6)
            throw std::runtime_error("usage: query_filter public_input.txt filters.bin valid_prefix_cap residuals.bin result.json");
        const int prefix_cap = std::stoi(argv[3]);
        if (prefix_cap < 1 || prefix_cap > 3167136)
            throw std::runtime_error("invalid frozen valid-prefix cap");
        const auto setup_start = std::chrono::steady_clock::now();
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("missing public input");
        uint64_t qx, qy, subgroup_order;
        int windows;
        input >> qx >> qy >> subgroup_order >> windows;
        if (!input || qx != 1458168294740ULL || qy != 1672312028033ULL ||
            subgroup_order != 549756390943ULL || windows != 4)
            throw std::runtime_error("frozen public instance changed");
        Point target = finite(qx, qy);
        if (!on_curve(target)) throw std::runtime_error("public target off curve");
        std::array<std::vector<SeedPoint>, 4> source;
        for (int w = 0; w < 4; ++w) {
            int count;
            input >> count;
            if (!input || count != 64) throw std::runtime_error("source count changed");
            for (int k = 0; k < 64; ++k) {
                uint64_t x, y;
                int column, mask;
                input >> x >> y >> column >> mask;
                if (!input || column < 0 || column >= 26 || mask < 0 || mask >= 64 ||
                    !on_curve(finite(x, y)))
                    throw std::runtime_error("invalid source point");
                source[w].push_back({finite(x, y), uint8_t(column), uint8_t(mask)});
            }
        }
        std::string extra;
        if (input >> extra) throw std::runtime_error("trailing public input");
        const auto first = pair_states(source[0]);
        const auto second = pair_states(source[1]);
        std::ifstream filters(argv[2], std::ios::binary);
        if (!filters) throw std::runtime_error("missing frozen filter table");
        std::vector<uint64_t> transpose(size_t(FEATURES) * FILTERS * BLOCKS, 0);
        int no_filter_bins = 0;
        for (int bin = 0; bin < BINS; ++bin) {
            int lo = filters.get(), hi = filters.get(), count = filters.get();
            int reserved = filters.get();
            if (reserved != 0 || count < 0 || count > FILTERS ||
                lo < 0 || hi < 0 || ((hi << 8) | lo) > FEATURES)
                throw std::runtime_error("invalid filter header");
            if (count == 0) ++no_filter_bins;
            for (int eq = 0; eq < FILTERS; ++eq) {
                for (int word = 0; word < WORDS; ++word) {
                    uint64_t value = read_u64(filters);
                    if (eq >= count && value) throw std::runtime_error("nonzero inactive equation");
                    while (value) {
                        const int feature = word * 64 + __builtin_ctzll(value);
                        if (feature >= FEATURES) throw std::runtime_error("filter feature outside family");
                        transpose[(size_t(feature) * FILTERS + eq) * BLOCKS + bin / 64] |=
                            uint64_t(1) << (bin & 63);
                        value &= value - 1;
                    }
                }
            }
        }
        if (filters.get() != EOF) throw std::runtime_error("trailing filter bytes");
        const uint64_t setup_ns = elapsed(setup_start);
        std::ofstream residuals(argv[4], std::ios::binary);
        if (!residuals) throw std::runtime_error("cannot write residual sample");
        const auto query_start = std::chrono::steady_clock::now();
        uint64_t visited = 0, column_rejects = 0, valid = 0, identities = 0;
        uint64_t passed_bins = 0;
        int min_passed = BINS, max_passed = 0;
        std::vector<int> passed_per_residual;
        bool time_cap = false, memory_cap = false;
        for (size_t i = 0; i < first.size() && int(valid) < prefix_cap; ++i) {
            Point after_first = add(target, neg(first[i].point));
            for (size_t j = 0; j < second.size() && int(valid) < prefix_cap; ++j) {
                ++visited;
                if (first[i].columns & second[j].columns) {
                    ++column_rejects;
                    continue;
                }
                Point residual = add(after_first, neg(second[j].point));
                ++valid;
                if (residual.infinity) {
                    ++identities;
                    continue;
                }
                const std::vector<int> active = feature_list(residual.x);
                Accumulator parities{};
                for (int feature : active) {
                    const uint64_t* source_row = transpose.data() +
                                                 size_t(feature) * FILTERS * BLOCKS;
                    for (size_t offset = 0; offset < parities.size(); ++offset)
                        parities[offset] ^= source_row[offset];
                }
                int passed = 0;
                for (int block = 0; block < BLOCKS; ++block) {
                    uint64_t failed = 0;
                    for (int eq = 0; eq < FILTERS; ++eq)
                        failed |= parities[eq * BLOCKS + block];
                    uint64_t mask = ~failed;
                    if (block == BLOCKS - 1) mask &= (uint64_t(1) << (BINS % 64)) - 1;
                    passed += __builtin_popcountll(mask);
                }
                passed_bins += passed;
                min_passed = std::min(min_passed, passed);
                max_passed = std::max(max_passed, passed);
                passed_per_residual.push_back(passed);
                for (int b = 0; b < 6; ++b) residuals.put(char((residual.x >> (8 * b)) & 255));
                write_u16(residuals, i);
                write_u16(residuals, j);
                if (valid % 64 == 0) {
                    time_cap = elapsed(query_start) >= 120000000000ULL;
                    memory_cap = peak_rss() >= 4ULL * 1024 * 1024 * 1024;
                    if (time_cap || memory_cap) break;
                }
            }
            if (time_cap || memory_cap) break;
        }
        residuals.close();
        if (!residuals) throw std::runtime_error("residual write failed");
        std::sort(passed_per_residual.begin(), passed_per_residual.end());
        const int median = passed_per_residual.empty() ? 0 :
                           passed_per_residual[passed_per_residual.size() / 2];
        const uint64_t query_ns = elapsed(query_start);
        const char* status = time_cap ? "TIME_CAP" : memory_cap ? "MEMORY_CAP" :
                             valid == uint64_t(prefix_cap) ? "COMPLETE_PANEL" : "PREFIX_EXHAUSTED";
        std::ofstream result(argv[5]);
        if (!result) throw std::runtime_error("cannot write query receipt");
        result << "{\n\"status\":\"" << status << "\","
               << "\n\"curve_id\":\"EC1N41Ckb1h7d5e80d3c4d0\","
               << "\n\"public_target_q\":[" << qx << ',' << qy << "],"
               << "\n\"candidate_id\":null,\"run_id\":null,"
               << "\n\"valid_prefix_cap\":" << prefix_cap
               << ",\"visited_prefixes\":" << visited
               << ",\"column_rejects\":" << column_rejects
               << ",\"valid_prefixes\":" << valid
               << ",\"identity_residuals\":" << identities
               << ",\"screened_seed_bins_per_nonidentity_residual\":" << BINS
               << ",\"no_filter_seed_bins\":" << no_filter_bins
               << ",\"total_seed_bins_passed\":" << passed_bins
               << ",\"minimum_seed_bins_passed\":" << min_passed
               << ",\"median_seed_bins_passed\":" << median
               << ",\"maximum_seed_bins_passed\":" << max_passed
               << ",\"setup_wall_ns\":" << setup_ns
               << ",\"query_wall_ns\":" << query_ns
               << ",\"peak_rss_bytes\":" << peak_rss() << "\n}\n";
        std::cout << status << " prefixes=" << valid << " passed_bins=" << passed_bins
                  << " query_s=" << query_ns / 1e9 << '\n';
    } catch (const std::exception& error) {
        std::cerr << "query_filter error: " << error.what() << '\n';
        return 1;
    }
}
