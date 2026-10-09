// Exact N41 two-free-pair completion using batched affine inversions.
#define main unused_frozen_helper_main
#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
#undef main

#include <algorithm>
#include <array>
#include <chrono>
#include <fstream>
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
struct Stats {
    uint64_t residuals = 0, x_hits = 0, exact_group_hits = 0;
    uint64_t prefix_column_rejects = 0, final_column_rejects = 0;
    uint64_t scanned_b = 0, nonzero_denominators = 0;
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

static bool distinct(const std::array<uint16_t, 8>& c) {
    for (int i = 0; i < 8; ++i)
        for (int j = i + 1; j < 8; ++j)
            if (c[i] == c[j]) return false;
    return true;
}

static std::vector<PairState> make_pairs(const std::vector<Seed>& domain) {
    std::vector<PairState> out;
    for (int i = 0; i < 64; ++i)
        for (int j = i + 1; j < 64; ++j)
            if (domain[i].column != domain[j].column) {
                Point sum = add(domain[i].point, domain[j].point);
                if (sum.infinity) throw std::runtime_error("unexpected identity pair");
                out.push_back({sum, uint8_t(i), uint8_t(j)});
            }
    if (out.size() != 1956) throw std::runtime_error("wrong pair count");
    return out;
}

struct Filter {
    const std::array<std::vector<Seed>, 4>& seeds;
    const std::array<std::vector<PairState>, 4>& pairs;
    std::unordered_map<uint64_t, std::vector<uint16_t>> x2;
    std::unordered_map<Point, std::vector<uint16_t>, PointHash> exact2, exact3;
    std::vector<uint16_t> b3_representatives;
    std::vector<uint64_t> prefix, inverses, denominators;
    std::vector<uint8_t> exceptional;

    Filter(const std::array<std::vector<Seed>, 4>& seeds_,
           const std::array<std::vector<PairState>, 4>& pairs_)
        : seeds(seeds_), pairs(pairs_) {
        std::unordered_map<uint64_t, uint16_t> first_b3;
        for (uint16_t i = 0; i < pairs[2].size(); ++i) {
            x2[pairs[2][i].sum.x].push_back(i);
            exact2[pairs[2][i].sum].push_back(i);
            exact3[pairs[3][i].sum].push_back(i);
            first_b3.emplace(pairs[3][i].sum.x, i);
        }
        if (x2.size() != 978 || first_b3.size() != 978 ||
            exact2.size() != 1956 || exact3.size() != 1956)
            throw std::runtime_error("pair-sign symmetry/count failure");
        for (const auto& entry : first_b3) b3_representatives.push_back(entry.second);
        std::sort(b3_representatives.begin(), b3_representatives.end());
        const size_t count = b3_representatives.size();
        prefix.resize(count); inverses.resize(count);
        denominators.resize(count); exceptional.resize(count);
    }

