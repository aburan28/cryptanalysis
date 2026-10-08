// Ring-only Macaulay layouts, fresh GF(2) pivots and original-equation witnesses.
// A produced candidate is NOT a Gröbner basis until the independent check passes.
#include "proof_abi.h"
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

struct LayoutStats {
    uint64_t support, columns, multipliers, rows, payload_bytes;
    double total_seconds;
    uint32_t status;
};
struct MatrixStats {
    uint64_t work, rows, forward_xors, backward_xors, word_xors, pivots;
    uint64_t kept_rows, nodes, output_nodes, peak_payload_words;
    double decode_seconds, elimination_seconds, extraction_seconds, total_seconds;
    uint32_t status; // 0 candidate, 1 invalid, 2 budget, 3 internal
};
namespace
{
using Clock = std::chrono::steady_clock;
using Masks = std::vector<uint64_t>;
struct Invalid : std::runtime_error {
    using std::runtime_error::runtime_error;
};
struct Budget : std::runtime_error {
    using std::runtime_error::runtime_error;
};
thread_local std::string failure;
double elapsed(Clock::time_point t)
{
    return std::chrono::duration<double>(Clock::now() - t).count();
}
size_t count_monomials(uint32_t n, uint32_t degree)
{
    uint64_t sum = 1, choose = 1;
    for (uint32_t k = 1; k <= degree; ++k) {
        // Previous choose <= 262144, n <= 64: this product cannot overflow.
        choose = choose * (n - k + 1) / k;
        if (choose > 262144 - sum) throw Budget("monomial layout limit");
        sum += choose;
    }
    return size_t(sum);
}
void combinations(Masks &out, uint32_t n, uint32_t next, uint32_t left, uint64_t mask)
{
    if (!left) {
        out.push_back(mask);
        return;
    }
    for (uint32_t i = next; i + left <= n; ++i)
        combinations(out, n, i + 1, left - 1, mask | (UINT64_C(1) << i));
}
Masks monomials(uint32_t n, uint32_t degree, size_t size)
{
    Masks out;
    out.reserve(size);
    for (uint32_t d = 0; d <= degree; ++d) combinations(out, n, 0, d, 0);
    if (out.size() != size) throw std::runtime_error("monomial count mismatch");
    return out;
}
struct Layout {
    uint32_t n, equations;
    Masks support, columns, multipliers;
    std::vector<uint32_t> scatter;
};
struct Row {
    Masks words;
    uint32_t proof;
};
struct Result {
    Masks terms, offsets;
    std::vector<ProofNode> graph;
    std::vector<uint32_t> outputs;
    ProofView view{};
};
class Engine
{
    const Layout &layout;
    uint64_t max_work;
    uint32_t max_nodes, max_rows;
    MatrixStats &stats;
    std::vector<ProofNode> graph;
    Clock::time_point phase = Clock::now();
    uint32_t phase_index = 0;
    void record()
    {
        if (phase_index == 0) stats.decode_seconds = elapsed(phase);
        if (phase_index == 1) stats.elimination_seconds = elapsed(phase);
        if (phase_index == 2) stats.extraction_seconds = elapsed(phase);
    }
    void finish()
    {
        record();
        phase = Clock::now();
        ++phase_index;
    }
    void charge(uint64_t n = 1)
    {
        if (n > max_work - stats.work) throw Budget("matrix work budget");
        stats.work += n;
    }
    uint32_t emit(uint32_t op, uint32_t a, uint64_t b = 0)
    {
        if (graph.size() >= max_nodes) throw Budget("matrix proof node budget");
        graph.push_back({op, a, b});
        stats.nodes = graph.size();
        return uint32_t(graph.size() - 1);
    }
    void xor_row(Row &a, const Row &b, size_t first, bool backward)
    {
        const size_t words = a.words.size() - first;
        charge(words);
        // Emit before changing coefficients: node-limit failure discards the call.
        const uint32_t id = emit(2, a.proof, b.proof);
        for (size_t w = first; w < a.words.size(); ++w) a.words[w] ^= b.words[w];
        a.proof = id;
        stats.word_xors += words;
        if (backward)
            ++stats.backward_xors;
        else
            ++stats.forward_xors;
    }

