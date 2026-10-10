// Complete 3+4 group join on seven frozen diagonal N41 blocks.
#define main unused_frozen_helper_main
#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
#undef main

#include <algorithm>

struct State { Point point; uint16_t column; uint8_t mask, sign; };
struct Pair7 { Point sum; uint8_t a, b; };
static uint64_t now_ns() {
    return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
static uint64_t rss_bytes() {
    rusage usage{};
    getrusage(RUSAGE_SELF, &usage);
#ifdef __APPLE__
    return uint64_t(usage.ru_maxrss);
#else
    return uint64_t(usage.ru_maxrss) * 1024;
#endif
}
static std::vector<Pair7> pairs(const std::vector<State>& a, const std::vector<State>& b) {
    std::vector<Pair7> out;
    out.reserve(4096);
    for (int i = 0; i < 64; ++i)
        for (int j = 0; j < 64; ++j)
            out.push_back({add(a[i].point, b[j].point), uint8_t(i), uint8_t(j)});
    return out;
}
int main(int argc, char** argv) {
    try {
        if (argc != 5) throw std::runtime_error("usage: join input hits.jsonl result.json cap_seconds");
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("missing input");
        uint64_t qx, qy, order;
        int blocks_count;
        input >> qx >> qy >> order >> blocks_count;
        if (!input || order != 549756390943ULL || blocks_count != 7 ||
            qx != 1458168294740ULL || qy != 1672312028033ULL)
            throw std::runtime_error("wrong public target or subgroup");
        const Point target = finite(qx, qy);
        if (!on_curve(target)) throw std::runtime_error("target off curve");
        std::array<std::vector<State>, 7> blocks;
        for (auto& block : blocks) {
            int size;
            input >> size;
            if (!input || size != 64) throw std::runtime_error("wrong block size");
            for (int i = 0; i < size; ++i) {
                uint64_t x, y;
                int column, mask, sign;
                input >> x >> y >> column >> mask >> sign;
                Point p = finite(x, y);
                if (!input || !on_curve(p) || column < 0 || column >= 26 ||
                    mask < 0 || mask >= 64 || sign < 0 || sign > 1)
                    throw std::runtime_error("invalid state");
                block.push_back({p, uint16_t(column), uint8_t(mask), uint8_t(sign)});
            }
        }
        std::string trailing;
        if (input >> trailing) throw std::runtime_error("trailing input");
        const uint64_t began = now_ns();
        const uint64_t cap_ns = std::stoull(argv[4]) * 1000000000ULL;
        std::unordered_map<Point, std::vector<uint32_t>, PointHash> left;
        left.reserve(300000);
        for (int a = 0; a < 64; ++a)
            for (int b = 0; b < 64; ++b)
                for (int c = 0; c < 64; ++c) {
                    Point sum = add(add(blocks[0][a].point, blocks[1][b].point), blocks[2][c].point);
                    left[sum].push_back(uint32_t(a | (b << 6) | (c << 12)));
                }
        const auto p34 = pairs(blocks[3], blocks[4]);
        const auto p56 = pairs(blocks[5], blocks[6]);
        const uint64_t built = now_ns();
        std::ofstream hits(argv[2]);
        if (!hits) throw std::runtime_error("cannot open hits");
        std::vector<uint64_t> prefix(4097), inverse(4096), denom(4096);
        uint64_t probes = 0, group_hits = 0, column_rejects = 0, valid_hits = 0, completed = 0;
        bool timed_out = false, memory_capped = false;
        for (size_t i = 0; i < p34.size(); ++i) {
            if (now_ns() - began >= cap_ns) { timed_out = true; break; }
            if (rss_bytes() > 4ULL * 1024 * 1024 * 1024) { memory_capped = true; break; }
            const Point residual = add(target, neg(p34[i].sum));
            prefix[0] = 1;
            for (size_t j = 0; j < p56.size(); ++j) {
                denom[j] = residual.infinity ? 0 : residual.x ^ p56[j].sum.x;
                prefix[j+1] = denom[j] ? mul(prefix[j], denom[j]) : prefix[j];
            }
            uint64_t current = inv(prefix.back());
            for (size_t j = p56.size(); j-- > 0;) {
                if (denom[j]) {
                    inverse[j] = mul(current, prefix[j]);
                    current = mul(current, denom[j]);
                }
            }
            for (size_t j = 0; j < p56.size(); ++j) {
                ++probes;
                const Point needed = denom[j] ?
                    add_negative_with_inverse(residual, p56[j].sum, inverse[j]) :
                    add(residual, neg(p56[j].sum));
                auto it = left.find(needed);
                if (it == left.end()) continue;
                for (uint32_t packed : it->second) {
                    ++group_hits;
                    std::array<int, 7> ids{int(packed & 63), int((packed >> 6) & 63),
                        int((packed >> 12) & 63), p34[i].a, p34[i].b, p56[j].a, p56[j].b};
                    bool distinct = true;
                    for (int k = 0; k < 7; ++k)
                        for (int l = k + 1; l < 7; ++l)
                            distinct &= blocks[k][ids[k]].column != blocks[l][ids[l]].column;
                    if (!distinct) { ++column_rejects; continue; }
                    Point sum{};
                    for (int k = 0; k < 7; ++k) sum = add(sum, blocks[k][ids[k]].point);
                    if (!(sum == target)) throw std::runtime_error("group replay mismatch");
                    ++valid_hits;
                    hits << "{\"indices\":[";
                    for (int k = 0; k < 7; ++k) hits << (k ? "," : "") << ids[k];
                    hits << "],\"masks\":[";
                    for (int k = 0; k < 7; ++k) hits << (k ? "," : "") << int(blocks[k][ids[k]].mask);
                    hits << "],\"signs\":[";
                    for (int k = 0; k < 7; ++k) hits << (k ? "," : "") << int(blocks[k][ids[k]].sign);
                    hits << "]}\n";
                }
            }
            ++completed;
        }
        hits.close();
        std::ofstream result(argv[3]);
        if (!result) throw std::runtime_error("cannot open result");
        const char* status = memory_capped ? "OOM" : timed_out ? "CENSORED_TIME" : "EXHAUSTIVE";
        result << "{\"status\":\"" << status
               << "\",\"completed_outer\":" << completed
               << ",\"outer_total\":4096,\"probes\":" << probes
               << ",\"group_hits\":" << group_hits
               << ",\"column_rejects\":" << column_rejects
               << ",\"distinct_column_hits\":" << valid_hits
               << ",\"left_unique_sums\":" << left.size()
               << ",\"build_ns\":" << built-began
               << ",\"wall_ns\":" << now_ns()-began
               << ",\"peak_rss_bytes\":" << rss_bytes() << "}\n";
        std::cout << status
                  << " hits=" << valid_hits << " probes=" << probes << "\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << "\n";
        return 1;
    }
}
