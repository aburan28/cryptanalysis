// Four zero-sum source triples joined on one public N41 subgroup point.
#define main unused_frozen_helper_main
#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
#undef main

#include <algorithm>
#include <array>
#include <chrono>
#include <fstream>
#include <vector>

struct Seed {
    Point point;
    uint16_t column;
    uint8_t mask, sign;
};
struct Triple {
    Point sum;
    std::array<uint16_t, 3> seed_indices;
    std::array<uint16_t, 3> columns;
};
struct Entry {
    Point sum;
    uint16_t first, second;
};
struct Counters {
    uint64_t triple_column_rejects = 0;
    uint64_t left_column_rejects = 0;
    uint64_t right_column_rejects = 0;
    uint64_t right_probes = 0;
    uint64_t group_hits = 0;
    uint64_t cross_column_rejects = 0;
};

static uint64_t elapsed_ns(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - start).count();
}

static uint64_t peak_rss_bytes() {
    rusage usage{};
    getrusage(RUSAGE_SELF, &usage);
#ifdef __APPLE__
    return uint64_t(usage.ru_maxrss);
#else
    return uint64_t(usage.ru_maxrss) * 1024;
#endif
}

static bool point_less(const Point& a, const Point& b) {
    if (a.infinity != b.infinity) return a.infinity < b.infinity;
    if (a.x != b.x) return a.x < b.x;
    return a.y < b.y;
}

template <size_t N>
static bool distinct(const std::array<uint16_t, N>& values) {
    for (size_t i = 0; i < N; ++i)
        for (size_t j = i + 1; j < N; ++j)
            if (values[i] == values[j]) return false;
    return true;
}

static std::vector<Triple> make_triples(const std::vector<Seed>& seeds,
                                        Counters& counters) {
    std::array<std::array<int, 2>, 128> lookup;
    for (auto& row : lookup) row.fill(-1);
    for (size_t i = 0; i < seeds.size(); ++i) {
        const auto& value = seeds[i];
        if (lookup[value.mask][value.sign] != -1)
            throw std::runtime_error("duplicate mask/sign in source block");
        lookup[value.mask][value.sign] = int(i);
    }
    std::vector<Triple> result;
    unsigned shapes = 0;
    const uint64_t rejects_before = counters.triple_column_rejects;
    for (int a = 1; a < 128; ++a) {
        if (lookup[a][0] < 0) continue;
        for (int b = a + 1; b < 128; ++b) {
            const int c = a ^ b;
            if (lookup[b][0] < 0 || c <= b || lookup[c][0] < 0) continue;
            ++shapes;
            for (int branch = 0; branch < 8; ++branch) {
                std::array<uint16_t, 3> indices{
                    uint16_t(lookup[a][branch & 1]),
                    uint16_t(lookup[b][(branch >> 1) & 1]),
                    uint16_t(lookup[c][(branch >> 2) & 1])};
                std::array<uint16_t, 3> columns{
                    seeds[indices[0]].column, seeds[indices[1]].column,
                    seeds[indices[2]].column};
                if (!distinct(columns)) {
                    ++counters.triple_column_rejects;
                    continue;
                }
                Point total = add(add(seeds[indices[0]].point,
                                      seeds[indices[1]].point),
                                  seeds[indices[2]].point);
                result.push_back({total, indices, columns});
            }
        }
    }
    if (shapes != 317 || result.size() +
            (counters.triple_column_rejects - rejects_before) != shapes * 8ULL)
        throw std::runtime_error("zero-sum triple census mismatch");
    return result;
}

static bool cross_distinct(const Triple& a, const Triple& b) {
    std::array<uint16_t, 6> columns{
        a.columns[0], a.columns[1], a.columns[2],
        b.columns[0], b.columns[1], b.columns[2]};
    return distinct(columns);
}

static bool all_distinct(const std::array<Triple, 4>& rows) {
    std::array<uint16_t, 12> columns{};
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < 3; ++j) columns[3*i+j] = rows[i].columns[j];
    return distinct(columns);
}

