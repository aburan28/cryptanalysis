void rewrite_witness(Result &result, uint32_t equations)
{
    const auto started = Clock::now();
    struct Timer {
        ParityStats &stats;
        Clock::time_point start;
        ~Timer() { stats.total_seconds = elapsed(start); }
    } timer{parity, started};
    const auto &old = result.graph;
    const size_t count = old.size(), outputs = result.outputs.size();
    parity.input_nodes = count;
    parity.outputs = outputs;
    if (!parity.mode) return;
    auto pay = [&](uint64_t amount = 1) {
        charge(amount);
        parity.work += amount;
    };
    pay();
    if (!outputs || outputs > 64) {
        parity.fallback_outputs = 1;
        return;
    }
    // This cap covers parity and index arrays. Original/output proof graphs,
    // coefficients and allocator bookkeeping retain their separate scope.
    const uint64_t bytes = 8 * uint64_t(count) + 4 * (uint64_t(equations) + outputs);
    if (bytes > max_parity_bytes) {
        parity.fallback_bytes = 1;
        return;
    }
    pay(count + equations + outputs);
    std::vector<uint64_t> owners(count, 0);
    std::vector<uint32_t> inputs(equations, UINT32_MAX), roots(outputs, UINT32_MAX);
    parity.peak_metadata_bytes = bytes;
    for (size_t i = 0; i < outputs; ++i) {
        pay();
        if (result.outputs[i] >= count) {
            parity.fallback_shape = 1;
            return;
        }
        owners[result.outputs[i]] ^= UINT64_C(1) << i;
    }
    std::vector<ProofNode> compact;
    struct TooLarge {
    };
    auto emit_compact = [&](uint32_t op, uint32_t a, uint64_t b = 0) {
        pay();
        // Never enlarge the proof or reset its original node cap. Failed
        // attempts leave the original graph and output pins untouched.
        if (!count || compact.size() >= count - 1) throw TooLarge{};
        compact.push_back({op, a, b});
        parity.emitted_nodes = compact.size();
        return uint32_t(compact.size() - 1);
    };
    auto original = [&](uint32_t equation) {
        pay();
        if (inputs[equation] == UINT32_MAX) inputs[equation] = emit_compact(0, equation);
        return inputs[equation];
    };
    try {
        for (size_t i = count; i-- > 0;) {
            pay();
            ++parity.visited_nodes;
            uint64_t mask = owners[i];
            if (!mask) continue;
            const auto &node = old[i];
            if (node.op == 2) {
                if (node.a >= i || node.b >= i) {
                    parity.fallback_shape = 1;
                    return;
                }
                pay(2);
                owners[node.a] ^= mask;
                owners[node.b] ^= mask;
                parity.parity_edges += 2;
                continue;
            }
            uint32_t value;
            if (node.op == 0 && node.a < equations && !node.b) {
                value = original(node.a);
            } else if (node.op == 1 && node.a < i) {
                pay();
                const auto &input = old[node.a];
                if (input.op || input.a >= equations || input.b) {
                    parity.fallback_shape = 1;
                    return;
                }
                value = emit_compact(1, original(input.a), node.b);
            } else {
                parity.fallback_shape = 1;
                return;
            }
            ++parity.leaves;
            while (mask) {
                pay();
                const uint32_t j = __builtin_ctzll(mask);
                mask &= mask - 1;
                ++parity.incidences;
                roots[j] = roots[j] == UINT32_MAX ? value : emit_compact(2, roots[j], value);
            }
        }
        for (auto root : roots) {
            pay();
            if (root == UINT32_MAX) {
                parity.fallback_shape = 1;
                return;
            }
        }
    } catch (const TooLarge &) {
        parity.fallback_size = 1;
        return;
    }
    result.graph.swap(compact);
    result.outputs.swap(roots);
    parity.selected = 1;
}
