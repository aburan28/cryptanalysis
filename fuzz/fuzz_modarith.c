/*
 * fuzz_modarith.c - libFuzzer harness for the 64-bit number-theory layer
 * (ca_modarith.h): powmod / invmod / gcd / isqrt / iroot / sqrtmod /
 * legendre / crt2 / factorize / mult_order / primitive_root / sieve and
 * the Montgomery context.
 *
 * The fuzzer's bytes are decoded into a handful of 64-bit operands; every
 * call is followed by the invariant that must hold for *any* input the
 * function accepts.  Preconditions the headers state (odd prime modulus
 * for Tonelli-Shanks and Montgomery, prime p for ca_mult_order, non-zero
 * modulus for the plain modular helpers) are enforced here instead of
 * being reported as bugs; see fuzz/README.md.
 */
#include "cryptanalysis/cryptanalysis.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* An invariant violation must look like a crash to libFuzzer. */
#define CHK(cond)                                                                                  \
    do {                                                                                           \
        if (!(cond)) __builtin_trap();                                                             \
    } while (0)

/* ---- byte-stream decoder ------------------------------------------------ */
typedef struct {
    const uint8_t *d;
    size_t n, i;
} fz;

static uint8_t fz_u8(fz *f) { return f->i < f->n ? f->d[f->i++] : 0; }
static uint64_t fz_u64(fz *f)
{
    uint64_t v = 0;
    for (int k = 0; k < 8; k++) v |= (uint64_t)fz_u8(f) << (8 * k);
    return v;
}

