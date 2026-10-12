// Q1434: exact sparse-tail completions after the cached partial-span screen.
#include "../q1422_leaf_lift_gate/lift_gate.hpp"
#include "exact_tail.hpp"

#include <cadical.hpp>

#include <algorithm>
#include <chrono>
#include <deque>
#include <fstream>
#include <iostream>
#include <set>
#include <tuple>
#include <vector>

using q1420::U128;
using q1420::require;

struct Variables {
    int n = 0, weight = 0;
    std::vector<std::vector<int>> leaves, mids;
    std::vector<int> selector;
    explicit Variables(const std::string &path) {
        std::ifstream input(path);
        require(bool(input), "variable map missing");
        std::string magic;
        input >> magic >> n >> weight;
        require(magic == "Q1420MAP1" && (n == 53 || n == 83),
                "bad variable map header");
        require(weight > 0 && weight < n, "bad weight limit");
        for (int row = 0; row < 6; ++row) {
            std::vector<int> bits(n);
            for (int &bit : bits) {
                input >> bit;
                require(bool(input) && bit > 0, "short variable map row");
            }
            if (row < 4) leaves.push_back(bits);
            else mids.push_back(bits);
        }
        int selector_count = 0;
        input >> selector_count;
        require(bool(input) && selector_count > 0 && selector_count < 16,
                "bad selector width");
        selector.resize(selector_count);
        for (int &bit : selector) {
            input >> bit;
            require(bool(input) && bit > 0, "short selector row");
        }
        int extra = 0;
        require(!(input >> extra), "extra variable map data");
        std::set<int> seen;
        for (const auto &row : leaves)
            for (int bit : row) require(seen.insert(bit).second,
                                        "duplicate leaf variable");
        for (const auto &row : mids)
            for (int bit : row) require(seen.insert(bit).second,
                                        "duplicate mid variable");
        for (int bit : selector)
            require(seen.insert(bit).second, "duplicate selector variable");
    }
};

struct Targets {
    int n = 0;
    std::vector<U128> x;
    explicit Targets(const std::string &path) {
        std::ifstream input(path);
        require(bool(input), "target-preimage list missing");
        std::string magic, encoded;
        int count = 0;
        input >> magic >> n >> count;
        require(magic == "Q1423TARGETS1" && (n == 53 || n == 83) &&
                count > 0 && count < 1024, "bad target-preimage header");
        for (int i = 0; i < count; ++i) {
            input >> encoded;
            require(bool(input), "short target-preimage list");
            U128 value = q1420::parse_hex(encoded);
            require(value && value < (U128(1) << n),
                    "invalid target-preimage x");
            x.push_back(value);
        }
        require(!(input >> encoded), "extra target-preimage data");
    }
};

struct RootTheory : CaDiCaL::ExternalPropagator {
    struct PartialSnapshot {
        U128 mid, a_fixed, a_ones, b_fixed, b_ones;
        int free_a, free_b, slack_a, slack_b;
    };
    q1420::Field &field;
    const Variables &vars;
    const Targets &targets;
    q1432::CachedSpan span_cache;
    bool leaf_first;
    bool lift_gate;
    bool target_coupled;
    bool mid_before_leaves;
    bool interleave_pair1;
    std::vector<int8_t> assignment;
    std::vector<int> trail;
    std::vector<size_t> level_start;
    std::set<std::tuple<int, U128, U128>> cached;
    std::set<std::tuple<int, int, U128, U128>> cached_reverse;
    std::set<std::pair<U128, int>> cached_final;
    std::set<std::pair<int, U128>> cached_leaves, invalid_leaves;
    std::deque<std::vector<int>> pending;
    std::vector<int> current;
    size_t current_index = 0;
    uint64_t emitted_clauses = 0, no_root_pairs = 0, one_root_pairs = 0;
    uint64_t two_root_pairs = 0, rejected_models = 0;
    uint64_t assignment_lits_seen = 0, complete_pair_visits = 0;
    uint64_t decision_requests = 0, forced_leaf_decisions = 0;
    uint64_t model_checks = 0;
    uint64_t valid_leaf_x = 0, invalid_leaf_x = 0;
    uint64_t final_zero_roots = 0, final_one_root = 0;
    uint64_t final_two_roots = 0, final_root_calls = 0;
    uint64_t forced_target_decisions = 0, forced_mid_decisions = 0;
    uint64_t pair0_root_calls = 0, pair1_root_calls = 0;
    uint64_t reverse_pair0_calls = 0, reverse_pair1_calls = 0;
    uint64_t reverse_raw_roots = 0, reverse_weight_rejects = 0;
    uint64_t reverse_lift_rejects = 0, reverse_zero_candidates = 0;
    uint64_t reverse_one_candidate = 0, reverse_two_candidates = 0;
    uint64_t both_partial_mid1_events = 0;
    uint64_t unsaturated_mid1_events = 0;
    uint64_t screen_window_events = 0;
    uint64_t screen_window_distinct_overflow = 0;
    std::set<std::tuple<U128, U128, U128, U128, U128>> screen_states;
    std::vector<PartialSnapshot> screen_snapshots;
    std::set<std::tuple<U128, U128, U128, U128, U128>> span_checked_states;
    std::vector<PartialSnapshot> span_rejection_snapshots;
    uint64_t span_checks = 0, span_rejections = 0;
    uint64_t span_linear_columns = 0, span_bilinear_columns = 0;
    uint64_t span_guard_literals = 0;
    uint64_t span_field_mul_calls = 0, span_field_sqr_calls = 0;
    uint64_t span_field_inv_calls = 0;
    int span_min_rank = 128, span_max_rank = 0;
    uint64_t tail_checks = 0, tail_zero = 0, tail_unique = 0;
    uint64_t tail_multiple = 0, tail_candidate_pairs = 0;
    uint64_t tail_forced_literals = 0, tail_guard_literals = 0;
    uint64_t tail_field_mul_calls = 0, tail_field_sqr_calls = 0;
    uint64_t tail_field_inv_calls = 0;
    std::vector<PartialSnapshot> tail_zero_snapshots;
    std::vector<std::pair<PartialSnapshot, q1434::TailResult>>
        tail_unique_snapshots;

