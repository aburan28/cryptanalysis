/*
 * group_ec.c - short Weierstrass curves y^2 = x^3 + ax + b over F_p,
 * affine coordinates with Montgomery field arithmetic.
 *
 * Point layout: w[0] = x, w[1] = y (both Montgomery form), w[2] = 1 for
 * the point at infinity.
 */
#include "cryptanalysis/ca_group.h"
#include "ca_internal.h"

#define FX(e) ((e)->w[0])
#define FY(e) ((e)->w[1])
#define FINF(e) ((e)->w[2])

static inline uint64_t fadd(const ca_group *g, uint64_t a, uint64_t b) { return ca_addmod(a, b, g->p); }
static inline uint64_t fsub(const ca_group *g, uint64_t a, uint64_t b) { return ca_submod(a, b, g->p); }
static inline uint64_t fmul(const ca_group *g, uint64_t a, uint64_t b) { return ca_mont_mul(&g->mont, a, b); }
static inline uint64_t fsqr(const ca_group *g, uint64_t a) { return ca_mont_sqr(&g->mont, a); }
static inline uint64_t finv(const ca_group *g, uint64_t a) { return ca_mont_inv(&g->mont, a); }

static void ec_identity(const ca_group *g, ca_elem *r)
{
    (void)g;
    r->w[0] = r->w[1] = 0;
    r->w[2] = 1;
    r->w[3] = 0;
}

static int ec_is_identity(const ca_group *g, const ca_elem *a)
{
    (void)g;
    return FINF(a) != 0;
}

/* r = a + b given the already-inverted denominator (lambda numerator/denominator split). */
static inline void ec_add_with_inv(const ca_group *g, ca_elem *r, const ca_elem *a,
                                   const ca_elem *b, uint64_t lam)
{
    uint64_t x3 = fsub(g, fsub(g, fsqr(g, lam), FX(a)), FX(b));
    uint64_t y3 = fsub(g, fmul(g, lam, fsub(g, FX(a), x3)), FY(a));
    FX(r) = x3;
    FY(r) = y3;
    FINF(r) = 0;
    r->w[3] = 0;
}

static void ec_dbl(const ca_group *g, ca_elem *r, const ca_elem *a)
{
    if (FINF(a) || FY(a) == 0) { ec_identity(g, r); return; }
    uint64_t x2 = fsqr(g, FX(a));
    uint64_t num = fadd(g, fadd(g, fadd(g, x2, x2), x2), g->a_mont);
    uint64_t den = fadd(g, FY(a), FY(a));
    uint64_t lam = fmul(g, num, finv(g, den));
    ec_add_with_inv(g, r, a, a, lam);
}

static void ec_op(const ca_group *g, ca_elem *r, const ca_elem *a, const ca_elem *b)
{
    if (FINF(a)) { *r = *b; return; }
    if (FINF(b)) { *r = *a; return; }
    if (FX(a) == FX(b)) {
        if (FY(a) == FY(b)) { ec_dbl(g, r, a); return; }
        ec_identity(g, r);
        return;
    }
    uint64_t lam = fmul(g, fsub(g, FY(b), FY(a)), finv(g, fsub(g, FX(b), FX(a))));
    ec_add_with_inv(g, r, a, b, lam);
}

static void ec_inv(const ca_group *g, ca_elem *r, const ca_elem *a)
{
    if (FINF(a)) { *r = *a; return; }
    FX(r) = FX(a);
    FY(r) = FY(a) ? g->p - FY(a) : 0;
    FINF(r) = 0;
    r->w[3] = 0;
}

static int ec_equal(const ca_group *g, const ca_elem *a, const ca_elem *b)
{
    (void)g;
    if (FINF(a) || FINF(b)) return FINF(a) == FINF(b);
    return FX(a) == FX(b) && FY(a) == FY(b);
}

static uint64_t ec_hash(const ca_group *g, const ca_elem *a)
{
    (void)g;
    if (FINF(a)) return 0x9e3779b97f4a7c15ULL;
    return ca_mix64(FX(a) * 0x9E3779B97F4A7C15ULL ^ ca_mix64(FY(a)));
}

/*
 * Batched affine addition with Montgomery's simultaneous inversion trick:
 * one field inversion for n additions at the cost of 3(n-1) extra
 * multiplications.  Special cases (infinity, doubling, inverse pairs)
 * are handled inline so that the common path stays branch-light.
 */
