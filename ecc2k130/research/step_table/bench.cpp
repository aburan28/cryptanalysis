// Exact finite collision-work experiment on y^2+xy=x^3+1 over GF(2^23).
// This counts group operations, not GPU throughput. No unknown target input.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
#include "../../include/bitslice.h"
#include "../../generated/eccF23.h"

using U = uint32_t;
using V = uint64_t;
constexpr U M = 23, MASK = (1u << M) - 1, POLY = (1u << M) | 33u;
constexpr U ELL = 2095853, EIGEN = 93194, KNOWN = 65537;
V groupOps = 0;

void require(bool condition, const char *message) {
    if (!condition) throw std::runtime_error(message);
}
V mix64(V z) {
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
    return z ^ (z >> 31);
}
V random64(V &state) { state += 0x9e3779b97f4a7c15ull; return mix64(state); }
U modpow(U a, U e) {
    U r = 1;
    for (; e; e >>= 1, a = V(a) * a % ELL) if (e & 1) r = V(r) * a % ELL;
    return r;
}
U mul(U a, U b) {
    U r = 0;
    for (; b; b >>= 1) {
        if (b & 1) r ^= a;
        a <<= 1;
        if (a >> M) a ^= POLY;
    }
    return r;
}
U inverse(U a) {
    require(a != 0, "zero inverse");
    U b = POLY, u = 1, v = 0;
    while (a != 1) {
        int d = __builtin_clz(b) - __builtin_clz(a);
        if (d < 0) { std::swap(a, b); std::swap(u, v); d = -d; }
        a ^= b << d;
        u ^= v << d;
    }
    require((u & ~MASK) == 0, "unreduced inverse");
    return u;
}

// Byte lookup linear maps for basis changes and Frobenius; not group ops.
struct Map {
    U tab[3][256] = {};
    explicit Map(const std::array<U, M> &columns) {
        for (U b = 0; b < 3; ++b)
            for (U v = 1; v < 256; ++v) {
                const U bit = __builtin_ctz(v), idx = 8 * b + bit;
                tab[b][v] = tab[b][v & (v - 1)] ^ (idx < M ? columns[idx] : 0);
            }
    }
    U operator()(U x) const { return tab[0][x & 255] ^ tab[1][(x >> 8) & 255] ^ tab[2][x >> 16]; }
};
struct Point { U x = 0, y = 0; bool inf = true; };
bool equal(Point p, Point q) { return p.inf || q.inf ? p.inf == q.inf : p.x == q.x && p.y == q.y; }
bool onCurve(Point p) { return p.inf || (mul(p.y, p.y) ^ mul(p.x, p.y)) == (mul(mul(p.x, p.x), p.x) ^ 1); }
Point negate(Point p) { if (!p.inf) p.y ^= p.x; return p; }
Point doubleRaw(Point p) {
    if (p.inf || p.x == 0) return {};
    U lam = p.x ^ mul(p.y, inverse(p.x));
    U x = mul(lam, lam) ^ lam;
    return {x, mul(p.x, p.x) ^ mul(lam ^ 1, x), false};
}
Point add(Point p, Point q) {
    if (p.inf) return q;
    if (q.inf) return p;
    ++groupOps;
    if (p.x == q.x) return p.y == q.y ? doubleRaw(p) : Point{};
    U d = p.x ^ q.x, lam = mul(p.y ^ q.y, inverse(d));
    U x = mul(lam, lam) ^ lam ^ d;
    return {x, mul(lam, p.x ^ x) ^ x ^ p.y, false};
}
Point scalar(Point p, U n) {
    Point r;
    while (n) {
        if (n & 1) r = add(r, p);
        n >>= 1;
        if (n) { if (!p.inf) ++groupOps; p = doubleRaw(p); }
    }
    return r;
}
struct Tag { int h = -1, k = -1, eps = -1; };
bool opposite(Tag a, Tag b) { return a.h == b.h && a.k == b.k && (a.eps ^ b.eps) == 1; }
bool fruitless(Tag t, const std::array<Tag, 3> &history) {
    return opposite(t, history[0]) || (opposite(t, history[1]) && opposite(history[0], history[2]));
}
struct Orientation { U weight, phase, eps, key; };
struct Entry { U a, b; std::array<Point, M> points; };
struct Algebra {
    Map toPb, toCyclic;
    std::vector<Map> frobenius;
    std::array<U, M> spow{}, sinv{}, weightInv{};

