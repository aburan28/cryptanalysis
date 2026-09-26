// Synthetic GF(2^131) pair-sum materializer. CPU only; no walk or solver.
// Polynomial z^131+z^13+z^2+z+1. Native ARM carryless products where available.
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include <unistd.h>
#ifdef __aarch64__
#include <arm_neon.h>
#endif

using U = uint64_t;
struct F { U a = 0, b = 0, c = 0; };
struct Point { F x, y; bool inf = true; };
using Scalar = std::array<U, 3>;

void need(bool ok, const char *why) { if (!ok) throw std::runtime_error(why); }
F operator^(F x, F y) { return {x.a ^ y.a, x.b ^ y.b, x.c ^ y.c}; }
bool operator==(F x, F y) { return x.a == y.a && x.b == y.b && x.c == y.c; }
bool zero(F x) { return (x.a | x.b | x.c) == 0; }
std::array<U, 2> clmul(U a, U b) {
#ifdef __aarch64__
    uint64x2_t p = vreinterpretq_u64_p128(vmull_p64(a, b));
    return {vgetq_lane_u64(p, 0), vgetq_lane_u64(p, 1)};
#else
    U lo = 0, hi = 0;
    while (b) { unsigned i = __builtin_ctzll(b); lo ^= a << i; if (i) hi ^= a >> (64 - i); b &= b - 1; }
    return {lo, hi};
#endif
}
F reduce(U h0, U h1, U h2, U h3, U h4) {
    // H = product >> 131. Fold H*(1+z+z^2+z^13), then its at-most 12
    // overflow bits. No field-sized loop and no data-dependent reduction.
    U q0 = (h2 >> 3) | (h3 << 61), q1 = (h3 >> 3) | (h4 << 61), q2 = h4 >> 3;
    F r{h0 ^ q0, h1 ^ q1, (h2 & 7) ^ q2};
    for (unsigned s : {1u, 2u, 13u}) {
        r.a ^= q0 << s;
        r.b ^= (q1 << s) | (q0 >> (64 - s));
        r.c ^= (q2 << s) | (q1 >> (64 - s));
    }
    U excess = r.c >> 3;
    r.c &= 7;
    r.a ^= excess ^ (excess << 1) ^ (excess << 2) ^ (excess << 13);
    return r;
}
F mul(F x, F y) {
    auto p0 = clmul(x.a, y.a), p1 = clmul(x.b, y.b);
    auto cross = clmul(x.a ^ x.b, y.a ^ y.b);
    cross[0] ^= p0[0] ^ p1[0]; cross[1] ^= p0[1] ^ p1[1];
    U h0 = p0[0], h1 = p0[1] ^ cross[0], h2 = p1[0] ^ cross[1], h3 = p1[1], h4 = 0;
    // The top limbs are only three bits. Six masked shifts finish 131x131.
    for (unsigned i = 0; i < 3; ++i) {
        U mx = U(0) - ((x.c >> i) & 1), my = U(0) - ((y.c >> i) & 1);
        h2 ^= ((y.a & mx) ^ (x.a & my)) << i;
        h3 ^= ((y.b & mx) ^ (x.b & my)) << i;
        h4 ^= (y.c & mx) << i;
        if (i) {
            h3 ^= ((y.a & mx) ^ (x.a & my)) >> (64 - i);
            h4 ^= ((y.b & mx) ^ (x.b & my)) >> (64 - i);
        }
    }
    return reduce(h0, h1, h2, h3, h4);
}
F square(F x) {
    auto lo = clmul(x.a, x.a), hi = clmul(x.b, x.b);
    U top = (x.c & 1) | ((x.c & 2) << 1) | ((x.c & 4) << 2);
    return reduce(lo[0], lo[1], hi[0], hi[1], top);
}
F inverse(F x) {
    need(!zero(x), "zero inverse");
    // Itoh-Tsujii: a^(2^130-1), then square. 130 = binary 10000010.
    F r = x;
    unsigned k = 1;
    for (int bit = 6; bit >= 0; --bit) {
        F t = r;
        for (unsigned j = 0; j < k; ++j) t = square(t);
        r = mul(r, t); k *= 2;
        if ((130 >> bit) & 1) { r = mul(square(r), x); ++k; }
    }
    return square(r);
}
bool equal(Point p, Point q) { return p.inf || q.inf ? p.inf == q.inf : p.x == q.x && p.y == q.y; }
Point negate(Point p) { if (!p.inf) p.y = p.y ^ p.x; return p; }
bool onCurve(Point p) { return p.inf || (square(p.y) ^ mul(p.x, p.y)) == (mul(square(p.x), p.x) ^ F{1, 0, 0}); }
Point doubled(Point p) {
    if (p.inf || zero(p.x)) return {};
    F lam = p.x ^ mul(p.y, inverse(p.x)), x = square(lam) ^ lam;
    return {x, square(p.x) ^ mul(lam ^ F{1, 0, 0}, x), false};
}
Point add(Point p, Point q) {
    if (p.inf) return q;
    if (q.inf) return p;
    if (p.x == q.x) return p.y == q.y ? doubled(p) : Point{};
    F d = p.x ^ q.x, lam = mul(p.y ^ q.y, inverse(d)), x = square(lam) ^ lam ^ d;
    return {x, mul(lam, p.x ^ x) ^ x ^ p.y, false};
}
Point scalar(Point p, Scalar s) {
    Point r;
    for (int bit = 130; bit >= 0; --bit) {
        r = doubled(r);
        if ((s[bit / 64] >> (bit % 64)) & 1) r = add(r, p);
    }
    return r;
}
std::array<uint32_t, 9> pack(Point p) {
    if (p.inf) return {0, 0, 0, 0, 0, 0, 0, 0, 0x80000000u};
    return {uint32_t(p.x.a), uint32_t(p.x.a >> 32), uint32_t(p.x.b), uint32_t(p.x.b >> 32),
            uint32_t(p.y.a), uint32_t(p.y.a >> 32), uint32_t(p.y.b), uint32_t(p.y.b >> 32),
            uint32_t(p.x.c | (p.y.c << 3))};
}
template <class T> T read(std::istream &in) {
    T value{}; in.read(reinterpret_cast<char *>(&value), sizeof(value));
    need(bool(in), "short input"); return value;
}
void pwriteAll(int fd, const void *data, size_t bytes, U offset) {
    const char *p = static_cast<const char *>(data);
    while (bytes) {
        ssize_t n = pwrite(fd, p, bytes, off_t(offset));
        if (n < 0 && errno == EINTR) continue;
        need(n > 0, "output write failed");
        p += n; bytes -= size_t(n); offset += U(n);
    }
}
void selfTest(const char *path) {
    std::ifstream input(path, std::ios::binary);
    U count = read<U>(input);
    for (U i = 0; i < count; ++i) {
        F a = read<F>(input), b = read<F>(input), product = read<F>(input), inv = read<F>(input);
        need(mul(a, b) == product, "independent field product mismatch");
        need(square(a) == mul(a, a), "square mismatch");
        if (!zero(a)) need(inverse(a) == inv && mul(a, inv) == F{1, 0, 0}, "independent inverse mismatch");
    }
    std::cout << "PASS independent polynomial field vectors: " << count << std::endl;
}

