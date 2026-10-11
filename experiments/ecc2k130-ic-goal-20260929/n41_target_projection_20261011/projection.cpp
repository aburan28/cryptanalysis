// Exhaustive target-conditioned support census for the transported N41 source.
#define main frozen_three_pair_reference_main
#include "../../koblitz-s5-invariant-20260924/three_pair_s7_native.cpp"
#undef main

#include <algorithm>
#include <chrono>
#include <set>
#include <sstream>

struct S8Seed { Point point; uint16_t column, mask; uint8_t branch, sign; };
struct S8Pair { Point sum; uint8_t a, b; };
struct S8Four { Point sum; std::array<uint8_t, 4> ids; };

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
    if (left.size() != right.size()) throw std::runtime_error("unequal pair slots");
    std::vector<S8Pair> result;
    for (uint8_t i = 0; i < left.size(); ++i)
        for (uint8_t j = i+1; j < right.size(); ++j) {
            if (left[i].column == right[j].column) continue;
            result.push_back({add(left[i].point, right[j].point), i, j});
        }
    return result;
}

static Point transport(Point p) {
    if (p.infinity) return p;
    Point frobenius = finite(sq(p.x), sq(p.y));
    if (!on_curve(frobenius)) throw std::runtime_error("Frobenius off curve");
    return add(p, frobenius);
}

