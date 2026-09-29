// Portable native quotient-pair arithmetic on the exact n=83 known-log base.
// Receives frozen ONB target coordinates and affine schedule parameters from
// the Python driver. No target scalar or answer is linked into this program.
#if defined(__aarch64__)
#include <arm_neon.h>
#elif defined(__x86_64__)
#include <wmmintrin.h>
#endif
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#define ECC_BIG
#include "../../ecc2k130/runner/generated/eccF83.h"

using U = uint64_t;
using V = unsigned __int128;
#ifndef ECC2K83_ORBITS
#define ECC2K83_ORBITS 24097
#endif
constexpr unsigned N = 83, L = 166, K = ECC2K83_ORBITS;
constexpr U HIGH_MASK = (U(1) << 19) - 1;
constexpr V CYCLE_MASK = (V(1) << N) - 1;

void need(bool ok, const char *why) {
    if (!ok) throw std::runtime_error(why);
}
struct F { U a = 0, b = 0; };
bool operator==(F x, F y) { return x.a == y.a && x.b == y.b; }
bool zero(F x) { return !(x.a | x.b); }
F operator^(F x, F y) { return {x.a ^ y.a, x.b ^ y.b}; }
F one() { return {1, 0}; }

std::array<U, 2> clmul(U a, U b) {
#if defined(__aarch64__) && defined(__ARM_FEATURE_CRYPTO)
    uint64x2_t p = vreinterpretq_u64_p128(vmull_p64(a, b));
    return {vgetq_lane_u64(p, 0), vgetq_lane_u64(p, 1)};
#elif defined(__x86_64__) && defined(__PCLMUL__)
    __m128i left = _mm_cvtsi64_si128(static_cast<long long>(a));
    __m128i right = _mm_cvtsi64_si128(static_cast<long long>(b));
    __m128i product = _mm_clmulepi64_si128(left, right, 0x00);
    return {U(_mm_cvtsi128_si64(product)),
            U(_mm_cvtsi128_si64(_mm_srli_si128(product, 8)))};
#else
    U low = 0, high = 0;
    for (unsigned bit = 0; bit < 64; ++bit) {
        U mask = U(0) - ((b >> bit) & 1);
        low ^= (a << bit) & mask;
        if (bit) high ^= (a >> (64 - bit)) & mask;
    }
    return {low, high};
#endif
}
F reduce(U h0, U h1, U h2) {
    // z^83 = z^7 + z^4 + z^2 + 1. Product degree is at most 164.
    U q0 = (h1 >> 19) | (h2 << 45), q1 = h2 >> 19;
    U r0 = h0 ^ q0, r1 = (h1 & HIGH_MASK) ^ q1;
    for (unsigned s : {2u, 4u, 7u}) {
        r0 ^= q0 << s;
        r1 ^= (q1 << s) | (q0 >> (64 - s));
    }
    U overflow = r1 >> 19;
    r1 &= HIGH_MASK;
    r0 ^= overflow ^ (overflow << 2) ^ (overflow << 4) ^ (overflow << 7);
    return {r0, r1};
}
F mul(F x, F y) {
    auto p0 = clmul(x.a, y.a), p1 = clmul(x.b, y.b);
    auto cross = clmul(x.a ^ x.b, y.a ^ y.b);
    cross[0] ^= p0[0] ^ p1[0];
    cross[1] ^= p0[1] ^ p1[1];
    need(p1[1] == 0, "high product limb");
    return reduce(p0[0], p0[1] ^ cross[0], p1[0] ^ cross[1]);
}
F sqr(F x) {
    auto p0 = clmul(x.a, x.a), p1 = clmul(x.b, x.b);
    need(p1[1] == 0, "high square limb");
    return reduce(p0[0], p0[1], p1[0]);
}
F sigma(F x, unsigned k) {
    for (unsigned i = 0; i < k; ++i) x = sqr(x);
    return x;
}
F inv(F x) {
    need(!zero(x), "zero inverse");
    // Itoh-Tsujii chain for x^(2^83-2), using 82 = binary 1010010.
    F r = x;
    unsigned k = 1;
    for (int bit = 5; bit >= 0; --bit) {
        r = mul(sigma(r, k), r);
        k <<= 1;
        if ((82 >> bit) & 1) {
            r = mul(sqr(r), x);
            ++k;
        }
    }
    need(k == 82, "inverse chain exponent");
    return sqr(r);
}

