// Q1465: memoize exact S3 roots shared by nested Q1458 partial domains.
// Preserve its decision policy, guards and archived compact-S3 CNF loader.
#define main q1446_unused_main
#include "../q1446_joint_pair_span/theory_solver.cpp"
#undef main
#include "../q1458_batch_roots/batch_roots.hpp"

#include <map>
#include <unordered_map>

using q1420::U128;

struct JointTheory : RootTheory {
    struct PairKey {
        U128 a = 0, b = 0;
        bool operator==(const PairKey &other) const {
            return a == other.a && b == other.b;
        }
    };
    struct PairHash {
        size_t operator()(const PairKey &key) const {
            auto mix = [](uint64_t x) {
                x ^= x >> 30;
                x *= UINT64_C(0xbf58476d1ce4e5b9);
                x ^= x >> 27;
                x *= UINT64_C(0x94d049bb133111eb);
                return x ^ (x >> 31);
            };
            uint64_t a0 = uint64_t(key.a), a1 = uint64_t(key.a >> 64);
            uint64_t b0 = uint64_t(key.b), b1 = uint64_t(key.b >> 64);
            return size_t(mix(a0) ^ mix(a1 + 0x9e3779b97f4a7c15ULL) ^
                          mix(b0 + 0x243f6a8885a308d3ULL) ^
                          mix(b1 + 0x13198a2e03707344ULL));
        }
    };
    static PairKey key_for(U128 a, U128 b) {
        return a < b ? PairKey{a, b} : PairKey{b, a};
    }
    struct LeafState {
        U128 fixed = 0, ones = 0;
        int free = 0, slack = 0;
    };
    struct Snapshot {
        unsigned target_choice = 0;
        std::array<LeafState, 4> leaves;
        std::array<uint64_t, 2> pair_candidates{};
    };
    int pair_cap;
    uint64_t partial_events = 0, eligible_checks = 0, cap_skips = 0;
    uint64_t no_chain_rejections = 0, x_only_hits = 0;
    uint64_t pair_root_calls[2] = {0, 0}, final_join_root_calls = 0;
    uint64_t pair_outputs[2] = {0, 0}, join_guard_literals = 0;
    uint64_t join_mul_calls = 0, join_sqr_calls = 0, join_inv_calls = 0;
    q1458::BatchStats batch_stats{};
    // A root set depends only on the two x inputs. Cache it across SAT
    // branches and all three S3 links; the key is symmetric in its inputs.
    std::unordered_map<PairKey, std::vector<U128>, PairHash> root_cache;
    std::array<uint64_t, 3> cache_hits{}, cache_misses{}, batch_reuses{};
    uint64_t cache_capacity_skips = 0;
    static constexpr size_t cache_entry_cap = 2000000;
    std::array<uint64_t, 2> max_pair_candidates_seen{};
    std::vector<Snapshot> rejection_snapshots, hit_snapshots;

    JointTheory(q1420::Field &f, const Variables &v, const Targets &t,
                int max_var, int max_pair_candidates)
        : RootTheory(f, v, t, max_var, true, true, true,
                     false, false, true),
          pair_cap(max_pair_candidates) {
        require(pair_cap > 0, "invalid joint-pair cap");
    }

    int cb_decide() override {
        ++decision_requests;
        for (int bit : vars.selector)
            if (!assignment[bit]) {
                ++forced_target_decisions;
                return bit;
            }
        for (int j = 0; j < vars.n; ++j)
            for (int leaf : {0, 2, 1, 3}) {
                int bit = vars.leaves[leaf][j];
                if (!assignment[bit]) {
                    ++forced_leaf_decisions;
                    return bit;
                }
            }
        for (const auto &mid : vars.mids)
            for (int bit : mid)
                if (!assignment[bit]) {
                    ++forced_mid_decisions;
                    return bit;
                }
        return 0;
    }

    LeafState leaf_state(int leaf) const {
        LeafState state;
        for (int j = 0; j < vars.n; ++j) {
            int8_t sign = assignment[vars.leaves[leaf][j]];
            if (!sign) ++state.free;
            else {
                state.fixed |= U128(1) << j;
                if (sign > 0) state.ones |= U128(1) << j;
            }
        }
        state.slack = vars.weight - popcount(state.ones);
        return state;
    }

