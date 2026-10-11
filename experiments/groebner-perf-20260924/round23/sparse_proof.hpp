// Independent exact proof over GF(2)[x]/(x_i^2+x_i).
// Roots come only from the independent evaluator. No producer data is trusted.
static int dense_basis(Workspace &w, const Rows &basis, uint32_t alive,
                       Certificate *out, ProofStats &stats)
{
    const auto n = w.n, universe = w.universe, blocks = w.blocks;
    const auto &low = w.low;
    const auto &roots = w.roots;
#include "build/dense_basis_checks.inc"
}

static int root_list_basis(Workspace &w, const Rows &basis, uint32_t alive,
                           Certificate *out, ProofStats &stats)
{
    const auto n = w.n, universe = w.universe, blocks = w.blocks;
    const auto &low = w.low;
#include "build/root_list_checks.inc"
}

static int check_basis(Workspace &w, const Rows &basis, uint32_t alive,
                       Certificate *out, ProofStats &stats)
{
    stats.mode = w.proof_mode;
    stats.budget_limit = SPARSE_PROOF_BUDGET;
    stats.workspace_bytes = sizeof(w.proof_storage.roots) + sizeof(w.proof_storage.standard)
        + sizeof(uint32_t) * w.proof_storage.leading.capacity();
    out->roots = alive;
    if (!w.proof_mode || alive > w.proof_storage.roots.size()) {
        if (w.proof_mode) stats.fallback_reason = 1; // large independent zero set
        return dense_basis(w, basis, alive, out, stats);
    }

    // Rebuild the compact root list, in the same order as the frozen checker.
    uint32_t count = 0;
    stats.root_list_used = 1;
    for (uint32_t block = 0; block < w.blocks; ++block) {
        ++stats.root_blocks_scanned;
        auto bits = w.roots[block];
        while (bits) {
            if (count >= alive) throw std::runtime_error("independent root count mismatch");
            w.proof_storage.roots[count++] = 64 * block + uint32_t(__builtin_ctzll(bits));
            bits &= bits - 1;
        }
    }
    if (count != alive) throw std::runtime_error("independent root count mismatch");
    if (w.proof_mode == 1) return root_list_basis(w, basis, alive, out, stats);

    for (const auto &row : basis)
        for (uint32_t i = 0; i < alive; ++i) {
            ++stats.root_parity_tests;
            if (parity(row, w.proof_storage.roots[i])) return out->code = 2;
        }

    auto &leading = w.proof_storage.leading;
    leading.clear();
    leading.reserve(basis.size());
    for (const auto &row : basis) {
        uint32_t lm = row[0];
        for (uint32_t m : row)
            if (__builtin_popcount(m) > __builtin_popcount(lm) ||
                (__builtin_popcount(m) == __builtin_popcount(lm) && m < lm)) lm = m;
        leading.push_back(lm);
    }
    stats.workspace_bytes = sizeof(w.proof_storage.roots) + sizeof(w.proof_storage.standard)
        + sizeof(uint32_t) * leading.capacity();

    bool budget = true;
    const auto allowed = [&](uint32_t monomial) {
        for (uint32_t lm : leading) {
            if (stats.divisibility_tests == SPARSE_PROOF_BUDGET) {
                budget = false;
                return false;
            }
            ++stats.divisibility_tests;
            if ((monomial & lm) == lm) return false;
        }
        return true;
    };
    auto fallback = [&](uint32_t reason) {
        stats.fallback_reason = reason;
        // Repeat the frozen exact dimension/reducedness checks. No truncated
        // count is exposed as an exact dimension, including for invalid bases.
        return root_list_basis(w, basis, alive, out, stats);
    };

    uint32_t used = 0;
    if (allowed(0)) w.proof_storage.standard[used++] = 0;
    if (!budget) return fallback(3);
    for (uint32_t cursor = 0; cursor < used; ++cursor) {
        const auto monomial = w.proof_storage.standard[cursor];
        // Increasing variable indices give every subset exactly one parent.
        // The allowed set is downward closed, so every allowed mask is reached.
        const uint32_t first = monomial ? 32u - uint32_t(__builtin_clz(monomial)) : 0;
        for (uint32_t variable = first; variable < w.n; ++variable) {
            const auto child = monomial | (uint32_t(1) << variable);
            if (allowed(child)) {
                if (used == w.proof_storage.standard.size()) {
                    stats.standard_visited = used;
                    return fallback(2); // workspace bound, not a claimed dimension
                }
                w.proof_storage.standard[used++] = child;
            }
            if (!budget) {
                stats.standard_visited = used;
                return fallback(3);
            }
        }
    }
    stats.standard_visited = used;
    stats.staircase_used = 1;
    out->standard = used;
    if (used != alive) return out->code = 3;
    for (size_t i = 0; i < basis.size(); ++i) {
        for (size_t j = 0; j < basis.size(); ++j)
            if (i != j && (leading[i] & leading[j]) == leading[j]) return out->code = 4;
        for (uint32_t m : basis[i])
            if (m != leading[i])
                for (uint32_t lm : leading)
                    if ((m & lm) == lm) return out->code = 5;
    }
    for (uint32_t i = 0; i < alive; ++i)
        out->solutions[out->solution_count++] = w.proof_storage.roots[i];
    return 0;
}
