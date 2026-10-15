// Known-answer vectors for the point arithmetic of the n = 131 walk, computed
// from cryptanalysis:ecc2k130/src/f131.h (mul, sqr, fromPolynomial) and
// include/packed131.h (inv131, sigma131, toPolynomial131), the header's own
// routines: nothing here re-derives the field.
//
//   g++ -O2 -mpclmul -DECC_HOST_CLMUL=1 -DECC_TABLE_PIVOT_BYTES=1 -I../../../ecc2k130 point_kat.cpp -o point_kat
//   ./point_kat 300 > point_kat.txt    (committed; CI regenerates and compares)
//
// Line i (hex limbs, polynomial basis unless noted):
//   a | inv(a) | sigma^k(a), k = i % 131 | toPolynomial(w) for the permuted-NB word w = b |
//   x1 y1 x2 y2 | x3 y3 = affine sum on y^2+xy=x^3+1 | x4 y4 = affine double of (x1, y1)
// The formulas are applied to arbitrary field elements (rational maps); the
// group law on actual curve points is checked separately.
#include <cstdio>
#include <cstdlib>
#include "src/f131.h"

using namespace f131;
using eccPacked131::P131;

static uint64_t s = 0x706f696e745f6b61ull;
static uint64_t next()
{
    s += 0x9E3779B97F4A7C15ull;
    uint64_t z = s;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}
static F131 rnd()
{
    F131 a{{next(), next(), next() & 7u}};
    return a;
}
static F131 toPoly(const F131 &nb) { return fromPacked(eccPacked131::toPolynomial131(toPacked(nb))); }
static F131 inv(const F131 &a) { return toPoly(fromPacked(eccPacked131::inv131(toPacked(fromPolynomial(a))))); }
static F131 sigma(const F131 &a, int k)
{
    return toPoly(fromPacked(eccPacked131::sigma131(toPacked(fromPolynomial(a)), k)));
}
static bool eq(const F131 &a, const F131 &b) { return a.w[0] == b.w[0] && a.w[1] == b.w[1] && a.w[2] == b.w[2]; }
static void pr(const F131 &a) { printf(" %016llx %016llx %016llx", (unsigned long long)a.w[0], (unsigned long long)a.w[1], (unsigned long long)a.w[2]); }

int main(int argc, char **argv)
{
    const int n = argc > 1 ? atoi(argv[1]) : 300;
    const F131 one{{1, 0, 0}};
    for (int i = 0; i < n; ++i) {
        F131 a = rnd();
        if (!(a.w[0] | a.w[1] | a.w[2])) a.w[0] = 1;
        const F131 ia = inv(a);
        if (!eq(mul(a, ia), one)) { fprintf(stderr, "self-check: a * inv(a) != 1\n"); return 1; }
        const F131 sk = sigma(a, i % 131);
        const F131 w = rnd(), tw = toPoly(w);
        if (!eq(fromPolynomial(tw), w)) { fprintf(stderr, "self-check: fromPolynomial(toPolynomial(w)) != w\n"); return 1; }
        const F131 x1 = rnd(), y1 = rnd(), x2 = rnd(), y2 = rnd();
        // sum
        const F131 lam = mul(add(y1, y2), inv(add(x1, x2)));
        const F131 x3 = add(add(sqr(lam), lam), add(x1, x2));
        const F131 y3 = add(add(mul(lam, add(x1, x3)), x3), y1);
        // double (a = 0)
        const F131 l2 = add(x1, mul(y1, inv(x1)));
        const F131 x4 = add(sqr(l2), l2);
        const F131 y4 = add(sqr(x1), mul(add(l2, one), x4));
        printf("%016llx %016llx %016llx", (unsigned long long)a.w[0], (unsigned long long)a.w[1], (unsigned long long)a.w[2]);
        pr(ia); pr(sk); pr(w); pr(tw); pr(x1); pr(y1); pr(x2); pr(y2); pr(x3); pr(y3); pr(x4); pr(y4);
        printf("\n");
    }
    return 0;
}