    uint64_t option_count(const LeafState &state) const {
        if (state.slack < 0) return 0;
        uint64_t total = 0, choose = 1;
        for (int size = 0; size <= std::min(state.slack, state.free);
             ++size) {
            if (size) {
                choose = choose * uint64_t(state.free - size + 1) /
                         uint64_t(size);
            }
            total += choose;
            if (total > uint64_t(pair_cap) + 1) return pair_cap + 1;
        }
        return total - unsigned(state.ones == 0);
    }

    std::vector<U128> options(const LeafState &state) const {
        std::vector<int> free;
        for (int j = 0; j < vars.n; ++j)
            if (!((state.fixed >> j) & 1)) free.push_back(j);
        std::vector<U128> answer;
        auto visit = [&](auto &&self, int start, int left, U128 value) -> void {
            if (!left) {
                if (value) answer.push_back(value);
                return;
            }
            for (int i = start; i <= int(free.size()) - left; ++i)
                self(self, i + 1, left - 1,
                     value | (U128(1) << free[i]));
        };
        for (int size = 0; size <= std::min(state.slack, state.free);
             ++size)
            visit(visit, 0, size, state.ones);
        return answer;
    }

    std::vector<std::vector<U128>> cached_roots(
        const std::vector<std::pair<U128, U128>> &inputs, int lane) {
        require(lane >= 0 && lane < 3, "invalid root-cache lane");
        std::vector<std::vector<U128>> answer(inputs.size());
        std::vector<std::pair<U128, U128>> missing;
        std::vector<PairKey> missing_keys;
        std::vector<std::vector<size_t>> positions;
        std::unordered_map<PairKey, size_t, PairHash> pending;
        missing.reserve(inputs.size());
        missing_keys.reserve(inputs.size());
        positions.reserve(inputs.size());
        for (size_t i = 0; i < inputs.size(); ++i) {
            PairKey key = key_for(inputs[i].first, inputs[i].second);
            auto found = root_cache.find(key);
            if (found != root_cache.end()) {
                answer[i] = found->second;
                ++cache_hits[lane];
                continue;
            }
            auto [slot, inserted] = pending.emplace(key, missing.size());
            if (inserted) {
                missing.emplace_back(key.a, key.b);
                missing_keys.push_back(key);
                positions.push_back({i});
            } else {
                positions[slot->second].push_back(i);
                ++batch_reuses[lane];
            }
        }
        cache_misses[lane] += missing.size();
        auto roots = q1458::roots_onb(field, missing, batch_stats);
        for (size_t j = 0; j < missing.size(); ++j) {
            if (root_cache.size() < cache_entry_cap)
                root_cache.emplace(missing_keys[j], roots[j]);
            else
                ++cache_capacity_skips;
            for (size_t index : positions[j]) answer[index] = roots[j];
        }
        return answer;
    }

    bool has_chain(const std::array<LeafState, 4> &state, U128 target) {
        std::array<std::vector<U128>, 4> domains;
        for (int leaf = 0; leaf < 4; ++leaf) {
            domains[leaf] = options(state[leaf]);
            require(domains[leaf].size() == option_count(state[leaf]),
                    "joint completion count mismatch");
        }
        std::vector<std::pair<U128, U128>> right_inputs;
        right_inputs.reserve(domains[2].size() * domains[3].size());
        for (U128 c : domains[2]) for (U128 d : domains[3])
            right_inputs.emplace_back(c, d);
        auto right_roots = cached_roots(right_inputs, 1);
        pair_root_calls[1] += right_inputs.size();
        std::map<U128, std::pair<U128, U128>> right;
        for (size_t i = 0; i < right_inputs.size(); ++i)
            for (U128 root : right_roots[i])
                right.emplace(root, right_inputs[i]);
        pair_outputs[1] += right.size();
        std::vector<std::pair<U128, U128>> left_inputs;
        left_inputs.reserve(domains[0].size() * domains[1].size());
        for (U128 a : domains[0]) for (U128 b : domains[1])
            left_inputs.emplace_back(a, b);
        auto left_roots = cached_roots(left_inputs, 0);
        pair_root_calls[0] += left_inputs.size();
        std::set<U128> seen_left;
        std::vector<U128> left_order;
        for (const auto &roots : left_roots)
            for (U128 middle : roots)
                if (seen_left.insert(middle).second)
                    left_order.push_back(middle);
        final_join_root_calls += left_order.size();
        std::vector<std::pair<U128, U128>> final_inputs;
        final_inputs.reserve(left_order.size());
        for (U128 middle : left_order)
            if (middle) final_inputs.emplace_back(middle, target);
        auto final_roots = cached_roots(final_inputs, 2);
        size_t cursor = 0;
        for (U128 middle : left_order) {
            std::vector<U128> partners;
            if (middle) partners = std::move(final_roots[cursor++]);
            else partners = {
                field.to_onb(field.inv(field.to_poly(target)))};
            for (U128 partner : partners)
                if (right.count(partner)) {
                    pair_outputs[0] += seen_left.size();
                    return true;
                }
        }
        pair_outputs[0] += seen_left.size();
        return false;
    }