    RootTheory(q1420::Field &f, const Variables &v, const Targets &t,
               int max_var, bool leaf_first_policy, bool lift_gate_active,
               bool target_coupled_active, bool mid_first_policy,
               bool interleave_pair1_policy)
        : field(f), vars(v), targets(t), span_cache(f),
          leaf_first(leaf_first_policy),
          lift_gate(lift_gate_active), target_coupled(target_coupled_active),
          mid_before_leaves(mid_first_policy),
          interleave_pair1(interleave_pair1_policy),
          assignment(max_var + 1, 0) {}

    static U128 value(const std::vector<int> &bits,
                      const std::vector<int8_t> &assigned) {
        U128 result = 0;
        for (size_t position = 0; position < bits.size(); ++position)
            if (assigned.at(bits[position]) > 0) result |= U128(1) << position;
        return result;
    }

    bool all_fixed(const std::vector<int> &bits) const {
        for (int bit : bits) if (!assignment.at(bit)) return false;
        return true;
    }

    static int popcount(U128 x) {
        return __builtin_popcountll(uint64_t(x)) +
               __builtin_popcountll(uint64_t(x >> 64));
    }

    bool observe_partial_second_pair(PartialSnapshot &snapshot) {
        if (!all_fixed(vars.mids[1])) return false;
        U128 fixed[2] = {0, 0}, ones[2] = {0, 0};
        int free[2] = {0, 0};
        for (int side = 0; side < 2; ++side) {
            const auto &bits = vars.leaves[2 + side];
            for (int j = 0; j < vars.n; ++j) {
                int8_t assigned = assignment[bits[j]];
                if (!assigned) ++free[side];
                else {
                    fixed[side] |= U128(1) << j;
                    if (assigned > 0) ones[side] |= U128(1) << j;
                }
            }
        }
        if (!free[0] || !free[1]) return false;
        ++both_partial_mid1_events;
        int slack_a = vars.weight - popcount(ones[0]);
        int slack_b = vars.weight - popcount(ones[1]);
        require(slack_a >= 0 && slack_b >= 0,
                "SAT violated second-pair weight bound");
        if (!slack_a || !slack_b) return false;
        ++unsaturated_mid1_events;
        const int threshold = vars.n == 53 ? 14 : 20;
        if (free[0] > threshold || free[1] > threshold ||
            slack_a > 2 || slack_b > 2) return false;
        ++screen_window_events;
        U128 mid = value(vars.mids[1], assignment);
        snapshot = {mid, fixed[0], ones[0], fixed[1], ones[1],
                    free[0], free[1], slack_a, slack_b};
        auto key = std::make_tuple(mid, fixed[0], ones[0], fixed[1], ones[1]);
        if (screen_states.size() == 256) {
            if (!screen_states.count(key)) ++screen_window_distinct_overflow;
            return true;
        }
        if (!screen_states.insert(key).second) return true;
        if (screen_snapshots.size() < 16)
            screen_snapshots.push_back(snapshot);
        return true;
    }

    std::vector<int> guard_for_partial(const PartialSnapshot &snapshot) const {
        std::vector<int> guard;
        for (int bit : vars.mids[1])
            guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (int side = 0; side < 2; ++side) {
            U128 fixed = side == 0 ? snapshot.a_fixed : snapshot.b_fixed;
            U128 ones = side == 0 ? snapshot.a_ones : snapshot.b_ones;
            const auto &bits = vars.leaves[2 + side];
            for (int j = 0; j < vars.n; ++j)
                if (fixed >> j & 1)
                    guard.push_back(ones >> j & 1 ? -bits[j] : bits[j]);
        }
        require(guard.size() == size_t(vars.n +
                popcount(snapshot.a_fixed) + popcount(snapshot.b_fixed)),
                "incomplete partial-pair guard");
        for (int lit : guard) {
            int bit = lit < 0 ? -lit : lit;
            require(assignment[bit] == (lit > 0 ? -1 : 1),
                    "partial-pair guard not false on current trail");
        }
        return guard;
    }

