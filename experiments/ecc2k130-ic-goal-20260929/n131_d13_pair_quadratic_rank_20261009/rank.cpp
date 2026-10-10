// M4RI rank of all Boolean coordinate monomials of degree at most two.
#include <m4ri/m4ri.h>
#include <sys/resource.h>

#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>

namespace {
constexpr int N = 131;
constexpr int ROWS = 17600;
constexpr int FEATURES = 1 + N + N * (N - 1) / 2;
constexpr uint64_t FNV_OFFSET = 1469598103934665603ULL;
constexpr uint64_t FNV_PRIME = 1099511628211ULL;
uint64_t ns(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
}
uint64_t rss() {
    rusage usage{}; getrusage(RUSAGE_SELF, &usage);
#ifdef __APPLE__
    return uint64_t(usage.ru_maxrss);
#else
    return uint64_t(usage.ru_maxrss) * 1024;
#endif
}
int quadratic(int i, int j) {
    return 1 + N + i * (2 * N - i - 1) / 2 + (j - i - 1);
}
}

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: rank sample.bin result.json");
        const auto start = std::chrono::steady_clock::now();
        std::ifstream in(argv[1], std::ios::binary);
        if (!in) throw std::runtime_error("missing frozen sample");
        mzd_t* matrix = mzd_init(ROWS, FEATURES);
        if (!matrix) throw std::runtime_error("M4RI allocation failed");
        uint64_t digest = FNV_OFFSET, populated = 0;
        for (int row = 0; row < ROWS; ++row) {
            uint8_t raw[22]{};
            in.read(reinterpret_cast<char*>(raw), sizeof(raw));
            if (!in) throw std::runtime_error("truncated sample");
            if (raw[21] & 0xf8) throw std::runtime_error("phi exceeds 131 bits");
            int active[N], count = 0;
            auto put = [&](int col) {
                mzd_write_bit(matrix, row, col, 1);
                ++populated;
                if (row < 256) {
                    digest ^= uint64_t(col + 1);
                    digest *= FNV_PRIME;
                }
            };
            put(0);
            for (int i = 0; i < N; ++i)
                if (raw[5 + i / 8] & (1U << (i % 8))) {
                    active[count++] = i;
                    put(1 + i);
                }
            for (int a = 0; a < count; ++a)
                for (int b = a + 1; b < count; ++b)
                    put(quadratic(active[a], active[b]));
        }
        char extra;
        if (in.read(&extra, 1)) throw std::runtime_error("trailing sample bytes");
        const uint64_t populate_ns = ns(start);
        const auto rank_start = std::chrono::steady_clock::now();
        const int rank = mzd_echelonize_m4ri(matrix, 0, 5);
        const uint64_t rank_ns = ns(rank_start);
        mzd_free(matrix);
        if (rank < 0 || rank > FEATURES) throw std::runtime_error("invalid rank");
        std::ofstream out(argv[2]);
        if (!out) throw std::runtime_error("cannot write result");
        out << "{\n\"status\":\"" << (rank == FEATURES ? "FULL_FEATURE_RANK" : "NONFULL_RANK")
            << "\",\"rows\":" << ROWS << ",\"features\":" << FEATURES
            << ",\"rank\":" << rank << ",\"nullity\":" << FEATURES - rank
            << ",\"feature_bits_written\":" << populated
            << ",\"first_256_feature_digest_fnv64\":" << digest
            << ",\"population_wall_ns\":" << populate_ns
            << ",\"rank_wall_ns\":" << rank_ns
            << ",\"total_wall_ns\":" << ns(start)
            << ",\"peak_rss_bytes\":" << rss() << "}\n";
        out.close();
        if (!out) throw std::runtime_error("result write failed");
        std::cout << "rank=" << rank << '/' << FEATURES
                  << " rank_s=" << rank_ns / 1e9 << '\n';
    } catch (const std::exception& e) {
        std::cerr << "rank error: " << e.what() << '\n';
        return 1;
    }
}
