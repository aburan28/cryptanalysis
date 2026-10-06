#include <fstream>
#include <iomanip>
#include <cstdlib>
#define BOOLEAN_F5B_NO_MAIN
#include "boolean_f5b_native.cpp"
#include <m4ri/m4ri.h>

static uint64_t reverse_bits(uint64_t value) {
    value = ((value & UINT64_C(0x5555555555555555)) << 1) |
            ((value >> 1) & UINT64_C(0x5555555555555555));
    value = ((value & UINT64_C(0x3333333333333333)) << 2) |
            ((value >> 2) & UINT64_C(0x3333333333333333));
    value = ((value & UINT64_C(0x0f0f0f0f0f0f0f0f)) << 4) |
            ((value >> 4) & UINT64_C(0x0f0f0f0f0f0f0f0f));
    value = ((value & UINT64_C(0x00ff00ff00ff00ff)) << 8) |
            ((value >> 8) & UINT64_C(0x00ff00ff00ff00ff));
    value = ((value & UINT64_C(0x0000ffff0000ffff)) << 16) |
            ((value >> 16) & UINT64_C(0x0000ffff0000ffff));
    return (value << 32) | (value >> 32);
}

static std::vector<Poly> f5_signature_seed(Engine& e,
                                           const std::vector<Poly>& generators) {
    std::vector<Poly> reduced = generators;
    for (;;) {
        std::vector<Poly> next;
        std::vector<Poly> rows(e.universe);
        for (const Poly& polynomial: reduced) {
            Poly remainder = e.normal_rows(polynomial, rows);
            if (!e.zero(remainder)) {
                next.push_back(remainder);
                e.add_reducer(rows, remainder);
            }
        }
        if (next == reduced) break;
        reduced.swap(next);
    }

    std::vector<Labeled> basis;
    for (int i = 0; i < (int)reduced.size(); ++i) {
        basis.push_back({{0, i + 1}, reduced[i], i + 1});
        e.index_label(basis.back());
    }
    std::sort(basis.begin(), basis.end(), [&](const Labeled& a, const Labeled& b) {
        return e.rank_by_mask[e.lead(a.poly)] > e.rank_by_mask[e.lead(b.poly)];
    });
    std::vector<Poly> basis_polys;
    for (const Labeled& labeled: basis) basis_polys.push_back(labeled.poly);
    auto reducer_rows = e.reduction_table(basis_polys);
    std::vector<Pair> pairs;
    for (int i = 0; i < (int)basis.size(); ++i)
        for (int j = i + 1; j < (int)basis.size(); ++j)
            if (e.lead(basis[i].poly) & e.lead(basis[j].poly))
                pairs.push_back(e.critical(basis[i], i, basis[j], j));
    auto sort_pairs = [&]() {
        std::sort(pairs.begin(), pairs.end(), [&](const Pair& a, const Pair& b) {
            return e.pair_less(b, a, basis);
        });
    };
    sort_pairs();
    int number = basis.size();
    while (!pairs.empty() && e.insertions < e.signature_limit) {
        Pair pair = pairs.back();
        pairs.pop_back();
        ++e.pairs_processed;
        if (e.redundant(pair.s1, basis[pair.i1].num) ||
                e.redundant(pair.s2, basis[pair.i2].num)) continue;
        Labeled spoly = e.label_xor(e.label_mul(basis[pair.i1], pair.m1),
                                    e.label_mul(basis[pair.i2], pair.m2));
        Labeled candidate = e.signature_reduce(spoly, basis);
        candidate.poly = e.normal_rows(candidate.poly, reducer_rows);
        if (e.zero(candidate.poly)) {
            e.index_syzygy(candidate.sig);
            continue;
        }
        candidate.num = ++number;
        e.index_label(candidate);
        e.add_reducer(reducer_rows, candidate.poly);
        int new_index = basis.size();
        basis.push_back(candidate);
        ++e.insertions;
        std::vector<Pair> kept;
        for (const Pair& old: pairs)
            if (!e.redundant(old.s1, basis[old.i1].num) &&
                    !e.redundant(old.s2, basis[old.i2].num)) kept.push_back(old);
        pairs.swap(kept);
        for (int i = 0; i < new_index; ++i) {
            if (!(e.lead(basis[i].poly) & e.lead(candidate.poly))) continue;
            Pair next = e.critical(candidate, new_index, basis[i], i);
            if (!e.redundant(next.s1, basis[next.i1].num) &&
                    !e.redundant(next.s2, basis[next.i2].num)) pairs.push_back(next);
        }
        sort_pairs();
    }
    std::vector<Poly> result;
    for (size_t i = reduced.size(); i < basis.size(); ++i)
        if (std::find(result.begin(), result.end(), basis[i].poly) == result.end())
            result.push_back(basis[i].poly);
    return result;
}

