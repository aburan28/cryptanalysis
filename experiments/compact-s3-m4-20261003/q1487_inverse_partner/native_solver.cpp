// Q1487: exact inverse-S3 partner support on Q1482's unchanged CNF.
#include "base_solver.hpp"

struct InverseTheory : JointTheory {
    uint64_t inverse_events = 0, inverse_cap_skips = 0;
    uint64_t inverse_eligible_checks = 0, inverse_rejections = 0;
    uint64_t inverse_x_only_hits = 0, inverse_no_first_mid = 0;
    uint64_t inverse_right_supports = 0, inverse_guard_literals = 0;
    uint64_t inverse_anchor_values = 0, inverse_root_calls = 0;
    uint64_t inverse_zero_mid_reciprocals = 0, inverse_membership_checks = 0;
    uint64_t inverse_field_mul_calls = 0, inverse_field_sqr_calls = 0;
    uint64_t inverse_field_inv_calls = 0;
    uint64_t anchor_decisions = 0;
    static constexpr uint64_t anchor_option_cap = 4096;

    InverseTheory(q1420::Field &f, const Variables &v, const Targets &t,
                  const WindowMap &w, int max_var, int max_anchor_options)
        : JointTheory(f, v, t, w, max_var, max_anchor_options) {
        require(max_anchor_options == int(anchor_option_cap),
                "Q1487 anchor cap must match frozen design");
    }

    int cb_decide() override {
        ++decision_requests;
        for (int bit : vars.selector)
            if (!assignment[bit]) {
                ++forced_target_decisions;
                return bit;
            }
        for (int leaf = 0; leaf < 4; ++leaf) {
            bool selected = false;
            for (int bit : windows.selectors[leaf])
                selected |= assignment[bit] > 0;
            if (selected) continue;
            for (int bit : windows.selectors[leaf])
                if (!assignment[bit]) {
                    ++forced_window_decisions;
                    return bit;
                }
        }
        for (int bit : vars.mids[1])
            if (!assignment[bit]) {
                ++forced_mid_decisions;
                return bit;
            }
        LeafState a = leaf_state(0), b = leaf_state(1);
        LeafState c = leaf_state(2), d = leaf_state(3);
        uint64_t counts[4] = {option_count(a), option_count(b),
                              option_count(c), option_count(d)};
        bool need_left = std::min(counts[0], counts[1]) >
                         anchor_option_cap;
        bool need_right = std::min(counts[2], counts[3]) >
                          anchor_option_cap;
        if (need_left || need_right) {
            int left_anchor = counts[0] <= counts[1] ? 0 : 1;
            int right_anchor = counts[2] <= counts[3] ? 2 : 3;
            for (int j = 0; j < vars.n; ++j)
                for (int leaf : {left_anchor, right_anchor}) {
                    if ((leaf == left_anchor && !need_left) ||
                        (leaf == right_anchor && !need_right)) continue;
                    int coordinate = (j + leaf * (vars.n / 4)) % vars.n;
                    int bit = vars.leaves[leaf][coordinate];
                    if (!assignment[bit]) {
                        ++forced_leaf_decisions;
                        ++anchor_decisions;
                        return bit;
                    }
                }
        }
        for (const auto &row : vars.leaves)
            for (int bit : row)
                if (!assignment[bit]) {
                    ++forced_leaf_decisions;
                    return bit;
                }
        for (const auto &row : vars.mids)
            for (int bit : row)
                if (!assignment[bit]) {
                    ++forced_mid_decisions;
                    return bit;
                }
        return 0;
    }

    bool contains(const LeafState &state, U128 x) {
        ++inverse_membership_checks;
        if (!x || (x & state.fixed) != state.ones) return false;
        for (U128 mask : allowed_window_masks(state))
            if (!(x & ~mask)) return true;
        return false;
    }

    bool pair_supported(const LeafState &first, const LeafState &second,
                        U128 midpoint, int lane) {
        uint64_t first_count = option_count(first);
        uint64_t second_count = option_count(second);
        const LeafState &anchor = first_count <= second_count ? first : second;
        const LeafState &partner = first_count <= second_count ? second : first;
        require(std::min(first_count, second_count) <= anchor_option_cap,
                "inverse partner anchor exceeds cap");
        std::vector<U128> anchors = options(anchor);
        require(anchors.size() <= anchor_option_cap,
                "inverse partner exact anchor exceeds cap");
        inverse_anchor_values += anchors.size();
        if (anchors.empty()) return false;
        if (!midpoint) {
            for (U128 x : anchors) {
                U128 reciprocal = field.to_onb(
                    field.inv(field.to_poly(x)));
                ++inverse_zero_mid_reciprocals;
                if (contains(partner, reciprocal)) return true;
            }
            return false;
        }
        std::vector<std::pair<U128, U128>> inputs;
        inputs.reserve(anchors.size());
        for (U128 x : anchors) inputs.emplace_back(x, midpoint);
        auto roots = cached_roots(inputs, lane);
        inverse_root_calls += inputs.size();
        for (const auto &row : roots)
            for (U128 y : row)
                if (contains(partner, y)) return true;
        return false;
    }