    static std::array<U, M> pbColumns() {
        std::array<U, M> c{};
        for (U i = 0; i < M; ++i) c[i] = eccF23::GAMMA_TO_PB[i][0];
        return c;
    }
    static std::array<U, M> cyclicColumns() {
        std::array<U, M> c{}, logarithm{};
        U e = 1;
        for (U t = 0; t < M; ++t, e = 2 * e % (2 * M + 1)) logarithm[std::min(e, 2 * M + 1 - e) - 1] = t;
        for (U i = 0; i < M; ++i)
            for (U bit = 0; bit < M; ++bit)
                if ((eccF23::Z_TO_ONB[i][0] >> bit) & 1) c[i] |= 1u << logarithm[bit];
        return c;
    }
    Algebra() : toPb(pbColumns()), toCyclic(cyclicColumns()) {
        std::array<U, M> columns{};
        for (U i = 0; i < M; ++i) columns[i] = 1u << i;
        for (U k = 0; k < M; ++k) {
            frobenius.emplace_back(columns);
            for (U &x : columns) x = mul(x, x);
            spow[k] = modpow(EIGEN, k);
            sinv[k] = modpow(spow[k], ELL - 2);
        }
        for (U w = 1; w < M; ++w) for (U i = 1; i < M; ++i) if (w * i % M == 1) weightInv[w] = i;
    }
    Point frob(Point p, U k) const { return p.inf ? p : Point{frobenius[k](p.x), frobenius[k](p.y), false}; }
    Orientation orient(Point p) const {
        require(!p.inf, "cannot orient infinity");
        U x = toCyclic(p.x), y = toCyclic(p.y), w = __builtin_popcount(x), sum = 0;
        require(w > 0 && w < M, "subfield point has no phase");
        for (U t = x; t; t &= t - 1) sum += __builtin_ctz(t);
        U phase = (sum * weightInv[w]) % M;
        U key = ((x >> phase) | (x << (M - phase))) & MASK;
        U pivot = (31 - __builtin_clz(key) + phase) % M;
        return {w, phase, (y >> pivot) & 1u, key};
    }
    U normalize(U a, Orientation o) const {
        a = V(a) * sinv[o.phase] % ELL;
        return o.eps && a ? ELL - a : a;
    }
};
struct Config { const char *name; int branches; bool orbit; };
struct Seen { U a, b; };

void trial(const Algebra &algebra, Point base, Point target, const std::vector<Entry> &table,
           Config config, U index, V seed, U cap) {
    // A multiplicative Frobenius walk cannot give an independent relation
    // with itself. Multiple independent starts are essential for this control.
    struct Lane { Point p; U a, b; std::array<Tag, 3> history{}; };
    std::array<Lane, 8> lanes{};
    V state = mix64(seed ^ (V(index) * 0x9e3779b97f4a7c15ull));
    V startOps = 0, walkOps = 0;
    auto reseed = [&](Lane &lane) {
        const V before = groupOps;
        lane.a = random64(state) % ELL; lane.b = 1;
        lane.p = add(scalar(base, lane.a), target);
        lane.history = {};
        startOps += groupOps - before;
    };
    for (Lane &lane : lanes) reseed(lane);
    std::unordered_map<U, Seen> seen;
    std::vector<U> histogram(std::max(8, config.branches));
    U steps = 0, rejects = 0, badRelations = 0, signFlips = 0, restarts = 0, turn = 0;
    bool useful = false, exceptional = false;
    auto begun = std::chrono::steady_clock::now();
    for (;;) {
        Lane &lane = lanes[turn++ % lanes.size()];
        Point &p = lane.p;
        U &a = lane.a, &b = lane.b;
        auto &history = lane.history;
        if (p.inf || p.x == 0) {
            if (++restarts > 128) { exceptional = true; break; }
            reseed(lane); continue;
        }
        Orientation o = algebra.orient(p);
        U na = algebra.normalize(a, o), nb = algebra.normalize(b, o);
        auto old = seen.find(o.key);
        if (old != seen.end()) {
            require((V(na) + V(nb) * KNOWN) % ELL ==
                    (V(old->second.a) + V(old->second.b) * KNOWN) % ELL,
                    "collision does not satisfy the planted group equation");
            if (old->second.b != nb) { useful = true; break; }
            ++badRelations;
            if (++restarts > 128) { exceptional = true; break; }
            reseed(lane); continue;
        } else seen.emplace(o.key, Seen{na, nb});
        if (steps == cap) break;
        const V beforeStep = groupOps;
        if (!config.branches) {
            U j = 3 + ((o.weight / 2) & 7), factor = (1 + algebra.spow[j]) % ELL;
            ++histogram[j - 3];
            p = add(p, algebra.frob(p, j));
            a = V(a) * factor % ELL;
            b = V(b) * factor % ELL;
        } else {
            // Salt is held fixed per table seed, not per trail: coalescing
            // trails must use the same selector. Shared across branch counts.
            U h = (config.orbit ? mix64(o.key ^ seed) : o.weight / 2) & (config.branches - 1);
            Tag tag{int(h), int(o.phase), int(o.eps)};
            while (fruitless(tag, history)) { tag.h = (tag.h + 1) % config.branches; ++rejects; }
            history = {tag, history[0], history[1]};
            const Entry &entry = table[tag.h];
            Point delta = entry.points[o.phase];
            U da = V(entry.a) * algebra.spow[o.phase] % ELL;
            U db = V(entry.b) * algebra.spow[o.phase] % ELL;
            if (o.eps) { delta = negate(delta); da = da ? ELL - da : 0; db = db ? ELL - db : 0; ++signFlips; }
            p = add(p, delta);
            a = (a + da) % ELL;
            b = (b + db) % ELL;
            ++histogram[tag.h];
        }
        walkOps += groupOps - beforeStep;
        ++steps;
    }
    double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - begun).count();
    // Complete final point replay, on top of independent table/field checks.
    for (const Lane &lane : lanes) {
        require(onCurve(lane.p), "walk left the curve");
        require(equal(lane.p, scalar(base, (V(lane.a) + V(lane.b) * KNOWN) % ELL)), "coefficient replay failed");
    }
    std::cout << "{\"mode\":\"" << config.name << "\",\"trial\":" << index
              << ",\"useful\":" << (useful ? "true" : "false")
              << ",\"exceptional\":" << (exceptional ? "true" : "false")
              << ",\"censored\":" << (!useful && !exceptional ? "true" : "false")
              << ",\"steps\":" << steps << ",\"walkGroupOps\":" << walkOps
              << ",\"startGroupOps\":" << startOps << ",\"cycleAvoidance\":" << rejects
              << ",\"restarts\":" << restarts
              << ",\"fruitlessCollisions\":" << badRelations << ",\"negatedSteps\":" << signFlips
              << ",\"referenceSeconds\":" << seconds << ",\"branches\":[";
    for (size_t h = 0; h < histogram.size(); ++h) std::cout << (h ? "," : "") << histogram[h];
    std::cout << "]}\n";
}

