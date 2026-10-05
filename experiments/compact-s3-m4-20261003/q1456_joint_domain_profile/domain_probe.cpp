// Q1456: measure exact pair-domain sizes at Q1455's unfixed-midpoint states.
#include "joint_base.cpp"

#include <limits>

struct DomainTheory : JointTheory {
    struct Snapshot {
        unsigned target_choice = 0;
        std::array<LeafState, 4> leaves;
        std::array<uint64_t, 2> pairs{};
    };
    std::set<std::pair<unsigned, std::array<U128, 8>>> observed;
    std::array<uint64_t, 64> max_pair_log2_histogram{};
    std::vector<Snapshot> all_snapshots;
    uint64_t observed_unique_states = 0;
    uint64_t min_pair0 = std::numeric_limits<uint64_t>::max();
    uint64_t min_pair1 = std::numeric_limits<uint64_t>::max();
    uint64_t min_max_pair = std::numeric_limits<uint64_t>::max();
    uint64_t min_sum_pairs = std::numeric_limits<uint64_t>::max();

    DomainTheory(q1420::Field &f, const Variables &v, const Targets &t,
                 int max_var, int pair_cap)
        : JointTheory(f, v, t, max_var, pair_cap) {}

    static uint64_t exact_count(const LeafState &state) {
        if (state.slack < 0) return 0;
        uint64_t choose = 1, total = 0;
        for (int k = 0; k <= std::min(state.slack, state.free); ++k) {
            if (k) choose = choose * uint64_t(state.free - k + 1) /
                            uint64_t(k);
            total += choose;
        }
        return total - unsigned(state.ones == 0);
    }

    static int bucket(uint64_t value) {
        return value ? 63 - __builtin_clzll(value) : 0;
    }

    void profile() {
        if (!all_fixed(vars.selector) || all_fixed(vars.mids[0]) ||
            all_fixed(vars.mids[1])) return;
        unsigned choice = unsigned(value(vars.selector, assignment));
        if (choice >= targets.x.size()) return;
        std::array<LeafState, 4> state;
        std::array<U128, 8> key{};
        for (int leaf = 0; leaf < 4; ++leaf) {
            state[leaf] = leaf_state(leaf);
            if (!state[leaf].free) return;
            key[2 * leaf] = state[leaf].fixed;
            key[2 * leaf + 1] = state[leaf].ones;
        }
        if (!observed.insert({choice, key}).second) return;
        ++observed_unique_states;
        uint64_t counts[4];
        for (int leaf = 0; leaf < 4; ++leaf)
            counts[leaf] = exact_count(state[leaf]);
        require(counts[0] <= UINT64_MAX / std::max(uint64_t(1), counts[1]) &&
                counts[2] <= UINT64_MAX / std::max(uint64_t(1), counts[3]),
                "pair-domain count overflow");
        uint64_t p0 = counts[0] * counts[1];
        uint64_t p1 = counts[2] * counts[3];
        uint64_t largest = std::max(p0, p1);
        min_pair0 = std::min(min_pair0, p0);
        min_pair1 = std::min(min_pair1, p1);
        min_max_pair = std::min(min_max_pair, largest);
        min_sum_pairs = std::min(min_sum_pairs, p0 + p1);
        ++max_pair_log2_histogram[bucket(largest)];
        all_snapshots.push_back({choice, state, {p0, p1}});
    }

    void notify_assignment(const std::vector<int> &lits) override {
        JointTheory::notify_assignment(lits);
        profile();
    }
};

int main(int argc, char **argv) {
    try {
        require(argc == 9,
                "usage: domain_probe FIELD CNF MAP MODEL_OUT "
                "CONFLICT_CAP WALL_CAP_SECONDS TARGETS PAIR_CAP");
        auto start = std::chrono::steady_clock::now();
        q1420::Field field(argv[1]);
        Variables vars(argv[3]);
        Targets targets(argv[7]);
        require(field.n == vars.n && field.n == targets.n,
                "field/map/target degree mismatch");
        CaDiCaL::Solver solver;
        solver.set("quiet", 1);
        CnfInfo cnf = load_cnf(solver, argv[2]);
        DomainTheory theory(field, vars, targets, cnf.variables,
                            std::stoi(argv[8]));
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
                  << ",\"stop_reason\":\""
                  << (status == 10 ? "sat" : status == 20 ? "unsat" :
                      deadline.fired ? "wall_cap" : "conflict_cap") << "\""
                  << ",\"setup_seconds\":" << seconds(setup_end, start)
                  << ",\"solve_seconds\":" << seconds(end, setup_end)
                  << ",\"conflicts\":"
                  << solver.get_statistic_value("conflicts")
                  << ",\"decisions\":"
                  << solver.get_statistic_value("decisions")
                  << ",\"cnf_variables\":" << cnf.variables
                  << ",\"cnf_clauses\":" << cnf.clauses
                  << ",\"pair_cap\":" << theory.pair_cap
                  << ",\"partial_events\":" << theory.partial_events
                  << ",\"cap_skips\":" << theory.cap_skips
                  << ",\"joint_checks\":" << theory.eligible_checks
                  << ",\"joint_rejections\":"
                  << theory.no_chain_rejections
                  << ",\"unique_partial_states\":"
                  << theory.observed_unique_states
                  << ",\"min_pair0_candidates\":"
                  << (theory.observed_unique_states ? theory.min_pair0 : 0)
                  << ",\"min_pair1_candidates\":"
                  << (theory.observed_unique_states ? theory.min_pair1 : 0)
                  << ",\"min_max_pair_candidates\":"
                  << (theory.observed_unique_states ? theory.min_max_pair : 0)
                  << ",\"min_sum_pair_candidates\":"
                  << (theory.observed_unique_states ? theory.min_sum_pairs : 0)
                  << ",\"field_mul_calls\":" << field.counts.mul
                  << ",\"field_sqr_calls\":" << field.counts.sqr
                  << ",\"field_inv_calls\":" << field.counts.inv
                  << ",\"max_pair_log2_histogram\":[";
        bool first = true;
        for (size_t k = 0; k < theory.max_pair_log2_histogram.size(); ++k) {
            uint64_t count = theory.max_pair_log2_histogram[k];
            if (!count) continue;
            if (!first) std::cout << ',';
            first = false;
            std::cout << "{\"floor_log2\":" << k
                      << ",\"unique_states\":" << count << '}';
        }
        std::cout << "],\"domain_snapshots\":[";
        for (size_t i = 0; i < theory.all_snapshots.size(); ++i) {
            if (i) std::cout << ',';
            const auto &s = theory.all_snapshots[i];
            std::cout << "{\"target_preimage_index\":"
                      << s.target_choice
                      << ",\"pair_candidate_counts\":["
                      << s.pairs[0] << ',' << s.pairs[1]
                      << "],\"leaf_fixed_mask_onb_hex\":[";
            for (int leaf = 0; leaf < 4; ++leaf) {
                if (leaf) std::cout << ',';
                std::cout << '\"' << q1420::hex(s.leaves[leaf].fixed)
                          << '\"';
            }
            std::cout << "],\"leaf_ones_onb_hex\":[";
            for (int leaf = 0; leaf < 4; ++leaf) {
                if (leaf) std::cout << ',';
                std::cout << '\"' << q1420::hex(s.leaves[leaf].ones)
                          << '\"';
            }
            std::cout << "]}";
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
