// Full-coordinate mixed-cubic GF(2) rank for the frozen N41 pair-pair rows.
#include <m4ri/m4ri.h>
#include <sys/resource.h>

#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr int kSeed = 12;
constexpr int kCoord = 81;
constexpr int kVars = kSeed + kCoord;
constexpr int kRows = 80000;
constexpr int kFeatureCount = 48818;
constexpr int kCoordFeatures = 1 + kCoord + kCoord * (kCoord - 1) / 2;

uint64_t elapsed(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
}

int triple_key(int a, int b, int c) { return (a * kVars + b) * kVars + c; }
int pair_key(int a, int b) { return a * kVars + b; }

struct MatrixHandle {
    mzd_t* value;
    explicit MatrixHandle(rci_t rows, rci_t cols) : value(mzd_init(rows, cols)) {
        if (!value) throw std::runtime_error("M4RI allocation failed");
    }
    ~MatrixHandle() { mzd_free(value); }
    MatrixHandle(const MatrixHandle&) = delete;
    MatrixHandle& operator=(const MatrixHandle&) = delete;
};

uint64_t coordinate(const std::array<uint8_t, 18>& row, int offset) {
    uint64_t value = 0;
    for (int k = 0; k < 6; ++k) value |= uint64_t(row[offset + k]) << (8 * k);
    return value;
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: rank rows.bin rank.json");
        std::ifstream input(argv[1], std::ios::binary);
        if (!input) throw std::runtime_error("cannot open frozen rows");
        const auto start = std::chrono::steady_clock::now();
        std::vector<int> pair(kVars * kVars, -1);
        std::vector<int> triple(kVars * kVars * kVars, -1);
        std::vector<int> coord_pair(kCoord * kCoord, -1);
        int next = 1;
        for (int a = 0; a < kVars; ++a) ++next;
        for (int a = 0; a < kVars; ++a)
            for (int b = a + 1; b < kVars; ++b) pair[pair_key(a, b)] = next++;
        for (int a = 0; a < kSeed; ++a)
            for (int b = a + 1; b < kVars; ++b)
                for (int c = b + 1; c < kVars; ++c)
                    triple[triple_key(a, b, c)] = next++;
        if (next != kFeatureCount)
            throw std::runtime_error("mixed-cubic feature count changed: " + std::to_string(next));
        int next_coord = 1 + kCoord;
        for (int a = 0; a < kCoord; ++a)
            for (int b = a + 1; b < kCoord; ++b)
                coord_pair[a * kCoord + b] = next_coord++;
        if (next_coord != kCoordFeatures) throw std::runtime_error("coordinate features changed");

        MatrixHandle mixed(kRows, kFeatureCount);
        MatrixHandle coordinates(kRows, kCoordFeatures);
        uint64_t active_seed_sum = 0;
        uint64_t active_coordinate_sum = 0;
        for (int r = 0; r < kRows; ++r) {
            std::array<uint8_t, 18> raw{};
            input.read(reinterpret_cast<char*>(raw.data()), raw.size());
            if (!input) throw std::runtime_error("truncated frozen row file");
            const uint64_t x = coordinate(raw, 2), y = coordinate(raw, 8);
            const int i = raw[14] | (raw[15] << 8);
            const int j = raw[16] | (raw[17] << 8);
            if (raw[0] >= 64 || raw[1] >= 64 || (x & 1) ||
                (x >> 41) || (y >> 41) || i >= 1956 || j >= 1956)
                throw std::runtime_error("invalid frozen row encoding");
            std::array<int, kVars> active{};
            std::array<int, kCoord> active_coord{};
            int n = 0, nc = 0;
            for (int b = 0; b < 6; ++b) if ((raw[0] >> b) & 1) active[n++] = b;
            for (int b = 0; b < 6; ++b) if ((raw[1] >> b) & 1) active[n++] = 6 + b;
            active_seed_sum += n;
            for (int b = 1; b <= 40; ++b) if ((x >> b) & 1) {
                active[n++] = 12 + b - 1;
                active_coord[nc++] = b - 1;
            }
            for (int b = 0; b <= 40; ++b) if ((y >> b) & 1) {
                active[n++] = 52 + b;
                active_coord[nc++] = 40 + b;
            }
            active_coordinate_sum += nc;
            mzd_write_bit(mixed.value, r, 0, 1);
            mzd_write_bit(coordinates.value, r, 0, 1);
            for (int a = 0; a < n; ++a) mzd_write_bit(mixed.value, r, 1 + active[a], 1);
            for (int a = 0; a < nc; ++a)
                mzd_write_bit(coordinates.value, r, 1 + active_coord[a], 1);
            for (int a = 0; a < n; ++a)
                for (int b = a + 1; b < n; ++b)
                    mzd_write_bit(mixed.value, r, pair[pair_key(active[a], active[b])], 1);
            for (int a = 0; a < nc; ++a)
                for (int b = a + 1; b < nc; ++b)
                    mzd_write_bit(coordinates.value, r,
                                  coord_pair[active_coord[a] * kCoord + active_coord[b]], 1);
            for (int a = 0; a < n && active[a] < kSeed; ++a)
                for (int b = a + 1; b < n; ++b)
                    for (int c = b + 1; c < n; ++c)
                        mzd_write_bit(mixed.value, r,
                                      triple[triple_key(active[a], active[b], active[c])], 1);
        }
        char trailing;
        if (input.read(&trailing, 1)) throw std::runtime_error("trailing frozen row bytes");
        const uint64_t population_ns = elapsed(start);
        const rci_t coord_rank = mzd_echelonize_m4ri(coordinates.value, 0, 5);
        const uint64_t coordinate_rank_ns = elapsed(start) - population_ns;
        const rci_t mixed_rank = mzd_echelonize_m4ri(mixed.value, 0, 5);
        const uint64_t total_ns = elapsed(start);
        rusage usage{};
        getrusage(RUSAGE_SELF, &usage);
        const uint64_t peak_rss =
#if defined(__APPLE__)
            uint64_t(usage.ru_maxrss);
#else
            uint64_t(usage.ru_maxrss) * 1024;
#endif
        std::ofstream result(argv[2]);
        if (!result) throw std::runtime_error("cannot write rank receipt");
        result << "{\n\"status\":\""
               << (mixed_rank == kFeatureCount ? "FULL_MIXED_CUBIC_RANK" : "DEFICIENT_OR_INCOMPLETE")
               << "\",\n\"rows\":" << kRows << ",\"feature_count\":" << kFeatureCount
               << ",\"rank\":" << mixed_rank << ",\"nullity\":" << kFeatureCount - mixed_rank
               << ",\"coordinate_feature_count\":" << kCoordFeatures
               << ",\"coordinate_rank\":" << coord_rank
               << ",\"mixed_excess_nullity\":"
               << (kFeatureCount - mixed_rank) - (kCoordFeatures - coord_rank)
               << ",\"active_seed_sum\":" << active_seed_sum
               << ",\"active_coordinate_sum\":" << active_coordinate_sum
               << ",\"population_wall_ns\":" << population_ns
               << ",\"coordinate_rank_wall_ns\":" << coordinate_rank_ns
               << ",\"mixed_rank_wall_ns\":" << total_ns - population_ns - coordinate_rank_ns
               << ",\"total_wall_ns\":" << total_ns
               << ",\"peak_rss_bytes\":" << peak_rss << "\n}\n";
        std::cout << "mixed=" << mixed_rank << "/" << kFeatureCount
                  << " coordinate=" << coord_rank << "/" << kCoordFeatures
                  << " wall_s=" << total_ns / 1e9 << '\n';
    } catch (const std::exception& error) {
        std::cerr << "rank error: " << error.what() << '\n';
        return 1;
    }
}
