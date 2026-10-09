// Exact N41 D2+D3 group-sum census and fixed-Q first-two-pair probes.
#define main unused_frozen_helper_main
#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
#undef main

#include <algorithm>
#include <array>
#include <chrono>
#include <fstream>
#include <limits>
#include <string>
#include <unordered_map>
#include <vector>

struct Seed {
    Point point;
    uint16_t column;
    uint8_t mask, sign;
};
struct PairState {
    Point sum;
    uint8_t a, b;
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

static U128 pack(Point point) {
    if (point.infinity) return U128(1) << 82;
    if (point.x > MASK || point.y > MASK) throw std::runtime_error("bad point encoding");
    return (U128(point.x) << 41) | point.y;
}

static bool distinct(const std::array<uint16_t, 8>& columns) {
    for (int i = 0; i < 8; ++i)
        for (int j = i+1; j < 8; ++j)
            if (columns[i] == columns[j]) return false;
    return true;
}

static std::vector<PairState> pairs(const std::vector<Seed>& domain) {
    std::vector<PairState> result;
    for (int i = 0; i < 64; ++i)
        for (int j = i+1; j < 64; ++j)
            if (domain[i].column != domain[j].column)
                result.push_back({add(domain[i].point, domain[j].point),
                                  uint8_t(i), uint8_t(j)});
    if (result.size() != 1956) throw std::runtime_error("pair-domain size mismatch");
    return result;
}

static void write_row(std::ostream& out,
                      const std::array<std::vector<Seed>, 4>& seeds,
                      const std::array<PairState, 4>& chosen) {
    out << "[";
    for (int pair = 0; pair < 4; ++pair)
        for (int side = 0; side < 2; ++side) {
            if (pair || side) out << ",";
            const Seed& seed = seeds[pair][side ? chosen[pair].b : chosen[pair].a];
            out << "{\"point\":"; write_point(out, seed.point);
            out << ",\"column\":" << seed.column
                << ",\"mask\":" << int(seed.mask)
                << ",\"sign\":" << int(seed.sign) << "}";
        }
    out << "]";
}

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: census input.txt result.json");
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("missing input");
        uint64_t qx, qy, subgroup_order;
        int summands;
        input >> qx >> qy >> subgroup_order >> summands;
        if (!input || qx != 1458168294740ULL || qy != 1672312028033ULL ||
            subgroup_order != 549756390943ULL || summands != 8)
            throw std::runtime_error("wrong frozen N41 header");
        Point target = finite(qx, qy);
        if (!on_curve(target)) throw std::runtime_error("off-curve target");
        std::array<std::vector<Seed>, 4> seeds;
        for (int slot = 0; slot < 8; ++slot) {
            int count;
            input >> count;
            if (!input || count != 64) throw std::runtime_error("wrong slot size");
            for (int index = 0; index < count; ++index) {
                uint64_t x, y;
                int column, mask, branch, sign;
                input >> x >> y >> column >> mask >> branch >> sign;
                if (!input || !on_curve(finite(x,y)) || column < 0 || column >= 26 ||
                    mask <= 0 || mask >= 64 || branch != 0 || sign < 0 || sign > 1)
                    throw std::runtime_error("bad seed");
                Seed seed{finite(x,y), uint16_t(column), uint8_t(mask), uint8_t(sign)};
                if (slot % 2 == 0) seeds[slot/2].push_back(seed);
                else {
                    const Seed& prior = seeds[slot/2][index];
                    if (!(prior.point == seed.point) || prior.column != seed.column ||
                        prior.mask != seed.mask || prior.sign != seed.sign)
                        throw std::runtime_error("duplicated slots differ");
                }
            }
        }
        std::string extra;
        if (input >> extra) throw std::runtime_error("trailing input");

        const auto setup_start = std::chrono::steady_clock::now();
        std::array<std::vector<PairState>, 4> domains;
        for (int i = 0; i < 4; ++i) domains[i] = pairs(seeds[i]);
        std::vector<U128> completion;
        completion.reserve(domains[2].size() * domains[3].size());
        uint64_t identity_raw_combinations = 0;
        for (const auto& c : domains[2])
            for (const auto& d : domains[3]) {
                Point total = add(c.sum, d.sum);
                identity_raw_combinations += total.infinity;
                completion.push_back(pack(total));
            }
        std::sort(completion.begin(), completion.end());
        const size_t raw_count = completion.size();
        completion.erase(std::unique(completion.begin(), completion.end()), completion.end());
        const bool identity_present = std::binary_search(
            completion.begin(), completion.end(), U128(1) << 82);
        std::unordered_map<Point, std::vector<uint16_t>, PointHash> last;
        for (uint16_t i = 0; i < domains[3].size(); ++i)
            last[domains[3][i].sum].push_back(i);
        const uint64_t setup_ns = elapsed_ns(setup_start);
        if (peak_rss_bytes() >= 4ULL*1024*1024*1024)
            throw std::runtime_error("setup memory cap exceeded");

