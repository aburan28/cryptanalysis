// Exact native GF(2^41) three-pair search on a frozen ordinary target.
#include <arm_neon.h>
#include <sys/resource.h>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using U128 = __uint128_t;
constexpr uint64_t MASK = (1ULL << 41) - 1;
constexpr U128 MOD = (U128(1) << 41) | (U128(1) << 3) | 1;

uint64_t reduce(U128 value) {
    while (value >> 41) {
        U128 upper = value >> 41;
        value = (value & MASK) ^ upper ^ (upper << 3);
    }
    return uint64_t(value);
}

uint64_t mul(uint64_t a, uint64_t b) {
    poly128_t product = vmull_p64(poly64_t(a), poly64_t(b));
    uint64x2_t words = vreinterpretq_u64_p128(product);
    U128 value = U128(vgetq_lane_u64(words, 0)) |
                 (U128(vgetq_lane_u64(words, 1)) << 64);
    return reduce(value);
}

uint64_t sq(uint64_t a) { return mul(a, a); }

int degree(U128 x) {
    uint64_t upper = uint64_t(x >> 64);
    if (upper) return 127 - __builtin_clzll(upper);
    uint64_t lower = uint64_t(x);
    if (!lower) return -1;
    return 63 - __builtin_clzll(lower);
}

uint64_t inv(uint64_t a) {
    if (!a) throw std::runtime_error("inverse of zero");
    U128 u = a, v = MOD, g1 = 1, g2 = 0;
    while (u != 1) {
        if (!u) throw std::runtime_error("noninvertible field element");
        int j = degree(u) - degree(v);
        if (j < 0) {
            std::swap(u, v);
            std::swap(g1, g2);
            j = -j;
        }
        u ^= v << j;
        g1 ^= g2 << j;
    }
    uint64_t result = reduce(g1);
    return result;
}

struct Point {
    uint64_t x = 0, y = 0;
    bool infinity = true;
    bool operator==(const Point& other) const {
        return infinity == other.infinity &&
               (infinity || (x == other.x && y == other.y));
    }
};

Point finite(uint64_t x, uint64_t y) { return {x, y, false}; }
Point neg(Point p) {
    if (!p.infinity) p.y ^= p.x;
    return p;
}

bool on_curve(Point p) {
    if (p.infinity) return true;
    return (sq(p.y) ^ mul(p.x, p.y)) == (mul(sq(p.x), p.x) ^ 1);
}

Point add(Point p, Point q) {
    if (p.infinity) return q;
    if (q.infinity) return p;
    uint64_t lambda;
    if (p.x == q.x) {
        if (p.y != q.y) return {};
        if (!p.x) return {};
        lambda = p.x ^ mul(p.y, inv(p.x));
        uint64_t x3 = sq(lambda) ^ lambda;
        uint64_t y3 = sq(p.x) ^ mul(lambda ^ 1, x3);
        return finite(x3, y3);
    }
    lambda = mul(p.y ^ q.y, inv(p.x ^ q.x));
    uint64_t x3 = sq(lambda) ^ lambda ^ p.x ^ q.x;
    uint64_t y3 = mul(lambda, p.x ^ x3) ^ x3 ^ p.y;
    return finite(x3, y3);
}

struct PointHash {
    size_t operator()(Point p) const {
        uint64_t h = p.x ^ (p.y + 0x9e3779b97f4a7c15ULL + (p.x << 6) + (p.x >> 2));
        h ^= uint64_t(p.infinity) * 0x517cc1b727220a95ULL;
        h ^= h >> 33;
        h *= 0xff51afd7ed558ccdULL;
        h ^= h >> 33;
        return size_t(h);
    }
};

struct BasePoint {
    int shift = 0, mask = 0;
    uint64_t w = 0;
    Point point;
};
struct Pair {
    uint16_t first = 0, second = 0;
    Point sum;
};
struct UniqueSum {
    Point sum;
    std::vector<uint32_t> pair_indices;
};

std::vector<Pair> pairs(const std::vector<BasePoint>& base) {
    std::vector<Pair> result;
    for (size_t i = 0; i < base.size(); ++i) {
        for (size_t j = i + 1; j < base.size(); ++j) {
            if (base[i].w == base[j].w) continue;
            Point total = add(base[i].point, base[j].point);
            if (total.infinity || total.x == 0 || total.x == 1) continue;
            result.push_back({uint16_t(i), uint16_t(j), total});
        }
    }
    return result;
}

