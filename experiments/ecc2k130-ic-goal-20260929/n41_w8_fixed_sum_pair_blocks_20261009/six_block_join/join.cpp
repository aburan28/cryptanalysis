// Exact public-target 3+3 join of six signed, fixed-sum N41 pair blocks.
#define main unused_frozen_helper_main
#include "../../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
#undef main

#include <array>
#include <chrono>
#include <sys/resource.h>

using Clock = std::chrono::steady_clock;
using Mask = unsigned __int128;
constexpr uint64_t ORDER = 549756390943ULL;
constexpr uint64_t RSS_CAP = 4ULL * 1024 * 1024 * 1024;

struct State {
    Point point;
    uint8_t a, b, mask_a, mask_b, sign_a, sign_b;
    Mask columns;
};

struct PairState {
    Point point;
    Mask columns;
    uint8_t first, second;
};

uint64_t ns(Clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count();
}

uint64_t rss_bytes() {
    rusage usage{};
    if (getrusage(RUSAGE_SELF, &usage)) return 0;
#ifdef __APPLE__
    return uint64_t(usage.ru_maxrss);
#else
    return uint64_t(usage.ru_maxrss) * 1024;
#endif
}

std::vector<PairState> make_pairs(const std::vector<State>& left,
                                  const std::vector<State>& right) {
    std::vector<PairState> out;
    out.reserve(left.size() * right.size());
    for (unsigned i = 0; i < left.size(); ++i)
        for (unsigned j = 0; j < right.size(); ++j) {
            if (left[i].columns & right[j].columns) continue;
            out.push_back({add(left[i].point, right[j].point),
                           left[i].columns | right[j].columns,
                           uint8_t(i), uint8_t(j)});
        }
    return out;
}

uint32_t pack(unsigned a, unsigned b, unsigned c) {
    return uint32_t(a | (b << 8) | (c << 16));
}

