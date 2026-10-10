// Independent incremental packed-bit Gaussian elimination for the same sample.
#include <sys/resource.h>

#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace {
constexpr int N = 131;
constexpr int ROWS = 17600;
constexpr int FEATURES = 1 + N + N * (N - 1) / 2;
constexpr int WORDS = (FEATURES + 63) / 64;
using Row = std::array<uint64_t, WORDS>;
void set(Row& row, int bit) { row[bit / 64] |= uint64_t(1) << (bit % 64); }
bool test(const Row& row, int bit) { return row[bit / 64] & (uint64_t(1) << (bit % 64)); }
int quadratic(int i, int j) { return 1 + N + i * (2*N-i-1)/2 + j-i-1; }
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
}

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: audit_rank sample.bin result.json");
        const auto start = std::chrono::steady_clock::now();
        std::ifstream in(argv[1], std::ios::binary);
        if (!in) throw std::runtime_error("missing sample");
        std::vector<Row> basis(FEATURES);
        std::vector<uint8_t> occupied(FEATURES, 0);
        int rank = 0, full_at = -1, processed = 0;
        for (int index = 0; index < ROWS; ++index) {
            uint8_t raw[22]{};
            in.read(reinterpret_cast<char*>(raw), sizeof(raw));
            if (!in) throw std::runtime_error("truncated sample");
            if (raw[21] & 0xf8) throw std::runtime_error("invalid field coordinate");
            if (full_at >= 0) continue;
            Row row{};
            int active[N], count = 0;
            set(row, 0);
            for (int bit = 0; bit < N; ++bit)
                if (raw[5 + bit/8] & (1U << (bit%8))) {
                    active[count++] = bit;
                    set(row, 1 + bit);
                }
            for (int a = 0; a < count; ++a)
                for (int b = a+1; b < count; ++b)
                    set(row, quadratic(active[a], active[b]));
            for (int col = 0; col < FEATURES; ++col) {
                if (!test(row, col)) continue;
                if (!occupied[col]) {
                    occupied[col] = 1;
                    basis[col] = row;
                    ++rank;
                    break;
                }
                for (int word = col/64; word < WORDS; ++word)
                    row[word] ^= basis[col][word];
            }
            ++processed;
            if (rank == FEATURES) full_at = index + 1;
        }
        char extra;
        if (in.read(&extra, 1)) throw std::runtime_error("trailing sample bytes");
        std::ofstream out(argv[2]);
        if (!out) throw std::runtime_error("cannot write audit result");
        out << "{\n\"status\":\"" << (rank == FEATURES ? "FULL_FEATURE_RANK" : "NONFULL_RANK")
            << "\",\"rows_read\":" << ROWS
            << ",\"rows_eliminated\":" << processed
            << ",\"full_rank_at_row\":" << full_at
            << ",\"features\":" << FEATURES << ",\"rank\":" << rank
            << ",\"wall_ns\":" << ns(start)
            << ",\"peak_rss_bytes\":" << rss() << "}\n";
        out.close();
        if (!out) throw std::runtime_error("audit result write failed");
        std::cout << "independent_rank=" << rank << '/' << FEATURES
                  << " full_at=" << full_at << '\n';
    } catch (const std::exception& e) {
        std::cerr << "rank audit error: " << e.what() << '\n';
        return 1;
    }
}