static void ec_batch_op(const ca_group *g, ca_elem *r, const ca_elem *a, const ca_elem *b,
                        size_t n, uint64_t *scratch)
{
    if (n == 0) return;
    uint64_t *den = scratch;       /* n denominators */
    uint64_t *pre = scratch + n;   /* n prefix products */
    const uint64_t one = g->mont.r1;
    for (size_t i = 0; i < n; i++) {
        uint64_t d;
        if (FINF(&a[i]) || FINF(&b[i])) d = one;
        else if (FX(&a[i]) == FX(&b[i])) {
            if (FY(&a[i]) == FY(&b[i]) && FY(&a[i]) != 0) d = fadd(g, FY(&a[i]), FY(&a[i]));
            else d = one;
        } else d = fsub(g, FX(&b[i]), FX(&a[i]));
        den[i] = d;
        pre[i] = i ? fmul(g, pre[i - 1], d) : d;
    }
    uint64_t inv = finv(g, pre[n - 1]);
    for (size_t i = n; i-- > 0;) {
        uint64_t di = i ? fmul(g, inv, pre[i - 1]) : inv; /* den[i]^{-1} */
        inv = fmul(g, inv, den[i]);
        const ca_elem *A = &a[i], *B = &b[i];
        if (FINF(A)) { r[i] = *B; continue; }
        if (FINF(B)) { r[i] = *A; continue; }
        if (FX(A) == FX(B)) {
            if (FY(A) == FY(B) && FY(A) != 0) {
                uint64_t x2 = fsqr(g, FX(A));
                uint64_t num = fadd(g, fadd(g, fadd(g, x2, x2), x2), g->a_mont);
                ec_add_with_inv(g, &r[i], A, A, fmul(g, num, di));
            } else {
                ec_identity(g, &r[i]);
            }
            continue;
        }
        uint64_t lam = fmul(g, fsub(g, FY(B), FY(A)), di);
        ec_add_with_inv(g, &r[i], A, B, lam);
    }
}

static int ec_on_curve_words(const ca_group *g, uint64_t x, uint64_t y)
{
    uint64_t xm = ca_mont_to(&g->mont, x), ym = ca_mont_to(&g->mont, y);
    uint64_t lhs = fsqr(g, ym);
    uint64_t rhs = fadd(g, fmul(g, fadd(g, fsqr(g, xm), g->a_mont), xm), g->b_mont);
    return lhs == rhs;
}

static int ec_encode(const ca_group *g, ca_elem *r, const uint64_t *words)
{
    if (words[2]) { ec_identity(g, r); return 1; }
    if (words[0] >= g->p || words[1] >= g->p) return 0;
    if (!ec_on_curve_words(g, words[0], words[1])) return 0;
    FX(r) = ca_mont_to(&g->mont, words[0]);
    FY(r) = ca_mont_to(&g->mont, words[1]);
    FINF(r) = 0;
    r->w[3] = 0;
    return 1;
}

static void ec_decode(const ca_group *g, uint64_t *words, const ca_elem *a)
{
    if (FINF(a)) { words[0] = words[1] = 0; words[2] = 1; words[3] = 0; return; }
    words[0] = ca_mont_from(&g->mont, FX(a));
    words[1] = ca_mont_from(&g->mont, FY(a));
    words[2] = 0;
    words[3] = 0;
}

static int ec_is_valid(const ca_group *g, const ca_elem *a)
{
    if (FINF(a)) return 1;
    if (FX(a) >= g->p || FY(a) >= g->p) return 0;
    uint64_t lhs = fsqr(g, FY(a));
    uint64_t rhs = fadd(g, fmul(g, fadd(g, fsqr(g, FX(a)), g->a_mont), FX(a)), g->b_mont);
    return lhs == rhs;
}

/* Canonical representative of {P, -P}: the one whose (Montgomery) y is
 * the smaller of y and p - y.  Montgomery form is a bijection commuting
 * with negation, so this is a valid canonical choice. */
static int ec_canonicalize(const ca_group *g, ca_elem *a)
{
    if (FINF(a) || FY(a) == 0) return 0;
    uint64_t ny = g->p - FY(a);
    if (ny < FY(a)) { FY(a) = ny; return 1; }
    return 0;
}

static const ca_group_vtable ec_vt = {
    ec_op, ec_dbl, ec_inv, ec_identity, ec_is_identity, ec_equal, ec_hash,
    ec_batch_op, ec_encode, ec_decode, ec_is_valid, ec_canonicalize,
};

ca_status ca_group_ec_init(ca_group *g, uint64_t p, uint64_t a, uint64_t b, uint64_t order)
{
    memset(g, 0, sizeof(*g));
    if (p < 5 || !ca_is_prime(p)) {
        ca_set_error("p=%llu is not a prime > 3", (unsigned long long)p);
        return CA_ERR_INVALID;
    }
    a %= p;
    b %= p;
    /* discriminant 4a^3 + 27b^2 != 0 */
    uint64_t d = ca_addmod(ca_mulmod(4, ca_powmod(a, 3, p), p),
                           ca_mulmod(27, ca_mulmod(b, b, p), p), p);
    if (d == 0) {
        ca_set_error("curve is singular");
        return CA_ERR_INVALID;
    }
    g->vt = &ec_vt;
    g->kind = CA_GROUP_EC;
    g->p = p;
    g->a = a;
    g->b = b;
    g->order = order;
    ca_mont_init(&g->mont, p);
    g->a_mont = ca_mont_to(&g->mont, a);
    g->b_mont = ca_mont_to(&g->mont, b);
    g->cofactor = 0;
    return CA_OK;
}