    void maybe_add_partial_span(const PartialSnapshot &snapshot) {
        auto key = std::make_tuple(snapshot.mid, snapshot.a_fixed,
                                   snapshot.a_ones, snapshot.b_fixed,
                                   snapshot.b_ones);
        if (!span_checked_states.insert(key).second) return;
        q1420::Counts before = field.counts;
        q1431::SpanResult check = span_cache.check(
            snapshot.mid, snapshot.a_fixed, snapshot.a_ones,
            snapshot.b_fixed, snapshot.b_ones);
        ++span_checks;
        span_min_rank = std::min(span_min_rank, check.rank);
        span_max_rank = std::max(span_max_rank, check.rank);
        span_linear_columns += check.linear_columns;
        span_bilinear_columns += check.bilinear_columns;
        span_field_mul_calls += field.counts.mul - before.mul;
        span_field_sqr_calls += field.counts.sqr - before.sqr;
        span_field_inv_calls += field.counts.inv - before.inv;
        if (!check.feasible) {
            ++span_rejections;
            if (span_rejection_snapshots.size() < 16)
                span_rejection_snapshots.push_back(snapshot);
            auto guard = guard_for_partial(snapshot);
            span_guard_literals += guard.size();
            add_clause(guard, {});
            return;
        }
        if (snapshot.slack_a != 1 || snapshot.slack_b != 1) return;
        before = field.counts;
        q1434::TailResult tail = q1434::check(
            span_cache, snapshot.mid, snapshot.a_fixed, snapshot.a_ones,
            snapshot.b_fixed, snapshot.b_ones, vars.weight);
        ++tail_checks;
        tail_candidate_pairs += tail.candidates;
        tail_field_mul_calls += field.counts.mul - before.mul;
        tail_field_sqr_calls += field.counts.sqr - before.sqr;
        tail_field_inv_calls += field.counts.inv - before.inv;
        if (tail.solutions > 1) {
            ++tail_multiple;
            return;
        }
        auto guard = guard_for_partial(snapshot);
        tail_guard_literals += guard.size();
        if (!tail.solutions) {
            ++tail_zero;
            if (tail_zero_snapshots.size() < 16)
                tail_zero_snapshots.push_back(snapshot);
            add_clause(guard, {});
            return;
        }
        ++tail_unique;
        if (tail_unique_snapshots.size() < 16)
            tail_unique_snapshots.push_back({snapshot, tail});
        for (int side = 0; side < 2; ++side) {
            U128 fixed = side == 0 ? snapshot.a_fixed : snapshot.b_fixed;
            U128 chosen = side == 0 ? tail.unique_a : tail.unique_b;
            const auto &bits = vars.leaves[2 + side];
            for (int j = 0; j < vars.n; ++j) {
                if (fixed >> j & 1) continue;
                require(assignment[bits[j]] == 0,
                        "exact tail forcing an assigned leaf bit");
                add_clause(guard, {chosen >> j & 1 ? bits[j] : -bits[j]});
                ++tail_forced_literals;
            }
        }
    }

    std::vector<int> guard_for_leaf(const std::vector<int> &bits) const {
        U128 coordinate = value(bits, assignment);
        unsigned count = unsigned(__builtin_popcountll(uint64_t(coordinate)) +
                                  __builtin_popcountll(uint64_t(coordinate >> 64)));
        require(count <= unsigned(vars.weight), "SAT violated leaf weight");
        std::vector<int> guard;
        if (count == unsigned(vars.weight)) {
            for (int bit : bits) if (assignment[bit] > 0) guard.push_back(-bit);
        } else {
            for (int bit : bits)
                guard.push_back(assignment[bit] > 0 ? -bit : bit);
        }
        return guard;
    }

    void add_clause(const std::vector<int> &guard,
                    std::initializer_list<int> extra) {
        std::vector<int> clause = guard;
        clause.insert(clause.end(), extra.begin(), extra.end());
        pending.push_back(std::move(clause));
        ++emitted_clauses;
    }

    void maybe_add_leaf(int leaf) {
        if (!lift_gate) return;
        const auto &bits = vars.leaves[leaf];
        if (!all_fixed(bits)) return;
        U128 x = value(bits, assignment);
        if (!cached_leaves.insert({leaf, x}).second) return;
        if (q1422::curve_lifts(field, x)) {
            ++valid_leaf_x;
        } else {
            ++invalid_leaf_x;
            invalid_leaves.insert({leaf, x});
            add_clause(guard_for_leaf(bits), {});
        }
    }

