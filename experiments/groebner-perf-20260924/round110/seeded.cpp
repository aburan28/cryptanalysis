#include "seeded.h"
#include <memory>
#include <unordered_set>
#include "engine.inc"

namespace
{
thread_local std::string failure;
using Clock = std::chrono::steady_clock;

struct Result {
    std::vector<uint64_t> terms, offsets;
    std::vector<ProofNode> graph;
    std::vector<uint32_t> outputs;
    std::unique_ptr<Result> continuation;
    ProofView view{};

    void bind(uint32_t n)
    {
        view = {1,
                n,
                1,
                0,
                outputs.size(),
                terms.size(),
                graph.size(),
                terms.data(),
                offsets.data(),
                graph.data(),
                outputs.data()};
    }
    void copy_basis(const ProofView &source)
    {
        if (source.terms) terms.assign(source.basis_terms, source.basis_terms + source.terms);
        offsets.assign(source.offsets, source.offsets + source.rows + 1);
    }
};

void require(bool condition, const char *message)
{
    if (!condition) throw std::invalid_argument(message);
}
bool in_ring(uint64_t mask, uint32_t n) { return n == 64 || !(mask >> n); }

void frame(const ProofView *v)
{
    require(v && v->version == 1 && v->nvars >= 1 && v->nvars <= 64 && v->order == 1 &&
                v->reserved == 0 && v->rows <= 4096 && v->nodes <= 10000000 &&
                v->terms <= UINT32_MAX && v->offsets && (!v->rows || v->outputs) &&
                (!v->nodes || v->graph) && (!v->terms || v->basis_terms),
            "invalid proof view");
    require(v->offsets[0] == 0 && v->offsets[v->rows] == v->terms, "invalid proof offsets");
    for (uint64_t i = 0; i < v->rows; ++i)
        require(v->offsets[i] <= v->offsets[i + 1] && v->offsets[i + 1] <= v->terms,
                "invalid proof offsets");
}

void charge(uint64_t &work, uint64_t limit, uint64_t amount, const char *reason)
{
    if (amount > limit - work) throw Budget(reason);
    work += amount;
}

std::unique_ptr<Result> compose(const ProofView &seed, const ProofView &continuation,
                                uint32_t originals, uint64_t max_work, uint32_t max_nodes,
                                CompositionStats &stats)
{
    require(originals <= 4096 && max_nodes <= 10000000 && seed.nvars == continuation.nvars,
            "invalid composition configuration");
    auto pay = [&](uint64_t amount = 1) {
        charge(stats.work, max_work, amount, "composition work budget");
    };
    auto result = std::make_unique<Result>();
    std::vector<ProofNode> graph;
    auto emit = [&](ProofNode node) {
        if (graph.size() >= max_nodes) throw Budget("composition node budget");
        pay();
        graph.push_back(node);
        stats.combined_nodes = graph.size();
        return uint32_t(graph.size() - 1);
    };
    auto validate = [&](const ProofNode &node, uint64_t prior, uint64_t inputs) {
        pay();
        if (node.op == 0)
            require(node.a < inputs && node.b == 0, "invalid proof input");
        else {
            require((node.op == 1 || node.op == 2) && node.a < prior, "invalid proof dependency");
            require(node.op == 1 ? in_ring(node.b, seed.nvars) : node.b < prior,
                    "invalid proof multiplier or xor dependency");
        }
    };
    for (uint64_t i = 0; i < seed.nodes; ++i) {
        validate(seed.graph[i], i, originals);
        emit(seed.graph[i]);
        ++stats.seed_nodes;
    }
    pay(seed.rows);
    std::vector<uint32_t> inputs;
    for (uint64_t i = 0; i < seed.rows; ++i) {
        require(seed.outputs[i] < graph.size(), "invalid seed output");
        inputs.push_back(seed.outputs[i]);
    }
    for (uint32_t i = 0; i < originals; ++i) inputs.push_back(emit({0, i, 0}));
    std::vector<uint32_t> mapping;
    for (uint64_t i = 0; i < continuation.nodes; ++i) {
        const auto node = continuation.graph[i];
        validate(node, i, inputs.size());
        uint32_t mapped;
        if (node.op == 0) {
            pay();
            mapped = inputs[node.a];
        } else
            mapped = emit({node.op, mapping[node.a], node.op == 1 ? node.b : mapping[node.b]});
        mapping.push_back(mapped);
        ++stats.continuation_nodes;
    }
    pay(continuation.rows);
    std::vector<uint32_t> outputs;
    for (uint64_t i = 0; i < continuation.rows; ++i) {
        require(continuation.outputs[i] < mapping.size(), "invalid continuation output");
        outputs.push_back(mapping[continuation.outputs[i]]);
    }
    pay(graph.size());
    std::vector<uint8_t> needed(graph.size());
    for (uint32_t i : outputs) {
        pay();
        needed[i] = 1;
    }
    for (size_t i = graph.size(); i-- > 0;) {
        pay();
        if (!needed[i]) continue;
        const auto node = graph[i];
        if (node.op) {
            pay();
            needed[node.a] = 1;
        }
        if (node.op == 2) {
            pay();
            needed[node.b] = 1;
        }
    }
    pay(graph.size());
    std::vector<uint32_t> remap(graph.size());
    for (size_t i = 0; i < graph.size(); ++i) {
        pay();
        if (!needed[i]) continue;
        pay();
        remap[i] = uint32_t(result->graph.size());
        const auto node = graph[i];
        result->graph.push_back({node.op, node.op == 0 ? node.a : remap[node.a],
                                 node.op == 2 ? remap[node.b] : node.b});
        ++stats.retained_nodes;
    }
    pay(outputs.size());
    for (uint32_t i : outputs) result->outputs.push_back(remap[i]);
    stats.retained_outputs = outputs.size();
    return result;
}

void canonical(Poly &row)
{
    std::sort(row.begin(), row.end());
    size_t out = 0;
    for (size_t i = 0; i < row.size();) {
        size_t j = i + 1;
        while (j < row.size() && row[j] == row[i]) ++j;
        if ((j - i) & 1) row[out++] = row[i];
        i = j;
    }
    row.resize(out);
}

void engine_stats(const Engine &engine, ProducerStats &stats)
{
    stats.work = engine.work;
    stats.matrices = engine.matrices;
    stats.matrix_rows = engine.matrix_rows;
    stats.peak_rows = engine.peak_rows;
    stats.pairs = engine.pairs;
    stats.nodes = engine.nodes.size();
}
} // namespace

