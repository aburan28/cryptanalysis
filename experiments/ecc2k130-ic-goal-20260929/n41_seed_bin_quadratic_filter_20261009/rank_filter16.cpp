// Exact quadratic x equations for each N41 suffix seed-sum pair.
#include <m4ri/m4ri.h>
#include <sys/resource.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr int BINS = 63 * 63;
constexpr int VARS = 40;
constexpr int FEATURES = 1 + VARS + VARS * (VARS - 1) / 2;
constexpr int WORDS = (FEATURES + 63) / 64;
constexpr int FILTERS = 16;
constexpr int ORBITS = 1583568;
using Bits = std::array<uint64_t, WORDS>;

uint64_t elapsed(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
}
void put(Bits& bits, int feature) { bits[feature >> 6] |= uint64_t(1) << (feature & 63); }
bool get(const Bits& bits, int feature) { return (bits[feature >> 6] >> (feature & 63)) & 1; }
int pair_index(int a, int b) {
    return 1 + VARS + a * (2 * VARS - a - 1) / 2 + b - a - 1;
}
Bits features(uint64_t x) {
    if ((x & 1) || x >> 41) throw std::runtime_error("x outside frozen subgroup encoding");
    Bits bits{};
    put(bits, 0);
    std::array<int, VARS> active{};
    int count = 0;
    for (int bit = 1; bit <= 40; ++bit) if ((x >> bit) & 1) {
        active[count++] = bit - 1;
        put(bits, bit);
    }
    for (int a = 0; a < count; ++a)
        for (int b = a + 1; b < count; ++b)
            put(bits, pair_index(active[a], active[b]));
    return bits;
}
int parity(const Bits& a, const Bits& b) {
    int result = 0;
    for (int word = 0; word < WORDS; ++word)
        result ^= __builtin_parityll(a[word] & b[word]);
    return result;
}
void write_u16(std::ofstream& out, uint16_t n) {
    out.put(char(n & 255)); out.put(char((n >> 8) & 255));
}
void write_u64(std::ofstream& out, uint64_t n) {
    for (int shift = 0; shift < 64; shift += 8) out.put(char((n >> shift) & 255));
}
struct Equation {
    int free_feature = 0;
    int support = 0;
    Bits coefficients{};
};
bool better(const Equation& a, const Equation& b) {
    return a.support < b.support ||
           (a.support == b.support && a.free_feature < b.free_feature);
}
struct Bin {
    std::vector<uint64_t> xs;
    uint16_t rank = 0;
    uint8_t equations = 0;
    std::array<Bits, FILTERS> selected{};
};
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 4)
            throw std::runtime_error("usage: rank_filter x_orbits.bin filters.bin filter_result.json");
        const auto start = std::chrono::steady_clock::now();
        std::ifstream input(argv[1], std::ios::binary);
        if (!input) throw std::runtime_error("cannot open exact x orbit input");
        std::vector<Bin> bins(BINS);
        std::vector<uint64_t> all_x;
        all_x.reserve(ORBITS);
        for (int row = 0; row < ORBITS; ++row) {
            std::array<uint8_t, 12> raw{};
            input.read(reinterpret_cast<char*>(raw.data()), raw.size());
            if (!input) throw std::runtime_error("truncated x orbit input");
            const int s = raw[0], t = raw[1];
            const int i = raw[8] | (raw[9] << 8);
            const int j = raw[10] | (raw[11] << 8);
            if (s < 1 || s > 63 || t < 1 || t > 63 || i >= 1956 || j >= 1956)
                throw std::runtime_error("invalid orbit encoding");
            uint64_t x = 0;
            for (int b = 0; b < 6; ++b) x |= uint64_t(raw[2 + b]) << (8 * b);
            if ((x & 1) || (x >> 41)) throw std::runtime_error("invalid orbit x");
            bins[(s - 1) * 63 + (t - 1)].xs.push_back(x);
            all_x.push_back(x);
        }
        char trailing;
        if (input.read(&trailing, 1)) throw std::runtime_error("trailing x orbit bytes");
        std::sort(all_x.begin(), all_x.end());
        if (std::adjacent_find(all_x.begin(), all_x.end()) != all_x.end())
            throw std::runtime_error("two seed bins share an x orbit");
        int min_bin = ORBITS, max_bin = 0;
        for (Bin& bin : bins) {
            min_bin = std::min(min_bin, int(bin.xs.size()));
            max_bin = std::max(max_bin, int(bin.xs.size()));
        }
        if (min_bin != 128 || max_bin != 832)
            throw std::runtime_error("seed-bin size range changed");
        const uint64_t input_ns = elapsed(start);
        std::map<int, int> rank_hist;
        int full_rank_bins = 0, equation_total = 0;
        int min_support = FEATURES + 1, max_support = 0;
        for (Bin& bin : bins) {
            mzd_t* matrix = mzd_init(bin.xs.size(), FEATURES);
            if (!matrix) throw std::runtime_error("M4RI matrix allocation failed");
            for (size_t row = 0; row < bin.xs.size(); ++row) {
                const Bits value = features(bin.xs[row]);
                for (int bit = 0; bit < FEATURES; ++bit)
                    if (get(value, bit)) mzd_write_bit(matrix, row, bit, 1);
            }
            const int rank = mzd_echelonize_m4ri(matrix, 1, 5);
            bin.rank = rank;
            rank_hist[rank] += 1;
            if (rank == FEATURES) {
                ++full_rank_bins;
            } else {
                std::vector<int> pivots;
                std::array<bool, FEATURES> is_pivot{};
                int next = 0;
                for (int row = 0; row < rank; ++row) {
                    while (next < FEATURES && !mzd_read_bit(matrix, row, next)) ++next;
                    if (next >= FEATURES) throw std::runtime_error("RREF pivot missing");
                    pivots.push_back(next);
                    is_pivot[next++] = true;
                }
                std::vector<Equation> best;
                for (int col = 0; col < FEATURES; ++col) {
                    if (is_pivot[col]) continue;
                    Equation equation;
                    equation.free_feature = col;
                    equation.support = 1;
                    put(equation.coefficients, col);
                    for (int row = 0; row < rank; ++row) {
                        if (mzd_read_bit(matrix, row, col)) {
                            put(equation.coefficients, pivots[row]);
                            ++equation.support;
                        }
                    }
                    best.push_back(equation);
                    std::sort(best.begin(), best.end(), better);
                    if (best.size() > FILTERS) best.pop_back();
                }
                bin.equations = best.size();
                equation_total += bin.equations;
                for (size_t k = 0; k < best.size(); ++k) {
                    bin.selected[k] = best[k].coefficients;
                    min_support = std::min(min_support, best[k].support);
                    max_support = std::max(max_support, best[k].support);
                }
            }
            mzd_free(matrix);
        }
        const uint64_t rank_ns = elapsed(start) - input_ns;
        uint64_t violations = 0;
        for (const Bin& bin : bins)
            for (uint64_t x : bin.xs) {
                const Bits row = features(x);
                for (int k = 0; k < bin.equations; ++k)
                    violations += parity(row, bin.selected[k]);
            }
        if (violations) throw std::runtime_error("selected equation fails an exact bin x");
        const uint64_t check_ns = elapsed(start) - input_ns - rank_ns;
        std::ofstream filters(argv[2], std::ios::binary);
        if (!filters) throw std::runtime_error("cannot write filter table");
        for (const Bin& bin : bins) {
            write_u16(filters, bin.rank);
            filters.put(char(bin.equations));
            filters.put(char(0));
            for (const Bits& equation : bin.selected)
                for (uint64_t word : equation) write_u64(filters, word);
        }
        filters.close();
        if (!filters) throw std::runtime_error("filter table write failed");
        rusage usage{}; getrusage(RUSAGE_SELF, &usage);
        const uint64_t peak =