void ca_ec_endo(const ca_group *g, ca_elem *r, const ca_elem *a)
{
    if (g->endo_kind == 0 || FINF(a)) {
        *r = *a;
        return;
    }
    if (g->endo_kind == 1) {
        /* j = 0: psi(x, y) = (beta * x, -y), beta a cube root of unity */
        FX(r) = fmul(g, g->endo_c_mont, FX(a));
        FY(r) = FY(a) ? g->p - FY(a) : 0;
    } else {
        /* j = 1728: psi(x, y) = (-x, i * y), i = sqrt(-1) */
        FX(r) = FX(a) ? g->p - FX(a) : 0;
        FY(r) = fmul(g, g->endo_c_mont, FY(a));
    }
    FINF(r) = 0;
    r->w[3] = 0;
}

int ca_ec_lift_x(const ca_group *g, ca_elem *r, uint64_t x)
{
    x %= g->p;
    uint64_t rhs = ca_addmod(ca_mulmod(ca_addmod(ca_mulmod(x, x, g->p), g->a, g->p), x, g->p),
                             g->b, g->p);
    uint64_t y;
    if (!ca_sqrtmod_prime(rhs, g->p, &y)) return 0;
    if (y > g->p - y) y = g->p - y;
    const uint64_t w[4] = {x, y, 0, 0};
    return ec_encode(g, r, w);
}

void ca_ec_random_point(const ca_group *g, ca_elem *r, uint64_t seed)
{
    ca_rng rng;
    ca_rng_seed(&rng, ca_seed_or_random(seed));
    while (1) {
        uint64_t x = ca_rng_below(&rng, g->p);
        if (ca_ec_lift_x(g, r, x)) {
            if (ca_rng_next(&rng) & 1) ec_inv(g, r, r);
            return;
        }
    }
}

/* ---- Mestre's point counting ------------------------------------------ */

/* All k in [lo, lo+width) with k*P == T, appended to out (up to cap).
 * Returns the number found (may exceed cap; only cap are stored). */
static size_t ec_interval_all(const ca_group *g, const ca_elem *P, const ca_elem *T, uint64_t lo,
                              uint64_t width, uint64_t *out, size_t cap, ca_stats *st)
{
    uint64_t m = ca_isqrt(width) + 1;
    ca_htab tab;
    if (ca_htab_init(&tab, (size_t)m) != CA_OK) return 0;
    ca_elem cur;
    ec_identity(g, &cur);
    uint64_t small_order = 0;
    for (uint64_t j = 0; j < m; j++) {
        uint64_t old;
        if (ca_htab_insert(&tab, ec_hash(g, &cur), j, 0, &old, NULL) == 1) {
            /* cur == old*P: P has small order j - old */
            small_order = j - old;
            break;
        }
        ec_op(g, &cur, &cur, P);
        if (st) st->group_ops++;
    }
    size_t found = 0;
    if (small_order) {
        /* k*P == T: find k0 < small_order with k0*P == T then enumerate. */
        ec_identity(g, &cur);
        uint64_t k0 = small_order;
        for (uint64_t j = 0; j < small_order; j++) {
            if (ec_equal(g, &cur, T)) {
                k0 = j;
                break;
            }
            ec_op(g, &cur, &cur, P);
        }
        if (k0 < small_order) {
            /* smallest k >= lo with k == k0 (mod small_order) */
            uint64_t so = small_order;
            ca_u128 k = (ca_u128)lo + (k0 + so - lo % so) % so;
            for (; k < (ca_u128)lo + width; k += so) {
                if (found < cap) out[found] = (uint64_t)k;
                found++;
            }
        }
        ca_htab_free(&tab);
        return found;
    }
    /* giant steps: R = T - (lo + i m) P; if R == jP then k = lo + i m + j */
    ca_elem mP, negmP, base, R;
    ca_group_mul(g, &mP, P, m, st ? &st->group_ops : NULL);
    ec_inv(g, &negmP, &mP);
    /* base = -lo * P */
    ca_group_mul(g, &base, P, lo, NULL);
    ec_inv(g, &base, &base);
    ec_op(g, &R, T, &base); /* T - lo P */
    uint64_t steps = m ? width / m + 1 : 1;
    for (uint64_t i = 0; i < steps; i++) {
        uint64_t j;
        if (ca_htab_find(&tab, ec_hash(g, &R), &j, NULL)) {
            /* verify */
            ca_elem chk;
            ca_group_mul(g, &chk, P, j, NULL);
            if (ec_equal(g, &chk, &R)) {
                ca_u128 k = (ca_u128)lo + (ca_u128)i * m + j;
                if (k < (ca_u128)lo + width) {
                    if (found < cap) out[found] = (uint64_t)k;
                    found++;
                }
            }
        }
        ec_op(g, &R, &R, &negmP);
        if (st) st->group_ops++;
    }
    ca_htab_free(&tab);
    return found;
}