extern "C" {
const char *seeded_error() { return failure.c_str(); }
uint64_t seeded_stats_size() { return sizeof(SeededStats); }
uint64_t seeded_composition_stats_size() { return sizeof(CompositionStats); }
const ProofView *seeded_view(void *handle)
{
    return handle ? &static_cast<Result *>(handle)->view : nullptr;
}
const ProofView *seeded_continuation_view(void *handle)
{
    auto *result = static_cast<Result *>(handle);
    return result && result->continuation ? &result->continuation->view : nullptr;
}
void seeded_destroy(void *handle) { delete static_cast<Result *>(handle); }

void *seeded_compose(const ProofView *seed, const ProofView *continuation, uint32_t originals,
                     uint64_t max_work, uint32_t max_nodes, CompositionStats *stats,
                     uint32_t *status)
{
    failure.clear();
    if (!stats || !status) {
        failure = "null composition stats";
        return nullptr;
    }
    *stats = {};
    *status = 0;
    try {
        frame(seed);
        frame(continuation);
        auto result = compose(*seed, *continuation, originals, max_work, max_nodes, *stats);
        for (uint64_t i = 0; i < continuation->terms; ++i)
            require(in_ring(continuation->basis_terms[i], continuation->nvars),
                    "basis term outside ring");
        result->copy_basis(*continuation);
        result->bind(seed->nvars);
        return result.release();
    } catch (const Budget &e) {
        *status = 2;
        failure = e.what();
    } catch (const std::invalid_argument &e) {
        *status = 1;
        failure = e.what();
    } catch (const std::exception &e) {
        *status = 3;
        failure = e.what();
    } catch (...) {
        *status = 3;
        failure = "unknown composition failure";
    }
    return nullptr;
}

void *seeded_produce(const PackedInput *input, const ProofView *seed, uint64_t max_work,
                     uint32_t max_nodes, uint32_t max_rows, uint32_t batch, uint32_t capture,
                     SeededStats *stats)
{
    auto start = Clock::now();
    failure.clear();
    top_stats = {};
    column_stats = {};
    scratch_stats = {};
    packed_stats = {};
    chain_stats = {};
    chain_stats.mode = 1;
    if (!stats) {
        failure = "null seeded stats";
        return nullptr;
    }
    *stats = {};
    std::unique_ptr<Engine> engine;
    bool producer_finished = false;
    uint64_t remaining = max_work;
    auto pay = [&](uint64_t amount, uint64_t &counter, const char *reason) {
        if (amount > remaining) throw Budget(reason);
        remaining -= amount;
        counter += amount;
    };
    auto bridge = [&](uint64_t amount) { pay(amount, stats->bridge_work, "bridge work budget"); };
    auto scan = [&](uint64_t amount) { pay(amount, stats->scan_work, "packed scan work budget"); };
    try {
        frame(seed);
        require(input && input->nvars == seed->nvars && input->equations <= 4096 &&
                    (!input->terms || (input->equations && input->masks && input->coefficients)) &&
                    input->terms <= UINT32_MAX && input->equations + seed->rows <= 4096 &&
                    max_nodes && max_nodes <= 10000000 && max_rows && max_rows <= 1000000 &&
                    batch && batch <= max_rows && capture <= 1,
                "invalid seeded configuration");
        // Preserve round109's bridge and F4 decode charges even where native
        // direct-row transfer removes their physical Python allocation/packing.
        // The new raw packed-input scan has an additional, never negative charge.
        bridge(seed->nodes + seed->rows + seed->terms);
        scan(input->equations);
        std::vector<Poly> originals(input->equations);
        uint32_t limbs = (input->equations + 63) / 64;
        for (uint64_t i = 0; i < input->terms; ++i) {
            scan(1);
            require(in_ring(input->masks[i], input->nvars), "input term outside ring");
            scan(limbs);
            for (uint32_t limb = 0; limb < limbs; ++limb) {
                uint64_t bits = input->coefficients[i * limbs + limb];
                require(limb + 1 != limbs || !(input->equations % 64) ||
                            !(bits >> (input->equations % 64)),
                        "input coefficient outside equation bitset");
                while (bits) {
                    unsigned bit = __builtin_ctzll(bits);
                    bits &= bits - 1;
                    scan(1);
                    originals[limb * 64 + bit].push_back(input->masks[i]);
                }
            }
        }
        uint64_t original_terms = 0;
        for (auto &row : originals) {
            scan(row.size());
            canonical(row);
            original_terms += row.size();
        }
        bridge(seed->rows + input->equations + seed->terms + original_terms);
        stats->reserved_seed_nodes = seed->nodes + input->equations;
        if (stats->reserved_seed_nodes >= max_nodes) throw Budget("retained seed node budget");
        std::vector<Poly> rows;
        std::vector<Mask> support;
        std::unordered_set<Mask> encountered;
        auto remember = [&](Mask term) {
            if (encountered.insert(term).second) support.push_back(term);
        };
        for (uint64_t i = 0; i < seed->rows; ++i) {
            Poly row;
            for (uint64_t j = seed->offsets[i]; j < seed->offsets[i + 1]; ++j) {
                auto term = seed->basis_terms[j];
                require(in_ring(term, input->nvars), "seed term outside ring");
                row.push_back(term);
                remember(term);
            }
            canonical(row);
            rows.push_back(std::move(row));
        }
        for (auto &row : originals) {
            for (Mask term : row) remember(term);
            rows.push_back(std::move(row));
        }
        std::unordered_map<Mask, uint32_t> counts;
        for (const auto &row : rows)
            for (Mask term : row) ++counts[term];
        engine = std::make_unique<Engine>(
            remaining, max_nodes - uint32_t(stats->reserved_seed_nodes), max_rows, batch, true);
        stats->f4_started = 1;
        uint32_t combined_limbs = uint32_t((rows.size() + 63) / 64);
        for (Mask term : support) {
            auto found = counts.find(term);
            if (found == counts.end()) continue;
            engine->charge(combined_limbs);
            for (uint32_t i = 0; i < found->second; ++i) engine->charge();
        }
        for (const auto &row : rows) engine->charge(row.size());
        engine->compute(rows);
        engine->compact(); // Unchanged reference compaction and its original accounting.
        engine_stats(*engine, stats->producer);
        producer_finished = true;
        remaining -= engine->work;
        auto continuation = std::make_unique<Result>();
        uint64_t terms = 0;
        for (const auto &row : engine->basis) terms += row.terms.size();
        bridge(engine->nodes.size() + engine->basis.size() + terms);
        continuation->offsets.push_back(0);
        for (const auto &row : engine->basis) {
            continuation->terms.insert(continuation->terms.end(), row.terms.begin(),
                                       row.terms.end());
            continuation->offsets.push_back(continuation->terms.size());
            continuation->outputs.push_back(row.proof);
        }
        for (const auto &node : engine->nodes)
            continuation->graph.push_back({node.op, node.a, node.b});
        continuation->bind(input->nvars);
        stats->composition_started = 1;
        auto result = compose(*seed, continuation->view, input->equations, remaining, max_nodes,
                              stats->composition);
        remaining -= stats->composition.work;
        bridge(continuation->terms.size() + continuation->outputs.size() + result->graph.size());
        if (capture) {
            result->copy_basis(continuation->view);
            result->continuation = std::move(continuation);
        } else {
            result->terms = std::move(continuation->terms);
            result->offsets = std::move(continuation->offsets);
        }
        result->bind(input->nvars);
        stats->work = max_work - remaining;
        stats->total_seconds = std::chrono::duration<double>(Clock::now() - start).count();
        return result.release();
    } catch (const Budget &e) {
        stats->status = 2;
        failure = e.what();
    } catch (const std::invalid_argument &e) {
        stats->status = 1;
        failure = e.what();
    } catch (const std::exception &e) {
        stats->status = 3;
        failure = e.what();
    } catch (...) {
        stats->status = 3;
        failure = "unknown seeded failure";
    }
    if (engine) {
        engine_stats(*engine, stats->producer);
        if (!producer_finished) stats->producer.status = uint32_t(stats->status);
    }
    stats->work =
        stats->bridge_work + stats->scan_work + stats->producer.work + stats->composition.work;
    stats->total_seconds = std::chrono::duration<double>(Clock::now() - start).count();
    return nullptr;
}
}