    // Returns true if there is an exact two-pair group witness; with a prefix,
    // returns true only if all eight folded columns are distinct.
    bool probe(Point residual, const PairState* first, const PairState* second,
               std::array<PairState, 4>* found, Stats& stats) {
        ++stats.residuals;
        const size_t count = b3_representatives.size();
        uint64_t total = 1;
        for (size_t i = 0; i < count; ++i) {
            const Point b = pairs[3][b3_representatives[i]].sum;
            prefix[i] = total;
            exceptional[i] = residual.infinity || residual.x == b.x;
            if (!exceptional[i]) {
                denominators[i] = residual.x ^ b.x;
                total = mul(total, denominators[i]);
                ++stats.nonzero_denominators;
            }
        }
        uint64_t current = inv(total);
        for (size_t i = count; i-- > 0;) {
            if (!exceptional[i]) {
                inverses[i] = mul(current, prefix[i]);
                current = mul(current, denominators[i]);
            }
        }

        for (size_t i = 0; i < count; ++i) {
            const Point b = pairs[3][b3_representatives[i]].sum;
            ++stats.scanned_b;
            uint64_t candidate_x[2];
            if (exceptional[i]) {
                const Point plus = add(residual, b);
                const Point minus = add(residual, neg(b));
                candidate_x[0] = plus.infinity ? UINT64_MAX : plus.x;
                candidate_x[1] = minus.infinity ? UINT64_MAX : minus.x;
            } else {
                const uint64_t invd = inverses[i];
                const uint64_t lambda = mul(residual.y ^ b.y, invd);
                const uint64_t delta = mul(b.x, invd);
                const uint64_t offset = residual.x ^ b.x;
                candidate_x[0] = sq(lambda) ^ lambda ^ offset; // R + B, so P3=-B.
                const uint64_t other = lambda ^ delta;
                candidate_x[1] = sq(other) ^ other ^ offset; // R - B, so P3=B.
            }
            for (int sign = 0; sign < 2; ++sign) {
                if (x2.find(candidate_x[sign]) == x2.end()) continue;
                ++stats.x_hits;
                const Point p3 = sign == 0 ? neg(b) : b;
                const Point p2 = add(residual, neg(p3));
                if (p2.infinity || p2.x != candidate_x[sign])
                    throw std::runtime_error("x-only formula disagrees with group law");
                auto it2 = exact2.find(p2);
                auto it3 = exact3.find(p3);
                if (it2 == exact2.end() || it3 == exact3.end())
                    throw std::runtime_error("pair-sign symmetry violation");
                ++stats.exact_group_hits;
                for (uint16_t index2 : it2->second)
                    for (uint16_t index3 : it3->second) {
                        if (first && second) {
                            const auto& c = pairs[2][index2];
                            const auto& d = pairs[3][index3];
                            std::array<uint16_t, 8> columns{
                                seeds[0][first->a].column, seeds[0][first->b].column,
                                seeds[1][second->a].column, seeds[1][second->b].column,
                                seeds[2][c.a].column, seeds[2][c.b].column,
                                seeds[3][d.a].column, seeds[3][d.b].column};
                            if (!distinct(columns)) { ++stats.final_column_rejects; continue; }
                            *found = {*first, *second, c, d};
                        }
                        return true;
                    }
            }
        }
        return false;
    }
};

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
        if (argc < 4) throw std::runtime_error("missing arguments");
        const std::string mode = argv[1];
        if (mode != "diagnostic" && mode != "search") throw std::runtime_error("bad mode");
        if (argc != (mode == "diagnostic" ? 5 : 4))
            throw std::runtime_error("usage: native_batch diagnostic|search input.txt result.json [controls.txt]");
        std::ifstream input(argv[2]);
        if (!input) throw std::runtime_error("missing input");
        uint64_t qx, qy, subgroup_order;
        int summands;
        input >> qx >> qy >> subgroup_order >> summands;
        if (!input || summands != 8 || qx != 1458168294740ULL ||
            qy != 1672312028033ULL || subgroup_order != 549756390943ULL)
            throw std::runtime_error("wrong frozen N41 header");
        const Point target = finite(qx, qy);
        if (!on_curve(target)) throw std::runtime_error("off-curve target");
        std::array<std::vector<Seed>, 4> seeds;
        for (int slot = 0; slot < 8; ++slot) {
            int count;
            input >> count;
            if (!input || count != 64) throw std::runtime_error("wrong slot size");
            for (int i = 0; i < count; ++i) {
                uint64_t x, y;
                int column, mask, branch, sign;
                input >> x >> y >> column >> mask >> branch >> sign;
                if (!input || !on_curve(finite(x, y)) || column < 0 || column >= 26 ||
                    mask <= 0 || mask >= 64 || branch != 0 || sign < 0 || sign > 1)
                    throw std::runtime_error("bad seed");
                Seed value{finite(x, y), uint16_t(column), uint8_t(mask), uint8_t(sign)};
                if (slot % 2 == 0) seeds[slot/2].push_back(value);
                else {
                    const Seed& prior = seeds[slot/2][i];
                    if (!(prior.point == value.point) || prior.column != value.column ||
                        prior.mask != value.mask || prior.sign != value.sign)
                        throw std::runtime_error("duplicated pair slots differ");
                }
            }
        }
        std::string extra;
        if (input >> extra) throw std::runtime_error("trailing input");
        const auto setup_started = std::chrono::steady_clock::now();
        std::array<std::vector<PairState>, 4> pairs;
        for (int i = 0; i < 4; ++i) pairs[i] = make_pairs(seeds[i]);
        Filter filter(seeds, pairs);
        const uint64_t setup_ns = elapsed_ns(setup_started);
        if (peak_rss_bytes() >= 4ULL*1024*1024*1024)
            throw std::runtime_error("setup memory guard");