struct Point { F x, y; bool inf = true; };
Point neg(Point p) { if (!p.inf) p.y = p.y ^ p.x; return p; }
bool on_curve(Point p) {
    return p.inf || (sqr(p.y) ^ mul(p.x, p.y)) == (mul(sqr(p.x), p.x) ^ one());
}
Point dbl(Point p) {
    if (p.inf || zero(p.x)) return {};
    F slope = p.x ^ mul(p.y, inv(p.x));
    F x = sqr(slope) ^ slope;
    return {x, sqr(p.x) ^ mul(slope ^ one(), x), false};
}
Point add(Point p, Point q) {
    if (p.inf) return q;
    if (q.inf) return p;
    if (p.x == q.x) return p.y == q.y ? dbl(p) : Point{};
    F d = p.x ^ q.x;
    F slope = mul(p.y ^ q.y, inv(d));
    F x = sqr(slope) ^ slope ^ d;
    return {x, mul(slope, p.x ^ x) ^ x ^ p.y, false};
}

F onb_to_pb(V coords) {
    F result{};
    while (coords) {
        unsigned bit = U(coords) ? unsigned(__builtin_ctzll(U(coords))) :
                                   64 + unsigned(__builtin_ctzll(U(coords >> 64)));
        result.a ^= eccF83::GAMMA_TO_PB[bit][0];
        result.b ^= eccF83::GAMMA_TO_PB[bit][1];
        coords &= coords - 1;
    }
    need((result.b & ~HIGH_MASK) == 0, "basis conversion overflow");
    return result;
}
V parse_hex(const std::string &s) {
    V value = 0;
    for (char c : s) {
        unsigned digit = c >= '0' && c <= '9' ? unsigned(c - '0') :
                         c >= 'a' && c <= 'f' ? unsigned(c - 'a' + 10) :
                         c >= 'A' && c <= 'F' ? unsigned(c - 'A' + 10) : 16;
        need(digit < 16, "invalid hex");
        value = (value << 4) | digit;
    }
    need((value >> N) == 0, "coordinate too wide");
    return value;
}
std::string hex(V value) {
    if (!value) return "0";
    std::string out;
    while (value) {
        unsigned digit = unsigned(value & 15);
        out.push_back("0123456789abcdef"[digit]);
        value >>= 4;
    }
    std::reverse(out.begin(), out.end());
    return out;
}