    void maybe_inverse_join() {
        if (!all_fixed(vars.selector) || !all_fixed(vars.mids[1])) return;
        unsigned choice = unsigned(value(vars.selector, assignment));
        if (choice >= targets.x.size()) return;
        std::array<LeafState, 4> state;
        bool any_free = false;
        for (int leaf = 0; leaf < 4; ++leaf) {
            state[leaf] = leaf_state(leaf);
            any_free |= state[leaf].free != 0;
        }
        if (!any_free) return;
        ++inverse_events;
        std::array<uint64_t, 4> count;
        for (int leaf = 0; leaf < 4; ++leaf)
            count[leaf] = option_count(state[leaf]);
        if (std::min(count[0], count[1]) > anchor_option_cap ||
            std::min(count[2], count[3]) > anchor_option_cap) {
            ++inverse_cap_skips;
            return;
        }
        auto [first_fixed, first_ones] = mid_masks(0);
        auto [second_fixed, second_mid] = mid_masks(1);
        require(second_fixed == (U128(1) << vars.n) - 1,
                "second midpoint not fully assigned");
        std::array<U128, 20> key{};
        for (int leaf = 0; leaf < 4; ++leaf) {
            key[4 * leaf] = state[leaf].fixed;
            key[4 * leaf + 1] = state[leaf].ones;
            key[4 * leaf + 2] = state[leaf].window_true;
            key[4 * leaf + 3] = state[leaf].window_false;
        }
        key[16] = first_fixed;
        key[17] = first_ones;
        key[18] = second_fixed;
        key[19] = second_mid;
        if (!checked_by_target[choice].insert(key).second) return;
        ++inverse_eligible_checks;
        q1420::Counts before = field.counts;
        bool right_supported = pair_supported(
            state[2], state[3], second_mid, 1);
        if (right_supported) ++inverse_right_supports;
        bool chain_supported = false;
        std::vector<U128> first_mids;
        if (right_supported) {
            U128 target = targets.x[choice];
            if (second_mid) {
                auto roots = cached_roots({{second_mid, target}}, 2);
                first_mids = std::move(roots[0]);
            } else {
                first_mids = {field.to_onb(field.inv(field.to_poly(target)))};
            }
            U128 mid_fixed_copy = first_fixed;
            U128 mid_ones_copy = first_ones;
            first_mids.erase(std::remove_if(first_mids.begin(),
                first_mids.end(), [&](U128 u) {
                    return (u & mid_fixed_copy) != mid_ones_copy;
                }), first_mids.end());
            if (first_mids.empty()) ++inverse_no_first_mid;
            for (U128 first_mid : first_mids)
                if (pair_supported(state[0], state[1], first_mid, 0)) {
                    chain_supported = true;
                    break;
                }
        }
        inverse_field_mul_calls += field.counts.mul - before.mul;
        inverse_field_sqr_calls += field.counts.sqr - before.sqr;
        inverse_field_inv_calls += field.counts.inv - before.inv;
        if (chain_supported) {
            ++inverse_x_only_hits;
            return;
        }
        ++inverse_rejections;
        std::vector<int> guard;
        for (int bit : vars.selector)
            guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (const auto &row : vars.leaves)
            for (int bit : row)
                if (assignment[bit])
                    guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (int leaf = 0; leaf < 4; ++leaf) append_window_guard(guard, leaf);
        for (const auto &row : vars.mids)
            for (int bit : row)
                if (assignment[bit])
                    guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (int lit : guard) {
            int bit = std::abs(lit);
            require(assignment[bit] == (lit > 0 ? -1 : 1),
                    "inverse partner guard not false on current trail");
        }
        inverse_guard_literals += guard.size();
        add_clause(guard, {});
    }

    void notify_assignment(const std::vector<int> &lits) override {
        RootTheory::notify_assignment(lits);
        maybe_inverse_join();
    }
};

