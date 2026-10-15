// Known-answer vectors for the Rust port of ecc2k130/src/f131.h (mul, sqr,
// fromPolynomial).  Built against the committed header itself, so the port is
// held to the walk's own host arithmetic, not to a re-derivation.
//
//   g++ -O2 -mpclmul -DECC_TABLE_PIVOT_BYTES=1 -I../../ecc2k130 f131_kat.cpp -o f131_kat
//   ./f131_kat 400 > f131_kat.txt   (committed; CI regenerates and compares)
//
// Each line: a0 a1 a2 b0 b1 b2 | mul(a,b) | sqr(a) | fromPolynomial(a), hex limbs.
#include <cstdio>
#include <cstdlib>
#include "src/f131.h"

static uint64_t s = 0x6b61745f6631333ull; // SplitMix64 state
static uint64_t next()
{
    s += 0x9E3779B97F4A7C15ull;
    uint64_t z = s;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}
static f131::F131 elem(int i)
{
    // the first 262 vectors are the unit vectors z^k (twice, as a and as b)
    f131::F131 a{{0, 0, 0}};
    if (i < 131) {
        a.w[i / 64] = 1ull << (i % 64);
        return a;
    }
    a.w[0] = next();
    a.w[1] = next();
    a.w[2] = next() & 7u;
    return a;
}
int main(int argc, char **argv)
{
    const int n = argc > 1 ? atoi(argv[1]) : 2000;
    for (int i = 0; i < n; ++i) {
        const f131::F131 a = elem(i), b = elem(i < 131 ? 131 + i : i);
        const f131::F131 m = f131::mul(a, b), q = f131::sqr(a), c = f131::fromPolynomial(a);
        printf("%016llx %016llx %016llx %016llx %016llx %016llx %016llx %016llx %016llx %016llx "
               "%016llx %016llx %016llx %016llx %016llx\n",
               (unsigned long long)a.w[0], (unsigned long long)a.w[1], (unsigned long long)a.w[2],
               (unsigned long long)b.w[0], (unsigned long long)b.w[1], (unsigned long long)b.w[2],
               (unsigned long long)m.w[0], (unsigned long long)m.w[1], (unsigned long long)m.w[2],
               (unsigned long long)q.w[0], (unsigned long long)q.w[1], (unsigned long long)q.w[2],
               (unsigned long long)c.w[0], (unsigned long long)c.w[1], (unsigned long long)c.w[2]);
    }
    return 0;
}