struct Keyer {
    std::array<V, N> pb_to_cycle{};
    std::array<unsigned, N> coord_at_cycle{};
#ifdef ECC2K83_FAST_KEYER
    std::array<std::array<V, 256>, (N + 7) / 8> pb_byte_to_cycle{};
#endif
    Keyer() {
        unsigned index = 1;
        for (unsigned j = 0; j < N; ++j) {
            coord_at_cycle[j] = index - 1;
            index = std::min(2 * index % 167, 167 - 2 * index % 167);
        }
        need(index == 1, "bad ONB coordinate cycle");
        std::array<unsigned, N> cycle_at_coord{};
        for (unsigned j = 0; j < N; ++j)
            cycle_at_coord[coord_at_cycle[j]] = j;
        for (unsigned i = 0; i < N; ++i) {
            V onb = V(eccF83::Z_TO_ONB[i][0]) |
                    (V(eccF83::Z_TO_ONB[i][1]) << 64);
            while (onb) {
                unsigned bit = U(onb) ? unsigned(__builtin_ctzll(U(onb))) :
                                        64 + unsigned(__builtin_ctzll(U(onb >> 64)));
                pb_to_cycle[i] ^= V(1) << cycle_at_coord[bit];
                onb &= onb - 1;
            }
        }
#ifdef ECC2K83_FAST_KEYER
        for (unsigned byte = 0; byte < pb_byte_to_cycle.size(); ++byte)
            for (unsigned value = 1; value < 256; ++value) {
                unsigned bit = 8 * byte + unsigned(__builtin_ctz(value));
                pb_byte_to_cycle[byte][value] =
                    pb_byte_to_cycle[byte][value & (value - 1)] ^
                    (bit < N ? pb_to_cycle[bit] : V(0));
            }
        // Check every basis vector and mixed coordinates before any query.
        for (unsigned bit = 0; bit < N; ++bit) {
            F x = bit < 64 ? F{U(1) << bit, 0} :
                             F{0, U(1) << (bit - 64)};
            need(cycle_bits_lookup(x) == cycle_bits_reference(x),
                 "byte-table basis conversion mismatch");
        }
        U seed = 0x83b1057ca11e531dull;
        for (unsigned i = 0; i < 256; ++i) {
            seed = seed * 6364136223846793005ull + 1;
            U lo = seed;
            seed = seed * 6364136223846793005ull + 1;
            F x{lo, seed & HIGH_MASK};
            need(cycle_bits_lookup(x) == cycle_bits_reference(x),
                 "byte-table mixed conversion mismatch");
        }
#endif
    }
    V cycle_bits_reference(F x) const {
        V bits = 0;
        U lo = x.a, hi = x.b;
        while (lo) {
            unsigned bit = unsigned(__builtin_ctzll(lo));
            bits ^= pb_to_cycle[bit];
            lo &= lo - 1;
        }
        while (hi) {
            unsigned bit = unsigned(__builtin_ctzll(hi));
            bits ^= pb_to_cycle[64 + bit];
            hi &= hi - 1;
        }
        return bits;
    }
#ifdef ECC2K83_FAST_KEYER
    V cycle_bits_lookup(F x) const {
        V coords = V(x.a) | (V(x.b) << 64);
        V bits = 0;
        for (unsigned byte = 0; byte < pb_byte_to_cycle.size(); ++byte)
            bits ^= pb_byte_to_cycle[byte][U(coords >> (8 * byte)) & 255];
        return bits;
    }
#endif
    V canonical_x(F x) const {
#ifdef ECC2K83_FAST_KEYER
        V bits = cycle_bits_lookup(x);
#else
        V bits = cycle_bits_reference(x);
#endif
        V best = bits;
        for (unsigned j = 1; j < N; ++j) {
            bits = ((bits << 1) | (bits >> (N - 1))) & CYCLE_MASK;
            if (bits < best) best = bits;
        }
        return best;
    }
};

std::vector<Point> load_base(const std::string &path, const Keyer &keyer) {
    std::ifstream in(path, std::ios::binary);
    need(bool(in), "missing base file");
    std::vector<Point> result(K * L);
    for (unsigned orbit = 0; orbit < K; ++orbit) {
        unsigned char record[32];
        in.read(reinterpret_cast<char *>(record), 32);
        need(bool(in), "short base file");
        auto key_bit = [&](unsigned i) -> unsigned {
            return (record[i >> 3] >> (i & 7)) & 1;
        };
        V xc = 0, yc = 0;
        for (unsigned j = 0; j < N; ++j) {
            xc |= V(key_bit(N + j)) << keyer.coord_at_cycle[j];
            yc |= V(key_bit(j)) << keyer.coord_at_cycle[j];
        }
        Point p{onb_to_pb(xc), onb_to_pb(yc), false};
        if (orbit < 8) need(on_curve(p), "base representative off curve");
        for (unsigned j = 0; j < N; ++j) {
            result[orbit * L + j] = p;
            result[orbit * L + N + j] = neg(p);
            p = {sqr(p.x), sqr(p.y), false};
        }
    }
    char extra;
    need(!in.read(&extra, 1), "base file has extra bytes");
    return result;
}

struct BatchScratch {
    std::vector<F> denominator, prefix;
    std::vector<unsigned char> exceptional;
    void resize(size_t count) {
        denominator.resize(count);
        prefix.resize(count);
        exceptional.resize(count);
    }
};

