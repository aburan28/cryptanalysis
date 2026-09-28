// Exact bounded five-point meet-in-the-middle on a signed subgroup base.
// Reuse the frozen frontier field/curve arithmetic without changing its hash.
#define main frozen_enumerator_unused_main
#include "explicit_base_frontier.cpp"
#undef main

#include <chrono>
#include <fstream>
#include <unordered_map>
#include <vector>
#include <sys/resource.h>

static U from_hex(const std::string& s) {
    U v = 0;
    if (s.empty() || s.size() > 32) throw std::invalid_argument("invalid hex width");
    for (char c : s) {
        unsigned d = c >= '0' && c <= '9' ? c - '0' :
                     c >= 'a' && c <= 'f' ? c - 'a' + 10 : 16;
        if (d >= 16) throw std::invalid_argument("invalid hex character");
        v = (v << 4) | d;
    }
    return v;
}

struct Key {
    U x, y;
    bool infinity;
    bool operator==(const Key& o) const {
        return x == o.x && y == o.y && infinity == o.infinity;
    }
};

static Key key(Point p) { return {p.x, p.y, p.infinity}; }

struct KeyHash {
    size_t operator()(Key p) const {
        auto mix = [](uint64_t h) {
            h ^= h >> 30; h *= 0xbf58476d1ce4e5b9ULL;
            h ^= h >> 27; h *= 0x94d049bb133111ebULL;
            return h ^ (h >> 31);
        };
        uint64_t h = mix(uint64_t(p.x)) ^ mix(uint64_t(p.x >> 64));
        h ^= mix(uint64_t(p.y) + 0x9e3779b97f4a7c15ULL);
        h ^= mix(uint64_t(p.y >> 64) + 0x243f6a8885a308d3ULL);
        return size_t(mix(h ^ uint64_t(p.infinity)));
    }
};

static std::vector<Point> read_points(const std::string& path, const Curve& curve) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open points");
    std::vector<Point> points;
    std::string x, y;
    while (input >> x >> y) {
        Point p{from_hex(x), from_hex(y), false};
        if (!curve.valid(p) || p.x >> curve.f.n || p.y >> curve.f.n)
            throw std::runtime_error("point outside curve/field");
        points.push_back(p);
    }
    if (!input.eof() || points.empty()) throw std::runtime_error("bad points file");
    return points;
}

int main(int argc, char** argv) {
    try {
        if (argc != 9) throw std::invalid_argument("usage: five_sum_mitm n modulus_decimal base.tsv targets.tsv max_checks max_seconds expected_targets summands");
        const int n = std::stoi(argv[1]);
        if (n != 13 && n != 83) throw std::invalid_argument("unsupported curve");
        Curve curve{Field{n, decimal(argv[2])}};
        const auto points = read_points(argv[3], curve);
        const uint64_t pairs = uint64_t(points.size()) * (points.size() + 1) / 2;
        // Bound the actual pair table and deny full-base launches before allocation.
        if (pairs > 1500000) throw std::invalid_argument("pair table exceeds 1.5m entries; choose a smaller frozen subset");
        std::ifstream targets(argv[4]);
        if (!targets) throw std::runtime_error("cannot open targets");
        const uint64_t max_triples = std::stoull(argv[5]);
        const double max_seconds = std::stod(argv[6]);
        const unsigned expected = std::stoul(argv[7]);
        const unsigned summands = std::stoul(argv[8]);
        if (summands != 3 && summands != 5) throw std::invalid_argument("only 3 or 5 summands");
        if (!(max_seconds > 0) || max_triples == 0 || expected == 0)
            throw std::invalid_argument("nonpositive bound");
        auto setup_start = std::chrono::steady_clock::now();
        std::unordered_map<Key, std::pair<unsigned, unsigned>, KeyHash> lookup;
        lookup.reserve(size_t(pairs));
        std::vector<Point> pair_sums;
        pair_sums.reserve(size_t(pairs));
        for (unsigned i = 0; i < points.size(); ++i)
            for (unsigned j = i; j < points.size(); ++j) {
                Point s = curve.add(points[i], points[j]);
                pair_sums.push_back(s);
                lookup.emplace(key(s), std::make_pair(i, j));
            }
        const auto setup_seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - setup_start).count();
        std::string x, y;
        unsigned count = 0;
        while (targets >> x >> y) {
            ++count;
            Point t{from_hex(x), from_hex(y), false};
            if (!curve.valid(t)) throw std::runtime_error("target off curve");
            const auto start = std::chrono::steady_clock::now();
            uint64_t visited = 0;
            bool found = false, stopped = false;
            unsigned witness[5] = {};
            if (summands == 3) {
                for (unsigned i = 0; i < points.size(); ++i) {
                    if (visited >= max_triples || std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count() >= max_seconds) {
                        stopped = true; break;
                    }
                    ++visited;
                    const Point rem = curve.add(t, curve.negate(points[i]));
                    const auto it = lookup.find(key(rem));
                    if (it == lookup.end()) continue;
                    witness[0] = i; witness[1] = it->second.first; witness[2] = it->second.second;
                    found = true; break;
                }
            } else {
                size_t pair_at = 0;
                for (unsigned i = 0; i < points.size() && !found && !stopped; ++i)
                  for (unsigned j = i; j < points.size() && !found && !stopped; ++j, ++pair_at) {
                    const Point remainder = curve.add(t, curve.negate(pair_sums[pair_at]));
                    for (unsigned k = j; k < points.size(); ++k) {
                        if (visited >= max_triples || std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count() >= max_seconds) {
                            stopped = true; break;
                        }
                        ++visited;
                        Point rem = curve.add(remainder, curve.negate(points[k]));
                        const auto it = lookup.find(key(rem));
                        if (it == lookup.end()) continue;
                        witness[0] = i; witness[1] = j; witness[2] = k;
                        witness[3] = it->second.first; witness[4] = it->second.second;
                        found = true; break;
                    }
                  }
            }
            if (found) {
                Point check{};
                for (unsigned z = 0; z < summands; ++z) check = curve.add(check, points[witness[z]]);
                if (!(key(check) == key(t))) throw std::runtime_error("witness replay failed");
            }
            const double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
            rusage usage{};
            if (getrusage(RUSAGE_SELF, &usage)) throw std::runtime_error("getrusage failed");
            std::cout << "{\"target\":[\"" << hex(t.x) << "\",\"" << hex(t.y) << "\"],\"status\":\""
                      << (found ? "found" : stopped ? "budget" : "exhausted")
                      << "\",\"triples_visited\":" << visited << ",\"seconds\":" << elapsed
                      << ",\"setup_seconds\":" << (count == 1 ? setup_seconds : 0.0)
                      << ",\"distinct_pair_sums\":" << lookup.size()
                      << ",\"peak_rss_kib\":" << usage.ru_maxrss << ",\"witness\":[";
            if (found) {
                for (unsigned z = 0; z < summands; ++z) {
                    if (z) std::cout << ',';
                    std::cout << witness[z];
                }
            }
            std::cout << "]}\n" << std::flush;
        }
        if (count != expected || !targets.eof()) throw std::runtime_error("target count differs from frozen input");
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 2;
    }
}