        std::ofstream out(argv[3]);
        if (!out) throw std::runtime_error("cannot open result");
        Stats stats;
        if (mode == "diagnostic") {
            std::ifstream control_input(argv[4]);
            uint64_t positive_x, positive_y, negative_x, negative_y;
            control_input >> positive_x >> positive_y >> negative_x >> negative_y;
            if (!control_input || !on_curve(finite(positive_x, positive_y)) ||
                !on_curve(finite(negative_x, negative_y)))
                throw std::runtime_error("bad control input");
            const std::array<Point, 2> controls{
                finite(positive_x, positive_y), finite(negative_x, negative_y)};
            out << "{\"kind\":\"n41_batch_inverse_controls\",\"controls\":[";
            for (int i = 0; i < 2; ++i) {
                if (i) out << ",";
                Stats local;
                std::array<PairState, 4> unused{};
                const auto start = std::chrono::steady_clock::now();
                const bool accepted = filter.probe(controls[i], nullptr, nullptr, &unused, local);
                const uint64_t ns = elapsed_ns(start);
                if (accepted != (i == 0)) throw std::runtime_error("control mismatch");
                out << "{\"residual\":"; write_point(out, controls[i]);
                out << ",\"accepted\":" << (accepted ? "true" : "false")
                    << ",\"wall_ns\":" << ns
                    << ",\"scanned_b\":" << local.scanned_b
                    << ",\"x_hits\":" << local.x_hits << "}";
            }
            out << "],\"setup_ns\":" << setup_ns
                << ",\"peak_rss_bytes\":" << peak_rss_bytes() << "}\n";
            std::cout << "PASS_CONTROLS\n";
            return 0;
        }

        const auto online_started = std::chrono::steady_clock::now();
        std::array<PairState, 4> chosen{};
        bool found = false, wall_cap = false, memory_guard = false;
        for (const auto& first : pairs[0]) {
            const Point after_first = add(target, neg(first.sum));
            for (const auto& second : pairs[1]) {
                std::array<uint16_t, 8> columns{
                    seeds[0][first.a].column, seeds[0][first.b].column,
                    seeds[1][second.a].column, seeds[1][second.b].column,
                    65535, 65534, 65533, 65532};
                if (!distinct(columns)) { ++stats.prefix_column_rejects; continue; }
                const Point residual = add(after_first, neg(second.sum));
                if (filter.probe(residual, &first, &second, &chosen, stats)) {
                    Point check = {};
                    for (const auto& value : chosen) check = add(check, value.sum);
                    if (!(check == target)) throw std::runtime_error("found row group mismatch");
                    found = true;
                    break;
                }
                if ((stats.residuals & 255) == 0) {
                    if (elapsed_ns(online_started) >= 120000000000ULL) wall_cap = true;
                    if (peak_rss_bytes() >= 4ULL*1024*1024*1024) memory_guard = true;
                    if (wall_cap || memory_guard) break;
                }
            }
            if (found || wall_cap || memory_guard) break;
        }
        const uint64_t online_ns = elapsed_ns(online_started);
        const char* status = found ? "VERIFIED_RAW_ROW" : wall_cap ?
            "ONLINE_TIME_CAP" : memory_guard ? "MEMORY_GUARD" : "EXHAUSTED_NO_ROW";
        out << "{\"kind\":\"n41_batch_inverse_public_search\","
            << "\"candidate_id\":null,\"run_id\":null,\"status\":\"" << status
            << "\",\"target\":[" << qx << "," << qy << "]"
            << ",\"pair_list_sizes\":[" << pairs[0].size() << "," << pairs[1].size()
            << "," << pairs[2].size() << "," << pairs[3].size() << "]"
            << ",\"unique_x_sizes\":[" << filter.x2.size() << ","
            << filter.b3_representatives.size() << "]"
            << ",\"setup_ns\":" << setup_ns << ",\"online_ns\":" << online_ns
            << ",\"residuals\":" << stats.residuals
            << ",\"x_hits\":" << stats.x_hits
            << ",\"exact_group_hits\":" << stats.exact_group_hits
            << ",\"prefix_column_rejects\":" << stats.prefix_column_rejects
            << ",\"final_column_rejects\":" << stats.final_column_rejects
            << ",\"scanned_b\":" << stats.scanned_b
            << ",\"nonzero_denominators\":" << stats.nonzero_denominators
            << ",\"peak_rss_bytes\":" << peak_rss_bytes() << ",\"row\":";
        if (found) write_row(out, seeds, chosen); else out << "null";
        out << "}\n";
        std::cout << status << " residuals=" << stats.residuals << " online_s="
                  << online_ns / 1000000000.0 << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 2;
    }
}
