// Enumerate an explicit Koblitz x-subspace base using 128-bit polynomial arithmetic.
// This program only constructs and checks points. It is not a PDP or DLP solver.
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>

using U = unsigned __int128;

static U decimal(const std::string& s) {
    U value = 0;
    if (s.empty()) throw std::invalid_argument("empty decimal");
    for (char c : s) {
        if (c < '0' || c > '9') throw std::invalid_argument("invalid decimal");
        value = 10 * value + static_cast<unsigned>(c - '0');
    }
    return value;
}

static std::string hex(U v) {
    if (!v) return "0";
    std::string result;
    constexpr char digits[] = "0123456789abcdef";
    while (v) {
        result.push_back(digits[static_cast<unsigned>(v & 15)]);
        v >>= 4;
    }
    std::reverse(result.begin(), result.end());
    return result;
}

struct Field {
    int n;
    U modulus;

    U reduce(U a) const {
        for (int i = 127; i >= n; --i)
            if (a & (U(1) << i)) a ^= modulus << (i - n);
        return a;
    }

    U mul(U a, U b) const {
        U result = 0;
        while (b) {
            if (b & 1) result ^= a;
            b >>= 1;
            a <<= 1;
            if (a & (U(1) << n)) a ^= modulus;
        }
        return result;
    }

    U square(U a) const { return mul(a, a); }

    U inverse(U a) const {
        if (!a) throw std::invalid_argument("inverse of zero");
        U u = a, v = modulus, g1 = 1, g2 = 0;
        auto degree = [](U x) {
            int d = -1;
            while (x) { x >>= 1; ++d; }
            return d;
        };
        while (u != 1) {
            if (!u) throw std::invalid_argument("reducible field modulus");
            int j = degree(u) - degree(v);
            if (j < 0) { std::swap(u, v); std::swap(g1, g2); j = -j; }
            u ^= v << j;
            g1 ^= g2 << j;
        }
        U result = reduce(g1);
        if (mul(a, result) != 1) throw std::runtime_error("inverse verification failed");
        return result;
    }

    U trace(U a) const {
        U sum = 0;
        for (int i = 0; i < n; ++i) { sum ^= a; a = square(a); }
        if (sum > 1) throw std::runtime_error("bad field trace");
        return sum;
    }

    U half_trace(U a) const {
        U sum = 0;
        for (int i = 0; i < (n + 1) / 2; ++i) {
            sum ^= a;
            a = square(square(a));
        }
        return sum;
    }
};

struct Point { U x = 0, y = 0; bool infinity = true; };

struct Curve {
    Field f;
    bool valid(Point p) const {
        return p.infinity ||
            (f.square(p.y) ^ f.mul(p.x, p.y)) == (f.mul(f.square(p.x), p.x) ^ 1);
    }

    Point negate(Point p) const {
        if (!p.infinity) p.y ^= p.x;
        return p;
    }

    Point lift(U x) const {
        if (!x) return {0, 1, false};
        U inverse = f.inverse(x);
        U rhs = x ^ f.square(inverse);
        if (f.trace(rhs)) return {};
        U z = f.half_trace(rhs);
        if ((f.square(z) ^ z) != rhs)
            throw std::runtime_error("half trace did not solve the lift");
        Point p{x, f.mul(x, z), false};
        if (!valid(p)) throw std::runtime_error("lift is off curve");
        return p;
    }

    Point add(Point p, Point q) const {
        if (p.infinity) return q;
        if (q.infinity) return p;
        U slope = 0, x = 0, y = 0;
        if (p.x == q.x) {
            if (p.y != q.y || !p.x) return {};
            slope = p.x ^ f.mul(p.y, f.inverse(p.x));
            x = f.square(slope) ^ slope;
            y = f.square(p.x) ^ f.mul(slope ^ 1, x);
        } else {
            slope = f.mul(p.y ^ q.y, f.inverse(p.x ^ q.x));
            x = f.square(slope) ^ slope ^ p.x ^ q.x;
            y = f.mul(slope, p.x ^ x) ^ x ^ p.y;
        }
        Point result{x, y, false};
        if (!valid(result)) throw std::runtime_error("sum is off curve");
        return result;
    }

    Point quadruple(Point p) const { return add(add(p, p), add(p, p)); }
};

int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::invalid_argument("usage: explicit_base_frontier n l modulus_decimal");
        const int n = std::stoi(argv[1]), l = std::stoi(argv[2]);
        if (n != 13 && n != 83) throw std::invalid_argument("only audited n=13 or n=83");
        if (l < 1 || l > 19 || l >= n) throw std::invalid_argument("l out of bounded range");
        const U modulus = decimal(argv[3]);
        if (!(modulus & 1) || !(modulus & (U(1) << n)) || modulus >> (n + 1))
            throw std::invalid_argument("modulus has wrong degree");
        Curve curve{Field{n, modulus}};
        std::set<std::pair<U, U>> representatives;
        unsigned lifted = 0, vanished = 0, duplicate = 0;
        for (unsigned x = 0; x < (1u << l); ++x) {
            Point p = curve.lift(x);
            if (p.infinity) continue;
            lifted += x ? 2 : 1;
            Point q = curve.quadruple(p);
            if (q.infinity) { ++vanished; continue; }
            if (!curve.valid(q)) throw std::runtime_error("projected point off curve");
            U canonical_y = std::min(q.y, q.y ^ q.x);
            if (!representatives.insert({q.x, canonical_y}).second) ++duplicate;
            std::cout << "{\"x\":\"" << hex(p.x) << "\",\"y\":\"" << hex(p.y)
                      << "\",\"projected_x\":\"" << hex(q.x)
                      << "\",\"projected_y\":\"" << hex(canonical_y) << "\"}\n";
        }
        std::cout << "{\"summary\":true,\"n\":" << n << ",\"l\":" << l
                  << ",\"lifted_original_points\":" << lifted
                  << ",\"vanishing_abscissae\":" << vanished
                  << ",\"repeated_orbit_representatives\":" << duplicate
                  << ",\"signed_projected_B\":" << 2 * representatives.size()
                  << ",\"signed_columns\":" << representatives.size() << "}\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 2;
    }
}