  public:
    Engine(const Layout &l, uint64_t w, uint32_t nodes, uint32_t rows, MatrixStats &s)
        : layout(l), max_work(w), max_nodes(nodes), max_rows(rows), stats(s)
    {
    }
    ~Engine() { record(); }
    std::unique_ptr<Result> run(const PackedInput &in)
    {
        const auto &l = layout;
        const size_t support = l.support.size(), width = (l.columns.size() + 63) / 64;
        const uint32_t limbs = (in.equations + 63) / 64;
        const uint64_t row_count = uint64_t(l.equations) * l.multipliers.size();
        const uint64_t max_pivots = std::min<uint64_t>(row_count, l.columns.size());
        if (row_count > max_rows) throw Budget("matrix row budget");
        if (width && max_pivots + 1 > UINT64_C(8388608) / width)
            throw Budget("matrix payload budget");
        if (in.nvars != l.n || in.equations != l.equations ||
            in.terms != (l.equations ? support : 0) ||
            (in.terms && (!in.masks || !in.coefficients)))
            throw Invalid("packed layout mismatch");
        std::vector<std::vector<uint32_t>> inputs(in.equations);
        charge(in.equations);
        for (size_t i = 0; i < in.terms; ++i) {
            charge();
            if (in.masks[i] != l.support[i]) throw Invalid("support order mismatch");
            charge(limbs);
            for (uint32_t k = 0; k < limbs; ++k) {
                uint64_t bits = in.coefficients[i * limbs + k];
                if (k + 1 == limbs && in.equations % 64 && bits >> (in.equations % 64))
                    throw Invalid("coefficient padding");
                while (bits) {
                    charge();
                    inputs[k * 64 + __builtin_ctzll(bits)].push_back(uint32_t(i));
                    bits &= bits - 1;
                }
            }
        }
        for (uint32_t e = 0; e < in.equations; ++e) emit(0, e);
        finish();
        std::vector<Row> pivots;
        std::vector<uint32_t> slots(l.columns.size(), UINT32_MAX);
        for (uint32_t e = 0; e < in.equations; ++e) {
            for (size_t m = 0; m < l.multipliers.size(); ++m) {
                charge();
                ++stats.rows;
                if (inputs[e].empty()) continue;
                Row row{Masks(width, 0), e};
                stats.peak_payload_words =
                    std::max<uint64_t>(stats.peak_payload_words, (pivots.size() + 1) * width);
                charge(inputs[e].size());
                for (auto i : inputs[e]) {
                    uint32_t c = l.scatter[m * support + i];
                    row.words[c >> 6] ^= UINT64_C(1) << (c & 63);
                }
                if (l.multipliers[m]) row.proof = emit(1, e, l.multipliers[m]);
                size_t first = 0;
                while (true) {
                    while (first < width) {
                        charge();
                        if (row.words[first]) break;
                        ++first;
                    }
                    if (first == width) break;
                    size_t column = first * 64 + __builtin_ctzll(row.words[first]);
                    if (slots[column] == UINT32_MAX) {
                        slots[column] = uint32_t(pivots.size());
                        pivots.push_back(std::move(row));
                        ++stats.pivots;
                        break;
                    }
                    xor_row(row, pivots[slots[column]], first, false);
                }
            }
        }
        // Back substitution uses the freshly selected pivot columns only.
        std::vector<size_t> pivot_columns;
        for (size_t c = 0; c < slots.size(); ++c)
            if (slots[c] != UINT32_MAX) pivot_columns.push_back(c);
        for (size_t i = pivot_columns.size(); i-- > 0;) {
            const size_t c = pivot_columns[i];
            for (size_t j = 0; j < i; ++j) {
                charge();
                const size_t earlier = pivot_columns[j];
                auto &row = pivots[slots[earlier]];
                if ((row.words[c >> 6] >> (c & 63)) & 1)
                    xor_row(row, pivots[slots[c]], c >> 6, true);
            }
        }
        finish();
        auto result = std::make_unique<Result>();
        result->offsets.push_back(0);
        Masks minimal;
        // Smallest monomials first: a retained divisor is already minimal.
        for (size_t c = l.columns.size(); c-- > 0;) {
            if (slots[c] == UINT32_MAX) continue;
            bool redundant = false;
            for (auto lm : minimal) {
                charge();
                if ((lm & l.columns[c]) == lm) {
                    redundant = true;
                    break;
                }
            }
            if (redundant) continue;
            minimal.push_back(l.columns[c]);
            const auto &row = pivots[slots[c]];
            Masks terms;
            for (size_t word = c >> 6; word < width; ++word) {
                charge();
                uint64_t bits = row.words[word];
                while (bits) {
                    charge();
                    terms.push_back(l.columns[word * 64 + __builtin_ctzll(bits)]);
                    bits &= bits - 1;
                }
            }
            std::sort(terms.begin(), terms.end());
            if (terms.size() > UINT32_MAX - result->terms.size())
                throw Budget("output term budget");
            result->terms.insert(result->terms.end(), terms.begin(), terms.end());
            result->offsets.push_back(result->terms.size());
            result->outputs.push_back(row.proof);
            ++stats.kept_rows;
        }
        std::vector<uint8_t> needed(graph.size(), 0);
        for (auto id : result->outputs) needed[id] = 1;
        for (size_t i = graph.size(); i-- > 0;) {
            charge();
            if (!needed[i]) continue;
            const auto &node = graph[i];
            if (node.op) needed[node.a] = 1;
            if (node.op == 2) needed[node.b] = 1;
        }
        std::vector<uint32_t> remap(graph.size(), UINT32_MAX);
        for (size_t i = 0; i < graph.size(); ++i) {
            charge();
            if (!needed[i]) continue;
            auto node = graph[i];
            if (node.op) node.a = remap[node.a];
            if (node.op == 2) node.b = remap[node.b];
            remap[i] = uint32_t(result->graph.size());
            result->graph.push_back(node);
        }
        for (auto &id : result->outputs) id = remap[id];
        stats.output_nodes = result->graph.size();
        result->view = {1,
                        in.nvars,
                        1,
                        0,
                        result->outputs.size(),
                        result->terms.size(),
                        result->graph.size(),
                        result->terms.data(),
                        result->offsets.data(),
                        result->graph.data(),
                        result->outputs.data()};
        finish();
        return result;
    }
};
} // namespace
extern "C" {
const char *macaulay_error() { return failure.c_str(); }
uint64_t macaulay_stats_size() { return sizeof(MatrixStats); }
uint64_t macaulay_layout_stats_size() { return sizeof(LayoutStats); }
void *macaulay_layout_create(uint32_t n, uint32_t equations, uint32_t degree,
                             uint32_t multiplier_degree, uint64_t max_bytes, LayoutStats *stats)
{
    auto start = Clock::now();
    failure.clear();
    if (!stats) {
        failure = "null layout stats";
        return nullptr;
    }
    *stats = {};
    std::unique_ptr<Layout> p;
    try {
        if (!n || n > 64 || equations > 4096 || degree > n || multiplier_degree > n)
            throw Invalid("layout shape");
        const uint32_t bound = std::min(n, degree + multiplier_degree);
        size_t a = count_monomials(n, degree), b = count_monomials(n, bound),
               c = count_monomials(n, multiplier_degree);
        const uint64_t bytes = uint64_t(a + b + c) * 8 + uint64_t(a) * c * 4;
        stats->support = a;
        stats->columns = b;
        stats->multipliers = c;
        stats->rows = uint64_t(equations) * c;
        stats->payload_bytes = bytes;
        if (bytes > max_bytes || bytes > UINT64_C(67108864)) throw Budget("layout payload budget");
        p = std::make_unique<Layout>();
        p->n = n;
        p->equations = equations;
        p->support = monomials(n, degree, a);
        std::sort(p->support.begin(), p->support.end());
        p->columns = monomials(n, bound, b);
        std::sort(p->columns.begin(), p->columns.end(), [](uint64_t x, uint64_t y) {
            auto dx = __builtin_popcountll(x), dy = __builtin_popcountll(y);
            return dx != dy ? dx > dy : x < y;
        });
        p->multipliers = monomials(n, multiplier_degree, c);
        std::unordered_map<uint64_t, uint32_t> columns;
        for (size_t i = 0; i < b; ++i) columns.emplace(p->columns[i], uint32_t(i));
        p->scatter.reserve(a * c);
        for (auto m : p->multipliers)
            for (auto term : p->support) p->scatter.push_back(columns.at(m | term));
    } catch (const Invalid &e) {
        stats->status = 1;
        failure = e.what();
        p.reset();
    } catch (const Budget &e) {
        stats->status = 2;
        failure = e.what();
        p.reset();
    } catch (const std::exception &e) {
        stats->status = 3;
        failure = e.what();
        p.reset();
    } catch (...) {
        stats->status = 3;
        failure = "unknown layout failure";
        p.reset();
    }
    stats->total_seconds = elapsed(start);
    return p.release();
}
void macaulay_layout_destroy(void *p) { delete static_cast<Layout *>(p); }
const uint64_t *macaulay_layout_support(void *p)
{
    return p ? static_cast<Layout *>(p)->support.data() : nullptr;
}
void *macaulay_apply(void *layout, const PackedInput *in, uint64_t work, uint32_t nodes,
                     uint32_t rows, MatrixStats *stats)
{
    auto start = Clock::now();
    failure.clear();
    if (!stats) {
        failure = "null matrix stats";
        return nullptr;
    }
    *stats = {};
    std::unique_ptr<Result> result;
    try {
        if (!layout || !in || !nodes || nodes > 10000000 || !rows || rows > 1000000)
            throw Invalid("matrix configuration");
        Engine engine(*static_cast<Layout *>(layout), work, nodes, rows, *stats);
        result = engine.run(*in);
    } catch (const Invalid &e) {
        stats->status = 1;
        failure = e.what();
    } catch (const Budget &e) {
        stats->status = 2;
        failure = e.what();
    } catch (const std::exception &e) {
        stats->status = 3;
        failure = e.what();
    } catch (...) {
        stats->status = 3;
        failure = "unknown matrix failure";
    }
    stats->total_seconds = elapsed(start);
    return result.release();
}
const ProofView *macaulay_view(void *p) { return p ? &static_cast<Result *>(p)->view : nullptr; }
void macaulay_result_destroy(void *p) { delete static_cast<Result *>(p); }
}