    void maybe_add_pair(int pair) {
        const auto &left = vars.leaves[2 * pair];
        const auto &right = vars.leaves[2 * pair + 1];
        if (!all_fixed(left) || !all_fixed(right)) return;
        ++complete_pair_visits;
        U128 a = value(left, assignment), b = value(right, assignment);
        if (lift_gate && (invalid_leaves.count({2 * pair, a}) ||
                          invalid_leaves.count({2 * pair + 1, b}))) return;
        if (!cached.insert({pair, a, b}).second) return;
        if (pair == 0) ++pair0_root_calls;
        else ++pair1_root_calls;
        std::vector<int> guard = guard_for_leaf(left);
        auto other = guard_for_leaf(right);
        guard.insert(guard.end(), other.begin(), other.end());
        auto roots = field.roots_onb(a, b);
        if (roots.empty()) {
            ++no_root_pairs;
            add_clause(guard, {});
            return;
        }
        const auto &mid = vars.mids[pair];
        if (roots.size() == 1) {
            ++one_root_pairs;
            for (int j = 0; j < vars.n; ++j)
                add_clause(guard, {roots[0] >> j & 1 ? mid[j] : -mid[j]});
            return;
        }
        require(roots.size() == 2, "too many S3 roots");
        ++two_root_pairs;
        int branch = -1;
        for (int j = 0; j < vars.n; ++j)
            if (((roots[0] ^ roots[1]) >> j) & 1) {
                branch = j;
                break;
            }
        require(branch >= 0, "identical S3 roots");
        int branch_var = mid[branch];
        for (int j = 0; j < vars.n; ++j) {
            bool first = bool(roots[0] >> j & 1);
            bool second = bool(roots[1] >> j & 1);
            if (first == second) {
                add_clause(guard, {first ? mid[j] : -mid[j]});
            } else if (j != branch) {
                bool first_branch = bool(roots[0] >> branch & 1);
                bool second_branch = !first_branch;
                add_clause(guard, {first_branch ? -branch_var : branch_var,
                                   first ? mid[j] : -mid[j]});
                add_clause(guard, {second_branch ? -branch_var : branch_var,
                                   second ? mid[j] : -mid[j]});
            }
        }
    }

    void maybe_add_reverse_pair(int pair, int known_side) {
        const auto &mid = vars.mids[pair];
        const auto &known = vars.leaves[2 * pair + known_side];
        const auto &partner = vars.leaves[2 * pair + 1 - known_side];
        if (!all_fixed(mid) || !all_fixed(known) || all_fixed(partner)) return;
        U128 m = value(mid, assignment), a = value(known, assignment);
        // The parent CNF excludes zero leaf x; its existing clause handles it.
        if (!a || invalid_leaves.count({2 * pair + known_side, a})) return;
        if (!cached_reverse.insert({pair, known_side, m, a}).second) return;
        if (pair == 0) ++reverse_pair0_calls;
        else ++reverse_pair1_calls;
        std::vector<U128> roots;
        if (m) {
            roots = field.roots_onb(a, m);
        } else {
            // S3(a,b,0)=a^2*b^2+1, so b=a^-1.
            roots = {field.to_onb(field.inv(field.to_poly(a)))};
        }
        reverse_raw_roots += roots.size();
        std::vector<U128> kept;
        for (U128 root : roots) {
            unsigned weight = unsigned(__builtin_popcountll(uint64_t(root)) +
                                       __builtin_popcountll(uint64_t(root >> 64)));
            if (!root || weight > unsigned(vars.weight)) {
                ++reverse_weight_rejects;
            } else if (!q1422::curve_lifts(field, root)) {
                ++reverse_lift_rejects;
            } else {
                kept.push_back(root);
            }
        }
        std::vector<int> guard = guard_for_leaf(known);
        for (int bit : mid)
            guard.push_back(assignment[bit] > 0 ? -bit : bit);
        if (kept.empty()) {
            ++reverse_zero_candidates;
            add_clause(guard, {});
            return;
        }
        if (kept.size() == 1) {
            ++reverse_one_candidate;
            for (int j = 0; j < vars.n; ++j)
                add_clause(guard, {kept[0] >> j & 1 ? partner[j] :
                                                  -partner[j]});
            return;
        }
        require(kept.size() == 2, "too many reverse S3 roots");
        ++reverse_two_candidates;
        int branch = -1;
        for (int j = 0; j < vars.n; ++j)
            if (((kept[0] ^ kept[1]) >> j) & 1) {
                branch = j;
                break;
            }
        require(branch >= 0, "identical reverse S3 roots");
        int branch_var = partner[branch];
        for (int j = 0; j < vars.n; ++j) {
            bool first = bool(kept[0] >> j & 1);
            bool second = bool(kept[1] >> j & 1);
            if (first == second) {
                add_clause(guard, {first ? partner[j] : -partner[j]});
            } else if (j != branch) {
                bool first_branch = bool(kept[0] >> branch & 1);
                bool second_branch = !first_branch;
                add_clause(guard, {first_branch ? -branch_var : branch_var,
                                   first ? partner[j] : -partner[j]});
                add_clause(guard, {second_branch ? -branch_var : branch_var,
                                   second ? partner[j] : -partner[j]});
            }
        }
    }