void batch_add(const std::vector<Point> &left, const std::vector<Point> &right,
               std::vector<Point> &out, BatchScratch &scratch) {
    need(left.size() == right.size(), "batch length mismatch");
    const size_t count = left.size();
    out.resize(count);
    scratch.resize(count);
    auto &denominator = scratch.denominator;
    auto &prefix = scratch.prefix;
    auto &exceptional = scratch.exceptional;
    F product = one();
    for (size_t i = 0; i < count; ++i) {
        exceptional[i] = left[i].inf || right[i].inf ||
                         left[i].x == right[i].x;
        denominator[i] = exceptional[i] ? one() : left[i].x ^ right[i].x;
        prefix[i] = product;
        product = mul(product, denominator[i]);
    }
    F inverse_product = inv(product);
    for (size_t i = count; i-- > 0;) {
        F inverse_denominator = mul(inverse_product, prefix[i]);
        inverse_product = mul(inverse_product, denominator[i]);
        if (exceptional[i]) {
            out[i] = add(left[i], right[i]);
            continue;
        }
        F slope = mul(left[i].y ^ right[i].y, inverse_denominator);
        F x = sqr(slope) ^ slope ^ denominator[i];
        out[i] = {x, mul(slope, left[i].x ^ x) ^ x ^ left[i].y, false};
    }
}

void batch_add(const std::vector<Point> &left, const std::vector<Point> &right,
               std::vector<Point> &out) {
    BatchScratch scratch;
    batch_add(left, right, out, scratch);
}

void self_test(const std::vector<Point> &base) {
    Point p = base[0], q = base[1], infinity{};
    need(on_curve(p) && on_curve(q), "sample base point off curve");
    need(mul(p.x, inv(p.x)) == one(), "field inverse mismatch");
    need(sqr(p.x) == mul(p.x, p.x), "field square mismatch");
    std::vector<Point> left{p, p, infinity, p, p};
    std::vector<Point> right{p, neg(p), p, infinity, q};
    std::vector<Point> out;
    batch_add(left, right, out);
    for (size_t i = 0; i < left.size(); ++i) {
        Point expected = add(left[i], right[i]);
        need(out[i].inf == expected.inf &&
             (out[i].inf || (out[i].x == expected.x && out[i].y == expected.y)),
             "batch exceptional addition mismatch");
    }
}

std::pair<U, U> unordered_pair(U rank) {
    U j = U((std::sqrt(8.0 * double(rank) + 1) - 1) / 2);
    while ((j + 1) * (j + 2) / 2 <= rank) ++j;
    while (j * (j + 1) / 2 > rank) --j;
    return {rank - j * (j + 1) / 2, j};
}
std::array<U, 3> cross_pair(U rank) {
    U pair_rank = rank / L, shift = rank % L;
    U j = U((1 + std::sqrt(1.0 + 8.0 * double(pair_rank))) / 2);
    while ((j + 1) * j / 2 <= pair_rank) ++j;
    while (j * (j - 1) / 2 > pair_rank) --j;
    return {pair_rank - j * (j - 1) / 2, j, shift};
}
U scheduled_rank(U position, U domain, U step, U offset) {
    return U((V(step) * position + offset) % domain);
}

struct Result {
    double table_seconds = 0, query_seconds = 0;
    V table_checksum = 0, query_checksum = 0;
    std::vector<std::string> table_first, query_first;
};
Result measure(const std::vector<Point> &base, Point target, const Keyer &keyer,
               U samples, U batch_size, U table_step, U table_offset,
               U query_step, U query_offset) {
    const U d_cross = U(K) * (K - 1) / 2 * L;
    const U pair_domain = U(base.size()) * (base.size() + 1) / 2;
    std::vector<Point> left, right, sums, complements, targets;
    left.reserve(batch_size); right.reserve(batch_size);
    targets.reserve(batch_size);
    Result result;
    auto start = std::chrono::steady_clock::now();
    for (U position = 0; position < samples; position += batch_size) {
        U count = std::min(batch_size, samples - position);
        left.clear(); right.clear();
        for (U i = 0; i < count; ++i) {
            U rank = scheduled_rank(position + i, d_cross,
                                    table_step, table_offset);
            auto pair = cross_pair(rank);
            left.push_back(base[pair[0] * L]);
            right.push_back(base[pair[1] * L + pair[2]]);
        }
        batch_add(left, right, sums);
        for (U i = 0; i < count; ++i) {
            need(!sums[i].inf, "cross-orbit zero pair");
            V key = keyer.canonical_x(sums[i].x);
            result.table_checksum ^= key;
            if (result.table_first.size() < 256) result.table_first.push_back(hex(key));
        }
    }
    result.table_seconds = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - start).count();
    start = std::chrono::steady_clock::now();
    for (U position = 0; position < samples; position += batch_size) {
        U count = std::min(batch_size, samples - position);
        left.clear(); right.clear(); targets.clear();
        for (U i = 0; i < count; ++i) {
            U rank = scheduled_rank(position + i, pair_domain,
                                    query_step, query_offset);
            auto pair = unordered_pair(rank);
            left.push_back(base[pair.first]);
            right.push_back(base[pair.second]);
        }
        batch_add(left, right, sums);
        for (U i = 0; i < count; ++i) {
            targets.push_back(target);
            sums[i] = neg(sums[i]);
        }
        batch_add(targets, sums, complements);
        for (U i = 0; i < count; ++i) {
            need(!complements[i].inf, "query complement infinity");
            V key = keyer.canonical_x(complements[i].x);
            result.query_checksum ^= key;
            if (result.query_first.size() < 256) result.query_first.push_back(hex(key));
        }
    }
    result.query_seconds = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - start).count();
    return result;
}