#ifndef Q1487_NO_MAIN
int main(int argc, char **argv) {
    try {
        require(argc == 11,
                "usage: q1487_solver FIELD CNF MAP MODEL_OUT CONFLICT_CAP "
                "WALL_CAP_SECONDS TARGETS ANCHOR_CAP POLICY WINDOW_MAP");
        auto start = std::chrono::steady_clock::now();
        q1420::Field field(argv[1]);
        Variables vars(argv[3]);
        Targets targets(argv[7]);
        require(field.n == vars.n && field.n == targets.n,
                "field/map/target degree mismatch");
        require(std::string(argv[9]) == "target_inverse_s3_partner_support",
                "invalid decision policy");
        CaDiCaL::Solver solver;
        solver.set("quiet", 1);
        CnfInfo cnf = load_cnf(solver, argv[2]);
        WindowMap windows(argv[10], vars, cnf.variables);
        InverseTheory theory(field, vars, targets, windows, cnf.variables,
                             std::stoi(argv[8]));
        solver.connect_external_propagator(&theory);
        for (const auto &row : vars.leaves)
            for (int bit : row) solver.add_observed_var(bit);
        for (const auto &row : vars.mids)
            for (int bit : row) solver.add_observed_var(bit);
        for (int bit : vars.selector) solver.add_observed_var(bit);
        for (const auto &row : windows.selectors)
            for (int bit : row) solver.add_observed_var(bit);
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
        int64_t propagations = solver.get_statistic_value("propagations");
        require(propagations >= 0, "propagations unavailable");
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
                  << ",\"decision_policy\":\"target_inverse_s3_partner_support\""
                  << ",\"stop_reason\":\""
                  << (status == 10 ? "sat" : status == 20 ? "unsat" :
                      deadline.fired ? "wall_cap" : "conflict_cap") << '"'
                  << ",\"conflicts\":" << conflicts
                  << ",\"decisions\":" << decisions
                  << ",\"propagations\":" << propagations
                  << ",\"setup_seconds\":" << seconds(setup_end, start)
                  << ",\"solve_seconds\":" << seconds(end, setup_end)
                  << ",\"cnf_variables\":" << cnf.variables
                  << ",\"cnf_clauses\":" << cnf.clauses
                  << ",\"target_preimage_count\":" << targets.x.size()
                  << ",\"window_selector_count\":" << 4 * windows.n
                  << ",\"window_dimension_d\":" << windows.d
                  << ",\"anchor_option_cap\":" << theory.anchor_option_cap
                  << ",\"inverse_events\":" << theory.inverse_events
                  << ",\"inverse_cap_skips\":" << theory.inverse_cap_skips
                  << ",\"inverse_eligible_checks\":"
                  << theory.inverse_eligible_checks
                  << ",\"inverse_rejections\":" << theory.inverse_rejections
                  << ",\"inverse_x_only_hits\":" << theory.inverse_x_only_hits
                  << ",\"inverse_no_first_mid\":" << theory.inverse_no_first_mid
                  << ",\"inverse_right_supports\":"
                  << theory.inverse_right_supports
                  << ",\"inverse_guard_literals\":"
                  << theory.inverse_guard_literals
                  << ",\"inverse_anchor_values\":"
                  << theory.inverse_anchor_values
                  << ",\"inverse_root_calls\":" << theory.inverse_root_calls
                  << ",\"inverse_zero_mid_reciprocals\":"
                  << theory.inverse_zero_mid_reciprocals
                  << ",\"inverse_membership_checks\":"
                  << theory.inverse_membership_checks
                  << ",\"anchor_decisions\":" << theory.anchor_decisions
                  << ",\"forced_window_decisions\":"
                  << theory.forced_window_decisions
                  << ",\"window_option_values_enumerated\":"
                  << theory.window_enumerated_values
                  << ",\"inverse_field_mul_calls\":"
                  << theory.inverse_field_mul_calls
                  << ",\"inverse_field_sqr_calls\":"
                  << theory.inverse_field_sqr_calls
                  << ",\"inverse_field_inv_calls\":"
                  << theory.inverse_field_inv_calls
                  << ",\"batch_root_inputs\":"
                  << theory.batch_stats.root_inputs
                  << ",\"field_mul_calls\":" << field.counts.mul
                  << ",\"field_sqr_calls\":" << field.counts.sqr
                  << ",\"field_inv_calls\":" << field.counts.inv
                  << ",\"field_s3_root_calls\":" << field.counts.roots
                  << ",\"external_clauses\":" << theory.emitted_clauses
                  << ",\"model_checks\":" << theory.model_checks
                  << ",\"rejected_models\":" << theory.rejected_models
                  << "}\n";
        solver.disconnect_terminator();
        solver.disconnect_external_propagator();
        return status == 10 ? 0 : status == 20 ? 20 : 10;
    } catch (const std::exception &error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
#endif