struct MatrixStats {
    size_t rows = 0;
    size_t rank = 0;
    size_t f5_rows = 0;
    size_t f5_remainders = 0;
    double generation = 0;
    double population = 0;
    double elimination = 0;
    double extraction = 0;
};

static std::vector<Poly> macaulay_m4ri(Engine& e, const std::vector<Poly>& F,
                                       const std::vector<Poly>& f5_consequences,
                                       int degree, MatrixStats& stats) {
    auto phase = std::chrono::steady_clock::now();
    std::vector<Poly> rows;
    for (const Poly& generator: F) {
        // Screen before initializing a 512-byte row or doing rank lookups.
        // Descending grevlex puts the strongest degree bounds first. The
        // condition is identical to multiply_bounded: even terms which later
        // cancel must meet the bound, preserving the exact original matrix.
        auto terms = e.masks(generator);
        std::reverse(terms.begin(), terms.end());
        for (uint32_t multiplier = 0; multiplier < (uint32_t)e.universe;
             ++multiplier) {
            bool admissible = true;
            for (uint32_t term: terms) {
                if (__builtin_popcount(term | multiplier) > degree) {
                    admissible = false;
                    break;
                }
            }
            if (!admissible) continue;
            Poly row;
            for (uint32_t term: terms) {
                uint32_t rank = e.rank_by_mask[term | multiplier];
                row.w[rank >> 6] ^= uint64_t(1) << (rank & 63);
            }
            if (!e.zero(row)) rows.push_back(row);
        }
    }
    for (const Poly& consequence: f5_consequences) {
        if (e.degree(consequence) <= degree &&
                std::find(rows.begin(), rows.end(), consequence) == rows.end()) {
            rows.push_back(consequence);
            ++stats.f5_rows;
        }
    }
    stats.rows = rows.size();
    if(const char* path=std::getenv("GB_CAPTURE_MATRIX")) {
        std::ofstream file(path);
        file<<"{\"rows\":"<<rows.size()<<",\"cols\":"<<e.universe<<",\"words_hex\":[";
        bool first=true;
        for(const auto& row:rows) for(int w=e.words-1;w>=0;--w) {
            if(!first) file<<",";first=false;
            file<<"\""<<std::hex<<reverse_bits(row.w[w])<<"\"";
        }
        file<<"]}\n";
    }
    stats.generation = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - phase).count();
    phase = std::chrono::steady_clock::now();
    mzd_t *matrix = mzd_init(rows.size(), e.universe);
    for (size_t i = 0; i < rows.size(); ++i) {
        // Both layouts are packed, but their column order is reversed. Copy
        // complete words instead of performing a read/modify/write per term.
        if (e.universe >= 64) {
            word* target = mzd_row(matrix, i);
            for (int w = 0; w < e.words; ++w)
                target[e.words - 1 - w] = reverse_bits(rows[i].w[w]);
            continue;
        }
        for (int word = 0; word < e.words; ++word) {
            uint64_t bits = rows[i].w[word];
            while (bits) {
                int bit = __builtin_ctzll(bits);
                int rank = word * 64 + bit;
                mzd_write_bit(matrix, i, e.universe - 1 - rank, 1);
                bits &= bits - 1;
            }
        }
    }
    stats.population = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - phase).count();
    phase = std::chrono::steady_clock::now();
    // The recurring 12-variable matrix is about 3k x 4k. M4RI's automatic
    // table size is conservative for this shape; k=5 wins on every matched
    // seed while producing the identical reduced row echelon form.
    rci_t rank = mzd_echelonize_m4ri(matrix, 1, 5);
    stats.rank = rank;
    stats.elimination = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - phase).count();
    phase = std::chrono::steady_clock::now();
    std::vector<Poly> echelon;
    for (rci_t i = 0; i < rank; ++i) {
        Poly row;
        if (e.universe < 64) {
            for (int monomial_rank = 0; monomial_rank < e.universe;
                 ++monomial_rank)
                if (mzd_read_bit(matrix, i, e.universe - 1 - monomial_rank))
                    row.w[0] |= uint64_t(1) << monomial_rank;
        } else {
            for (int word = 0; word < e.words; ++word)
                row.w[word] = reverse_bits(mzd_read_bits(
                    matrix, i, e.universe - (word + 1) * 64, 64));
        }
        if (!e.zero(row)) echelon.push_back(row);
    }
    mzd_free(matrix);
    std::vector<uint8_t> has_lead(e.universe, 0);
    for (const Poly& row: echelon) has_lead[e.lead(row)] = 1;
    std::vector<Poly> minimal;
    for (int i = 0; i < (int)echelon.size(); ++i) {
        uint32_t lm = e.lead(echelon[i]);
        bool redundant = false;
        uint32_t subset = lm;
        while (subset) {
            subset = (subset - 1) & lm;
            if (subset != lm && has_lead[subset]) { redundant = true; break; }
        }
        if (!redundant) minimal.push_back(echelon[i]);
    }
    // Every matrix row lies in <F>. Conversely, reduce each original
    // generator by the selected rows and retain its remainder. This gives an
    // ideal-equivalent seed without carrying redundant original generators
    // into the scalar completion tail.
    std::vector<Poly> seed = minimal;
    auto reduction_rows = e.reduction_table(seed);
    for (const Poly& generator: F) {
        Poly remainder = e.normal_rows(generator, reduction_rows);
        if (e.zero(remainder)) continue;
        seed.push_back(remainder);
        e.add_reducer(reduction_rows, remainder);
    }
    for (const Poly& consequence: f5_consequences) {
        Poly remainder = e.normal_rows(consequence, reduction_rows);
        if (e.zero(remainder)) continue;
        seed.push_back(remainder);
        e.add_reducer(reduction_rows, remainder);
        ++stats.f5_remainders;
    }
    auto result = e.reduce_basis(e.complete(seed));
    stats.extraction = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - phase).count();
    return result;
}

