// Portable bounded witness producer. Python independently verifies its output.
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <new>

namespace
{
using U = std::uint64_t;
struct Point {
    U x, y, inf;
};
struct Result {
    U status, signs_checked, lifts_checked, sign_mask;
    Point points[8], steps[8];
    U slopes[8];
};
constexpr Point infinity{0, 0, 1};
bool same(Point p, Point q) { return p.x == q.x && p.y == q.y && p.inf == q.inf; }
unsigned degree(U a)
{
    unsigned n = 0;
    while (a >>= 1) ++n;
    return n;
}
U remainder(U a, U b)
{
    const unsigned d = degree(b);
    while (a && degree(a) >= d) a ^= b << (degree(a) - d);
    return a;
}
U gcd(U a, U b)
{
    while (b) {
        const U r = remainder(a, b);
        a = b;
        b = r;
    }
    return a;
}
struct Field {
    unsigned n;
    U modulus, limit, b;
    U mul(U a, U c) const
    {
        U r = 0;
        while (c) {
            if (c & 1) r ^= a;
            c >>= 1;
            a <<= 1; // degree <= 63, so the reduction bit fits in uint64_t.
            if (a & limit) a ^= modulus;
        }
        return r;
    }
    U sqr(U a) const { return mul(a, a); }
    U power(U a, U exponent) const
    {
        U r = 1;
        while (exponent) {
            if (exponent & 1) r = mul(r, a);
            a = sqr(a);
            exponent >>= 1;
        }
        return r;
    }
    U inverse(U a) const { return power(a, limit - 2); } // callers exclude zero
    bool irreducible() const
    {
        U z = 2;
        for (unsigned i = 0; i < n / 2; ++i) {
            z = sqr(z);
            if (gcd(modulus, z ^ 2) != 1) return false;
        }
        return true;
    }
    bool on_curve(Point p) const
    {
        if (p.inf) return p.inf == 1 && p.x == 0 && p.y == 0;
        return p.x < limit && p.y < limit && (sqr(p.y) ^ mul(p.x, p.y)) == (mul(sqr(p.x), p.x) ^ b);
    }
    bool lift(U x, Point &p) const
    {
        if (!x) {
            U y = b;
            for (unsigned i = 1; i < n; ++i) y = sqr(y);
            p = {0, y, 0};
            return true;
        }
        const U c = x ^ mul(b, inverse(sqr(x)));
        U trace = 0, z = c;
        for (unsigned i = 0; i < n; ++i) {
            trace ^= z;
            z = sqr(z);
        }
        if (trace) return false;
        U h = 0;
        z = c;
        for (unsigned i = 0; i < (n + 1) / 2; ++i) {
            h ^= z;
            z = sqr(sqr(z));
        }
        p = {x, mul(x, h), 0};
        return on_curve(p);
    }
    Point add(Point p, Point q, U &slope) const
    {
        slope = 0;
        if (p.inf) return q;
        if (q.inf) return p;
        if (p.x == q.x) {
            if (p.y != q.y || p.x == 0) return infinity;
            slope = p.x ^ mul(p.y, inverse(p.x));
            const U x = sqr(slope) ^ slope;
            return {x, sqr(p.x) ^ mul(slope ^ 1, x), 0};
        }
        slope = mul(p.y ^ q.y, inverse(p.x ^ q.x));
        const U x = sqr(slope) ^ slope ^ p.x ^ q.x;
        return {x, mul(slope, p.x ^ x) ^ x ^ p.y, 0};
    }
};
} // namespace

extern "C" {
std::size_t replay_result_size() { return sizeof(Result); }
void *replay_create(U n, U modulus, U b)
{
    if (n < 3 || n > 63 || !(n & 1) || degree(modulus) != n || !(modulus & 1) || !b ||
        b >= (U{1} << n))
        return nullptr;
    Field f{static_cast<unsigned>(n), modulus, U{1} << n, b};
    if (!f.irreducible()) return nullptr;
    return new (std::nothrow) Field(f);
}
void replay_destroy(void *context) { delete static_cast<Field *>(context); }
void replay_find(const void *context, U m, U ell, U assignment, U target_x, U target_y, U max_signs,
                 Result *out)
{
    if (!out) return;
    *out = {};
    out->status = 3;
    if (!context) return;
    const auto &f = *static_cast<const Field *>(context);
    if (!m || m > 8 || !ell || ell > f.n || m * ell > 64 || max_signs > 256) return;
    const unsigned nvars = static_cast<unsigned>(m * ell);
    if (nvars < 64 && assignment >> nvars) return;
    const Point target{target_x, target_y, 0};
    if (!f.on_curve(target)) return;
    out->status = 2;
    if (!max_signs) return;
    Point lifted[8]{};
    for (unsigned i = 0; i < m; ++i) {
        const U x = (assignment >> (i * ell)) & ((U{1} << ell) - 1);
        ++out->lifts_checked;
        if (!f.lift(x, lifted[i])) {
            out->status = 0;
            return;
        }
    }
    for (U signs = 0; signs < std::min(max_signs, U{1} << m); ++signs) {
        Point sum = infinity;
        for (unsigned i = 0; i < m; ++i) {
            Point p = lifted[i];
            if ((signs >> i) & 1) p.y ^= p.x;
            out->points[i] = p;
            sum = f.add(sum, p, out->slopes[i]);
            out->steps[i] = sum;
        }
        ++out->signs_checked;
        if (same(sum, target)) {
            out->status = 1;
            out->sign_mask = signs;
            return;
        }
    }
    out->status = max_signs >= (U{1} << m) ? 0 : 2;
}
} // extern C
