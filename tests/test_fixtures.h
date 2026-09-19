/* Shared test fixtures: small groups with known structure. */
#ifndef CA_TEST_FIXTURES_H
#define CA_TEST_FIXTURES_H
#include "cryptanalysis/cryptanalysis.h"
#include "ca_internal.h"
#include "test_util.h"

/* Z_p^* with p = 2q+1 safe prime (q prime), subgroup of order q. */
static inline void fx_zp_safe(ca_group *g, ca_elem *gen, uint64_t p)
{
    uint64_t q = (p - 1) / 2;
    CHECK(ca_is_prime(p) && ca_is_prime(q));
    CHECK(ca_group_zp_init(g, p, q) == CA_OK);
    CHECK(ca_group_find_generator(g, gen, 1) == CA_OK);
}

/* Elliptic curve over F_p: starting from (a, b), scan b upwards until the
 * curve order has a prime factor q > p/8; use that order-q subgroup. */
static inline void fx_ec(ca_group *g, ca_elem *gen, uint64_t p, uint64_t a, uint64_t b)
{
    uint64_t n = 0, q = 0;
    for (int tries = 0; tries < 200; tries++, b++) {
        if (ca_ec_count_points(p, a, b, &n, NULL) != CA_OK) continue;
        ca_factorization f;
        ca_factorize(n, &f);
        q = f.f[f.count - 1].p;
        if (q > p / 8) break;
    }
    CHECK(q > p / 8);
    CHECK(ca_group_ec_init(g, p, a, b, q) == CA_OK);
    g->cofactor = n / q;
    CHECK(ca_group_find_generator(g, gen, 3) == CA_OK);
}

static inline void fx_instance(const ca_group *g, const ca_elem *gen, uint64_t x, ca_elem *h)
{
    ca_group_mul(g, h, gen, x, NULL);
}

#endif