struct Witness {
    std::array<uint8_t, 8> ids;
    std::array<uint8_t, 4> sums;
};

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: projection input.txt receipt.json");
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("cannot open input");
        uint64_t qx, qy, r;
        int m;
        input >> qx >> qy >> r >> m;
        if (!input || m != 8 || r != 549756390943ULL)
            throw std::runtime_error("invalid input header");
        Point original = finite(qx, qy);
        if (!on_curve(original)) throw std::runtime_error("target off curve");
        Point target = transport(original);
        if (target.infinity || !on_curve(target)) throw std::runtime_error("bad transported target");
        std::array<std::vector<S8Seed>, 8> base;
        for (int slot = 0; slot < 8; ++slot) {
            int count;
            input >> count;
            if (!input || count != 64) throw std::runtime_error("bad source count");
            for (int i = 0; i < count; ++i) {
                uint64_t x, y;
                int column, mask, branch, sign;
                input >> x >> y >> column >> mask >> branch >> sign;
                if (!input || column < 0 || column >= 26 || mask <= 0 || mask >= 64 ||
                    branch != 0 || sign < 0 || sign > 1)
                    throw std::runtime_error("invalid source row");
                Point p = finite(x, y);
                if (!on_curve(p)) throw std::runtime_error("source off curve");
                Point d = transport(p);
                if (d.infinity || !on_curve(d)) throw std::runtime_error("transported source invalid");
                base[slot].push_back({d, uint16_t(column), uint16_t(mask),
                                      uint8_t(branch), uint8_t(sign)});
            }
        }
        std::string extra;
        if (input >> extra) throw std::runtime_error("trailing input");
        for (int pair = 0; pair < 4; ++pair)
            for (int i = 0; i < 64; ++i) {
                const auto& a = base[2*pair][i];
                const auto& b = base[2*pair+1][i];
                if (!(a.point == b.point) || a.column != b.column ||
                    a.mask != b.mask || a.sign != b.sign)
                    throw std::runtime_error("repeated pair windows differ");
            }
        const auto setup_start = std::chrono::steady_clock::now();
        std::array<std::vector<S8Pair>, 4> pairs;
        std::array<std::set<uint8_t>, 4> pair_sum_domains;
        for (int i = 0; i < 4; ++i) {
            pairs[i] = s8_pairs(base[2*i], base[2*i+1]);
            for (const auto& p : pairs[i])
                pair_sum_domains[i].insert(base[2*i][p.a].mask ^ base[2*i+1][p.b].mask);
        }
        std::vector<S8Four> left_four;
        left_four.reserve(pairs[0].size()*pairs[1].size());
        uint64_t left_column_rejections = 0;
        for (const auto& a : pairs[0])
            for (const auto& b : pairs[1]) {
                std::array<uint16_t, 8> columns{
                    base[0][a.a].column, base[1][a.b].column,
                    base[2][b.a].column, base[3][b.b].column,
                    65535, 65534, 65533, 65532};
                if (!s8_distinct(columns)) { ++left_column_rejections; continue; }
                left_four.push_back({add(a.sum, b.sum), {a.a, a.b, b.a, b.b}});
            }
        std::sort(left_four.begin(), left_four.end(),
                  [](const S8Four& a, const S8Four& b) { return s8_less(a.sum, b.sum); });
        const uint64_t setup_ns = s8_elapsed_ns(setup_start);
        if (setup_ns > 120000000000ULL || s8_peak_rss_bytes() > 4ULL*1024*1024*1024)
            throw std::runtime_error("setup resource cap");

        const auto online_start = std::chrono::steady_clock::now();
        uint64_t probes = 0, raw_hits = 0, column_rejections = 0, valid_hits = 0;
        uint64_t replay_ns = 0;
        std::array<std::set<uint32_t>, 4> prefix_support;
        std::vector<Witness> witnesses;
        bool cap = false;
        for (const auto& c : pairs[2]) {
            for (const auto& d : pairs[3]) {
                ++probes;
                Point required = add(target, neg(add(c.sum, d.sum)));
                auto it = std::lower_bound(left_four.begin(), left_four.end(), required,
                    [](const S8Four& row, Point key) { return s8_less(row.sum, key); });
                for (; it != left_four.end() && it->sum == required; ++it) {
                    ++raw_hits;
                    std::array<uint8_t, 8> ids{it->ids[0], it->ids[1],
                        it->ids[2], it->ids[3], c.a, c.b, d.a, d.b};
                    std::array<uint16_t, 8> columns{};
                    std::array<Point, 8> points{};
                    std::array<uint8_t, 4> sums{};
                    for (int i = 0; i < 8; ++i) {
                        columns[i] = base[i][ids[i]].column;
                        points[i] = base[i][ids[i]].point;
                    }
                    if (!s8_distinct(columns)) { ++column_rejections; continue; }
                    const auto check_start = std::chrono::steady_clock::now();
                    Point total;
                    for (const auto& point : points) total = add(total, point);
                    if (!(total == target)) throw std::runtime_error("invalid exact hit");
                    replay_ns += s8_elapsed_ns(check_start);
                    ++valid_hits;
                    uint32_t packed = 0;
                    for (int i = 0; i < 4; ++i) {
                        sums[i] = base[2*i][ids[2*i]].mask ^
                                  base[2*i+1][ids[2*i+1]].mask;
                        packed |= uint32_t(sums[i]) << (6*i);
                        prefix_support[i].insert(packed & ((1U << (6*(i+1)))-1));
                    }
                    if (witnesses.size() < 128) witnesses.push_back({ids, sums});
                }
                if ((probes & 16383) == 0 &&
                    (s8_elapsed_ns(online_start) > 120000000000ULL ||
                     s8_peak_rss_bytes() > 4ULL*1024*1024*1024)) {
                    cap = true; break;
                }
            }
            if (cap) break;
        }
        const uint64_t online_ns = s8_elapsed_ns(online_start);
        std::ofstream out(argv[2]);
        if (!out) throw std::runtime_error("cannot write receipt");
        out << "{\n\"status\":\"" << (cap ? "BOUNDED_UNKNOWN" : "COMPLETE_EXACT_FIBER")
            << "\",\n\"candidate_id\":null,\"curve_id\":\"EC1N41Ckb1h023d9a38bbf7\","
            << "\n\"target_original\":[" << original.x << "," << original.y << "],"
            << "\n\"target_transported\":[" << target.x << "," << target.y << "],"
            << "\n\"actual_union_points_B\":256,\"folded_columns_K\":26,"
            << "\n\"pair_list_sizes\":[";
        for (int i = 0; i < 4; ++i) out << (i ? "," : "") << pairs[i].size();
        out << "],\n\"pair_sum_domain_sizes\":[";
        for (int i = 0; i < 4; ++i) out << (i ? "," : "") << pair_sum_domains[i].size();
        out << "],\n\"left_four_index_rows\":" << left_four.size()
            << ",\"left_column_rejections\":" << left_column_rejections
            << ",\"right_four_probes\":" << probes
            << ",\"raw_exact_sum_hits\":" << raw_hits
            << ",\"cross_column_rejections\":" << column_rejections
            << ",\"verified_rows\":" << valid_hits
            << ",\n\"prefix_support_sizes\":[";
        for (int i = 0; i < 4; ++i) out << (i ? "," : "") << prefix_support[i].size();
        out << "],\n\"prefix_support\":[";
        for (int i = 0; i < 4; ++i) {
            out << (i ? ",[" : "[");
            bool first = true;
            for (uint32_t x : prefix_support[i]) out << (first ? "" : ",") << x, first = false;
            out << "]";
        }
        out << "],\n\"first_witnesses\":[";
        for (size_t w = 0; w < witnesses.size(); ++w) {
            out << (w ? "," : "") << "{\"ids\":[";
            for (int i = 0; i < 8; ++i)
                out << (i ? "," : "") << unsigned(witnesses[w].ids[i]);
            out << "],\"seed_sums\":[";
            for (int i = 0; i < 4; ++i)
                out << (i ? "," : "") << unsigned(witnesses[w].sums[i]);
            out << "]}";
        }
        out << "],\n\"witnesses_truncated\":" << (valid_hits > witnesses.size() ? "true" : "false")
            << ",\"setup_ns\":" << setup_ns
            << ",\"online_ns\":" << online_ns
            << ",\"relation_replay_ns\":" << replay_ns
            << ",\"peak_rss_bytes\":" << s8_peak_rss_bytes()
            << ",\"limits\":{\"setup_seconds\":120,\"online_seconds\":120,"
               "\"rss_bytes\":4294967296,\"workers\":1}}\n";
        std::cout << "status=" << (cap ? "BOUNDED_UNKNOWN" : "COMPLETE_EXACT_FIBER")
                  << " rows=" << valid_hits << " online_ns=" << online_ns << "\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 2;
    }
}
