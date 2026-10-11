// Q1478: one-worker, one-target distinguished-point Pollard rho reference.
#define main q1468_unused_main
#include "../q1468_n53_pair_oracle/pair_oracle.cpp"
#undef main

#include <array>
#include <unordered_map>

namespace {

constexpr uint64_t ORDER = 21044858204113ULL;
constexpr uint64_t STEP_CAP = 50000000ULL;
constexpr uint64_t WALL_CAP_NS = 1800000000000ULL;
constexpr uint64_t MAX_WALK_STEPS = 262144ULL;
constexpr unsigned PARTITIONS = 16;
constexpr unsigned DISTINGUISHED_BITS = 10;

struct PointCount {
    uint64_t additions = 0, doublings = 0;
};

struct Phase {
    uint64_t ns = 0;
    q1420::Counts field{};
    PointCount point{};
};

struct State {
    Point point;
    uint64_t a = 0, b = 0;
};

struct Walk {
    uint64_t start_a = 0, start_b = 0, steps = 0;
    std::string status;
    U128 endpoint_x = 0, endpoint_y = 0;
};

struct PointKey {
    uint64_t x = 0, y = 0;
    bool operator==(const PointKey &other) const {
        return x == other.x && y == other.y;
    }
};

struct PointHash {
    size_t operator()(const PointKey &key) const {
        uint64_t value = key.x ^ (key.y + 0x9e3779b97f4a7c15ULL +
                                  (key.x << 6) + (key.x >> 2));
        value ^= value >> 30;
        value *= UINT64_C(0xbf58476d1ce4e5b9);
        value ^= value >> 27;
        value *= UINT64_C(0x94d049bb133111eb);
        return size_t(value ^ (value >> 31));
    }
};

struct Collision {
    State old_state, new_state;
    uint64_t numerator = 0, denominator = 0, candidate = 0;
};

struct Input {
    Point generator, target;
};

uint64_t splitmix64(uint64_t &state) {
    state += UINT64_C(0x9e3779b97f4a7c15);
    uint64_t value = state;
    value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
}

uint64_t mul_mod(uint64_t a, uint64_t b) {
    return uint64_t((U128(a) * b) % ORDER);
}

uint64_t pow_mod(uint64_t base, uint64_t exponent) {
    uint64_t answer = 1;
    while (exponent) {
        if (exponent & 1) answer = mul_mod(answer, base);
        exponent >>= 1;
        if (exponent) base = mul_mod(base, base);
    }
    return answer;
}

Point scalar_mul(Field &field, const Point &base, uint64_t scalar,
                 PointCount &counts) {
    Point answer;
    Point power = base;
    while (scalar) {
        if (scalar & 1) {
            answer = add(field, answer, power);
            ++counts.additions;
        }
        scalar >>= 1;
        if (scalar) {
            power = add(field, power, power);
            ++counts.doublings;
        }
    }
    return answer;
}

Input read_target(Field &field, const char *path) {
    std::ifstream stream(path);
    require(bool(stream), "Q1478 target file missing");
    std::string magic, gx, gy, qx, qy, extra;
    unsigned n = 0;
    uint64_t order = 0;
    stream >> magic >> n >> order >> gx >> gy >> qx >> qy;
    require(bool(stream) && magic == "Q1477TARGET1" && n == 53 &&
                order == ORDER, "bad Q1478 target header");
    require(!(stream >> extra), "extra Q1478 target data");
    auto decode = [&](const std::string &x, const std::string &y) {
        U128 ox = parse_hex(x), oy = parse_hex(y);
        require((ox & ~field.mask) == 0 && (oy & ~field.mask) == 0,
                "Q1478 point coordinate overflow");
        return Point{field.to_poly(ox), field.to_poly(oy), false};
    };
    return {decode(gx, gy), decode(qx, qy)};
}

State make_combination(Field &field, const Input &input,
                       uint64_t a, uint64_t b, PointCount &counts) {
    Point left = scalar_mul(field, input.generator, a, counts);
    Point right = scalar_mul(field, input.target, b, counts);
    Point point = add(field, left, right);
    ++counts.additions;
    return {point, a, b};
}

unsigned partition(Field &field, const Point &point) {
    if (point.infinity) return 0;
    return unsigned(field.to_onb(point.x) & (PARTITIONS - 1));
}

bool distinguished(Field &field, const Point &point) {
    return !point.infinity &&
           (field.to_onb(point.x) & ((U128(1) << DISTINGUISHED_BITS) - 1)) == 0;
}

void step(Field &field, State &state, const std::array<State, PARTITIONS> &jump,
          PointCount &counts) {
    unsigned index = partition(field, state.point);
    state.point = add(field, state.point, jump[index].point);
    ++counts.additions;
    state.a = (state.a + jump[index].a) % ORDER;
    state.b = (state.b + jump[index].b) % ORDER;
}

void write_phase(const Phase &phase) {
    std::cout << "{\"wall_ns\":" << phase.ns << ",\"field_calls\":";
    write_counts(std::cout, phase.field);
    std::cout << ",\"point_additions\":" << phase.point.additions
              << ",\"point_doublings\":" << phase.point.doublings << '}';
}

void write_state(Field &field, const State &state) {
    std::cout << "{\"a\":" << state.a << ",\"b\":" << state.b
              << ",\"x_onb_hex\":\"" << hex(field.to_onb(state.point.x))
              << "\",\"y_onb_hex\":\"" << hex(field.to_onb(state.point.y))
              << "\"}";
}

}  // namespace