    void maybe_join() {
        if (!all_fixed(vars.selector) || all_fixed(vars.mids[0]) ||
            all_fixed(vars.mids[1])) return;
        unsigned choice = unsigned(value(vars.selector, assignment));
        if (choice >= targets.x.size()) return;
        std::array<LeafState, 4> state;
        for (int leaf = 0; leaf < 4; ++leaf) {
            state[leaf] = leaf_state(leaf);
            if (!state[leaf].free) return;
        }
        ++partial_events;
        std::array<uint64_t, 4> count;
        for (int leaf = 0; leaf < 4; ++leaf)
            count[leaf] = option_count(state[leaf]);
        uint64_t pairs[2] = {count[0] * count[1], count[2] * count[3]};
        for (int pair = 0; pair < 2; ++pair)
            max_pair_candidates_seen[pair] = std::max(
                max_pair_candidates_seen[pair], pairs[pair]);
        if (pairs[0] > unsigned(pair_cap) ||
            pairs[1] > unsigned(pair_cap)) {
            ++cap_skips;
            return;
        }
        std::array<U128, 8> key{};
        for (int leaf = 0; leaf < 4; ++leaf) {
            key[2 * leaf] = state[leaf].fixed;
            key[2 * leaf + 1] = state[leaf].ones;
        }
        // The same leaf state at a different target must be rechecked.
        // Target selection is fixed first, so augment the cache via a map.
        auto &selected = checked_by_target[choice];
        if (!selected.insert(key).second) return;
        ++eligible_checks;
        q1420::Counts before = field.counts;
        bool found = has_chain(state, targets.x[choice]);
        join_mul_calls += field.counts.mul - before.mul;
        join_sqr_calls += field.counts.sqr - before.sqr;
        join_inv_calls += field.counts.inv - before.inv;
        if (found) {
            ++x_only_hits;
            if (hit_snapshots.size() < 16)
                hit_snapshots.push_back({choice, state,
                                         {pairs[0], pairs[1]}});
            return;
        }
        ++no_chain_rejections;
        if (rejection_snapshots.size() < 16)
            rejection_snapshots.push_back({choice, state,
                                           {pairs[0], pairs[1]}});
        std::vector<int> guard;
        for (int bit : vars.selector)
            guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (const auto &bits : vars.leaves)
            for (int bit : bits)
                if (assignment[bit])
                    guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (int lit : guard) {
            int var = std::abs(lit);
            require(assignment[var] == (lit > 0 ? -1 : 1),
                    "joint rejection guard not false on current trail");
        }
        join_guard_literals += guard.size();
        add_clause(guard, {});
    }

    std::map<unsigned, std::set<std::array<U128, 8>>> checked_by_target;

    void notify_assignment(const std::vector<int> &lits) override {
        RootTheory::notify_assignment(lits);
        maybe_join();
    }
};

