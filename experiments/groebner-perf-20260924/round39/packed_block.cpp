// Bounded CPU research pilot; not a polynomial solver or automatic dispatch.
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>

struct Counters {
    uint64_t coefficient_reads = 0, xor_words = 0, and_words = 0;
    uint64_t copied_words = 0, nonzero_updates = 0, partial_updates = 0;
};

struct Matrix {
    uint32_t rows, columns, lanes, per_word, words;
    uint64_t unit, repeat;
    std::vector<uint64_t> values;

    Matrix(uint32_t m, uint32_t n, uint32_t l)
        : rows(m), columns(n), lanes(l), per_word(64 / l), words((n + per_word - 1) / per_word),
          unit((uint64_t(1) << l) - 1), repeat(UINT64_MAX / unit), values(size_t(m) * words, 0)
    {
    }

    uint64_t *row(uint32_t i) { return values.data() + size_t(i) * words; }
    const uint64_t *row(uint32_t i) const { return values.data() + size_t(i) * words; }
    uint64_t get(uint32_t i, uint32_t j) const
    {
        return (row(i)[j / per_word] >> ((j % per_word) * lanes)) & unit;
    }
    void set(uint32_t i, uint32_t j, uint64_t value)
    {
        const uint32_t shift = (j % per_word) * lanes;
        auto &word = row(i)[j / per_word];
        word = (word & ~(unit << shift)) | (value << shift);
    }
};

// Return a constant GF(2) row combination whose coefficient function is one.
// Coefficient Gaussian elimination uses its own compact equation selectors.
static std::vector<uint32_t> unit_combination(const Matrix &a, uint32_t start, uint32_t column,
                                              Counters &count)
{
    const uint32_t selector_words = (a.rows + 63) / 64;
    std::vector<uint64_t> pivots(a.lanes, 0);
    std::vector<uint64_t> selectors(size_t(a.lanes) * selector_words, 0);
    std::vector<uint64_t> candidate(selector_words), answer(selector_words, 0);
    for (uint32_t i = start; i < a.rows; ++i) {
        uint64_t value = a.get(i, column);
        ++count.coefficient_reads;
        std::fill(candidate.begin(), candidate.end(), 0);
        candidate[i / 64] = uint64_t(1) << (i % 64);
        while (value) {
            const uint32_t bit = 63u - uint32_t(__builtin_clzll(value));
            auto *selector = selectors.data() + size_t(bit) * selector_words;
            if (!pivots[bit]) {
                pivots[bit] = value;
                std::copy(candidate.begin(), candidate.end(), selector);
                count.copied_words += selector_words;
                break;
            }
            value ^= pivots[bit];
            for (uint32_t w = 0; w < selector_words; ++w) candidate[w] ^= selector[w];
            count.xor_words += 1 + selector_words;
        }
    }
    uint64_t remaining = a.unit;
    while (remaining) {
        const uint32_t bit = 63u - uint32_t(__builtin_clzll(remaining));
        if (!pivots[bit]) return {};
        remaining ^= pivots[bit];
        const auto *selector = selectors.data() + size_t(bit) * selector_words;
        for (uint32_t w = 0; w < selector_words; ++w) answer[w] ^= selector[w];
        count.xor_words += 1 + selector_words;
    }
    std::vector<uint32_t> selected;
    for (uint32_t i = start; i < a.rows; ++i)
        if ((answer[i / 64] >> (i % 64)) & 1) selected.push_back(i);
    return selected;
}

static void replace_and_swap(Matrix &a, const std::vector<uint32_t> &selected, uint32_t rank,
                             Counters &count)
{
    std::vector<uint64_t> combined(a.words, 0);
    for (uint32_t i : selected) {
        const auto *source = a.row(i);
        for (uint32_t w = 0; w < a.words; ++w) combined[w] ^= source[w];
        count.xor_words += a.words;
    }
    auto *replacement = a.row(selected.front());
    std::copy(combined.begin(), combined.end(), replacement);
    count.copied_words += a.words;
    if (rank != selected.front()) {
        auto *destination = a.row(rank);
        for (uint32_t w = 0; w < a.words; ++w) std::swap(destination[w], replacement[w]);
        count.copied_words += 2 * a.words;
    }
}

static void swap_rows(Matrix &a, uint32_t left, uint32_t right, Counters &count)
{
    if (left == right) return;
    for (uint32_t w = 0; w < a.words; ++w) std::swap(a.row(left)[w], a.row(right)[w]);
    count.copied_words += 2 * a.words;
}

