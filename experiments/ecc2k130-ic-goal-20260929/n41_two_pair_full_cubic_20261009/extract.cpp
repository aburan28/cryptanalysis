// Extract low-support null equations after the frozen mixed-cubic rank screen.
#include <m4ri/m4ri.h>
#include <sys/resource.h>

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
constexpr int V = 93, S = 12, N = 80000, F = 48818, EXPECTED_RANK = 47206;
struct Term { int a, b, c; };
int pair_key(int a, int b) { return a * V + b; }
int triple_key(int a, int b, int c) { return (a * V + b) * V + c; }
uint64_t elapsed(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
}
uint64_t field_coordinate(const std::array<uint8_t, 18>& raw, int offset) {
    uint64_t value = 0;
    for (int k = 0; k < 6; ++k) value |= uint64_t(raw[offset + k]) << (8 * k);
    return value;
}
struct Equation { int free_column; std::vector<int> support; };
bool better(const Equation& a, const Equation& b) {
    return a.support.size() < b.support.size() ||
           (a.support.size() == b.support.size() && a.free_column < b.free_column);
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: extract rows.bin equations.json");
        std::ifstream input(argv[1], std::ios::binary);
        if (!input) throw std::runtime_error("cannot open frozen rows");
        const auto start = std::chrono::steady_clock::now();
        std::vector<int> pairs(V * V, -1), triples(V * V * V, -1);
        std::vector<Term> terms;
        terms.reserve(F);
        terms.push_back({-1, -1, -1});
        for (int a = 0; a < V; ++a) terms.push_back({a, -1, -1});
        for (int a = 0; a < V; ++a) for (int b = a + 1; b < V; ++b) {
            pairs[pair_key(a, b)] = static_cast<int>(terms.size());
            terms.push_back({a, b, -1});
        }
        for (int a = 0; a < S; ++a)
            for (int b = a + 1; b < V; ++b)
                for (int c = b + 1; c < V; ++c) {
                    triples[triple_key(a, b, c)] = static_cast<int>(terms.size());
                    terms.push_back({a, b, c});
                }
        if (terms.size() != F) throw std::runtime_error("feature count differs");
        mzd_t* matrix = mzd_init(N, F);
        if (!matrix) throw std::runtime_error("M4RI allocation failed");
        for (int r = 0; r < N; ++r) {
            std::array<uint8_t, 18> raw{};
            input.read(reinterpret_cast<char*>(raw.data()), raw.size());
            if (!input) throw std::runtime_error("truncated row file");
            uint64_t x = field_coordinate(raw, 2), y = field_coordinate(raw, 8);
            if (raw[0] >= 64 || raw[1] >= 64 || (x & 1) || x >> 41 || y >> 41)
                throw std::runtime_error("invalid row encoding");
            std::array<int, V> active{};
            int n = 0;
            for (int b = 0; b < 6; ++b) if ((raw[0] >> b) & 1) active[n++] = b;
            for (int b = 0; b < 6; ++b) if ((raw[1] >> b) & 1) active[n++] = 6 + b;
            for (int b = 1; b <= 40; ++b) if ((x >> b) & 1) active[n++] = 11 + b;
            for (int b = 0; b <= 40; ++b) if ((y >> b) & 1) active[n++] = 52 + b;
            mzd_write_bit(matrix, r, 0, 1);
            for (int a = 0; a < n; ++a) mzd_write_bit(matrix, r, 1 + active[a], 1);
            for (int a = 0; a < n; ++a)
                for (int b = a + 1; b < n; ++b)
                    mzd_write_bit(matrix, r, pairs[pair_key(active[a], active[b])], 1);
            for (int a = 0; a < n && active[a] < S; ++a)
                for (int b = a + 1; b < n; ++b)
                    for (int c = b + 1; c < n; ++c)
                        mzd_write_bit(matrix, r,
                                      triples[triple_key(active[a], active[b], active[c])], 1);
        }
        char trailing;
        if (input.read(&trailing, 1)) throw std::runtime_error("trailing row bytes");
        const uint64_t populate_ns = elapsed(start);
        const rci_t rank = mzd_echelonize_m4ri(matrix, 1, 5);
        const uint64_t reduce_ns = elapsed(start) - populate_ns;
        if (rank != EXPECTED_RANK) throw std::runtime_error("rank changed under RREF");
        std::vector<int> pivots;
        std::vector<bool> is_pivot(F, false);
        pivots.reserve(rank);
        int next_search = 0;
        for (int row = 0; row < rank; ++row) {
            while (next_search < F && !mzd_read_bit(matrix, row, next_search)) ++next_search;
            if (next_search >= F) throw std::runtime_error("RREF row lost pivot");
            pivots.push_back(next_search);
            is_pivot[next_search] = true;
            ++next_search;
        }
        std::vector<Equation> best;
        int mixed_candidates = 0, lowest_any = F + 1;
        for (int col = 0; col < F; ++col) {
            if (is_pivot[col]) continue;
            Equation equation{col, {col}};
            bool has_seed = terms[col].a >= 0 && terms[col].a < S;
            bool has_coordinate = terms[col].a >= S || terms[col].b >= S || terms[col].c >= S;
            for (int row = 0; row < rank; ++row) {
                if (!mzd_read_bit(matrix, row, col)) continue;
                const int term = pivots[row];
                equation.support.push_back(term);
                has_seed |= terms[term].a >= 0 && terms[term].a < S;
                has_coordinate |= terms[term].a >= S || terms[term].b >= S || terms[term].c >= S;
            }
            lowest_any = std::min(lowest_any, static_cast<int>(equation.support.size()));
            if (!(has_seed && has_coordinate)) continue;
            ++mixed_candidates;
            std::sort(equation.support.begin(), equation.support.end());
            best.push_back(std::move(equation));
            std::sort(best.begin(), best.end(), better);
            if (best.size() > 8) best.pop_back();
        }
        if (best.empty()) throw std::runtime_error("no seed-coordinate null equation found");
        // Check the extracted equations against all original exact rows by
        // evaluating their monomials, rather than trusting the reduced matrix.
        input.clear(); input.seekg(0);
        std::vector<int> violations(best.size(), 0);
        for (int r = 0; r < N; ++r) {
            std::array<uint8_t, 18> raw{};
            input.read(reinterpret_cast<char*>(raw.data()), raw.size());
            const uint64_t x = field_coordinate(raw, 2), y = field_coordinate(raw, 8);
            const uint64_t packed_low = uint64_t(raw[0]) | (uint64_t(raw[1]) << 6) |
                                        ((x >> 1) << 12);
            auto active = [&](int bit) {
                if (bit < 0) return true;
                if (bit < 52) return ((packed_low >> bit) & 1) != 0;
                return ((y >> (bit - 52)) & 1) != 0;
            };
            for (size_t q = 0; q < best.size(); ++q) {
                int parity = 0;
                for (int feature : best[q].support) {
                    const Term term = terms[feature];
                    parity ^= active(term.a) && active(term.b) && active(term.c);
                }
                violations[q] += parity;
            }
        }
        if (std::any_of(violations.begin(), violations.end(), [](int v) { return v != 0; }))
            throw std::runtime_error("extracted equation fails original exact rows");
        rusage usage{}; getrusage(RUSAGE_SELF, &usage);
        const uint64_t peak =
#if defined(__APPLE__)
            uint64_t(usage.ru_maxrss);
#else
            uint64_t(usage.ru_maxrss) * 1024;
#endif
        std::ofstream output(argv[2]);
        if (!output) throw std::runtime_error("cannot write equation receipt");
        output << "{\n\"status\":\"EXTRACTED_EIGHT_RREF_EQUATIONS\","
               << "\n\"feature_count\":" << F << ",\"rank\":" << rank
               << ",\"nullity\":" << F - rank << ",\"mixed_candidates\":"
               << mixed_candidates << ",\"lowest_any_support\":" << lowest_any
               << ",\"population_wall_ns\":" << populate_ns
               << ",\"rref_wall_ns\":" << reduce_ns
               << ",\"total_wall_ns\":" << elapsed(start)
               << ",\"peak_rss_bytes\":" << peak << ",\n\"equations\":[\n";
        for (size_t k = 0; k < best.size(); ++k) {
            if (k) output << ",\n";
            output << "{\"free_column\":" << best[k].free_column
                   << ",\"support_size\":" << best[k].support.size()
                   << ",\"training_violations\":" << violations[k]
                   << ",\"support\":[";
            for (size_t p = 0; p < best[k].support.size(); ++p) {
                if (p) output << ',';
                output << best[k].support[p];
            }
            output << "]}";
        }
        output << "\n]}\n";
        mzd_free(matrix);
        std::cout << "rank=" << rank << " mixed_null_candidates=" << mixed_candidates
                  << " best_support=" << best.front().support.size() << '\n';
    } catch (const std::exception& error) {
        std::cerr << "extract error: " << error.what() << '\n';
        return 1;
    }
}
