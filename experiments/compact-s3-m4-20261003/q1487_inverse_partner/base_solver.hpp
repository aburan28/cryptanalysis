// Q1486: exact cyclic-window completion in target-coupled S3 pair domains.
// Preserve Q1482's complete window-orbit CNF and Q1485's conditioned join.
#define main q1446_unused_main
#include "../q1446_joint_pair_span/theory_solver.cpp"
#undef main
#include "../q1458_batch_roots/batch_roots.hpp"

#include <map>
#include <unordered_map>

using q1420::U128;

struct WindowMap {
    int n = 0, d = 0;
    std::array<std::vector<int>, 4> selectors;
    std::vector<U128> masks;
    explicit WindowMap(const std::string &path, const Variables &vars,
                       int cnf_variables) {
        std::ifstream input(path);
        require(bool(input), "window sidecar map missing");
        std::string magic;
        input >> magic >> n >> d;
        require(bool(input) && magic == "Q1486WIN1" &&
                    n == vars.n && d == vars.weight,
                "bad window sidecar map header");
        std::set<int> seen;
        for (auto &row : selectors) {
            row.resize(n);
            for (int &bit : row) {
                input >> bit;
                require(bool(input) && bit > 0 && bit <= cnf_variables &&
                            seen.insert(bit).second,
                        "bad window selector ID");
            }
        }
        masks.resize(n);
        for (U128 &mask : masks) {
            std::string encoded;
            input >> encoded;
            require(bool(input), "short window mask row");
            mask = q1420::parse_hex(encoded);
            require((mask >> n) == 0 &&
                        RootTheory::popcount(mask) == d,
                    "bad ONB window mask");
        }
        std::string extra;
        require(!(input >> extra), "extra window map data");
        for (const auto &row : vars.leaves)
            for (int bit : row)
                require(!seen.count(bit), "window selector aliases leaf");
        for (const auto &row : vars.mids)
            for (int bit : row)
                require(!seen.count(bit), "window selector aliases mid");
        for (int bit : vars.selector)
            require(!seen.count(bit), "window selector aliases target");
    }
};

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
        U128 window_true = 0, window_false = 0;
        int index = 0;
        int free = 0, slack = 0;
    };
    struct Snapshot {
        unsigned target_choice = 0;
        std::array<LeafState, 4> leaves;
        std::array<uint64_t, 2> pair_candidates{};
        U128 first_mid_fixed = 0, first_mid_ones = 0;
        U128 second_mid = 0;
    };
    int pair_cap;
    uint64_t partial_events = 0, eligible_checks = 0, cap_skips = 0;
    uint64_t no_chain_rejections = 0, x_only_hits = 0;
    uint64_t conditioned_final_root_calls = 0;
    uint64_t conditioned_left_evals = 0, conditioned_right_evals = 0;
    uint64_t conditioned_right_supports = 0;
    uint64_t conditioned_no_target_roots = 0;
    uint64_t join_guard_literals = 0;
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
    static constexpr uint64_t domain_pair_cap = 4096;
    static constexpr size_t domain_cache_cap = 64;
    using DomainKey = std::array<U128, 9>;
    std::map<DomainKey, std::vector<U128>> domain_cache;
    std::deque<DomainKey> domain_fifo;
    uint64_t domain_events = 0, domain_cap_skips = 0;
    uint64_t domain_builds = 0, domain_cache_hits = 0;
    uint64_t domain_pair_root_calls = 0, domain_final_root_calls = 0;
    uint64_t domain_output_values = 0, domain_max_output_values = 0;
    uint64_t domain_rejections = 0, domain_implications = 0;
    uint64_t domain_guard_literals = 0;
    uint64_t domain_mul_calls = 0, domain_sqr_calls = 0, domain_inv_calls = 0;
    static constexpr uint64_t coupled_pair_cap = 4096;
    static constexpr size_t coupled_cache_cap = 64;
    using RightKey = std::array<U128, 8>;
    std::map<DomainKey, std::vector<U128>> coupled_left_cache;
    std::deque<DomainKey> coupled_left_fifo;
    std::map<RightKey, std::vector<U128>> coupled_right_cache;
    std::deque<RightKey> coupled_right_fifo;
    std::map<unsigned, std::set<std::array<U128, 18>>> coupled_checked;
    uint64_t coupled_events = 0, coupled_cap_skips = 0;
    uint64_t coupled_eligible_checks = 0;
    uint64_t coupled_left_builds = 0, coupled_left_cache_hits = 0;
    uint64_t coupled_right_builds = 0, coupled_right_cache_hits = 0;
    uint64_t coupled_right_pair_root_calls = 0;
    uint64_t coupled_intersection_values = 0;
    uint64_t coupled_nonempty_intersections = 0;
    uint64_t coupled_rejections = 0, coupled_implications = 0;
    uint64_t coupled_guard_literals = 0;
    uint64_t coupled_mul_calls = 0, coupled_sqr_calls = 0;
    uint64_t coupled_inv_calls = 0;

    const WindowMap &windows;
    uint64_t forced_window_decisions = 0;
    mutable uint64_t window_count_calls = 0;
    mutable uint64_t window_count_capped = 0;
    mutable uint64_t window_enumerations = 0;
    mutable uint64_t window_enumerated_values = 0;
    JointTheory(q1420::Field &f, const Variables &v, const Targets &t,
                const WindowMap &w, int max_var, int max_pair_candidates)
        : RootTheory(f, v, t, max_var, true, true, true,
                     false, false, true),
          pair_cap(max_pair_candidates), windows(w) {
        require(pair_cap > 0, "invalid joint-pair cap");
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
        LeafState a = leaf_state(0), b = leaf_state(1);
        if (option_count(a) * option_count(b) > domain_pair_cap) {
            for (int j = 0; j < vars.n; ++j)
                for (int leaf : {0, 1}) {
                    int coordinate = (j + leaf * (vars.n / 4)) % vars.n;
                    int bit = vars.leaves[leaf][coordinate];
                    if (!assignment[bit]) {
                        ++forced_leaf_decisions;
                        return bit;
                    }
                }
        }
        LeafState c = leaf_state(2), d = leaf_state(3);
        if (option_count(c) * option_count(d) > coupled_pair_cap) {
            for (int j = 0; j < vars.n; ++j)
                for (int leaf : {2, 3}) {
                    int coordinate = (j + (leaf - 2) * (vars.n / 4)) % vars.n;
                    int bit = vars.leaves[leaf][coordinate];
                    if (!assignment[bit]) {
                        ++forced_leaf_decisions;
                        return bit;
                    }
                }
        }
        for (int bit : vars.mids[1])
            if (!assignment[bit]) {
                ++forced_mid_decisions;
                return bit;
            }
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
        return 0;
    }

    LeafState leaf_state(int leaf) const {
        LeafState state;
        state.index = leaf;
        for (int j = 0; j < vars.n; ++j) {
            int8_t sign = assignment[vars.leaves[leaf][j]];
            if (!sign) ++state.free;
            else {
                state.fixed |= U128(1) << j;
                if (sign > 0) state.ones |= U128(1) << j;
            }
        }
        state.slack = vars.weight - popcount(state.ones);
        for (int start = 0; start < vars.n; ++start) {
            int8_t sign = assignment[windows.selectors[leaf][start]];
            if (sign > 0) state.window_true |= U128(1) << start;
            if (sign < 0) state.window_false |= U128(1) << start;
        }
        return state;
    }

    std::vector<U128> allowed_window_masks(const LeafState &state) const {
        if (state.window_true) {
            U128 mask = (U128(1) << vars.n) - 1;
            for (int start = 0; start < vars.n; ++start)
                if ((state.window_true >> start) & 1)
                    mask &= windows.masks[start];
            return {mask};
        }
        std::vector<U128> masks;
        for (int start = 0; start < vars.n; ++start)
            if (!((state.window_false >> start) & 1))
                masks.push_back(windows.masks[start]);
        return masks;
    }

    uint64_t option_count(const LeafState &state) const {
        ++window_count_calls;
        if (state.slack < 0) return 0;
        uint64_t total = 0;
        for (U128 allowed : allowed_window_masks(state)) {
            if (state.ones & ~allowed) continue;
            int free = popcount(allowed & ~state.fixed);
            require(free <= vars.weight, "window completion width too large");
            uint64_t count = (uint64_t(1) << free) -
                             unsigned(state.ones == 0);
            total += count;
            if (total > uint64_t(pair_cap)) {
                ++window_count_capped;
                return pair_cap + 1;
            }
        }
        return total;
    }

    std::vector<U128> options(const LeafState &state) const {
        ++window_enumerations;
        std::set<U128> values;
        for (U128 allowed : allowed_window_masks(state)) {
            if (state.ones & ~allowed) continue;
            std::vector<int> free;
            for (int j = 0; j < vars.n; ++j)
                if (((allowed >> j) & 1) && !((state.fixed >> j) & 1))
                    free.push_back(j);
            auto visit = [&](auto &&self, size_t index,
                             U128 value) -> void {
                if (index == free.size()) {
                    if (value) values.insert(value);
                    return;
                }
                self(self, index + 1, value);
                self(self, index + 1,
                     value | (U128(1) << free[index]));
            };
            visit(visit, 0, state.ones);
        }
        window_enumerated_values += values.size();
        return {values.begin(), values.end()};
    }

    void append_window_guard(std::vector<int> &guard, int leaf) const {
        for (int bit : windows.selectors[leaf])
            if (assignment[bit])
                guard.push_back(assignment[bit] > 0 ? -bit : bit);
    }

    std::vector<U128> build_domain(const LeafState &a,
                                   const LeafState &b, U128 target) {
        std::vector<U128> a_values = options(a), b_values = options(b);
        require(a_values.size() * b_values.size() <= domain_pair_cap,
                "left-pair domain exceeded cap");
        std::vector<std::pair<U128, U128>> inputs;
        inputs.reserve(a_values.size() * b_values.size());
        for (U128 left : a_values)
            for (U128 right : b_values)
                inputs.emplace_back(left, right);
        auto pair_roots = cached_roots(inputs, 0);
        domain_pair_root_calls += inputs.size();
        std::set<U128> middles;
        for (const auto &roots : pair_roots)
            middles.insert(roots.begin(), roots.end());
        std::vector<std::pair<U128, U128>> final_inputs;
        for (U128 middle : middles)
            if (middle) final_inputs.emplace_back(middle, target);
        auto final_roots = cached_roots(final_inputs, 2);
        domain_final_root_calls += final_inputs.size();
        std::set<U128> outputs;
        if (middles.count(0))
            outputs.insert(field.to_onb(field.inv(field.to_poly(target))));
        for (const auto &roots : final_roots)
            outputs.insert(roots.begin(), roots.end());
        domain_output_values += outputs.size();
        domain_max_output_values = std::max(domain_max_output_values,
                                            uint64_t(outputs.size()));
        return {outputs.begin(), outputs.end()};
    }

    void maybe_domain() {
        if (!all_fixed(vars.selector)) return;
        unsigned choice = unsigned(value(vars.selector, assignment));
        if (choice >= targets.x.size()) return;
        LeafState a = leaf_state(0), b = leaf_state(1);
        if (!a.free && !b.free) return;
        ++domain_events;
        uint64_t pair_count = option_count(a) * option_count(b);
        if (pair_count > domain_pair_cap) {
            ++domain_cap_skips;
            return;
        }
        DomainKey key{U128(choice), a.fixed, a.ones, a.window_true,
                      a.window_false, b.fixed, b.ones, b.window_true,
                      b.window_false};
        auto cached = domain_cache.find(key);
        const std::vector<U128> *values = nullptr;
        if (cached != domain_cache.end()) {
            ++domain_cache_hits;
            values = &cached->second;
        } else {
            ++domain_builds;
            q1420::Counts before = field.counts;
            std::vector<U128> built = build_domain(a, b, targets.x[choice]);
            domain_mul_calls += field.counts.mul - before.mul;
            domain_sqr_calls += field.counts.sqr - before.sqr;
            domain_inv_calls += field.counts.inv - before.inv;
            if (domain_cache.size() == domain_cache_cap) {
                domain_cache.erase(domain_fifo.front());
                domain_fifo.pop_front();
            }
            domain_fifo.push_back(key);
            values = &domain_cache.emplace(key, std::move(built)).first->second;
        }
        U128 fixed = 0, ones = 0;
        for (int j = 0; j < vars.n; ++j) {
            int8_t sign = assignment[vars.mids[1][j]];
            if (sign) {
                fixed |= U128(1) << j;
                if (sign > 0) ones |= U128(1) << j;
            }
        }
        U128 common_ones = (U128(1) << vars.n) - 1, any_ones = 0;
        uint64_t compatible = 0;
        for (U128 candidate : *values) {
            if ((candidate & fixed) != ones) continue;
            ++compatible;
            common_ones &= candidate;
            any_ones |= candidate;
        }
        std::vector<int> guard;
        for (int bit : vars.selector)
            guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (int leaf : {0, 1})
            for (int bit : vars.leaves[leaf])
                if (assignment[bit])
                    guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (int leaf : {0, 1}) append_window_guard(guard, leaf);
        for (int bit : vars.mids[1])
            if (assignment[bit])
                guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (int lit : guard) {
            int bit = std::abs(lit);
            require(assignment[bit] == (lit > 0 ? -1 : 1),
                    "domain guard not false on current trail");
        }
        if (!compatible) {
            ++domain_rejections;
            domain_guard_literals += guard.size();
            add_clause(guard, {});
            return;
        }
        for (int j = 0; j < vars.n; ++j) {
            int bit = vars.mids[1][j];
            if (assignment[bit]) continue;
            U128 mask = U128(1) << j;
            if (common_ones & mask) {
                ++domain_implications;
                domain_guard_literals += guard.size();
                add_clause(guard, {bit});
            } else if (!(any_ones & mask)) {
                ++domain_implications;
                domain_guard_literals += guard.size();
                add_clause(guard, {-bit});
            }
        }
    }

    const std::vector<U128> &coupled_left_domain(
        unsigned choice, const LeafState &a, const LeafState &b) {
        DomainKey key{U128(choice), a.fixed, a.ones, a.window_true,
                      a.window_false, b.fixed, b.ones, b.window_true,
                      b.window_false};
        auto parent_hit = domain_cache.find(key);
        if (parent_hit != domain_cache.end()) {
            ++coupled_left_cache_hits;
            return parent_hit->second;
        }
        auto hit = coupled_left_cache.find(key);
        if (hit != coupled_left_cache.end()) {
            ++coupled_left_cache_hits;
            return hit->second;
        }
        ++coupled_left_builds;
        std::vector<U128> built = build_domain(a, b, targets.x[choice]);
        if (coupled_left_cache.size() == coupled_cache_cap) {
            coupled_left_cache.erase(coupled_left_fifo.front());
            coupled_left_fifo.pop_front();
        }
        coupled_left_fifo.push_back(key);
        return coupled_left_cache.emplace(key, std::move(built)).first->second;
    }

    const std::vector<U128> &coupled_right_domain(
        const LeafState &c, const LeafState &d) {
        RightKey key{c.fixed, c.ones, c.window_true, c.window_false,
                     d.fixed, d.ones, d.window_true, d.window_false};
        auto hit = coupled_right_cache.find(key);
        if (hit != coupled_right_cache.end()) {
            ++coupled_right_cache_hits;
            return hit->second;
        }
        ++coupled_right_builds;
        std::vector<U128> c_values = options(c), d_values = options(d);
        require(c_values.size() * d_values.size() <= coupled_pair_cap,
                "right pair domain exceeded cap");
        std::vector<std::pair<U128, U128>> inputs;
        inputs.reserve(c_values.size() * d_values.size());
        for (U128 left : c_values)
            for (U128 right : d_values)
                inputs.emplace_back(left, right);
        coupled_right_pair_root_calls += inputs.size();
        auto roots = cached_roots(inputs, 1);
        std::set<U128> unique;
        for (const auto &row : roots) unique.insert(row.begin(), row.end());
        std::vector<U128> built(unique.begin(), unique.end());
        if (coupled_right_cache.size() == coupled_cache_cap) {
            coupled_right_cache.erase(coupled_right_fifo.front());
            coupled_right_fifo.pop_front();
        }
        coupled_right_fifo.push_back(key);
        return coupled_right_cache.emplace(key, std::move(built)).first->second;
    }

    void maybe_coupled() {
        if (!all_fixed(vars.selector)) return;
        unsigned choice = unsigned(value(vars.selector, assignment));
        if (choice >= targets.x.size()) return;
        ++coupled_events;
        std::array<LeafState, 4> states;
        for (int leaf = 0; leaf < 4; ++leaf)
            states[leaf] = leaf_state(leaf);
        uint64_t left_count = option_count(states[0]) *
                              option_count(states[1]);
        uint64_t right_count = option_count(states[2]) *
                               option_count(states[3]);
        if (left_count > coupled_pair_cap ||
            right_count > coupled_pair_cap) {
            ++coupled_cap_skips;
            return;
        }
        auto [second_fixed, second_ones] = mid_masks(1);
        std::array<U128, 18> key{};
        for (int leaf = 0; leaf < 4; ++leaf) {
            key[4 * leaf] = states[leaf].fixed;
            key[4 * leaf + 1] = states[leaf].ones;
            key[4 * leaf + 2] = states[leaf].window_true;
            key[4 * leaf + 3] = states[leaf].window_false;
        }
        key[16] = second_fixed;
        key[17] = second_ones;
        if (!coupled_checked[choice].insert(key).second) return;
        ++coupled_eligible_checks;
        q1420::Counts before = field.counts;
        const auto &left = coupled_left_domain(
            choice, states[0], states[1]);
        const auto &right = coupled_right_domain(states[2], states[3]);
        U128 common_ones = (U128(1) << vars.n) - 1;
        U128 any_ones = 0;
        uint64_t compatible = 0;
        size_t i = 0, j = 0;
        while (i < left.size() && j < right.size()) {
            if (left[i] < right[j]) { ++i; continue; }
            if (right[j] < left[i]) { ++j; continue; }
            U128 candidate = left[i];
            if ((candidate & second_fixed) == second_ones) {
                ++compatible;
                common_ones &= candidate;
                any_ones |= candidate;
            }
            ++i;
            ++j;
        }
        coupled_mul_calls += field.counts.mul - before.mul;
        coupled_sqr_calls += field.counts.sqr - before.sqr;
        coupled_inv_calls += field.counts.inv - before.inv;
        coupled_intersection_values += compatible;
        std::vector<int> guard;
        for (int bit : vars.selector)
            guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (const auto &bits : vars.leaves)
            for (int bit : bits)
                if (assignment[bit])
                    guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (int leaf = 0; leaf < 4; ++leaf)
            append_window_guard(guard, leaf);
        for (int bit : vars.mids[1])
            if (assignment[bit])
                guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (int lit : guard) {
            int bit = std::abs(lit);
            require(assignment[bit] == (lit > 0 ? -1 : 1),
                    "coupled-domain guard not false on current trail");
        }
        if (!compatible) {
            ++coupled_rejections;
            coupled_guard_literals += guard.size();
            add_clause(guard, {});
            return;
        }
        ++coupled_nonempty_intersections;
        for (int bit_index = 0; bit_index < vars.n; ++bit_index) {
            int bit = vars.mids[1][bit_index];
            if (assignment[bit]) continue;
            U128 mask = U128(1) << bit_index;
            if (common_ones & mask) {
                ++coupled_implications;
                coupled_guard_literals += guard.size();
                add_clause(guard, {bit});
            } else if (!(any_ones & mask)) {
                ++coupled_implications;
                coupled_guard_literals += guard.size();
                add_clause(guard, {-bit});
            }
        }
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

    std::pair<U128, U128> mid_masks(int which) const {
        U128 fixed = 0, ones = 0;
        for (int j = 0; j < vars.n; ++j) {
            int8_t sign = assignment[vars.mids[which][j]];
            if (sign) {
                fixed |= U128(1) << j;
                if (sign > 0) ones |= U128(1) << j;
            }
        }
        return {fixed, ones};
    }

    bool has_conditioned_chain(const std::array<LeafState, 4> &state,
                               U128 target, U128 second_mid,
                               U128 first_fixed, U128 first_ones) {
        std::vector<U128> first_mids;
        if (second_mid) {
            auto roots = cached_roots({{second_mid, target}}, 2);
            first_mids = std::move(roots[0]);
            ++conditioned_final_root_calls;
        } else {
            // S3(0,target,u)=target^2*u^2+1, hence u=target^-1.
            first_mids = {field.to_onb(field.inv(field.to_poly(target)))};
        }
        first_mids.erase(std::remove_if(first_mids.begin(), first_mids.end(),
            [&](U128 u) { return (u & first_fixed) != first_ones; }),
            first_mids.end());
        if (first_mids.empty()) {
            ++conditioned_no_target_roots;
            return false;
        }
        std::array<std::vector<U128>, 4> poly;
        auto fill_poly = [&](int leaf) {
            auto raw = options(state[leaf]);
            require(raw.size() <= option_count(state[leaf]),
                    "conditioned completion upper-bound mismatch");
            poly[leaf].reserve(raw.size());
            for (U128 x : raw) poly[leaf].push_back(field.to_poly(x));
        };
        fill_poly(2);
        fill_poly(3);
        U128 second_poly = field.to_poly(second_mid);
        bool right_supported = false;
        for (U128 c : poly[2]) {
            for (U128 d : poly[3]) {
                ++conditioned_right_evals;
                if (field.evaluate_s3(c, d, second_poly) == 0) {
                    right_supported = true;
                    break;
                }
            }
            if (right_supported) break;
        }
        if (!right_supported) return false;
        ++conditioned_right_supports;
        fill_poly(0);
        fill_poly(1);
        for (U128 first_mid : first_mids) {
            U128 first_poly = field.to_poly(first_mid);
            for (U128 a : poly[0])
                for (U128 b : poly[1]) {
                    ++conditioned_left_evals;
                    if (field.evaluate_s3(a, b, first_poly) == 0)
                        return true;
                }
        }
        return false;
    }

    void maybe_join() {
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
        auto &selected = checked_by_target[choice];
        if (!selected.insert(key).second) return;
        ++eligible_checks;
        q1420::Counts before = field.counts;
        bool found = has_conditioned_chain(
            state, targets.x[choice], second_mid, first_fixed, first_ones);
        join_mul_calls += field.counts.mul - before.mul;
        join_sqr_calls += field.counts.sqr - before.sqr;
        join_inv_calls += field.counts.inv - before.inv;
        if (found) {
            ++x_only_hits;
            if (hit_snapshots.size() < 16)
                hit_snapshots.push_back({choice, state,
                                         {pairs[0], pairs[1]}, first_fixed,
                                         first_ones, second_mid});
            return;
        }
        ++no_chain_rejections;
        if (rejection_snapshots.size() < 16)
            rejection_snapshots.push_back({choice, state,
                                           {pairs[0], pairs[1]}, first_fixed,
                                           first_ones, second_mid});
        std::vector<int> guard;
        for (int bit : vars.selector)
            guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (const auto &bits : vars.leaves)
            for (int bit : bits)
                if (assignment[bit])
                    guard.push_back(assignment[bit] > 0 ? -bit : bit);
        for (int leaf = 0; leaf < 4; ++leaf)
            append_window_guard(guard, leaf);
        for (const auto &bits : vars.mids)
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

    std::map<unsigned, std::set<std::array<U128, 20>>> checked_by_target;

    void notify_assignment(const std::vector<int> &lits) override {
        RootTheory::notify_assignment(lits);
        maybe_domain();
        maybe_coupled();
        maybe_join();
    }
};
