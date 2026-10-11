// Q1477: one-target online recovery with Q1473's verified N53 pair table.
// Inherit Q1468's point arithmetic and reproduce Q1473's table algorithm.
#define main q1468_unused_main
#include "../q1468_n53_pair_oracle/pair_oracle.cpp"
#undef main

#include <array>
#include <limits>

namespace {

std::vector<Entry> build_table(Field &field, const Base &base,
                               uint64_t wall_cap_ns) {
    constexpr size_t expected = 3651700;
    auto start = Clock::now();
    field.counts = {};
    std::vector<Entry> table;
    table.reserve(expected);
    for (unsigned i = 0; i < base.points.size(); ++i) {
        std::vector<Point> other;
        std::vector<unsigned> indices;
        for (unsigned j = i + 1; j < base.points.size(); ++j) {
            if (base.columns[i] == base.columns[j]) continue;
            other.push_back(base.points[j]);
            indices.push_back(j);
        }
        auto sums = batch_add_fixed(field, base.points[i], other);
        for (size_t k = 0; k < sums.size(); ++k) {
            require(!sums[k].infinity, "cross-column pair is identity");
            table.push_back(encode(sums[k], pair_code(i, indices[k])));
        }
        if ((i & 63U) == 0 && elapsed_ns(start) > wall_cap_ns)
            throw std::runtime_error("Q1477 table wall cap reached");
    }
    require(table.size() == expected, "incomplete Q1477 pair table");
    std::sort(table.begin(), table.end(), less_key);
    size_t duplicates = 0;
    for (size_t i = 1; i < table.size(); ++i)
        duplicates += same_key(table[i - 1], table[i]);
    std::cout << "{\"mode\":\"setup\",\"pair_table_entries\":"
              << table.size() << ",\"duplicate_pair_sums\":" << duplicates
              << ",\"table_wall_ns\":" << elapsed_ns(start)
              << ",\"table_field_calls\":";
    write_counts(std::cout, field.counts);
    std::cout << "}" << std::endl;
    return table;
}

struct PointCount {
    uint64_t additions = 0, doublings = 0;
};

struct Phase {
    uint64_t ns = 0;
    q1420::Counts field{};
    PointCount point{};
};

struct Attempt {
    unsigned index = 0;
    uint64_t shift = 0;
    std::string status;
    uint64_t examined = 0, hits = 0, rejected_columns = 0;
    std::array<unsigned, 4> witness{};
    bool has_witness = false;
    std::array<Phase, 5> phases{};
    uint64_t queried_x_onb = 0, queried_y_onb = 0;
};

constexpr size_t QUERY_GEN = 0, PDP = 1, RELATION_CHECK = 2;
constexpr size_t DESCENT = 3, RECOVERY_CHECK = 4;

Point scalar_mul(Field &field, const Point &base, uint64_t scalar,
                 PointCount &count) {
    Point answer;
    Point power = base;
    while (scalar) {
        if (scalar & 1) {
            answer = add(field, answer, power);
            ++count.additions;
        }
        scalar >>= 1;
        if (scalar) {
            power = add(field, power, power);
            ++count.doublings;
        }
    }
    return answer;
}

uint64_t splitmix64(uint64_t &state) {
    state += UINT64_C(0x9e3779b97f4a7c15);
    uint64_t value = state;
    value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
}

struct TargetInput {
    uint64_t order = 0;
    Point generator, public_target;
};

TargetInput read_q1477_target(Field &field, const char *path) {
    std::ifstream input(path);
    require(bool(input), "Q1477 target file missing");
    std::string magic, gx, gy, qx, qy, extra;
    unsigned n = 0;
    uint64_t order = 0;
    input >> magic >> n >> order >> gx >> gy >> qx >> qy;
    require(bool(input) && magic == "Q1477TARGET1" && n == 53 &&
                order == 21044858204113ULL, "bad Q1477 target header");
    require(!(input >> extra), "extra Q1477 target data");
    auto decode_point = [&](const std::string &x, const std::string &y) {
        U128 ox = parse_hex(x), oy = parse_hex(y);
        require((ox & ~field.mask) == 0 && (oy & ~field.mask) == 0,
                "Q1477 point coordinate overflow");
        Point point{field.to_poly(ox), field.to_poly(oy), false};
        require(on_curve(field, point), "Q1477 point is off curve");
        return point;
    };
    TargetInput result{order, decode_point(gx, gy), decode_point(qx, qy)};
    PointCount ignored;
    require(scalar_mul(field, result.generator, order, ignored).infinity,
            "Q1477 generator subgroup check failed");
    require(scalar_mul(field, result.public_target, order, ignored).infinity,
            "Q1477 target subgroup check failed");
    return result;
}

std::vector<uint64_t> read_logs(const char *path, const Base &base,
                                uint64_t order) {
    std::ifstream input(path);
    require(bool(input), "Q1477 log lookup missing");
    std::string magic, extra;
    unsigned n = 0, size = 0, columns = 0;
    uint64_t file_order = 0;
    input >> magic >> n >> size >> columns >> file_order;
    require(bool(input) && magic == "Q1477LOGS1" && n == 53 &&
                size == 2756 && columns == 26 && file_order == order,
            "bad Q1477 log header");
    std::vector<uint64_t> answer;
    answer.reserve(size);
    for (unsigned i = 0; i < size; ++i) {
        unsigned index = 0, column = 0;
        uint64_t value = 0;
        input >> index >> column >> value;
        require(bool(input) && index == i && column == base.columns[i] &&
                    value < order, "invalid Q1477 log row");
        answer.push_back(value);
    }
    require(!(input >> extra), "extra Q1477 log rows");
    return answer;
}

void query_pair_table(Field &field, const Base &base,
                      const std::vector<Entry> &table, const Point &target,
                      uint64_t cap_ns, Attempt &report) {
    auto start = Clock::now();
    constexpr size_t batch_size = 4096;
    for (size_t offset = 0; offset < table.size(); offset += batch_size) {
        if (elapsed_ns(start) > cap_ns) {
            report.status = "censored";
            return;
        }
        size_t length = std::min(batch_size, table.size() - offset);
        std::vector<Point> negatives;
        negatives.reserve(length);
        for (size_t k = 0; k < length; ++k)
            negatives.push_back(neg(decode(table[offset + k])));
        auto complements = batch_add_fixed(field, target, negatives);
        report.examined += length;
        report.phases[PDP].point.additions += length;
        for (size_t k = 0; k < length; ++k) {
            if (complements[k].infinity) continue;
            Entry key = encode(complements[k]);
            auto hit = std::lower_bound(table.begin(), table.end(), key,
                                        less_key);
            for (; hit != table.end() && same_key(*hit, key); ++hit) {
                ++report.hits;
                unsigned a = first(table[offset + k].pair);
                unsigned b = second(table[offset + k].pair);
                unsigned c = first(hit->pair);
                unsigned d = second(hit->pair);
                unsigned columns[4] = {base.columns[a], base.columns[b],
                                       base.columns[c], base.columns[d]};
                bool distinct = true;
                for (int x = 0; x < 4; ++x)
                    for (int y = x + 1; y < 4; ++y)
                        distinct &= columns[x] != columns[y];
                if (!distinct) {
                    ++report.rejected_columns;
                    continue;
                }
                report.witness = {a, b, c, d};
                report.has_witness = true;
                report.status = "found";
                return;
            }
        }
    }
    report.status = "absent";
}

void write_phase(const Phase &phase) {
    std::cout << "{\"wall_ns\":" << phase.ns
              << ",\"field_calls\":";
    write_counts(std::cout, phase.field);
    std::cout << ",\"point_additions\":" << phase.point.additions
              << ",\"point_doublings\":" << phase.point.doublings << '}';
}

void emit_attempt(const Attempt &attempt) {
    std::cout << "{\"index\":" << attempt.index
              << ",\"shift_scalar\":" << attempt.shift
              << ",\"queried_x_onb_hex\":\""
              << std::hex << attempt.queried_x_onb << std::dec
              << "\",\"queried_y_onb_hex\":\""
              << std::hex << attempt.queried_y_onb << std::dec
              << "\",\"status\":\"" << attempt.status
              << "\",\"pair_sums_examined\":" << attempt.examined
              << ",\"complement_hits\":" << attempt.hits
              << ",\"rejected_shared_columns\":" <<
              attempt.rejected_columns << ",\"witness_indices\":";
    if (attempt.has_witness) {
        std::cout << '[' << attempt.witness[0] << ',' << attempt.witness[1]
                  << ',' << attempt.witness[2] << ',' << attempt.witness[3]
                  << ']';
    } else std::cout << "null";
    const char *names[5] = {"target_query_generation", "target_PDP",
                            "target_relation_check", "target_descent",
                            "target_recovery_check"};
    std::cout << ",\"phases\":{";
    for (size_t p = 0; p < 5; ++p) {
        if (p) std::cout << ',';
        std::cout << '"' << names[p] << "\":";
        write_phase(attempt.phases[p]);
    }
    std::cout << "}}";
}

}  // namespace