int main(int argc, char **argv) {
    try {
        require(argc == 3, "usage: rho_reference FIELD Q1477_TARGET");
        auto setup_start = Clock::now();
        Field field(argv[1]);
        require(field.n == 53, "Q1478 only admits N53");
        Input input = read_target(field, argv[2]);
        uint64_t setup_ns = elapsed_ns(setup_start);

        Phase validation, precompute, search, recovery;
        field.counts = {};
        auto online_start = Clock::now();
        auto phase_start = Clock::now();
        require(on_curve(field, input.generator) &&
                    on_curve(field, input.target), "Q1478 point off curve");
        require(scalar_mul(field, input.generator, ORDER,
                           validation.point).infinity,
                "Q1478 generator subgroup check failed");
        require(scalar_mul(field, input.target, ORDER,
                           validation.point).infinity,
                "Q1478 target subgroup check failed");
        validation.ns = elapsed_ns(phase_start);
        validation.field = field.counts;

        uint64_t random_state = 14780053;
        field.counts = {};
        phase_start = Clock::now();
        std::array<State, PARTITIONS> jump;
        for (unsigned i = 0; i < PARTITIONS; ++i) {
            uint64_t a = 1 + splitmix64(random_state) % (ORDER - 1);
            uint64_t b = 1 + splitmix64(random_state) % (ORDER - 1);
            jump[i] = make_combination(field, input, a, b,
                                       precompute.point);
            require(!jump[i].point.infinity, "Q1478 zero jump");
        }
        precompute.ns = elapsed_ns(phase_start);
        precompute.field = field.counts;

        std::unordered_map<PointKey, State, PointHash> table;
        std::vector<Walk> walks;
        uint64_t steps = 0, duplicates = 0, degenerate = 0, abandoned = 0;
        bool solved = false;
        Collision collision;
        field.counts = {};
        phase_start = Clock::now();
        while (steps < STEP_CAP && elapsed_ns(online_start) < WALL_CAP_NS) {
            uint64_t a = 1 + splitmix64(random_state) % (ORDER - 1);
            uint64_t b = 1 + splitmix64(random_state) % (ORDER - 1);
            State state = make_combination(field, input, a, b, search.point);
            if (state.point.infinity) continue;
            Walk walk;
            walk.start_a = a;
            walk.start_b = b;
            for (; walk.steps < MAX_WALK_STEPS && steps < STEP_CAP;) {
                step(field, state, jump, search.point);
                ++walk.steps;
                ++steps;
                if (!distinguished(field, state.point)) {
                    if ((steps & 4095ULL) == 0 &&
                        elapsed_ns(online_start) >= WALL_CAP_NS) break;
                    continue;
                }
                walk.status = "distinguished";
                walk.endpoint_x = state.point.x;
                walk.endpoint_y = state.point.y;
                PointKey key{uint64_t(state.point.x),
                             uint64_t(state.point.y)};
                auto [position, inserted] = table.emplace(key, state);
                if (!inserted) {
                    ++duplicates;
                    const State &old = position->second;
                    uint64_t numerator = (old.a + ORDER - state.a) % ORDER;
                    uint64_t denominator = (state.b + ORDER - old.b) % ORDER;
                    if (!denominator) {
                        ++degenerate;
                    } else {
                        collision.old_state = old;
                        collision.new_state = state;
                        collision.numerator = numerator;
                        collision.denominator = denominator;
                        collision.candidate = mul_mod(
                            numerator, pow_mod(denominator, ORDER - 2));
                        solved = true;
                        walk.status = "collision";
                    }
                }
                break;
            }
            if (walk.status.empty()) {
                walk.status = "abandoned_or_capped";
                ++abandoned;
            }
            walks.push_back(walk);
            if (solved) break;
        }
        search.ns = elapsed_ns(phase_start);
        search.field = field.counts;

        if (solved) {
            field.counts = {};
            phase_start = Clock::now();
            Point replay = scalar_mul(field, input.generator,
                                      collision.candidate, recovery.point);
            require(equal(replay, input.target),
                    "Q1478 collision scalar replay failed");
            recovery.ns = elapsed_ns(phase_start);
            recovery.field = field.counts;
        }
        uint64_t online_ns = elapsed_ns(online_start);
        uint64_t charged = validation.ns + precompute.ns + search.ns +
                           recovery.ns;
        require(charged <= online_ns, "Q1478 phase clocks exceed online");
        search.ns += online_ns - charged;
        std::cout << "{\"proposal_id\":\"Q1478\",\"status\":\""
                  << (solved ? "verified" : "censored")
                  << "\",\"setup_wall_ns_outside_online\":" << setup_ns
                  << ",\"online_wall_ns\":" << online_ns
                  << ",\"walk_steps\":" << steps
                  << ",\"walk_count\":" << walks.size()
                  << ",\"distinguished_points_stored\":" << table.size()
                  << ",\"duplicate_endpoints\":" << duplicates
                  << ",\"degenerate_collisions\":" << degenerate
                  << ",\"abandoned_walks\":" << abandoned
                  << ",\"worker_count\":1,\"partition_count\":16"
                  << ",\"distinguished_bits\":10,\"recovered_scalar\":";
        if (solved) std::cout << collision.candidate;
        else std::cout << "null";
        std::cout << ",\"phases\":{\"target_validation\":";
        write_phase(validation);
        std::cout << ",\"target_walk_precompute\":";
        write_phase(precompute);
        std::cout << ",\"target_walk_search\":";
        write_phase(search);
        std::cout << ",\"target_recovery_check\":";
        write_phase(recovery);
        std::cout << "},\"collision_certificate\":";
        if (solved) {
            std::cout << "{\"old\":";
            write_state(field, collision.old_state);
            std::cout << ",\"new\":";
            write_state(field, collision.new_state);
            std::cout << ",\"numerator\":" << collision.numerator
                      << ",\"denominator\":" << collision.denominator
                      << "}";
        } else std::cout << "null";
        std::cout << ",\"walks\":[";
        for (size_t i = 0; i < walks.size(); ++i) {
            if (i) std::cout << ',';
            const Walk &walk = walks[i];
            std::cout << "{\"start_a\":" << walk.start_a
                      << ",\"start_b\":" << walk.start_b
                      << ",\"steps\":" << walk.steps
                      << ",\"status\":\"" << walk.status << '\"';
            if (walk.status == "distinguished" ||
                walk.status == "collision")
                std::cout << ",\"endpoint_x_onb_hex\":\""
                          << hex(field.to_onb(walk.endpoint_x))
                          << "\",\"endpoint_y_onb_hex\":\""
                          << hex(field.to_onb(walk.endpoint_y)) << '\"';
            std::cout << '}';
        }
        std::cout << "]}" << std::endl;
        return solved ? 0 : 10;
    } catch (const std::exception &error) {
        std::cerr << "Q1478 rho error: " << error.what() << '\n';
        return 2;
    }
}