int main(int argc, char **argv) {
    try {
        require(argc == 10,
                "usage: native_joint_solver FIELD CNF MAP MODEL_OUT "
                "CONFLICT_CAP WALL_CAP_SECONDS TARGETS PAIR_CAP POLICY");
        auto start = std::chrono::steady_clock::now();
        q1420::Field field(argv[1]);
        Variables vars(argv[3]);
        Targets targets(argv[7]);
        require(field.n == vars.n && field.n == targets.n,
                "field/map/target degree mismatch");
        require(std::string(argv[9]) == "joint_tail_leaf_interleave",
                "invalid decision policy");
        CaDiCaL::Solver solver;
        solver.set("quiet", 1);
        CnfInfo cnf = load_cnf(solver, argv[2]);
        JointTheory theory(field, vars, targets, cnf.variables,
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
                  << ",\"decision_policy\":\"joint_tail_leaf_interleave\""
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
                  << ",\"pair_cap\":" << theory.pair_cap
                  << ",\"joint_partial_events\":" << theory.partial_events
                  << ",\"joint_eligible_checks\":" << theory.eligible_checks
                  << ",\"joint_cap_skips\":" << theory.cap_skips
                  << ",\"joint_no_chain_rejections\":"
                  << theory.no_chain_rejections
                  << ",\"joint_x_only_hits\":" << theory.x_only_hits
                  << ",\"joint_pair0_root_calls\":"
                  << theory.pair_root_calls[0]
                  << ",\"joint_pair1_root_calls\":"
                  << theory.pair_root_calls[1]
                  << ",\"joint_final_root_calls\":"
                  << theory.final_join_root_calls
                  << ",\"joint_pair0_output_states\":"
                  << theory.pair_outputs[0]
                  << ",\"joint_pair1_output_states\":"
                  << theory.pair_outputs[1]
                  << ",\"joint_guard_literals\":"
                  << theory.join_guard_literals
                  << ",\"joint_field_mul_calls\":"
                  << theory.join_mul_calls
                  << ",\"joint_field_sqr_calls\":"
                  << theory.join_sqr_calls
                  << ",\"joint_field_inv_calls\":"
                  << theory.join_inv_calls
                  << ",\"batch_inverse_batches\":"
                  << theory.batch_stats.inverse_batches
                  << ",\"batch_denominators\":"
                  << theory.batch_stats.denominators
                  << ",\"batch_root_inputs\":"
                  << theory.batch_stats.root_inputs
                  << ",\"root_cache_hits\":["
                  << theory.cache_hits[0] << ',' << theory.cache_hits[1]
                  << ',' << theory.cache_hits[2] << ']'
                  << ",\"root_cache_misses\":["
                  << theory.cache_misses[0] << ',' << theory.cache_misses[1]
                  << ',' << theory.cache_misses[2] << ']'
                  << ",\"root_batch_reuses\":["
                  << theory.batch_reuses[0] << ',' << theory.batch_reuses[1]
                  << ',' << theory.batch_reuses[2] << ']'
                  << ",\"root_cache_entries\":" << theory.root_cache.size()
                  << ",\"root_cache_capacity_skips\":"
                  << theory.cache_capacity_skips
                  << ",\"root_cache_entry_cap\":"
                  << theory.cache_entry_cap
                  << ",\"field_mul_calls\":" << field.counts.mul
                  << ",\"field_sqr_calls\":" << field.counts.sqr
                  << ",\"field_inv_calls\":" << field.counts.inv
                  << ",\"field_s3_root_calls\":" << field.counts.roots
                  << ",\"external_clauses\":" << theory.emitted_clauses
                  << ",\"model_checks\":" << theory.model_checks
                  << ",\"rejected_models\":" << theory.rejected_models
                  << ",\"joint_rejection_snapshots\":[";
        auto emit_snapshots = [](const std::vector<JointTheory::Snapshot> &rows) {
            for (size_t i = 0; i < rows.size(); ++i) {
                if (i) std::cout << ',';
                const auto &s = rows[i];
                std::cout << "{\"target_preimage_index\":"
                          << s.target_choice
                          << ",\"leaf_fixed_mask_onb_hex\":[";
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
                std::cout << "],\"pair_candidate_counts\":["
                          << s.pair_candidates[0] << ','
                          << s.pair_candidates[1] << "]}";
            }
        };
        emit_snapshots(theory.rejection_snapshots);
        std::cout << "],\"joint_hit_snapshots\":[";
        emit_snapshots(theory.hit_snapshots);
        std::cout << "]}\n";
        solver.disconnect_terminator();
        solver.disconnect_external_propagator();
        return status == 10 ? 0 : status == 20 ? 20 : 10;
    } catch (const std::exception &error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
