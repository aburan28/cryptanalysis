// Exact N41 eight-atom 4+4 reference on one frozen ordinary target.
#define main unused_three_pair_s7_main
#include "../../koblitz-s5-invariant-20260924/three_pair_s7_native.cpp"
#undef main

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

struct S8Seed {
    Point point;
    uint16_t column, mask;
    uint8_t branch, sign;
};
struct S8Pair {
    Point sum;
    uint8_t a, b;
};
struct S8Four {
    Point sum;
    std::array<uint8_t, 4> ids;
};

static uint64_t s8_elapsed_ns(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now()-start).count();
}

static uint64_t s8_peak_rss_bytes() {
    rusage usage{};
    getrusage(RUSAGE_SELF, &usage);
#if defined(__APPLE__)
    return uint64_t(usage.ru_maxrss);
#else
    return uint64_t(usage.ru_maxrss)*1024;
#endif
}

static bool s8_less(Point left, Point right) {
    if (left.infinity != right.infinity) return left.infinity;
    if (left.infinity) return false;
    if (left.x != right.x) return left.x < right.x;
    return left.y < right.y;
}

static bool s8_distinct(const std::array<uint16_t, 8>& columns) {
    for (int i = 0; i < 8; ++i)
        for (int j = i+1; j < 8; ++j)
            if (columns[i] == columns[j]) return false;
    return true;
}