int main(int argc, char **argv) {
    try {
        require(argc == 7,
                "usage: online_oracle FIELD BASE LOGS TARGET QUERY_CAP_S "
                "ONLINE_CAP_S");
        auto startup = Clock::now();
        Field field(argv[1]);
        require(field.n == 53, "Q1477 only admits N53");
        Base base = read_base(field, argv[2]);
        TargetInput input = read_q1477_target(field, argv[4]);
        auto logs = read_logs(argv[3], base, input.order);
        const uint64_t query_cap_s = std::stoull(argv[5]);
        const uint64_t online_cap_s = std::stoull(argv[6]);
        require(query_cap_s == 30 && online_cap_s == 1200,
                "Q1477 caps differ from frozen design");
        auto table = build_table(field, base, 1200000000000ULL);
        const uint64_t setup_ns = elapsed_ns(startup);
        std::vector<Attempt> attempts;
        attempts.reserve(256);
        uint64_t shift_state = 14770054;
        uint64_t recovered = 0;
        bool solved = false;
        auto online_start = Clock::now();
        for (unsigned i = 0; i < 256; ++i) {
            if (elapsed_ns(online_start) > online_cap_s * 1000000000ULL)
                break;
            Attempt attempt;
            attempt.index = i;
            field.counts = {};
            auto phase_start = Clock::now();
            Point query = input.public_target;
            if (i) {
                attempt.shift = 1 + splitmix64(shift_state) % (input.order - 1);
                Point shifted = scalar_mul(field, input.generator,
                                           attempt.shift,
                                           attempt.phases[QUERY_GEN].point);
                query = add(field, query, shifted);
                ++attempt.phases[QUERY_GEN].point.additions;
            }
            require(!query.infinity, "shifted target is identity");
            attempt.queried_x_onb = uint64_t(field.to_onb(query.x));
            attempt.queried_y_onb = uint64_t(field.to_onb(query.y));
            attempt.phases[QUERY_GEN].ns = elapsed_ns(phase_start);
            attempt.phases[QUERY_GEN].field = field.counts;

            field.counts = {};
            phase_start = Clock::now();
            query_pair_table(field, base, table, query,
                             query_cap_s * 1000000000ULL, attempt);
            attempt.phases[PDP].ns = elapsed_ns(phase_start);
            attempt.phases[PDP].field = field.counts;
            if (attempt.has_witness) {
                field.counts = {};
                phase_start = Clock::now();
                Point sum;
                for (unsigned index : attempt.witness) {
                    sum = add(field, sum, base.points[index]);
                    ++attempt.phases[RELATION_CHECK].point.additions;
                }
                require(equal(sum, query), "Q1477 witness replay mismatch");
                attempt.phases[RELATION_CHECK].ns = elapsed_ns(phase_start);
                attempt.phases[RELATION_CHECK].field = field.counts;

                phase_start = Clock::now();
                uint64_t shifted_log = 0;
                for (unsigned index : attempt.witness)
                    shifted_log = (shifted_log + logs[index]) % input.order;
                recovered = (shifted_log + input.order - attempt.shift) %
                            input.order;
                attempt.phases[DESCENT].ns = elapsed_ns(phase_start);

                field.counts = {};
                phase_start = Clock::now();
                PointCount replay_count;
                Point replay = scalar_mul(field, input.generator, recovered,
                                          replay_count);
                require(equal(replay, input.public_target),
                        "Q1477 recovered scalar replay mismatch");
                attempt.phases[RECOVERY_CHECK].ns = elapsed_ns(phase_start);
                attempt.phases[RECOVERY_CHECK].field = field.counts;
                attempt.phases[RECOVERY_CHECK].point = replay_count;
                solved = true;
            }
            attempts.push_back(attempt);
            if (solved) break;
        }
        uint64_t online_ns = elapsed_ns(online_start);
        uint64_t charged = 0;
        for (const auto &attempt : attempts)
            for (const auto &phase : attempt.phases) charged += phase.ns;
        require(!attempts.empty() && charged <= online_ns,
                "Q1477 phase clocks exceed online interval");
        // Loop/control overhead is target-dependent and belongs to query
        // generation; it must not disappear from the charged total.
        attempts.front().phases[QUERY_GEN].ns += online_ns - charged;
        size_t found = 0, absent = 0, censored = 0;
        for (const auto &attempt : attempts) {
            found += attempt.status == "found";
            absent += attempt.status == "absent";
            censored += attempt.status == "censored";
        }
        std::cout << "{\"mode\":\"online\",\"proposal_id\":\"Q1477\""
                  << ",\"status\":\"" << (solved ? "verified" : "unsolved")
                  << "\",\"setup_wall_ns_outside_online\":" << setup_ns
                  << ",\"online_wall_ns\":" << online_ns
                  << ",\"attempt_count\":" << attempts.size()
                  << ",\"found\":" << found << ",\"absent\":" << absent
                  << ",\"censored\":" << censored
                  << ",\"recovered_scalar\":";
        if (solved) std::cout << recovered;
        else std::cout << "null";
        std::cout << ",\"attempts\":[";
        for (size_t i = 0; i < attempts.size(); ++i) {
            if (i) std::cout << ',';
            emit_attempt(attempts[i]);
        }
        std::cout << "]}" << std::endl;
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "Q1477 online oracle error: " << error.what() << '\n';
        return 1;
    }
}