int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::runtime_error("usage: join input.txt result.json cap_seconds");
        std::ifstream stream(argv[1]);
        if (!stream) throw std::runtime_error("missing frozen input");
        uint64_t qx, qy, order;
        int block_count;
        stream >> qx >> qy >> order >> block_count;
        if (!stream || qx != 1458168294740ULL || qy != 1672312028033ULL ||
            order != ORDER || block_count != 6)
            throw std::runtime_error("wrong public point, subgroup, or block count");
        const Point target = finite(qx, qy);
        if (!on_curve(target)) throw std::runtime_error("public target off curve");
        std::array<std::vector<State>, 6> blocks;
        for (auto& block : blocks) {
            int count;
            stream >> count;
            if (!stream || count != 160) throw std::runtime_error("wrong block state count");
            block.reserve(count);
            for (int i = 0; i < count; ++i) {
                uint64_t x, y;
                unsigned a, b, ma, mb, sa, sb;
                stream >> x >> y >> a >> b >> ma >> mb >> sa >> sb;
                if (!stream || a >= 128 || b >= 128 || a == b || ma >= 256 ||
                    mb >= 256 || sa > 1 || sb > 1)
                    throw std::runtime_error("invalid frozen pair state");
                Point point = finite(x, y);
                if (!on_curve(point)) throw std::runtime_error("pair point off curve");
                block.push_back({point, uint8_t(a), uint8_t(b), uint8_t(ma),
                                 uint8_t(mb), uint8_t(sa), uint8_t(sb),
                                 (Mask(1) << a) | (Mask(1) << b)});
            }
        }
        std::string trailing;
        if (stream >> trailing) throw std::runtime_error("trailing frozen input");
        const uint64_t cap_ns = std::stoull(argv[3]) * 1000000000ULL;
        const auto started = Clock::now();
        const auto left_pairs = make_pairs(blocks[0], blocks[1]);
        std::unordered_map<Point, std::vector<uint32_t>, PointHash> table;
        table.max_load_factor(0.70f);
        table.reserve(left_pairs.size() * blocks[2].size());
        uint64_t left_rows = 0, right_probes = 0, group_hits = 0;
        uint64_t column_rejects = 0, right_pairs_count = 0;
        bool timed_out = false, memory_capped = false, found = false;
        std::array<unsigned, 6> witness{};
        for (const auto& pair : left_pairs) {
            if ((left_rows & 4095) == 0) {
                if (ns(started) >= cap_ns) { timed_out = true; break; }
                if (rss_bytes() > RSS_CAP) { memory_capped = true; break; }
            }
            for (unsigned c = 0; c < blocks[2].size(); ++c) {
                const State& state = blocks[2][c];
                if (pair.columns & state.columns) continue;
                table[add(pair.point, state.point)].push_back(
                    pack(pair.first, pair.second, c));
                ++left_rows;
            }
        }
        const uint64_t build_ns = ns(started);
        const auto online_start = Clock::now();
        if (!timed_out && !memory_capped) {
            const auto right_pairs = make_pairs(blocks[3], blocks[4]);
            right_pairs_count = right_pairs.size();
            for (const auto& pair : right_pairs) {
                if (found || timed_out || memory_capped) break;
                for (unsigned c = 0; c < blocks[5].size(); ++c) {
                    if ((right_probes & 4095) == 0) {
                        if (ns(started) >= cap_ns) { timed_out = true; break; }
                        if (rss_bytes() > RSS_CAP) { memory_capped = true; break; }
                    }
                    const State& state = blocks[5][c];
                    if (pair.columns & state.columns) continue;
                    const Mask right_columns = pair.columns | state.columns;
                    const Point right_sum = add(pair.point, state.point);
                    const Point needed = add(target, neg(right_sum));
                    ++right_probes;
                    auto it = table.find(needed);
                    if (it == table.end()) continue;
                    for (uint32_t packed : it->second) {
                        ++group_hits;
                        std::array<unsigned, 6> ids{
                            packed & 255, (packed >> 8) & 255, (packed >> 16) & 255,
                            pair.first, pair.second, c};
                        Mask left_columns = blocks[0][ids[0]].columns |
                            blocks[1][ids[1]].columns | blocks[2][ids[2]].columns;
                        if (left_columns & right_columns) {
                            ++column_rejects;
                            continue;
                        }
                        Point total{};
                        for (int k = 0; k < 6; ++k)
                            total = add(total, blocks[k][ids[k]].point);
                        if (!(total == target))
                            throw std::runtime_error("join replay misses target");
                        witness = ids;
                        found = true;
                        break;
                    }
                    if (found) break;
                }
            }
        }
        const uint64_t online_ns = ns(online_start);
        const char* status = found ? "FOUND_VERIFIED_RELATION" :
            memory_capped ? "MEMORY_CAP" : timed_out ? "WALL_CAP" : "EXHAUSTIVE_NO_RELATION";
        std::ofstream result(argv[2]);
        if (!result) throw std::runtime_error("cannot write result");
        result << "{\"status\":\"" << status
               << "\",\"left_rows\":" << left_rows
               << ",\"left_unique_sums\":" << table.size()
               << ",\"left_pair_rows\":" << left_pairs.size()
               << ",\"right_pair_rows\":" << right_pairs_count
               << ",\"right_probes\":" << right_probes
               << ",\"group_hits\":" << group_hits
               << ",\"column_rejects\":" << column_rejects
               << ",\"left_build_ns\":" << build_ns
               << ",\"online_target_search_ns\":" << online_ns
               << ",\"total_wall_ns\":" << ns(started)
               << ",\"peak_rss_bytes\":" << rss_bytes()
               << ",\"witness\":";
        if (found) {
            result << "[";
            for (int k = 0; k < 6; ++k) result << (k ? "," : "") << witness[k];
            result << "]";
        } else result << "null";
        result << "}\n";
        std::cout << status << " left=" << left_rows
                  << " right=" << right_probes << " hits=" << group_hits << "\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 1;
    }
}