static std::vector<S8Pair> s8_pairs(const std::vector<S8Seed>& left,
                                    const std::vector<S8Seed>& right) {
    std::vector<S8Pair> result;
    result.reserve(left.size()*right.size());
    for (uint8_t i = 0; i < left.size(); ++i)
        for (uint8_t j = 0; j < right.size(); ++j) {
            if (left[i].column == right[j].column) continue;
            result.push_back({add(left[i].point, right[j].point), i, j});
        }
    return result;
}

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: s8_join input.txt receipt.json");
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("cannot open input");
        uint64_t qx, qy, subgroup_order;
        int summands;
        input >> qx >> qy >> subgroup_order >> summands;
        if (!input || summands != 8) throw std::runtime_error("bad header");
        Point target = finite(qx, qy);
        if (!on_curve(target)) throw std::runtime_error("target off curve");
        std::array<std::vector<S8Seed>, 8> base;
        for (int slot = 0; slot < 8; ++slot) {
            int count;
            input >> count;
            if (!input || count != 64) throw std::runtime_error("bad slot size");
            base[slot].reserve(count);
            for (int i = 0; i < count; ++i) {
                uint64_t x, y;
                int column, mask, branch, sign;
                input >> x >> y >> column >> mask >> branch >> sign;
                if (!input || column < 0 || column >= 26 || mask <= 0 ||
                    mask >= 64 || branch != 0 || sign < 0 || sign > 1)
                    throw std::runtime_error("bad base row");
                Point point = finite(x, y);
                if (!on_curve(point)) throw std::runtime_error("base point off curve");
                base[slot].push_back({point, uint16_t(column), uint16_t(mask),
                                      uint8_t(branch), uint8_t(sign)});
            }
        }
        std::string extra;
        if (input >> extra) throw std::runtime_error("trailing input");
        const auto setup_start = std::chrono::steady_clock::now();
        std::array<std::vector<S8Pair>, 4> pair_lists;
        for (int pair = 0; pair < 4; ++pair)
            pair_lists[pair] = s8_pairs(base[2*pair], base[2*pair+1]);
        std::vector<S8Four> left_four;
        left_four.reserve(pair_lists[0].size()*pair_lists[1].size());
        uint64_t precompute_repeated_columns = 0;
        bool setup_cap = false, memory_guard = false;
        for (const auto& a : pair_lists[0]) {
            for (const auto& b : pair_lists[1]) {
                std::array<uint16_t, 8> cols{
                    base[0][a.a].column, base[1][a.b].column,
                    base[2][b.a].column, base[3][b.b].column,
                    65535, 65534, 65533, 65532};
                if (!s8_distinct(cols)) { ++precompute_repeated_columns; continue; }
                left_four.push_back({add(a.sum, b.sum), {a.a, a.b, b.a, b.b}});
                if ((left_four.size() & 65535) == 0) {
                    if (s8_elapsed_ns(setup_start) >= 120000000000ULL) setup_cap = true;
                    if (s8_peak_rss_bytes() >= 4ULL*1024*1024*1024) memory_guard = true;
                    if (setup_cap || memory_guard) break;
                }
            }
            if (setup_cap || memory_guard) break;
        }
        if (!setup_cap && !memory_guard) {
            std::sort(left_four.begin(), left_four.end(),
                      [](const S8Four& a, const S8Four& b) {
                          return s8_less(a.sum, b.sum);
                      });
            if (s8_elapsed_ns(setup_start) >= 120000000000ULL) setup_cap = true;
            if (s8_peak_rss_bytes() >= 4ULL*1024*1024*1024) memory_guard = true;
        }
        const uint64_t setup_ns = s8_elapsed_ns(setup_start);

        uint64_t probes = 0, hash_hits = 0, duplicate_column_rejections = 0;
        uint64_t relation_check_ns = 0;
        bool found = false, online_cap = false;
        std::array<uint8_t, 8> chosen{};
        std::array<Point, 8> chosen_points{};
        std::array<uint16_t, 8> chosen_columns{};
        uint64_t online_ns = 0;
        if (!setup_cap && !memory_guard) {
            const auto online_start = std::chrono::steady_clock::now();
            for (const auto& c : pair_lists[2]) {
                for (const auto& d : pair_lists[3]) {
                    ++probes;
                    const Point last_four = add(c.sum, d.sum);
                    const Point needed = add(target, neg(last_four));
                    auto hit = std::lower_bound(
                        left_four.begin(), left_four.end(), needed,
                        [](const S8Four& row, Point key) { return s8_less(row.sum, key); });
                    for (; hit != left_four.end() && hit->sum == needed; ++hit) {
                        ++hash_hits;
                        std::array<uint8_t, 8> ids{
                            hit->ids[0], hit->ids[1], hit->ids[2], hit->ids[3],
                            c.a, c.b, d.a, d.b};
                        std::array<uint16_t, 8> columns{};
                        std::array<Point, 8> points{};
                        for (int i = 0; i < 8; ++i) {
                            columns[i] = base[i][ids[i]].column;
                            points[i] = base[i][ids[i]].point;
                        }
                        if (!s8_distinct(columns)) {
                            ++duplicate_column_rejections;
                            continue;
                        }
                        const auto check_start = std::chrono::steady_clock::now();
                        Point sum;
                        for (Point point : points) sum = add(sum, point);
                        relation_check_ns += s8_elapsed_ns(check_start);
                        if (!(sum == target))
                            throw std::runtime_error("4+4 hit failed exact group replay");
                        chosen = ids;
                        chosen_points = points;
                        chosen_columns = columns;
                        found = true;
                        break;
                    }
                    if (found) break;
                    if ((probes & 16383) == 0) {
                        if (s8_elapsed_ns(online_start) >= 120000000000ULL) online_cap = true;
                        if (s8_peak_rss_bytes() >= 4ULL*1024*1024*1024) memory_guard = true;
                        if (online_cap || memory_guard) break;
                    }
                }
                if (found || online_cap || memory_guard) break;
            }
            online_ns = s8_elapsed_ns(online_start);
        }
        const char* status = found ? "VERIFIED_EIGHT_POINT_ROW" :
            memory_guard ? "MEMORY_GUARD" :
            setup_cap ? "SETUP_TIME_CAP" :
            online_cap ? "ONLINE_TIME_CAP" : "FULL_SEARCH_NO_ROW";
        std::ofstream out(argv[2]);
        if (!out) throw std::runtime_error("cannot open output receipt");
        out << "{\n\"kind\":\"n41_w6_eight_diagonal_atom_exact_indexed_4plus4_join\",\n"
            << "\"status\":\"" << status << "\",\n"
            << "\"candidate_id\":null,\"run_id\":null,\n"
            << "\"target_count\":1,\"curve_id\":\"EC1N41Ckb1h7d5e80d3c4d0\",\n"
            << "\"target\":[" << target.x << "," << target.y << "],\n"
            << "\"subgroup_order\":" << subgroup_order << ",\n"
            << "\"base_points_by_slot\":[64,64,64,64,64,64,64,64],\n"
            << "\"actual_union_points_B\":512,\"folded_columns_K\":26,\n"
            << "\"pair_list_sizes\":[";
        for (int i = 0; i < 4; ++i)
            out << (i ? "," : "") << pair_lists[i].size();
        out << "],\n\"left_four_index_rows\":" << left_four.size()
            << ",\"precompute_repeated_column_rejections\":" << precompute_repeated_columns
            << ",\"right_four_probes\":" << probes
            << ",\"exact_sum_hits\":" << hash_hits
            << ",\"cross_pair_duplicate_column_rejections\":" << duplicate_column_rejections
            << ",\"reusable_setup_ns\":" << setup_ns
            << ",\"stage_online_wall_ns\":";
        if (setup_cap || (memory_guard && !probes)) out << "null";
        else out << online_ns;
        out << ",\n\"exclusive_stage_phase_ns\":{\"target_query\":";
        if (setup_cap || (memory_guard && !probes)) out << "null,\"target_PDP\":null,\"target_relation_check\":null";
        else out << "0,\"target_PDP\":" << online_ns-relation_check_ns
                 << ",\"target_relation_check\":" << relation_check_ns;
        out << ",\"target_descent\":null,\"target_recovery_check\":null},\n"
            << "\"complete_ic_online_wall_ns\":null,\n"
            << "\"peak_rss_bytes\":" << s8_peak_rss_bytes() << ",\n"
            << "\"limits\":{\"setup_wall_seconds\":120,\"online_wall_seconds\":120,"
            << "\"peak_rss_bytes\":4294967296,\"workers\":1},\n"
            << "\"verified_relation\":";
        if (!found) out << "null\n";
        else {
            out << "{\"points\":[";
            for (int i = 0; i < 8; ++i) {
                if (i) out << ",";
                write_point(out, chosen_points[i]);
            }
            out << "],\"columns\":[";
            for (int i = 0; i < 8; ++i)
                out << (i ? "," : "") << chosen_columns[i];
            out << "],\"seed_masks\":[";
            for (int i = 0; i < 8; ++i)
                out << (i ? "," : "") << base[i][chosen[i]].mask;
            out << "],\"seed_branches\":[";
            for (int i = 0; i < 8; ++i)
                out << (i ? "," : "") << unsigned(base[i][chosen[i]].branch);
            out << "],\"curve_sign_indices\":[";
            for (int i = 0; i < 8; ++i)
                out << (i ? "," : "") << unsigned(base[i][chosen[i]].sign);
            out << "]}\n";
        }
        out << "}\n";
        std::cout << "status=" << status << " setup_ns=" << setup_ns
                  << " online_ns=" << online_ns << " probes=" << probes
                  << " exact_sum_hits=" << hash_hits << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << "\n";
        return 1;
    }
}
