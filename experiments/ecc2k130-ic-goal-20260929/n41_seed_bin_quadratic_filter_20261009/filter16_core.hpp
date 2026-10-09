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
constexpr int FILTERS = 16;
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