    void maybe_add_final() {
        if (!target_coupled || !all_fixed(vars.mids[0]) ||
            !all_fixed(vars.selector)) return;
        U128 first_mid = value(vars.mids[0], assignment);
        unsigned choice = unsigned(value(vars.selector, assignment));
        // Out-of-range selector values are already forbidden by the parent CNF.
        if (choice >= targets.x.size()) return;
        if (!cached_final.insert({first_mid, int(choice)}).second) return;
        ++final_root_calls;
        U128 target = targets.x[choice];
        std::vector<U128> roots;
        if (first_mid) {
            roots = field.roots_onb(first_mid, target);
        } else {
            // S3(0,target,z)=target^2*z^2+1, so z=target^-1.
            roots = {field.to_onb(field.inv(field.to_poly(target)))};
        }
        std::vector<int> guard;
        for (int bit : vars.mids[0])
            guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (int bit : vars.selector)
            guard.push_back(assignment[bit] > 0 ? -bit : bit);
        if (roots.empty()) {
            ++final_zero_roots;
            add_clause(guard, {});
            return;
        }
        const auto &second_mid = vars.mids[1];
        if (roots.size() == 1) {
            ++final_one_root;
            for (int j = 0; j < vars.n; ++j)
                add_clause(guard, {roots[0] >> j & 1 ? second_mid[j] :
                                                   -second_mid[j]});
            return;
        }
        require(roots.size() == 2, "too many final S3 roots");
        ++final_two_roots;
        int branch = -1;
        for (int j = 0; j < vars.n; ++j)
            if (((roots[0] ^ roots[1]) >> j) & 1) {
                branch = j;
                break;
            }
        require(branch >= 0, "identical final S3 roots");
        int branch_var = second_mid[branch];
        for (int j = 0; j < vars.n; ++j) {
            bool first = bool(roots[0] >> j & 1);
            bool second = bool(roots[1] >> j & 1);
            if (first == second) {
                add_clause(guard, {first ? second_mid[j] : -second_mid[j]});
            } else if (j != branch) {
                bool first_branch = bool(roots[0] >> branch & 1);
                bool second_branch = !first_branch;
                add_clause(guard, {first_branch ? -branch_var : branch_var,
                                   first ? second_mid[j] : -second_mid[j]});
                add_clause(guard, {second_branch ? -branch_var : branch_var,
                                   second ? second_mid[j] : -second_mid[j]});
            }
        }
    }

    void notify_assignment(const std::vector<int> &lits) override {
        assignment_lits_seen += lits.size();
        for (int lit : lits) {
            int var = lit < 0 ? -lit : lit;
            int8_t sign = lit > 0 ? 1 : -1;
            require(var > 0 && var < int(assignment.size()),
                    "observed variable out of range");
            require(!assignment[var] || assignment[var] == sign,
                    "contradictory observed assignment");
            if (!assignment[var]) {
                assignment[var] = sign;
                trail.push_back(var);
            }
        }
        PartialSnapshot partial{};
        if (observe_partial_second_pair(partial))
            maybe_add_partial_span(partial);
        for (int leaf = 0; leaf < 4; ++leaf) maybe_add_leaf(leaf);
        for (int pair = 0; pair < 2; ++pair) maybe_add_pair(pair);
        maybe_add_final();
        for (int pair = 0; pair < 2; ++pair)
            for (int known_side = 0; known_side < 2; ++known_side)
                maybe_add_reverse_pair(pair, known_side);
    }
    void notify_new_decision_level() override {
        level_start.push_back(trail.size());
    }
    void notify_backtrack(size_t new_level) override {
        require(new_level < level_start.size(), "invalid decision backtrack");
        size_t keep = level_start[new_level];
        while (trail.size() > keep) {
            assignment[trail.back()] = 0;
            trail.pop_back();
        }
        level_start.resize(new_level);
    }
    bool cb_check_found_model(const std::vector<int> &model) override {
        ++model_checks;
        std::vector<int8_t> final_values(assignment.size(), 0);
        for (int lit : model) {
            int var = lit < 0 ? -lit : lit;
            if (var > 0 && var < int(final_values.size()))
                final_values[var] = lit > 0 ? 1 : -1;
        }
        for (int pair = 0; pair < 2; ++pair) {
            U128 a = value(vars.leaves[2 * pair], final_values);
            U128 b = value(vars.leaves[2 * pair + 1], final_values);
            U128 mid = value(vars.mids[pair], final_values);
            auto roots = field.roots_onb(a, b);
            bool valid = false;
            for (U128 root : roots) if (root == mid) valid = true;
            if (!valid) {
                ++rejected_models;
                std::vector<int> blocking;
                for (int leaf : {2 * pair, 2 * pair + 1})
                    for (int bit : vars.leaves[leaf])
                        blocking.push_back(final_values[bit] > 0 ? -bit : bit);
                for (int bit : vars.mids[pair])
                    blocking.push_back(final_values[bit] > 0 ? -bit : bit);
                pending.push_back(std::move(blocking));
                ++emitted_clauses;
                return false;
            }
        }
        if (lift_gate)
            for (int leaf = 0; leaf < 4; ++leaf) {
                U128 x = value(vars.leaves[leaf], final_values);
                if (q1422::curve_lifts(field, x)) continue;
                ++rejected_models;
                std::vector<int> blocking;
                for (int bit : vars.leaves[leaf])
                    blocking.push_back(final_values[bit] > 0 ? -bit : bit);
                pending.push_back(std::move(blocking));
                ++emitted_clauses;
                return false;
            }
        return true;
    }
    int cb_decide() override {
        ++decision_requests;
        if (!leaf_first) return 0;
        if (target_coupled) {
            for (int bit : vars.selector)
                if (!assignment[bit]) {
                    ++forced_target_decisions;
                    return bit;
                }
            if (mid_before_leaves) {
                for (const auto &mid : vars.mids)
                    for (int bit : mid)
                        if (!assignment[bit]) {
                            ++forced_mid_decisions;
                            return bit;
                        }
                for (int leaf : {0, 2, 1, 3})
                    for (int bit : vars.leaves[leaf])
                        if (!assignment[bit]) {
                            ++forced_leaf_decisions;
                            return bit;
                        }
            } else {
                for (int leaf : {0, 1})
                    for (int bit : vars.leaves[leaf])
                        if (!assignment[bit]) {
                            ++forced_leaf_decisions;
                            return bit;
                        }
                for (const auto &mid : vars.mids)
                    for (int bit : mid)
                        if (!assignment[bit]) {
                            ++forced_mid_decisions;
                            return bit;
                        }
                if (interleave_pair1) {
                    for (int j = 0; j < vars.n; ++j)
                        for (int leaf : {2, 3}) {
                            int bit = vars.leaves[leaf][j];
                            if (!assignment[bit]) {
                                ++forced_leaf_decisions;
                                return bit;
                            }
                        }
                } else {
                    for (int leaf : {2, 3})
                        for (int bit : vars.leaves[leaf])
                            if (!assignment[bit]) {
                                ++forced_leaf_decisions;
                                return bit;
                            }
                }
            }
            return 0;
        }
        for (const auto &leaf : vars.leaves)
            for (int bit : leaf)
                if (!assignment[bit]) {
                    ++forced_leaf_decisions;
                    return bit;
                }
        return 0;
    }
    bool cb_has_external_clause(bool &forgettable) override {
        forgettable = false;
        return !pending.empty() || !current.empty();
    }
    int cb_add_external_clause_lit() override {
        if (current.empty()) {
            require(!pending.empty(), "missing external clause");
            current = std::move(pending.front());
            pending.pop_front();
            current_index = 0;
        }
        if (current_index == current.size()) {
            current.clear();
            return 0;
        }
        return current[current_index++];
    }
};