static void subtract(Matrix &a, uint32_t destination, uint32_t source, uint64_t coefficient,
                     Counters &count)
{
    auto *dst = a.row(destination);
    const auto *src = a.row(source);
    if (coefficient == a.unit) {
        for (uint32_t w = 0; w < a.words; ++w) dst[w] ^= src[w];
    } else {
        // Repeat the truth-vector coefficient in every packed entry. This is
        // multiplication in the Boolean-function ring, not integer division.
        const uint64_t mask = coefficient * a.repeat;
        for (uint32_t w = 0; w < a.words; ++w) dst[w] ^= src[w] & mask;
        count.and_words += a.words;
    }
    count.xor_words += a.words;
}

static std::vector<uint32_t> eliminate(Matrix &a, Matrix &proof, Counters &count)
{
    std::vector<uint32_t> pivots;
    for (uint32_t i = 0; i < a.rows; ++i) proof.set(i, i, a.unit);
    for (uint32_t column = a.columns; column-- > 0;) {
        const uint32_t rank = uint32_t(pivots.size());
        std::vector<uint32_t> selected;
        if (a.lanes == 1) {
            // The scalar control uses ordinary first-pivot search, not the
            // more expensive function-valued combination search.
            for (uint32_t i = rank; i < a.rows; ++i) {
                ++count.coefficient_reads;
                if (a.get(i, column)) {
                    selected.push_back(i);
                    break;
                }
            }
        } else {
            selected = unit_combination(a, rank, column, count);
        }
        if (selected.empty()) continue;
        if (a.lanes == 1) {
            swap_rows(a, selected.front(), rank, count);
            swap_rows(proof, selected.front(), rank, count);
        } else {
            replace_and_swap(a, selected, rank, count);
            replace_and_swap(proof, selected, rank, count);
        }
        if (a.get(rank, column) != a.unit) throw std::logic_error("nonunit pivot");
        for (uint32_t i = 0; i < a.rows; ++i) {
            if (i == rank) continue;
            const uint64_t coefficient = a.get(i, column);
            ++count.coefficient_reads;
            if (!coefficient) continue;
            ++count.nonzero_updates;
            count.partial_updates += coefficient != a.unit;
            subtract(a, i, rank, coefficient, count);
            subtract(proof, i, rank, coefficient, count);
        }
        pivots.push_back(column);
        if (pivots.size() == a.rows) break;
    }
    return pivots;
}

static void print_matrix(const Matrix &a)
{
    std::cout << '[';
    for (uint32_t i = 0; i < a.rows; ++i) {
        if (i) std::cout << ',';
        std::cout << '[';
        for (uint32_t j = 0; j < a.columns; ++j) {
            if (j) std::cout << ',';
            std::cout << a.get(i, j);
        }
        std::cout << ']';
    }
    std::cout << ']';
}

int main()
{
    try {
        uint32_t m, n, lanes;
        while (std::cin >> m) {
            if (!(std::cin >> n >> lanes)) throw std::invalid_argument("partial header");
            if (!m || m > 512 || !n || n > 256 || !lanes || lanes > 16 || (lanes & (lanes - 1)))
                throw std::invalid_argument("unsupported matrix extent or lane count");
            Matrix a(m, n, lanes), proof(m, m, lanes);
            for (uint32_t i = 0; i < m; ++i)
                for (uint32_t j = 0; j < n; ++j) {
                    uint64_t value;
                    if (!(std::cin >> value) || value > a.unit)
                        throw std::invalid_argument("invalid or missing coefficient");
                    a.set(i, j, value);
                }
            Counters count;
            auto pivots = eliminate(a, proof, count);
            std::cout << "{\"rows\":";
            print_matrix(a);
            std::cout << ",\"proof\":";
            print_matrix(proof);
            std::cout << ",\"pivots\":[";
            for (size_t i = 0; i < pivots.size(); ++i) {
                if (i) std::cout << ',';
                std::cout << pivots[i];
            }
            std::cout << "],\"counts\":{\"coefficient_reads\":" << count.coefficient_reads
                      << ",\"xor_words\":" << count.xor_words
                      << ",\"and_words\":" << count.and_words
                      << ",\"copied_words\":" << count.copied_words
                      << ",\"nonzero_updates\":" << count.nonzero_updates
                      << ",\"partial_updates\":" << count.partial_updates
                      << "},\"matrix_bytes\":" << a.values.size() * sizeof(uint64_t)
                      << ",\"proof_bytes\":" << proof.values.size() * sizeof(uint64_t) << "}\n";
        }
        if (!std::cin.eof()) throw std::invalid_argument("invalid header");
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