        const auto query_start = std::chrono::steady_clock::now();
        uint64_t prefixes_seen = 0, admissible = 0, prefix_column_rejects = 0;
        uint64_t sumset_hits = 0, first_hit_index = 0, first_valid_index = 0;
        uint64_t exact_pair_witnesses = 0, complete_rows = 0, full_column_rejects = 0;
        bool have_row = false, time_cap = false, memory_cap = false;
        std::array<PairState, 4> first_row{};
        for (const auto& a : domains[0]) {
            const Point after_a = add(target, neg(a.sum));
            for (const auto& b : domains[1]) {
                ++prefixes_seen;
                std::array<uint16_t, 8> columns{
                    seeds[0][a.a].column, seeds[0][a.b].column,
                    seeds[1][b.a].column, seeds[1][b.b].column,
                    65535, 65534, 65533, 65532};
                if (!distinct(columns)) { ++prefix_column_rejects; continue; }
                ++admissible;
                Point residual = add(after_a, neg(b.sum));
                if ((admissible & 16383) == 0) {
                    time_cap = elapsed_ns(query_start) >= 120000000000ULL;
                    memory_cap = peak_rss_bytes() >= 4ULL*1024*1024*1024;
                    if (time_cap || memory_cap) break;
                }
                if (!std::binary_search(completion.begin(), completion.end(), pack(residual)))
                    continue;
                ++sumset_hits;
                if (!first_hit_index) first_hit_index = admissible;
                bool group_witness = false;
                for (const auto& c : domains[2]) {
                    Point need = add(residual, neg(c.sum));
                    auto it = last.find(need);
                    if (it == last.end()) continue;
                    group_witness = true;
                    for (uint16_t index : it->second) {
                        ++exact_pair_witnesses;
                        const auto& d = domains[3][index];
                        columns[4] = seeds[2][c.a].column;
                        columns[5] = seeds[2][c.b].column;
                        columns[6] = seeds[3][d.a].column;
                        columns[7] = seeds[3][d.b].column;
                        if (!distinct(columns)) { ++full_column_rejects; continue; }
                        ++complete_rows;
                        if (!have_row) {
                            Point check = add(add(add(a.sum,b.sum),c.sum),d.sum);
                            if (!(check == target))
                                throw std::runtime_error("eight-point sum mismatch");
                            first_row = {a,b,c,d};
                            first_valid_index = admissible;
                            have_row = true;
                        }
                    }
                }
                if (!group_witness) throw std::runtime_error("sumset hit lacks witness");
            }
            if (time_cap || memory_cap) break;
        }
        const uint64_t query_ns = elapsed_ns(query_start);
        const char* status = time_cap ? "QUERY_TIME_CAP" : memory_cap ?
            "MEMORY_CAP" : "COMPLETE_CENSUS";
        std::ofstream out(argv[2]);
        if (!out) throw std::runtime_error("cannot open output");
        out << "{\"kind\":\"n41_exact_two_pair_sumset_census\","
            << "\"status\":\"" << status << "\","
            << "\"proposal_id\":\"Q20261008220700\","
            << "\"candidate_id\":null,\"run_id\":null,"
            << "\"target\":[" << qx << "," << qy << "],"
            << "\"subgroup_order\":" << subgroup_order
            << ",\"pair_list_sizes\":[" << domains[0].size() << ","
            << domains[1].size() << "," << domains[2].size() << ","
            << domains[3].size() << "]"
            << ",\"raw_completion_combinations\":" << raw_count
            << ",\"distinct_completion_points\":" << completion.size()
            << ",\"identity_raw_combinations\":" << identity_raw_combinations
            << ",\"identity_in_completion_set\":" << (identity_present ? "true" : "false")
            << ",\"setup_ns\":" << setup_ns << ",\"query_ns\":" << query_ns
            << ",\"prefixes_seen\":" << prefixes_seen
            << ",\"admissible_prefixes\":" << admissible
            << ",\"prefix_column_rejects\":" << prefix_column_rejects
            << ",\"sumset_hits\":" << sumset_hits
            << ",\"first_hit_index\":" << first_hit_index
            << ",\"first_valid_index\":" << first_valid_index
            << ",\"exact_pair_witnesses\":" << exact_pair_witnesses
            << ",\"complete_rows\":" << complete_rows
            << ",\"full_column_rejects\":" << full_column_rejects
            << ",\"peak_rss_bytes\":" << peak_rss_bytes()
            << ",\"first_row\":";
        if (have_row) write_row(out, seeds, first_row); else out << "null";
        out << "}\n";
        std::cout << status << " distinct=" << completion.size()
                  << " hits=" << sumset_hits << " rows=" << complete_rows << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