struct Deadline : CaDiCaL::Terminator {
    std::chrono::steady_clock::time_point until;
    bool fired = false;
    explicit Deadline(int seconds)
        : until(std::chrono::steady_clock::now() +
                std::chrono::seconds(seconds)) {}
    bool terminate() override {
        if (std::chrono::steady_clock::now() < until) return false;
        fired = true;
        return true;
    }
};

struct CnfInfo { int variables = 0; int clauses = 0; };

CnfInfo load_cnf(CaDiCaL::Solver &solver, const std::string &path) {
    std::ifstream input(path);
    require(bool(input), "CNF file missing");
    std::string p, cnf;
    CnfInfo info;
    input >> p >> cnf >> info.variables >> info.clauses;
    require(p == "p" && cnf == "cnf" && info.variables > 0 &&
            info.clauses > 0, "bad CNF header");
    int clauses = 0, lit = 0;
    while (input >> lit) {
        require(lit >= -info.variables && lit <= info.variables,
                "CNF literal out of range");
        solver.add(lit);
        if (!lit) ++clauses;
    }
    require(clauses == info.clauses, "CNF clause count mismatch");
    return info;
}

int main(int argc, char **argv) {
    try {
        require(argc == 9,
                "usage: theory_solver FIELD CNF MAP MODEL_OUT CONFLICT_CAP WALL_CAP_SECONDS reverse_target|reverse_mid|interleave_pair1 TARGETS");
        auto start = std::chrono::steady_clock::now();
        q1420::Field field(argv[1]);
        Variables vars(argv[3]);
        Targets targets(argv[8]);
        require(field.n == vars.n, "field/map degree mismatch");
        require(field.n == targets.n, "field/targets degree mismatch");
        require((1u << vars.selector.size()) >= targets.x.size() &&
                (vars.selector.size() == 1 ||
                 (1u << (vars.selector.size() - 1)) < targets.x.size()),
                "target count/selector width mismatch");
        CaDiCaL::Solver solver;
        solver.set("quiet", 1);
        CnfInfo cnf = load_cnf(solver, argv[2]);
        const std::string policy = argv[7];
        require(policy == "reverse_target" || policy == "reverse_mid" ||
                policy == "interleave_pair1",
                "invalid decision policy");
        RootTheory theory(field, vars, targets, cnf.variables,
                          true, true, true, policy == "reverse_mid",
                          policy == "interleave_pair1");
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
        auto print_snapshot = [](const RootTheory::PartialSnapshot &s) {
            std::cout << "{\"mid_onb_hex\":\"" << q1420::hex(s.mid)
                      << "\",\"a_fixed_mask_onb_hex\":\""
                      << q1420::hex(s.a_fixed)
                      << "\",\"a_ones_onb_hex\":\""
                      << q1420::hex(s.a_ones)
                      << "\",\"b_fixed_mask_onb_hex\":\""
                      << q1420::hex(s.b_fixed)
                      << "\",\"b_ones_onb_hex\":\""
                      << q1420::hex(s.b_ones)
                      << "\",\"free_a\":" << s.free_a
                      << ",\"free_b\":" << s.free_b
                      << ",\"slack_a\":" << s.slack_a
                      << ",\"slack_b\":" << s.slack_b << '}';
        };
        std::cout << "{\"status\":" << status
                  << ",\"decision_policy\":\"" << policy << "\""
                  << ",\"lift_gate_active\":"
                  << (theory.lift_gate ? "true" : "false")
                  << ",\"target_coupled_active\":"
                  << (theory.target_coupled ? "true" : "false")
                  << ",\"reverse_pair_active\":true"
                  << ",\"target_preimage_count\":" << targets.x.size()
                  << ",\"stop_reason\":\""
                  << (status == 10 ? "sat" : status == 20 ? "unsat" :
                      deadline.fired ? "wall_cap" : "conflict_cap") << "\""
                  << ",\"conflicts\":" << conflicts
                  << ",\"decisions\":" << decisions
                  << ",\"setup_seconds\":" << seconds(setup_end, start)
                  << ",\"solve_seconds\":" << seconds(end, setup_end)
                  << ",\"cnf_variables\":" << cnf.variables
                  << ",\"cnf_clauses\":" << cnf.clauses
                  << ",\"cached_pair_assignments\":" << theory.cached.size()
                  << ",\"pair0_root_calls\":" << theory.pair0_root_calls
                  << ",\"pair1_root_calls\":" << theory.pair1_root_calls
                  << ",\"reverse_pair0_calls\":" << theory.reverse_pair0_calls
                  << ",\"reverse_pair1_calls\":" << theory.reverse_pair1_calls
                  << ",\"cached_reverse_assignments\":" << theory.cached_reverse.size()
                  << ",\"reverse_raw_roots\":" << theory.reverse_raw_roots
                  << ",\"reverse_weight_rejects\":" << theory.reverse_weight_rejects
                  << ",\"reverse_lift_rejects\":" << theory.reverse_lift_rejects
                  << ",\"reverse_zero_candidates\":" << theory.reverse_zero_candidates
                  << ",\"reverse_one_candidate\":" << theory.reverse_one_candidate
                  << ",\"reverse_two_candidates\":" << theory.reverse_two_candidates
                  << ",\"both_partial_mid1_events\":"
                  << theory.both_partial_mid1_events
                  << ",\"unsaturated_mid1_events\":"
                  << theory.unsaturated_mid1_events
                  << ",\"screen_window_free_threshold_each_leaf\":"
                  << (vars.n == 53 ? 14 : 20)
                  << ",\"screen_window_events\":"
                  << theory.screen_window_events
                  << ",\"screen_window_distinct_capped\":"
                  << theory.screen_states.size()
                  << ",\"screen_window_distinct_overflow_events\":"
                  << theory.screen_window_distinct_overflow
                  << ",\"span_checks\":" << theory.span_checks
                  << ",\"span_checked_state_count\":"
                  << theory.span_checked_states.size()
                  << ",\"span_rejections\":" << theory.span_rejections
                  << ",\"span_linear_columns\":"
                  << theory.span_linear_columns
                  << ",\"span_bilinear_columns\":"
                  << theory.span_bilinear_columns
                  << ",\"span_guard_literals\":"
                  << theory.span_guard_literals
                  << ",\"span_field_mul_calls\":"
                  << theory.span_field_mul_calls
                  << ",\"span_field_sqr_calls\":"
                  << theory.span_field_sqr_calls
                  << ",\"span_field_inv_calls\":"
                  << theory.span_field_inv_calls
                  << ",\"tail_checks\":" << theory.tail_checks
                  << ",\"tail_zero\":" << theory.tail_zero
                  << ",\"tail_unique\":" << theory.tail_unique
                  << ",\"tail_multiple\":" << theory.tail_multiple
                  << ",\"tail_candidate_pairs\":"
                  << theory.tail_candidate_pairs
                  << ",\"tail_forced_literals\":"
                  << theory.tail_forced_literals
                  << ",\"tail_guard_literals\":"
                  << theory.tail_guard_literals
                  << ",\"tail_field_mul_calls\":"
                  << theory.tail_field_mul_calls
                  << ",\"tail_field_sqr_calls\":"
                  << theory.tail_field_sqr_calls
                  << ",\"tail_field_inv_calls\":"
                  << theory.tail_field_inv_calls
                  << ",\"span_min_rank\":"
                  << (theory.span_checks ? theory.span_min_rank : -1)
                  << ",\"span_max_rank\":"
                  << (theory.span_checks ? theory.span_max_rank : -1)
                  << ",\"cache_pair_build_mul_calls\":"
                  << theory.span_cache.pair_build_mul_calls
                  << ",\"cache_pair_build_sqr_calls\":"
                  << theory.span_cache.pair_build_sqr_calls
                  << ",\"cache_gamma_build_mul_calls\":"
                  << theory.span_cache.gamma_build_mul_calls
                  << ",\"cache_gamma_table_builds\":"
                  << theory.span_cache.gamma_table_builds
                  << ",\"cache_gamma_tables_retained\":"
                  << theory.span_cache.gamma_tables.size()
                  << ",\"cache_gamma_hits\":"
                  << theory.span_cache.gamma_cache_hits
                  << ",\"cache_gamma_fallbacks\":"
                  << theory.span_cache.gamma_cache_fallbacks
                  << ",\"cache_linear_rows_retained\":"
                  << theory.span_cache.linear_rows.size()
                  << ",\"cache_linear_row_hits\":"
                  << theory.span_cache.linear_row_hits
                  << ",\"cache_linear_row_misses\":"
                  << theory.span_cache.linear_row_misses
                  << ",\"cache_linear_row_fallbacks\":"
                  << theory.span_cache.linear_row_fallbacks
                  << ",\"cache_linear_coefficient_hits\":"
                  << theory.span_cache.linear_coefficient_hits
                  << ",\"cache_linear_coefficient_misses\":"
                  << theory.span_cache.linear_coefficient_misses
                  << ",\"cache_payload_bytes_lower_bound\":"
                  << theory.span_cache.payload_bytes_lower_bound()
                  << ",\"checked_single_leaf_values\":"
                  << theory.cached_leaves.size()
                  << ",\"valid_single_leaf_values\":"
                  << theory.valid_leaf_x
                  << ",\"invalid_single_leaf_values\":"
                  << theory.invalid_leaf_x
                  << ",\"complete_pair_visits\":" << theory.complete_pair_visits
                  << ",\"assignment_lits_seen\":" << theory.assignment_lits_seen
                  << ",\"decision_requests\":" << theory.decision_requests
                  << ",\"forced_leaf_decisions\":" << theory.forced_leaf_decisions
                  << ",\"forced_target_decisions\":" << theory.forced_target_decisions
                  << ",\"forced_mid_decisions\":" << theory.forced_mid_decisions
                  << ",\"model_checks\":" << theory.model_checks
                  << ",\"external_clauses\":" << theory.emitted_clauses
                  << ",\"zero_root_pairs\":" << theory.no_root_pairs
                  << ",\"one_root_pairs\":" << theory.one_root_pairs
                  << ",\"two_root_pairs\":" << theory.two_root_pairs
                  << ",\"final_root_calls\":" << theory.final_root_calls
                  << ",\"cached_final_assignments\":" << theory.cached_final.size()
                  << ",\"final_zero_roots\":" << theory.final_zero_roots
                  << ",\"final_one_root\":" << theory.final_one_root
                  << ",\"final_two_roots\":" << theory.final_two_roots
                  << ",\"rejected_models\":" << theory.rejected_models
                  << ",\"field_mul_calls\":" << field.counts.mul
                  << ",\"field_sqr_calls\":" << field.counts.sqr
                  << ",\"field_inv_calls\":" << field.counts.inv
                  << ",\"s3_root_calls\":" << field.counts.roots
                  << ",\"screen_snapshots\":[";
        for (size_t i = 0; i < theory.screen_snapshots.size(); ++i) {
            const auto &s = theory.screen_snapshots[i];
            if (i) std::cout << ',';
            std::cout << "{\"mid_onb_hex\":\"" << q1420::hex(s.mid)
                      << "\",\"a_fixed_mask_onb_hex\":\""
                      << q1420::hex(s.a_fixed)
                      << "\",\"a_ones_onb_hex\":\""
                      << q1420::hex(s.a_ones)
                      << "\",\"b_fixed_mask_onb_hex\":\""
                      << q1420::hex(s.b_fixed)
                      << "\",\"b_ones_onb_hex\":\""
                      << q1420::hex(s.b_ones)
                      << "\",\"free_a\":" << s.free_a
                      << ",\"free_b\":" << s.free_b
                      << ",\"slack_a\":" << s.slack_a
                      << ",\"slack_b\":" << s.slack_b << '}';
        }
        std::cout << "],\"span_rejection_snapshots\":[";
        for (size_t i = 0; i < theory.span_rejection_snapshots.size(); ++i) {
            const auto &s = theory.span_rejection_snapshots[i];
            if (i) std::cout << ',';
            std::cout << "{\"mid_onb_hex\":\"" << q1420::hex(s.mid)
                      << "\",\"a_fixed_mask_onb_hex\":\""
                      << q1420::hex(s.a_fixed)
                      << "\",\"a_ones_onb_hex\":\""
                      << q1420::hex(s.a_ones)
                      << "\",\"b_fixed_mask_onb_hex\":\""
                      << q1420::hex(s.b_fixed)
                      << "\",\"b_ones_onb_hex\":\""
                      << q1420::hex(s.b_ones)
                      << "\",\"free_a\":" << s.free_a
                      << ",\"free_b\":" << s.free_b
                      << ",\"slack_a\":" << s.slack_a
                      << ",\"slack_b\":" << s.slack_b << '}';
        }
        std::cout << "],\"tail_zero_snapshots\":[";
        for (size_t i = 0; i < theory.tail_zero_snapshots.size(); ++i) {
            if (i) std::cout << ',';
            print_snapshot(theory.tail_zero_snapshots[i]);
        }
        std::cout << "],\"tail_unique_snapshots\":[";
        for (size_t i = 0; i < theory.tail_unique_snapshots.size(); ++i) {
            if (i) std::cout << ',';
            const auto &item = theory.tail_unique_snapshots[i];
            std::cout << "{\"partial\":";
            print_snapshot(item.first);
            std::cout << ",\"candidates\":" << item.second.candidates
                      << ",\"solutions\":" << item.second.solutions
                      << ",\"unique_a_onb_hex\":\""
                      << q1420::hex(item.second.unique_a)
                      << "\",\"unique_b_onb_hex\":\""
                      << q1420::hex(item.second.unique_b) << "\"}";
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