Point add_negative_with_inverse(Point p, Point q, uint64_t inverse_x_difference) {
    Point negative_q = neg(q);
    uint64_t lambda = mul(p.y ^ negative_q.y, inverse_x_difference);
    uint64_t x3 = sq(lambda) ^ lambda ^ p.x ^ q.x;
    uint64_t y3 = mul(lambda, p.x ^ x3) ^ x3 ^ p.y;
    return finite(x3, y3);
}

void write_point(std::ostream& out, Point p) {
    if (p.infinity) out << "null";
    else out << "[" << p.x << "," << p.y << "]";
}

int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("usage: program input.txt receipt.json");
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("cannot open input");
        Point target;
        input >> target.x >> target.y;
        target.infinity = false;
        if (!on_curve(target)) throw std::runtime_error("target off curve");
        std::array<std::vector<BasePoint>, 3> base;
        int shift, mask;
        uint64_t w, x, y;
        while (input >> shift >> mask >> w >> x >> y) {
            int group = shift == 0 ? 0 : shift == 7 ? 1 : shift == 13 ? 2 : -1;
            if (group < 0) throw std::runtime_error("unexpected rotation");
            Point point = finite(x, y);
            if (!on_curve(point)) throw std::runtime_error("base point off curve");
            if (mul(w, inv(w)) != 1) throw std::runtime_error("field inverse check");
            base[group].push_back({shift, mask, w, point});
        }
        auto start_build = std::chrono::steady_clock::now();
        auto A = pairs(base[0]), B = pairs(base[1]), C = pairs(base[2]);
        std::unordered_map<Point, std::vector<uint32_t>, PointHash> table;
        table.reserve(B.size() * 2);
        for (uint32_t i = 0; i < B.size(); ++i) table[B[i].sum].push_back(i);
        std::unordered_map<Point, size_t, PointHash> c_positions;
        c_positions.reserve(C.size() * 2);
        std::vector<UniqueSum> c_unique;
        c_unique.reserve(C.size());
        for (uint32_t i = 0; i < C.size(); ++i) {
            auto [it, inserted] = c_positions.emplace(C[i].sum, c_unique.size());
            if (inserted) c_unique.push_back({C[i].sum, {}});
            c_unique[it->second].pair_indices.push_back(i);
        }
        double build_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - start_build).count();
        auto start_query = std::chrono::steady_clock::now();
        uint64_t a_tested = 0, c_probes = 0, hash_hits = 0;
        std::vector<uint64_t> denominators(c_unique.size());
        std::vector<uint64_t> prefixes(c_unique.size() + 1);
        std::vector<uint64_t> inverses(c_unique.size());
        bool found = false;
        Pair chosen_a, chosen_b, chosen_c;
        Point chosen_middle;
        for (const Pair& a : A) {
            ++a_tested;
            Point complement = add(target, neg(a.sum));
            prefixes[0] = 1;
            for (size_t j = 0; j < c_unique.size(); ++j) {
                uint64_t denominator = complement.infinity ? 0 :
                                       complement.x ^ c_unique[j].sum.x;
                denominators[j] = denominator;
                prefixes[j+1] = denominator ? mul(prefixes[j], denominator) : prefixes[j];
            }
            uint64_t inverse_product = inv(prefixes.back());
            for (size_t j = c_unique.size(); j-- > 0;) {
                if (denominators[j]) {
                    inverses[j] = mul(inverse_product, prefixes[j]);
                    inverse_product = mul(inverse_product, denominators[j]);
                }
            }
            for (size_t j = 0; j < c_unique.size(); ++j) {
                ++c_probes;
                const UniqueSum& c_group = c_unique[j];
                Point needed = denominators[j] ?
                    add_negative_with_inverse(complement, c_group.sum, inverses[j]) :
                    add(complement, neg(c_group.sum));
                auto it = table.find(needed);
                if (it == table.end()) continue;
                for (uint32_t index : it->second) {
                    const Pair& b = B[index];
                    for (uint32_t c_index : c_group.pair_indices) {
                        ++hash_hits;
                        const Pair& c = C[c_index];
                        std::array<uint64_t, 6> ws{
                            base[0][a.first].w, base[0][a.second].w,
                            base[1][b.first].w, base[1][b.second].w,
                            base[2][c.first].w, base[2][c.second].w};
                        bool distinct = true;
                        for (int k = 0; k < 6; ++k)
                            for (int l = k + 1; l < 6; ++l)
                                distinct &= ws[k] != ws[l];
                        if (!distinct) continue;
                        Point middle = add(a.sum, b.sum);
                        if (middle.infinity || middle.x == 0 || middle.x == 1) continue;
                        if (!(add(middle, c.sum) == target))
                            throw std::runtime_error("hash hit failed group replay");
                        chosen_a = a; chosen_b = b; chosen_c = c;
                        chosen_middle = middle;
                        found = true;
                        break;
                    }
                    if (found) break;
                }
                if (found) break;
            }
            if (found) break;
        }
        double query_seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - start_query).count();
        rusage usage{};
        getrusage(RUSAGE_SELF, &usage);
        std::ofstream out(argv[2]);
        if (!out) throw std::runtime_error("cannot open output");
        out << "{\n\"kind\":\"n41_d8_three_pair_native_ordinary_relation_control\",\n"
            << "\"candidate_id\":null,\n\"scope\":\"Fixed ordinary target, pair rotations 0,7,13 and complete precomputed pair lists; stage-only direct search, no IC logs or rho speedup\",\n"
            << "\"status\":\"" << (found ? "VERIFIED_RAW_RELATION" : "EXHAUSTED_NO_RELATION") << "\",\n"
            << "\"target\":";
        write_point(out, target);
        out << ",\n\"base_points_by_rotation\":[" << base[0].size() << "," << base[1].size() << "," << base[2].size() << "],\n"
            << "\"pair_tuple_counts\":[" << A.size() << "," << B.size() << "," << C.size() << "],\n"
            << "\"distinct_second_pair_sums\":" << table.size() << ",\n"
            << "\"distinct_third_pair_sums\":" << c_unique.size() << ",\n"
            << "\"pair_precompute_seconds\":" << build_seconds << ",\n"
            << "\"online_query_seconds\":" << query_seconds << ",\n"
            << "\"first_pair_tuples_tested\":" << a_tested << ",\n"
            << "\"third_pair_distinct_sum_probes\":" << c_probes << ",\n"
            << "\"second_pair_hash_hits\":" << hash_hits << ",\n"
            << "\"peak_rss_bytes\":" << usage.ru_maxrss;
        if (found) {
            std::array<Pair, 3> selected{chosen_a, chosen_b, chosen_c};
            out << ",\n\"pair_sums\":[";
            for (int group = 0; group < 3; ++group) {
                if (group) out << ",";
                write_point(out, selected[group].sum);
            }
            out << "],\n\"middle\":";
            write_point(out, chosen_middle);
            out << ",\n\"raw_points\":[";
            for (int group = 0; group < 3; ++group) {
                for (int position = 0; position < 2; ++position) {
                    if (group || position) out << ",";
                    const Pair& pair = selected[group];
                    const BasePoint& value = base[group][position ? pair.second : pair.first];
                    write_point(out, value.point);
                }
            }
            out << "],\n\"seed_masks\":[";
            for (int group = 0; group < 3; ++group) {
                for (int position = 0; position < 2; ++position) {
                    if (group || position) out << ",";
                    const Pair& pair = selected[group];
                    const BasePoint& value = base[group][position ? pair.second : pair.first];
                    out << value.mask;
                }
            }
            out << "],\n\"rotated_w\":[";
            for (int group = 0; group < 3; ++group) {
                for (int position = 0; position < 2; ++position) {
                    if (group || position) out << ",";
                    const Pair& pair = selected[group];
                    const BasePoint& value = base[group][position ? pair.second : pair.first];
                    out << value.w;
                }
            }
            out << "]";
        }
        out << "\n}\n";
        std::cout << (found ? "VERIFIED_RAW_RELATION" : "EXHAUSTED_NO_RELATION")
                  << " A=" << a_tested << " C=" << c_probes
                  << " hits=" << hash_hits << " query=" << query_seconds
                  << "s\n";
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
}