int main(int argc, char **argv) {
    try {
        need(argc == 7, "usage: large_pairs INPUT VECTORS OUTPUT BASE_OUTPUT THREADS LIMIT(0=all)");
        const uint16_t endian = 1;
        need(*reinterpret_cast<const uint8_t *>(&endian) == 1, "little endian host required");
        selfTest(argv[2]);
        unsigned threads = unsigned(std::stoul(argv[5]));
        need(threads > 0 && threads <= 32, "invalid thread count");
        std::ifstream input(argv[1], std::ios::binary);
        U branches = read<U>(input);
        need(branches >= 8 && branches <= 256, "invalid branch count");
        Point base{read<F>(input), read<F>(input), false}, target{read<F>(input), read<F>(input), false};
        Scalar ell = read<Scalar>(input);
        need(onCurve(base) && !zero(base.x) && scalar(base, ell).inf, "invalid subgroup generator");
        need(equal(scalar(base, Scalar{65537, 0, 0}), target), "target is not the fixed synthetic target");
        std::vector<Point> bases(branches);
        for (U h = 0; h < branches; ++h) {
            Scalar a = read<Scalar>(input), b = read<Scalar>(input), effective = read<Scalar>(input);
            bases[h] = add(scalar(base, a), scalar(target, b));
            need(!bases[h].inf && onCurve(bases[h]) && equal(bases[h], scalar(base, effective)), "base entry equation failed");
        }
        std::vector<Point> points(2 * 131 * branches);
        const int baseFd = open(argv[4], O_CREAT | O_EXCL | O_WRONLY, 0600);
        need(baseFd >= 0, "base-point output already exists or cannot be created");
        for (U h = 0; h < branches; ++h) {
            Point p = bases[h];
            for (U k = 0; k < 131; ++k) {
                points[2 * (k * branches + h)] = p;
                points[2 * (k * branches + h) + 1] = negate(p);
                p = {square(p.x), square(p.y), false};
            }
            need(equal(p, bases[h]), "Frobenius closure failed");
        }
        std::vector<std::array<uint32_t, 9>> basePacked;
        basePacked.reserve(points.size());
        for (const Point &p : points) {
            need(onCurve(p), "conjugate left the curve");
            basePacked.push_back(pack(p));
        }
        pwriteAll(baseFd, basePacked.data(), basePacked.size() * 36, 0);
        need(fsync(baseFd) == 0, "base-point fsync failed"); close(baseFd);
        const U total = U(points.size()) * (points.size() + 1) / 2;
        const U limit = std::stoull(argv[6]), count = limit ? std::min(limit, total) : total;
        const int fd = open(argv[3], O_CREAT | O_EXCL | O_WRONLY, 0600);
        need(fd >= 0, "output already exists or cannot be created");
        constexpr U CHUNK = 65536, BATCH = 1024;
        std::atomic<U> next{0}, done{0}, infinities{0}, checked{0};
        std::atomic<bool> failed{false};
        std::mutex outputMutex;
        std::string error;
        auto begun = std::chrono::steady_clock::now();
        auto worker = [&] {
            try {
                std::vector<std::array<uint32_t, 9>> output(CHUNK);
                std::array<F, BATCH> denominator{}, prefix{};
                std::array<U, BATCH> left{}, right{};
                while (!failed) {
                    U begin = next.fetch_add(CHUNK);
                    if (begin >= count) break;
                    U end = std::min(count, begin + CHUNK);
                    U v = U((std::sqrt(8.0 * double(begin) + 1) - 1) / 2);
                    while ((v + 1) * (v + 2) / 2 <= begin) ++v;
                    while (v * (v + 1) / 2 > begin) --v;
                    U u = begin - v * (v + 1) / 2, infinityCount = 0;
                    for (U start = begin; start < end; start += BATCH) {
                        U n = std::min(BATCH, end - start);
                        F product{1, 0, 0};
                        for (U i = 0; i < n; ++i) {
                            left[i] = u; right[i] = v;
                            prefix[i] = product;
                            F d = points[u].x ^ points[v].x;
                            denominator[i] = zero(d) ? F{1, 0, 0} : d;
                            product = mul(product, denominator[i]);
                            if (++u > v) { ++v; u = 0; }
                        }
                        F inv = inverse(product);
                        for (U i = n; i-- > 0;) {
                            F di = mul(inv, prefix[i]);
                            inv = mul(inv, denominator[i]);
                            Point p = points[left[i]], q = points[right[i]], r;
                            F d = p.x ^ q.x;
                            if (zero(d)) r = p.y == q.y ? doubled(p) : Point{};
                            else {
                                F lam = mul(p.y ^ q.y, di), x = square(lam) ^ lam ^ d;
                                r = {x, mul(lam, p.x ^ x) ^ x ^ p.y, false};
                            }
                            need(onCurve(r), "pair sum left the curve");
                            if (i == 0) need(equal(r, add(p, q)), "batch inversion differs from individual addition");
                            infinityCount += r.inf;
                            output[start - begin + i] = pack(r);
                        }
                    }
                    pwriteAll(fd, output.data(), size_t(end - begin) * 36, begin * 36);
                    infinities += infinityCount; checked += end - begin;
                    U completed = done.fetch_add(end - begin) + end - begin;
                    if (completed == count || completed / (CHUNK * 64) != (completed - (end - begin)) / (CHUNK * 64)) {
                        std::lock_guard<std::mutex> lock(outputMutex);
                        double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - begun).count();
                        std::cout << "progress " << completed << '/' << count << " entries, "
                                  << double(completed) * 36 / 1e9 << " GB, " << sec << " s" << std::endl;
                    }
                }
            } catch (const std::exception &e) {
                failed = true; std::lock_guard<std::mutex> lock(outputMutex); error = e.what();
            }
        };
        std::vector<std::thread> pool;
        for (unsigned i = 0; i < threads; ++i) pool.emplace_back(worker);
        for (auto &thread : pool) thread.join();
        if (failed) { close(fd); throw std::runtime_error(error); }
        need(done == count && checked == count, "incomplete materialization");
        need(fsync(fd) == 0, "fsync failed"); close(fd);
        if (count == total) need(infinities == points.size() / 2, "unexpected infinity count");
        double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - begun).count();
        std::cout << "{\"entries\":" << count << ",\"bytes\":" << count * 36
                  << ",\"onCurveChecked\":" << checked << ",\"infinityEntries\":" << infinities
                  << ",\"seconds\":" << sec << ",\"complete\":" << (count == total ? "true" : "false") << "}" << std::endl;
    } catch (const std::exception &e) { std::cerr << e.what() << std::endl; return 1; }
}
