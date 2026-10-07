// Q1462: add the exact Q1461 sum-domain no-pair rule to Q1446's fixed-midpoint SAT search.
#define main q1446_unused_main
#include "../q1446_joint_pair_span/theory_solver.cpp"
#undef main
#include "../q1461_sparse_sum_inverse/sparse_sum.hpp"

#include <map>

struct SparseTheory : RootTheory {
    using Key = std::tuple<int, U128, U128, U128, U128, U128>;
    struct Snapshot {
        int pair = 0;
        U128 mid = 0, a_fixed = 0, a_ones = 0, b_fixed = 0, b_ones = 0;
        uint64_t sum_candidates = 0, direct_pair_candidates = 0;
        bool no_pair = false;
    };
    int sum_cap;
    q1420::Counts before_inverse_setup{};
    q1461::SparseSumInverse inverse;
    q1420::Counts after_inverse_setup{};
    uint64_t partial_events = 0, cap_skips = 0, zero_mid_skips = 0;
    uint64_t checks = 0, no_pair_rejections = 0, x_only_hits = 0;
    uint64_t checked_sums = 0, binary_basis_xors = 0, elimination_xors = 0;
    uint64_t exact_pairs = 0, guard_literals = 0;
    uint64_t check_mul = 0, check_sqr = 0, check_inv = 0;
    std::array<uint64_t, 2> checks_by_pair{}, rejections_by_pair{};
    std::set<Key> checked;
    std::vector<Snapshot> snapshots;

    SparseTheory(q1420::Field &f, const Variables &v, const Targets &t,
                 int max_var, int cap)
        : RootTheory(f, v, t, max_var, true, true, true,
                     true, false, true),
          sum_cap(cap), before_inverse_setup(f.counts),
          inverse(f, v.weight), after_inverse_setup(f.counts) {
        require(sum_cap > 0 && sum_cap <= 1000000,
                "invalid sparse-sum candidate cap");
    }

    static uint64_t options_count(int free, int slack, bool zero_ones) {
        if (slack < 0) return 0;
        uint64_t choose = 1, total = 0;
        for (int size = 0; size <= std::min(free, slack); ++size) {
            if (size) choose = choose * uint64_t(free - size + 1) /
                               uint64_t(size);
            total += choose;
        }
        return total - unsigned(zero_ones);
    }

    void maybe_sparse_pair(int pair) {
        if (!all_fixed(vars.mids[pair])) return;
        U128 m = value(vars.mids[pair], assignment);
        q1461::Leaf leaves[2];
        int free[2] = {0, 0};
        for (int side = 0; side < 2; ++side)
            for (int bit = 0; bit < vars.n; ++bit) {
                int8_t assigned = assignment[vars.leaves[2 * pair + side][bit]];
                if (!assigned) ++free[side];
                else {
                    leaves[side].fixed |= U128(1) << bit;
                    if (assigned > 0) leaves[side].ones |= U128(1) << bit;
                }
            }
        if (!free[0] || !free[1]) return;
        ++partial_events;
        if (!m) {
            // Q1446's complete/reverse rules remain the exact zero-mid fallback.
            ++zero_mid_skips;
            return;
        }
        int slack_a = vars.weight - q1461::weight(leaves[0].ones);
        int slack_b = vars.weight - q1461::weight(leaves[1].ones);
        require(slack_a >= 0 && slack_b >= 0, "SAT violated leaf weight");
        U128 free_union = field.mask &
                          ~(leaves[0].fixed & leaves[1].fixed);
        uint64_t bound = q1461::sum_candidate_count(
            q1461::weight(free_union), slack_a + slack_b, sum_cap);
        if (bound > unsigned(sum_cap)) {
            ++cap_skips;
            return;
        }
        Key key{pair, m, leaves[0].fixed, leaves[0].ones,
                leaves[1].fixed, leaves[1].ones};
        if (!checked.insert(key).second) return;
        q1420::Counts before = field.counts;
        auto result = inverse.check(leaves[0], leaves[1], m, sum_cap);
        require(!result.skipped && result.sum_candidate_bound == bound,
                "eligible sparse-sum check skipped");
        ++checks;
        ++checks_by_pair[pair];
        checked_sums += result.sums_visited;
        binary_basis_xors += result.basis_xors;
        elimination_xors += result.elimination_xors;
        exact_pairs += result.verified_pairs;
        check_mul += field.counts.mul - before.mul;
        check_sqr += field.counts.sqr - before.sqr;
        check_inv += field.counts.inv - before.inv;
        uint64_t direct = options_count(free[0], slack_a,
                                        leaves[0].ones == 0) *
                          options_count(free[1], slack_b,
                                        leaves[1].ones == 0);
        if (snapshots.size() < 24)
            snapshots.push_back({pair, m, leaves[0].fixed, leaves[0].ones,
                                 leaves[1].fixed, leaves[1].ones, bound,
                                 direct, result.pairs.empty()});
        if (!result.pairs.empty()) {
            ++x_only_hits;
            return;
        }
        ++no_pair_rejections;
        ++rejections_by_pair[pair];
        std::vector<int> guard;
        for (int bit : vars.mids[pair])
            guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (int side = 0; side < 2; ++side)
            for (int bit = 0; bit < vars.n; ++bit)
                if (leaves[side].fixed >> bit & 1) {
                    int var = vars.leaves[2 * pair + side][bit];
                    guard.push_back(leaves[side].ones >> bit & 1 ?
                                    -var : var);
                }
        require(guard.size() == size_t(vars.n +
                q1461::weight(leaves[0].fixed) +
                q1461::weight(leaves[1].fixed)),
                "incomplete sparse-sum rejection guard");
        for (int lit : guard) {
            int var = std::abs(lit);
            require(assignment[var] == (lit > 0 ? -1 : 1),
                    "sparse-sum guard not false on current trail");
        }
        guard_literals += guard.size();
        add_clause(guard, {});
    }