int main(int argc, char **argv) {
    try {
        need(argc == 11, "usage: native_n83_pairs BASE TARGET_X_ONB_HEX TARGET_Y_ONB_HEX SAMPLES BATCH TABLE_STEP TABLE_OFFSET QUERY_STEP QUERY_OFFSET REPETITIONS");
        Keyer keyer;
        auto base = load_base(argv[1], keyer);
        self_test(base);
        Point target{onb_to_pb(parse_hex(argv[2])),
                     onb_to_pb(parse_hex(argv[3])), false};
        need(on_curve(target), "target off curve");
        U samples = std::stoull(argv[4]), batch = std::stoull(argv[5]);
        U table_step = std::stoull(argv[6]), table_offset = std::stoull(argv[7]);
        U query_step = std::stoull(argv[8]), query_offset = std::stoull(argv[9]);
        U repetitions = std::stoull(argv[10]);
        need(samples > 0 && samples <= 10000000 && batch > 0 && batch <= 8192,
             "invalid benchmark size");
        need(repetitions > 0 && repetitions <= 9, "invalid repetitions");
        std::vector<Result> results;
        for (U rep = 0; rep < repetitions; ++rep)
            results.push_back(measure(base, target, keyer, samples, batch,
                                      table_step, table_offset,
                                      query_step, query_offset));
        for (const auto &r : results) {
            need(r.table_checksum == results[0].table_checksum &&
                 r.query_checksum == results[0].query_checksum,
                 "repetition key checksum mismatch");
        }
        std::cout << "{\"samples_per_phase\":" << samples
                  << ",\"batch_size\":" << batch
                  << ",\"repetitions\":" << repetitions
                  << ",\"actual_B\":" << base.size()
                  << ",\"table_seconds_each\":[";
        for (U i = 0; i < repetitions; ++i) {
            if (i) std::cout << ',';
            std::cout << std::setprecision(12) << results[i].table_seconds;
        }
        std::cout << "],\"query_seconds_each\":[";
        for (U i = 0; i < repetitions; ++i) {
            if (i) std::cout << ',';
            std::cout << std::setprecision(12) << results[i].query_seconds;
        }
        auto print_keys = [](const char *name, const std::vector<std::string> &keys) {
            std::cout << "],\"" << name << "\":[";
            for (size_t i = 0; i < keys.size(); ++i) {
                if (i) std::cout << ',';
                std::cout << '\"' << keys[i] << '\"';
            }
        };
        print_keys("table_first_256_xkeys_hex", results[0].table_first);
        print_keys("query_first_256_xkeys_hex", results[0].query_first);
        std::cout << "],\"table_xor_checksum_hex\":\""
                  << hex(results[0].table_checksum)
                  << "\",\"query_xor_checksum_hex\":\""
                  << hex(results[0].query_checksum)
                  << "\"}" << std::endl;
    } catch (const std::exception &e) {
        std::cerr << e.what() << std::endl;
        return 1;
    }
    return 0;
}
