// Exact finite-sample GF(2) rank of seed-degree<=2 times x-degree<=2 features.
#include <m4ri/m4ri.h>
#include <sys/resource.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace {
constexpr int ROWS = 80000;
constexpr int SEED_BITS = 12;
constexpr int X_BITS = 40;
constexpr int SEED_FEATURES = 79;
constexpr int X_FEATURES = 821;
constexpr int FEATURES = SEED_FEATURES * X_FEATURES;
constexpr uint64_t FNV_OFFSET = 1469598103934665603ULL;
constexpr uint64_t FNV_PRIME = 1099511628211ULL;

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
int pair_feature(int i, int j, int count) {
    return 1 + count + i * (2 * count - i - 1) / 2 + j - i - 1;
}
template<int BITS, int FEATURES_COUNT>
int active_features(uint64_t bits, std::array<int, FEATURES_COUNT>& output) {
    int active[BITS], count = 0, features = 0;
    output[features++] = 0;
    for (int i = 0; i < BITS; ++i)
        if ((bits >> i) & 1) {
            active[count++] = i;
            output[features++] = 1 + i;
        }
    for (int a = 0; a < count; ++a)
        for (int b = a + 1; b < count; ++b)
            output[features++] = pair_feature(active[a], active[b], BITS);
    return features;
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 3)
            throw std::runtime_error("usage: rank sample.bin rank_result.json");
        const auto start = std::chrono::steady_clock::now();
        std::ifstream input(argv[1], std::ios::binary);
        if (!input) throw std::runtime_error("missing frozen exact sample");
        mzd_t* matrix = mzd_init(ROWS, FEATURES);
        if (!matrix) throw std::runtime_error("M4RI allocation failed");
        uint64_t bits_written = 0, digest = FNV_OFFSET;
        int min_seed_active = SEED_FEATURES, max_seed_active = 0;
        int min_x_active = X_FEATURES, max_x_active = 0;
        for (int row = 0; row < ROWS; ++row) {
            std::array<uint8_t, 8> raw{};
            input.read(reinterpret_cast<char*>(raw.data()), raw.size());
            if (!input) throw std::runtime_error("truncated frozen exact sample");
            const uint64_t seed = uint64_t(raw[0]) | (uint64_t(raw[1]) << 6);
            uint64_t x = 0;
            for (int k = 0; k < 6; ++k) x |= uint64_t(raw[2 + k]) << (8 * k);
            if (raw[0] < 1 || raw[0] > 63 || raw[1] < 1 || raw[1] > 63 ||
                (x & 1) || (x >> 41))
                throw std::runtime_error("invalid exact sample row encoding");
            std::array<int, SEED_FEATURES> seed_active{};
            std::array<int, X_FEATURES> x_active{};
            const int seed_count = active_features<SEED_BITS, SEED_FEATURES>(
                seed, seed_active);
            const int x_count = active_features<X_BITS, X_FEATURES>(
                x >> 1, x_active);
            min_seed_active = std::min(min_seed_active, seed_count);
            max_seed_active = std::max(max_seed_active, seed_count);
            min_x_active = std::min(min_x_active, x_count);
            max_x_active = std::max(max_x_active, x_count);
            for (int a = 0; a < seed_count; ++a)
                for (int b = 0; b < x_count; ++b) {
                    const int feature = seed_active[a] * X_FEATURES + x_active[b];
                    mzd_write_bit(matrix, row, feature, 1);
                    ++bits_written;
                    if (row < 256) {
                        digest ^= uint64_t(feature + 1);
                        digest *= FNV_PRIME;
                    }
                }
        }
        char extra;
        if (input.read(&extra, 1)) throw std::runtime_error("trailing exact sample bytes");
        const uint64_t populate_ns = elapsed(start);
        const auto rank_start = std::chrono::steady_clock::now();
        const int rank = mzd_echelonize_m4ri(matrix, 0, 5);
        const uint64_t rank_ns = elapsed(rank_start);
        if (rank < 0 || rank > FEATURES) throw std::runtime_error("invalid M4RI rank");
        mzd_free(matrix);
        std::ofstream result(argv[2]);
        if (!result) throw std::runtime_error("cannot write rank receipt");
        result << "{\n\"status\":\"" <<
            (rank == FEATURES ? "FULL_FEATURE_RANK" : "NONFULL_RANK") << "\","
               << "\n\"curve_id\":\"EC1N41Ckb1h7d5e80d3c4d0\","
               << "\n\"proposal_id\":\"Q20261010000000\",\"candidate_id\":null,"
               << "\n\"rows\":" << ROWS
               << ",\"seed_features\":" << SEED_FEATURES
               << ",\"x_features\":" << X_FEATURES
               << ",\"tensor_features\":" << FEATURES
               << ",\"rank\":" << rank
               << ",\"nullity\":" << FEATURES - rank
               << ",\"population_bits_written\":" << bits_written
               << ",\"first_256_feature_digest_fnv64\":" << digest
               << ",\"minimum_seed_features_active\":" << min_seed_active
               << ",\"maximum_seed_features_active\":" << max_seed_active
               << ",\"minimum_x_features_active\":" << min_x_active
               << ",\"maximum_x_features_active\":" << max_x_active
               << ",\"population_wall_ns\":" << populate_ns
               << ",\"rank_wall_ns\":" << rank_ns
               << ",\"total_wall_ns\":" << elapsed(start)
               << ",\"peak_rss_bytes\":" << peak_rss() << "\n}\n";
        result.close();
        if (!result) throw std::runtime_error("rank receipt write failed");
        std::cout << "rank=" << rank << '/' << FEATURES
                  << " populate_s=" << populate_ns / 1e9
                  << " rank_s=" << rank_ns / 1e9 << '\n';
    } catch (const std::exception& error) {
        std::cerr << "rank error: " << error.what() << '\n';
        return 1;
    }
}
