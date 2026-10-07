// A fresh normal-form map for this query's basis. The one-word values encode
// standard monomials; they are not truth-table evaluations or cached answers.
bool quotient_membership(const std::vector<Polynomial> &originals,
                         const std::vector<Polynomial> &basis, const std::vector<uint64_t> &leads)
{
    if (!normal.mode) return false;
    struct Account {
        CheckStats &stats;
        NormalStats &normal;
        uint64_t start;
        ~Account() { normal.work = stats.work - start; }
    } account{stats, normal, stats.work};
    if (variables > 12) {
        normal.fallback_large_ring = 1;
        return false;
    }
    const uint64_t count = UINT64_C(1) << variables;
    normal.universe = count;
    charge(originals.size());
    for (const auto &row : originals) normal.input_terms += row.size();
    if (normal.mode == 1 && normal.input_terms < 2 * count) {
        normal.fallback_sparse = 1;
        return false;
    }
    const uint64_t bytes = count * sizeof(uint64_t);
    if (bytes > max_normal_bytes) {
        normal.fallback_bytes = 1;
        return false;
    }
    // Reserve initialization and every degree/mask test before allocating.
    // This is a conservative charge, independent of standard-library sorting.
    const uint64_t planning = count * (variables + 2);
    charge(planning);
    normal.planning_work = planning;
    std::vector<uint64_t> values(count, 0);
    normal.peak_bytes = bytes;
    for (unsigned degree = 0; degree <= variables; ++degree) {
        for (uint64_t next = count; next; --next) {
            const uint64_t monomial = next - 1;
            if (unsigned(__builtin_popcountll(monomial)) != degree) continue;
            size_t reducer = 0;
            for (; reducer < leads.size(); ++reducer) {
                charge();
                if ((monomial & leads[reducer]) == leads[reducer]) break;
            }
            if (reducer == leads.size()) {
                if (normal.dimension == 64) {
                    normal.dimension = 65;
                    normal.fallback_dimension = 1;
                    return false;
                }
                values[monomial] = UINT64_C(1) << normal.dimension++;
                continue;
            }
            auto product = multiply(basis[reducer], monomial & ~leads[reducer]);
            ++normal.table_products;
            if (product.empty() || leading(product) != monomial)
                throw Rejected("nondecreasing quotient-map reduction");
            product.erase(monomial);
            charge(product.size());
            for (uint64_t term : product) {
                const unsigned child_degree = __builtin_popcountll(term);
                if (child_degree > degree || (child_degree == degree && term <= monomial))
                    throw Rejected("quotient-map dependency is not strictly lower");
                values[monomial] ^= values[term];
                ++normal.table_terms;
            }
        }
    }
    normal.selected = 1;
    for (const auto &row : originals) {
        ++stats.generator_checks;
        charge(row.size());
        uint64_t value = 0;
        for (uint64_t term : row) {
            value ^= values[term];
            ++normal.input_xors;
        }
        if (value) throw Rejected("input generator has nonzero normal form");
    }
    return true;
}