#if defined(__APPLE__)
            uint64_t(usage.ru_maxrss);
#else
            uint64_t(usage.ru_maxrss) * 1024;
#endif
        std::ofstream receipt(argv[3]);
        if (!receipt) throw std::runtime_error("cannot write rank receipt");
        receipt << "{\n\"status\":\"EXACT_QUADRATIC_BIN_FILTERS\","
                << "\n\"bin_count\":" << BINS
                << ",\"x_orbits\":" << ORBITS
                << ",\"feature_count\":" << FEATURES
                << ",\"full_rank_bins\":" << full_rank_bins
                << ",\"selected_equations\":" << equation_total
                << ",\"min_equation_support\":" << min_support
                << ",\"max_equation_support\":" << max_support
                << ",\"training_violations\":" << violations
                << ",\"input_wall_ns\":" << input_ns
                << ",\"rank_wall_ns\":" << rank_ns
                << ",\"check_wall_ns\":" << check_ns
                << ",\"total_wall_ns\":" << elapsed(start)
                << ",\"peak_rss_bytes\":" << peak
                << ",\"rank_histogram\":{\n";
        bool first = true;
        for (const auto& entry : rank_hist) {
            if (!first) receipt << ",\n";
            first = false;
            receipt << "\"" << entry.first << "\":" << entry.second;
        }
        receipt << "\n}}\n";
        std::cout << "bins=" << BINS << " full_rank=" << full_rank_bins
                  << " filters=" << equation_total
                  << " rank_s=" << rank_ns / 1e9 << '\n';
    } catch (const std::exception& error) {
        std::cerr << "rank_filter error: " << error.what() << '\n';
        return 1;
    }
}