    void notify_assignment(const std::vector<int> &lits) override {
        RootTheory::notify_assignment(lits);
        for (int pair = 0; pair < 2; ++pair) maybe_sparse_pair(pair);
    }
};

#ifndef Q1462_NO_MAIN
int main(int argc, char **argv) {
    try {
        require(argc == 10,
                "usage: native_solver FIELD CNF MAP MODEL_OUT CONFLICT_CAP "
                "WALL_CAP_SECONDS sparse_sum_joint_pair_span TARGETS SUM_CAP");
        auto start = std::chrono::steady_clock::now();
        q1420::Field field(argv[1]);
        Variables vars(argv[3]);
        Targets targets(argv[8]);
        require(field.n == vars.n && field.n == targets.n,
                "field/map/target degree mismatch");
        require((1u << vars.selector.size()) >= targets.x.size() &&
                (vars.selector.size() == 1 ||
                 (1u << (vars.selector.size() - 1)) < targets.x.size()),
                "target count/selector width mismatch");
        require(std::string(argv[7]) == "sparse_sum_joint_pair_span",
                "invalid decision policy");
        CaDiCaL::Solver solver;
        solver.set("quiet", 1);
        CnfInfo cnf = load_cnf(solver, argv[2]);
        SparseTheory theory(field, vars, targets, cnf.variables,
                            std::stoi(argv[9]));
        solver.connect_external_propagator(&theory);
        for (const auto &row : vars.leaves)
            for (int bit : row) solver.add_observed_var(bit);
        for (const auto &row : vars.mids)
            for (int bit : row) solver.add_observed_var(bit);
        for (int bit : vars.selector) solver.add_observed_var(bit);
        int conflict_cap = std::stoi(argv[5]);
        require(conflict_cap > 0 && solver.limit("conflicts", conflict_cap),
                "invalid conflict cap");
        int wall_cap = std::stoi(argv[6]);
        require(wall_cap > 0, "invalid wall cap");
        Deadline deadline(wall_cap);
        solver.connect_terminator(&deadline);
        auto setup_end = std::chrono::steady_clock::now();
        int status = solver.solve();
        auto end = std::chrono::steady_clock::now();
        int64_t conflicts = solver.get_statistic_value("conflicts");
        int64_t decisions = solver.get_statistic_value("decisions");
        if (status == 10) {
            std::ofstream model(argv[4]);
            require(bool(model), "model output unavailable");
            model << "s SATISFIABLE\n";
            for (int var = 1; var <= cnf.variables; ++var) {
                if ((var - 1) % 16 == 0) model << "v ";
                model << solver.val(var) << ' ';
                if (var % 16 == 0 || var == cnf.variables) model << "0\n";
            }
        }
        auto seconds = [](auto later, auto earlier) {
            return std::chrono::duration<double>(later - earlier).count();
        };
        std::cout << "{\"status\":" << status
                  << ",\"decision_policy\":\"sparse_sum_joint_pair_span\""
                  << ",\"stop_reason\":\""
                  << (status == 10 ? "sat" : status == 20 ? "unsat" :
                      deadline.fired ? "wall_cap" : "conflict_cap") << "\""
                  << ",\"conflicts\":" << conflicts
                  << ",\"decisions\":" << decisions
                  << ",\"setup_seconds\":" << seconds(setup_end, start)
                  << ",\"solve_seconds\":" << seconds(end, setup_end)
                  << ",\"cnf_variables\":" << cnf.variables
                  << ",\"cnf_clauses\":" << cnf.clauses
                  << ",\"target_preimage_count\":" << targets.x.size()
                  << ",\"sum_cap\":" << theory.sum_cap
                  << ",\"sum_partial_events\":" << theory.partial_events
                  << ",\"sum_cap_skips\":" << theory.cap_skips
                  << ",\"sum_zero_mid_skips\":" << theory.zero_mid_skips
                  << ",\"sum_checks\":" << theory.checks
                  << ",\"sum_checks_pair0\":" << theory.checks_by_pair[0]
                  << ",\"sum_checks_pair1\":" << theory.checks_by_pair[1]
                  << ",\"sum_rejections\":" << theory.no_pair_rejections
                  << ",\"sum_rejections_pair0\":"
                  << theory.rejections_by_pair[0]
                  << ",\"sum_rejections_pair1\":"
                  << theory.rejections_by_pair[1]
                  << ",\"sum_x_only_hits\":" << theory.x_only_hits
                  << ",\"sum_checked_sums\":" << theory.checked_sums
                  << ",\"sum_exact_pairs\":" << theory.exact_pairs
                  << ",\"sum_basis_xors\":" << theory.binary_basis_xors
                  << ",\"sum_elimination_xors\":" << theory.elimination_xors
                  << ",\"sum_guard_literals\":" << theory.guard_literals
                  << ",\"sum_check_mul_calls\":" << theory.check_mul
                  << ",\"sum_check_sqr_calls\":" << theory.check_sqr
                  << ",\"sum_check_inv_calls\":" << theory.check_inv
                  << ",\"sum_setup_mul_calls\":"
                  << (theory.after_inverse_setup.mul -
                      theory.before_inverse_setup.mul)
                  << ",\"sum_setup_sqr_calls\":"
                  << (theory.after_inverse_setup.sqr -
                      theory.before_inverse_setup.sqr)
                  << ",\"sum_setup_inv_calls\":"
                  << (theory.after_inverse_setup.inv -
                      theory.before_inverse_setup.inv)
                  << ",\"span_checks\":" << theory.span_checks
                  << ",\"span_rejections\":" << theory.span_rejections
                  << ",\"span_checks_pair0\":"
                  << theory.span_checks_by_pair[0]
                  << ",\"span_checks_pair1\":"
                  << theory.span_checks_by_pair[1]
                  << ",\"span_rejections_pair0\":"
                  << theory.span_rejections_by_pair[0]
                  << ",\"span_rejections_pair1\":"
                  << theory.span_rejections_by_pair[1]
                  << ",\"complete_pair_visits\":"
                  << theory.complete_pair_visits
                  << ",\"model_checks\":" << theory.model_checks
                  << ",\"external_clauses\":" << theory.emitted_clauses
                  << ",\"field_mul_calls\":" << field.counts.mul
                  << ",\"field_sqr_calls\":" << field.counts.sqr
                  << ",\"field_inv_calls\":" << field.counts.inv
                  << ",\"s3_root_calls\":" << field.counts.roots
                  << ",\"sum_snapshots\":[";
        for (size_t i = 0; i < theory.snapshots.size(); ++i) {
            if (i) std::cout << ',';
            const auto &s = theory.snapshots[i];
            std::cout << "{\"pair\":" << s.pair
                      << ",\"mid_onb_hex\":\"" << q1420::hex(s.mid)
                      << "\",\"a_fixed_mask_onb_hex\":\""
                      << q1420::hex(s.a_fixed)
                      << "\",\"a_ones_onb_hex\":\""
                      << q1420::hex(s.a_ones)
                      << "\",\"b_fixed_mask_onb_hex\":\""
                      << q1420::hex(s.b_fixed)
                      << "\",\"b_ones_onb_hex\":\""
                      << q1420::hex(s.b_ones)
                      << "\",\"sum_candidates\":" << s.sum_candidates
                      << ",\"direct_pair_candidates\":"
                      << s.direct_pair_candidates
                      << ",\"no_pair\":"
                      << (s.no_pair ? "true" : "false") << '}';
        }
        std::cout << "]}\n";
        solver.disconnect_terminator();
        solver.disconnect_external_propagator();
        return status == 10 ? 0 : status == 20 ? 20 : 10;
    } catch (const std::exception &error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
#endif