static void write_row(std::ostream& out,
                      const std::array<std::vector<Seed>, 4>& seeds,
                      const std::array<Triple, 4>& triples,
                      const std::array<int, 4>& rotations) {
    out << "[";
    for (int block = 0; block < 4; ++block) {
        for (int side = 0; side < 3; ++side) {
            if (block || side) out << ",";
            const auto& leaf = seeds[block][triples[block].seed_indices[side]];
            out << "{\"rotation\":" << rotations[block]
                << ",\"mask\":" << int(leaf.mask)
                << ",\"sign\":" << int(leaf.sign)
                << ",\"column\":" << leaf.column << ",\"point\":";
            write_point(out, leaf.point);
            out << "}";
        }
    }
    out << "]";
}

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: join input.txt output.json");
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("input open failed");
        uint64_t qx, qy, order;
        int block_count;
        input >> qx >> qy >> order >> block_count;
        if (!input || order != 549756390943ULL || block_count != 4)
            throw std::runtime_error("bad N41 header");
        const Point target = finite(qx, qy);
        if (!on_curve(target)) throw std::runtime_error("target off curve");
        std::array<std::vector<Seed>, 4> seeds;
        std::array<int, 4> rotations{};
        for (int block = 0; block < 4; ++block) {
            int count;
            input >> rotations[block] >> count;
            if (!input || rotations[block] != 10 * block || count != 126)
                throw std::runtime_error("bad source block header");
            for (int i = 0; i < count; ++i) {
                int mask, sign, column;
                uint64_t x, y;
                input >> mask >> sign >> column >> x >> y;
                if (!input || mask <= 0 || mask >= 128 || sign < 0 || sign > 1 ||
                    column < 0 || column >= 128 || !on_curve(finite(x, y)))
                    throw std::runtime_error("bad source leaf");
                seeds[block].push_back({finite(x, y), uint16_t(column),
                                        uint8_t(mask), uint8_t(sign)});
            }
        }
        std::string extra;
        if (input >> extra) throw std::runtime_error("trailing source input");
        const auto setup_started = std::chrono::steady_clock::now();
        Counters counters;
        std::array<std::vector<Triple>, 4> triples;
        for (int i = 0; i < 4; ++i) triples[i] = make_triples(seeds[i], counters);
        const uint64_t triple_build_ns = elapsed_ns(setup_started);
        const auto left_started = std::chrono::steady_clock::now();
        std::vector<Entry> left;
        left.reserve(triples[0].size() * triples[1].size());
        bool setup_cap = false;
        for (size_t i = 0; i < triples[0].size(); ++i) {
            const auto& a = triples[0][i];
            for (size_t j = 0; j < triples[1].size(); ++j) {
                const auto& b = triples[1][j];
                if (!cross_distinct(a, b)) {
                    ++counters.left_column_rejects;
                    continue;
                }
                left.push_back({add(a.sum, b.sum), uint16_t(i), uint16_t(j)});
            }
            if ((i & 31) == 0 &&
                (elapsed_ns(setup_started) > 300000000000ULL ||
                 peak_rss_bytes() >= 4ULL*1024*1024*1024)) {
                setup_cap = true;
                break;
            }
        }
        const uint64_t left_build_ns = elapsed_ns(left_started);
        uint64_t left_sort_ns = 0, online_ns = 0, query_ns = 0;
        bool found = false, online_cap = false;
        std::array<Triple, 4> witness{};
        if (!setup_cap) {
            const auto sort_started = std::chrono::steady_clock::now();
            std::sort(left.begin(), left.end(),
                      [](const Entry& a, const Entry& b) {
                          return point_less(a.sum, b.sum);
                      });
            left_sort_ns = elapsed_ns(sort_started);
            if (elapsed_ns(setup_started) > 300000000000ULL ||
                peak_rss_bytes() >= 4ULL*1024*1024*1024) setup_cap = true;
        }
        if (!setup_cap) {
            const auto online_started = std::chrono::steady_clock::now();
            const auto query_started = online_started;
            for (const auto& c : triples[2]) {
                for (const auto& d : triples[3]) {
                    if (!cross_distinct(c, d)) {
                        ++counters.right_column_rejects;
                        continue;
                    }
                    ++counters.right_probes;
                    Point needed = add(target, neg(add(c.sum, d.sum)));
                    auto position = std::lower_bound(
                        left.begin(), left.end(), needed,
                        [](const Entry& entry, const Point& point) {
                            return point_less(entry.sum, point);
                        });
                    while (position != left.end() && position->sum == needed) {
                        ++counters.group_hits;
                        std::array<Triple, 4> candidate{
                            triples[0][position->first],
                            triples[1][position->second], c, d};
                        if (all_distinct(candidate)) {
                            Point check{};
                            for (const auto& block : candidate)
                                check = add(check, block.sum);
                            if (!(check == target))
                                throw std::runtime_error("group replay mismatch");
                            witness = candidate;
                            found = true;
                            break;
                        }
                        ++counters.cross_column_rejects;
                        ++position;
                    }
                    if (found) break;
                    if ((counters.right_probes & 4095) == 0 &&
                        (elapsed_ns(online_started) >= 120000000000ULL ||
                         peak_rss_bytes() >= 4ULL*1024*1024*1024)) {
                        online_cap = true;
                        break;
                    }
                }
                if (found || online_cap) break;
            }
            query_ns = elapsed_ns(query_started);
            online_ns = elapsed_ns(online_started);
        }
        const char* status = found ? "VERIFIED_RAW_ROW" : setup_cap ?
            "SETUP_CAP" : online_cap ? "ONLINE_CAP" : "EXHAUSTED_NO_ROW";
        std::ofstream out(argv[2]);
        if (!out) throw std::runtime_error("output open failed");
        out << "{\"status\":\"" << status << "\",\"candidate_id\":null,"
            << "\"run_id\":null,\"target\":";
        write_point(out, target);
        out << ",\"source_states\":[";
        for (int i = 0; i < 4; ++i) {
            if (i) out << ",";
            out << triples[i].size();
        }
        out << "],\"triple_column_rejects\":" << counters.triple_column_rejects
            << ",\"left_column_rejects\":" << counters.left_column_rejects
            << ",\"right_column_rejects\":" << counters.right_column_rejects
            << ",\"left_entries\":" << left.size()
            << ",\"right_probes\":" << counters.right_probes
            << ",\"group_hits\":" << counters.group_hits
            << ",\"cross_column_rejects\":" << counters.cross_column_rejects
            << ",\"triple_build_ns\":" << triple_build_ns
            << ",\"left_build_ns\":" << left_build_ns
            << ",\"left_sort_ns\":" << left_sort_ns
            << ",\"setup_ns\":" << triple_build_ns+left_build_ns+left_sort_ns
            << ",\"query_ns\":" << query_ns
            << ",\"online_overhead_ns\":" << online_ns-query_ns
            << ",\"online_ns\":" << online_ns
            << ",\"peak_rss_bytes\":" << peak_rss_bytes()
            << ",\"row\":";
        if (found) write_row(out, seeds, witness, rotations);
        else out << "null";
        out << "}\n";
        out.close();
        if (!out) throw std::runtime_error("output write failed");
        std::cout << status << " left=" << left.size()
                  << " right=" << counters.right_probes
                  << " online_s=" << online_ns / 1e9 << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