int main(int argc, char **argv) {
    try {
        require(argc == 5, "usage: bench TABLE.txt TRIALS CAP SEED");
        U trials = std::stoul(argv[2]), cap = std::stoul(argv[3]);
        V seed = std::stoull(argv[4]);
        require(trials > 0 && trials <= 100000 && cap > 0 && cap <= 100000, "invalid trial bounds");
        Algebra algebra;
        std::ifstream input(argv[1]);
        U px, py, qx, qy;
        input >> std::hex >> px >> py >> qx >> qy;
        Point base{algebra.toPb(px), algebra.toPb(py), false}, target{algebra.toPb(qx), algebra.toPb(qy), false};
        require(onCurve(base) && !base.inf && equal(scalar(base, ELL), Point{}), "bad base");
        require(equal(target, scalar(base, KNOWN)), "target must equal [65537]P");
        require(equal(algebra.frob(base, 1), scalar(base, EIGEN)), "wrong Frobenius eigenvalue");
        std::vector<Entry> table;
        while (input) {
            U a, b, x, y;
            if (!(input >> std::dec >> a >> b >> std::hex >> x >> y)) break;
            Point p{algebra.toPb(x), algebra.toPb(y), false};
            require(a < ELL && b < ELL && onCurve(p) &&
                    equal(p, scalar(base, (V(a) + V(b) * KNOWN) % ELL)), "bad table entry");
            Entry entry{}; entry.a = a; entry.b = b;
            for (U k = 0; k < M; ++k) {
                entry.points[k] = algebra.frob(p, k);
                auto o = algebra.orient(entry.points[k]), original = algebra.orient(p);
                require(o.key == original.key && o.eps == original.eps && o.phase == (original.phase + k) % M,
                        "orientation is not Frobenius equivariant");
                require(algebra.orient(negate(entry.points[k])).eps != o.eps, "negation did not flip sign");
            }
            table.push_back(entry);
        }
        require(table.size() == 64 && input.eof(), "expected exactly 64 table rows");
        V rng = 731;
        for (int i = 0; i < 10000; ++i) {
            U a = (random64(rng) & MASK) | 1;
            require(mul(a, inverse(a)) == 1, "inverse failed");
            require(algebra.frobenius[1](a) == mul(a, a), "Frobenius failed");
        }
        const Config configs[] = {{"legacy", 0, false}, {"weight8", 8, false}, {"orbit8", 8, true},
                                  {"weight16", 16, false}, {"orbit16", 16, true},
                                  {"orbit32", 32, true}, {"orbit64", 64, true}};
        for (U i = 0; i < trials; ++i) for (Config config : configs) trial(algebra, base, target, table, config, i, seed, cap);
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