static ca_status ec_count_once(const ca_group *g, uint64_t *order, ca_stats *st,
                               uint64_t seed, int *ambiguous)
{
    /* Hasse interval [p + 1 - 2 sqrt(p), p + 1 + 2 sqrt(p)], computed in
     * 128 bits so that primes up to 2^64 - 59 (whose p + 1 still fits a
     * uint64_t) are handled without overflow. */
    uint64_t p = g->p;
    uint64_t s = ca_isqrt(p);
    while ((ca_u128)s * s < p) s++; /* ceil(sqrt(p)) */
    ca_u128 lo128 = (ca_u128)p + 1 - 2 * (ca_u128)s;
    uint64_t lo = lo128 < 1 ? 1 : (uint64_t)lo128;
    uint64_t width = 4 * s + 1;
    ca_rng rng;
    ca_rng_seed(&rng, seed);
    enum { CAP = 4096 };
    uint64_t *cands = malloc(CAP * sizeof(uint64_t));
    uint64_t *cur = malloc(CAP * sizeof(uint64_t));
    if (!cands || !cur) { free(cands); free(cur); return CA_ERR_NOMEM; }
    size_t ncand = 0;
    int have = 0;
    *ambiguous = 0;
    ca_status rc = CA_ERR_NOT_FOUND;
    for (int tries = 0; tries < 24; tries++) {
        ca_elem P, T;
        ca_ec_random_point(g, &P, ca_rng_next(&rng));
        ec_identity(g, &T);
        size_t n = ec_interval_all(g, &P, &T, lo, width, cur, CAP, st);
        if (n == 0 || n > CAP) continue;
        if (!have) {
            memcpy(cands, cur, n * sizeof(uint64_t));
            ncand = n;
            have = 1;
        } else {
            size_t w = 0;
            for (size_t i = 0; i < ncand; i++) {
                for (size_t j = 0; j < n; j++) {
                    if (cands[i] == cur[j]) { cands[w++] = cands[i]; break; }
                }
            }
            ncand = w;
        }
        if (ncand == 1) {
            *order = cands[0];
            rc = CA_OK;
            break;
        }
        if (ncand == 0) { rc = CA_ERR_INTERNAL; break; }
    }
    if (rc != CA_OK && have && ncand > 1) *ambiguous = 1;
    free(cands);
    free(cur);
    return rc;
}

ca_status ca_ec_count_points(uint64_t p, uint64_t a, uint64_t b, uint64_t *order, ca_stats *st)
{
    ca_group g;
    ca_status rc = ca_group_ec_init(&g, p, a, b, 0);
    if (rc != CA_OK) return rc;
    ca_stats local = {0};
    if (!st) st = &local;
    double t0 = ca_now();
    if (p < 2000) {
        /* brute force: count x with x^3+ax+b a square */
        uint64_t cnt = 1;
        for (uint64_t x = 0; x < p; x++) {
            uint64_t rhs = ca_addmod(ca_mulmod(ca_addmod(ca_mulmod(x, x, p), a % p, p), x, p), b % p, p);
            int l = ca_legendre(rhs, p);
            cnt += (uint64_t)(1 + l);
        }
        *order = cnt;
        st->seconds += ca_now() - t0;
        return CA_OK;
    }
    int amb = 0;
    rc = ec_count_once(&g, order, st, 0x5eed5eedULL ^ p, &amb);
    if (rc != CA_OK && amb) {
        /* Use the quadratic twist: #E + #E' = 2p + 2. */
        uint64_t d = 2;
        while (ca_legendre(d, p) != -1) d++;
        uint64_t d2 = ca_mulmod(d, d, p), d3 = ca_mulmod(d2, d, p);
        ca_group tw;
        if (ca_group_ec_init(&tw, p, ca_mulmod(a, d2, p), ca_mulmod(b, d3, p), 0) == CA_OK) {
            uint64_t ot;
            int amb2 = 0;
            if (ec_count_once(&tw, &ot, st, 0x7715ULL ^ p, &amb2) == CA_OK) {
                /* #E + #E' = 2p + 2; 128-bit so p > 2^63 does not wrap */
                *order = (uint64_t)((ca_u128)2 * p + 2 - ot);
                rc = CA_OK;
            }
        }
    }
    st->seconds += ca_now() - t0;
    return rc;
}