/* u128 power with early exit, used to check root bounds without overflow. */
static int pow_le(uint64_t base, unsigned k, uint64_t bound)
{
    ca_u128 p = 1;
    for (unsigned i = 0; i < k; i++) {
        p *= base;
        if (p > bound) return 0;
    }
    return 1;
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    /* Struct-style decode: four 64-bit operands plus two selector bytes. */
    if (size < 12) return 0;
    fz f = {data, size, 0};
    uint64_t a = fz_u64(&f);
    uint64_t b = fz_u64(&f);
    uint64_t c = fz_u64(&f);
    uint64_t m = fz_u64(&f);
    uint8_t sel = fz_u8(&f);
    uint8_t bits = fz_u8(&f);

    /* ---- gcd: the result divides both operands (and gcd(a,0) == a) ---- */
    uint64_t g = ca_gcd(a, b);
    if (a || b) {
        CHK(g != 0);
        CHK(a % g == 0 && b % g == 0);
    } else {
        CHK(g == 0);
    }
    CHK(ca_gcd(a, 0) == a);
    CHK(ca_gcd(0, b) == b);

    /* ---- isqrt: s^2 <= n < (s+1)^2 ------------------------------------- */
    uint64_t s = ca_isqrt(a);
    CHK((ca_u128)s * s <= a);
    CHK((ca_u128)(s + 1) * (s + 1) > a);

    /* ---- iroot: r^k <= n < (r+1)^k for 1 <= k <= 64 -------------------- */
    unsigned k = 1u + (sel & 63u);
    uint64_t r = ca_iroot(a, k);
    CHK(pow_le(r, k, a));
    CHK(r == UINT64_MAX || !pow_le(r + 1, k, a));

    /* ---- plain modular arithmetic (modulus 0 is not a modulus) --------- */
    if (m >= 1) {
        uint64_t pw = ca_powmod(a, b, m);
        CHK(pw < m);
        /* powmod(a, 0) == 1 mod m, and powmod(a,1) == a mod m */
        CHK(ca_powmod(a, 0, m) == (m == 1 ? 0u : 1u));
        CHK(ca_powmod(a, 1, m) == a % m);
        /* a^(b+1) == a^b * a */
        if (b != UINT64_MAX) CHK(ca_powmod(a, b + 1, m) == ca_mulmod(pw, a % m, m));

        uint64_t inv = ca_invmod(a, m);
        if (inv) {
            CHK(inv < m);
            /* the defining property of an inverse */
            CHK(ca_mulmod(a % m, inv, m) == 1 % m);
        } else {
            /* only reason to fail: a is not a unit mod m */
            CHK(m == 1 || ca_gcd(a % m, m) != 1);
        }
        if (m > 1 && ca_gcd(a % m, m) == 1) CHK(inv != 0);
    }

    /* ---- crt2: x == r1 (mod m1) and x == r2 (mod m2) ------------------- */
    {
        uint64_t m1 = (b & 0xFFFFFFFFu) | 1u; /* odd, non-zero */
        uint64_t m2 = (c & 0xFFFFFFFFu) | 1u;
        if (m1 > 1 && m2 > 1 && ca_gcd(m1, m2) == 1 && (ca_u128)m1 * m2 <= (ca_u128)UINT64_MAX) {
            uint64_t r1 = a % m1, r2 = m % m2;
            uint64_t x = ca_crt2(r1, m1, r2, m2);
            CHK(x % m1 == r1);
            CHK(x % m2 == r2);
            CHK(x < m1 * m2);
        }
    }

    /* ---- factorisation: multiplies back to n, all factors prime -------- */
    {
        /* `bits` selects how much of `a` to factor, so that the fuzzer can
         * reach both tiny and full 64-bit inputs cheaply. */
        unsigned w = 1u + (bits & 63u);
        uint64_t n = w >= 64 ? a : (a & ((1ULL << w) - 1));
        ca_factorization fac;
        ca_status rc = ca_factorize(n, &fac);
        if (n == 0) {
            CHK(rc == CA_ERR_INVALID);
        } else {
            CHK(rc == CA_OK);
            CHK(fac.count <= CA_MAX_FACTORS);
            ca_u128 prod = 1;
            for (unsigned i = 0; i < fac.count; i++) {
                CHK(fac.f[i].e >= 1);
                CHK(ca_is_prime(fac.f[i].p));
                if (i) CHK(fac.f[i - 1].p < fac.f[i].p); /* sorted, distinct */
                for (unsigned e = 0; e < fac.f[i].e; e++) prod *= fac.f[i].p;
            }
            CHK(prod == (ca_u128)n);
        }
    }

    /* ---- prime-only helpers -------------------------------------------- */
    {
        /* An odd prime derived from the input, small enough that
         * ca_next_prime, ca_mult_order and ca_primitive_root stay cheap
         * (they all factor p-1). */
        uint64_t seedp = 2 + (c & 0xFFFFFu);
        uint64_t p = ca_next_prime(seedp);
        CHK(p == 0 || (p > seedp && ca_is_prime(p)));
        if (p >= 3) {
            /* legendre is 0 exactly on multiples of p, else +-1 */
            int leg = ca_legendre(a, p);
            CHK(leg == -1 || leg == 0 || leg == 1);
            CHK((leg == 0) == (a % p == 0));
            uint64_t root;
            int ok = ca_sqrtmod_prime(a, p, &root);
            CHK(ok == (leg >= 0));
            if (ok) CHK(ca_mulmod(root, root, p) == a % p);

            /* multiplicative order divides p-1 and really is an order */
            if (a % p != 0) {
                uint64_t ord = ca_mult_order(a, p);
                CHK(ord != 0);
                CHK((p - 1) % ord == 0);
                CHK(ca_powmod(a, ord, p) == 1 % p);
            }
            /* smallest primitive root generates the whole group */
            if (sel & 0x40) {
                uint64_t pr = ca_primitive_root(p);
                CHK(pr != 0);
                CHK(ca_mult_order(pr, p) == p - 1);
            }

            /* ---- Montgomery agrees with the plain path ------------------ */
            ca_mont mo;
            CHK(ca_mont_init(&mo, p) == 1);
            uint64_t am = ca_mont_to(&mo, a), bm = ca_mont_to(&mo, b);
            CHK(ca_mont_from(&mo, am) == a % p);
            CHK(ca_mont_from(&mo, ca_mont_mul(&mo, am, bm)) == ca_mulmod(a % p, b % p, p));
            CHK(ca_mont_from(&mo, ca_mont_sqr(&mo, am)) == ca_mulmod(a % p, a % p, p));
            CHK(ca_mont_from(&mo, ca_mont_pow(&mo, am, b)) == ca_powmod(a, b, p));
            if (a % p != 0) {
                uint64_t im = ca_mont_inv(&mo, am);
                CHK(ca_mont_mul(&mo, am, im) == mo.r1);        /* a * a^-1 == 1 */
                CHK(ca_mont_from(&mo, im) == ca_invmod(a, p)); /* same as plain */
            }
        }
        /* ca_mont_init rejects even moduli and p < 3 */
        ca_mont mo2;
        uint64_t even = a & ~1ULL;
        CHK(ca_mont_init(&mo2, even) == 0);
    }

    /* ---- sieve: bounded so one input stays cheap ------------------------ */
    if (sel & 0x80) {
        uint64_t bound = b & 0xFFFu;
        size_t cnt = ca_sieve_primes(bound, NULL, 0);
        uint32_t *out = (uint32_t *)malloc((cnt ? cnt : 1) * sizeof(uint32_t));
        CHK(out != NULL);
        size_t cnt2 = ca_sieve_primes(bound, out, cnt);
        CHK(cnt2 == cnt);
        for (size_t i = 0; i < cnt; i++) {
            CHK(ca_is_prime(out[i]));
            CHK(out[i] <= bound);
            if (i) CHK(out[i - 1] < out[i]);
        }
        free(out);
    }
    return 0;
}