int main() {
    std::ios::sync_with_stdio(false);
    int n, generators, signature_limit, degree;
    if (!(std::cin >> n >> generators >> signature_limit >> degree) ||
            n < 1 || n > 12 || signature_limit < 0 || degree < 0 || degree > n)
        return 2;
    Engine engine(n, signature_limit, -1);
    std::vector<Poly> F;
    for (int i = 0; i < generators; ++i) {
        int count;
        std::cin >> count;
        Poly polynomial;
        for (int j = 0; j < count; ++j) {
            uint32_t mask;
            std::cin >> mask;
            uint32_t rank = engine.rank_by_mask[mask];
            polynomial.w[rank >> 6] ^= uint64_t(1) << (rank & 63);
        }
        F.push_back(polynomial);
    }
    auto started = std::chrono::steady_clock::now();
    auto signature_started = std::chrono::steady_clock::now();
    auto signature_seed = f5_signature_seed(engine, F);
    double signature_seconds = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - signature_started).count();
    MatrixStats stats;
    auto basis = macaulay_m4ri(engine, F, signature_seed, degree, stats);
    double seconds = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
    std::cout << "OK " << basis.size() << " " << seconds << " "
              << engine.insertions << " " << engine.pairs_processed << " "
              << signature_seconds << " " << stats.rows << " " << stats.rank << " "
              << stats.generation << " " << stats.population << " "
              << stats.elimination << " " << stats.extraction << " "
              << stats.f5_rows << " " << stats.f5_remainders << "\n";
    for (auto& polynomial: basis) {
        auto masks = engine.masks(polynomial);
        std::sort(masks.begin(), masks.end());
        std::cout << masks.size();
        for (auto mask: masks) std::cout << " " << mask;
        std::cout << "\n";
    }
}
