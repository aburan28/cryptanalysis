#include "cryptanalysis/ca_group.h"
#include "ca_internal.h"
#include "test_util.h"

static void test_zp(void)
{
    ca_group g;
    CHECK(ca_group_zp_init(&g, 1000003, 0) == CA_OK);
    CHECK(ca_group_zp_init(&g, 1000004, 0) == CA_ERR_INVALID);
    CHECK(ca_group_zp_init(&g, 1000003, 7) == CA_ERR_INVALID);
    CHECK(ca_group_zp_init(&g, 1000003, 0) == CA_OK);
    uint64_t w[4] = {2, 0, 0, 0};
    ca_elem two, r;
    CHECK(ca_group_encode(&g, &two, w));
    ca_group_mul(&g, &r, &two, 20, NULL);
    ca_group_decode(&g, w, &r);
    CHECK_EQ_U64(w[0], ca_powmod(2, 20, 1000003));
    ca_group_mul(&g, &r, &two, 1000002, NULL);
    CHECK(ca_group_is_identity(&g, &r));
    CHECK_EQ_U64(ca_group_elem_order(&g, &two), 1000002);
    ca_group_div(&g, &r, &two, &two);
    CHECK(ca_group_is_identity(&g, &r));
    /* subgroup */
    CHECK(ca_group_zp_init(&g, 1000003, 500001) == CA_OK);
    ca_elem gen;
    CHECK(ca_group_find_generator(&g, &gen, 1) == CA_OK);
    CHECK_EQ_U64(ca_group_elem_order(&g, &gen), 500001);
}

static void test_ec(void)
{
    ca_group g;
    /* y^2 = x^3 + 2x + 3 over F_97 has 100 points */
    CHECK(ca_group_ec_init(&g, 97, 2, 3, 0) == CA_OK);
    uint64_t n;
    CHECK(ca_ec_count_points(97, 2, 3, &n, NULL) == CA_OK);
    CHECK_EQ_U64(n, 100);
    /* secp-like toy: check add/dbl consistency */
    uint64_t p = 1000003;
    CHECK(ca_group_ec_init(&g, p, 1, 7, 0) == CA_OK);
    CHECK(ca_ec_count_points(p, 1, 7, &n, NULL) == CA_OK);
    /* brute force count for validation */
    uint64_t cnt = 1;
    for (uint64_t x = 0; x < p; x++) {
        uint64_t rhs = ca_addmod(ca_mulmod(ca_addmod(ca_mulmod(x, x, p), 1, p), x, p), 7, p);
        cnt += (uint64_t)(1 + ca_legendre(rhs, p));
    }
    CHECK_EQ_U64(n, cnt);
    g.order = n;
    ca_elem P, Q, R, S;
    ca_ec_random_point(&g, &P, 7);
    CHECK(ca_group_is_valid(&g, &P));
    ca_group_mul(&g, &R, &P, n, NULL);
    CHECK(ca_group_is_identity(&g, &R));
    /* 2P via dbl == P + P via op */
    ca_group_dbl(&g, &Q, &P);
    ca_group_op(&g, &R, &P, &P);
    CHECK(ca_group_equal(&g, &Q, &R));
    /* associativity & batch op */
    ca_ec_random_point(&g, &Q, 8);
    ca_group_op(&g, &R, &P, &Q);
    ca_group_op(&g, &S, &Q, &P);
    CHECK(ca_group_equal(&g, &R, &S));
    ca_elem a[64], b[64], r[64], chk;
    uint64_t scratch[128];
    for (int i = 0; i < 64; i++) {
        ca_ec_random_point(&g, &a[i], 100 + i);
        ca_ec_random_point(&g, &b[i], 200 + i);
    }
    a[3] = b[3];                       /* doubling case */
    ca_group_inv(&g, &b[5], &a[5]);    /* inverse pair */
    ca_group_identity(&g, &a[7]);      /* identity */
    ca_group_identity(&g, &b[9]);
    ca_group_batch_op(&g, r, a, b, 64, scratch);
    for (int i = 0; i < 64; i++) {
        ca_group_op(&g, &chk, &a[i], &b[i]);
        CHECK(ca_group_equal(&g, &chk, &r[i]));
    }
    /* encode/decode round trip and on-curve check */
    uint64_t w[4];
    ca_group_decode(&g, w, &P);
    CHECK(ca_group_encode(&g, &R, w));
    CHECK(ca_group_equal(&g, &R, &P));
    w[1] ^= 1;
    CHECK(!ca_group_encode(&g, &R, w));
    /* elem order divides group order */
    uint64_t o = ca_group_elem_order(&g, &P);
    CHECK(o != 0 && n % o == 0);
    /* singular curve rejected */
    CHECK(ca_group_ec_init(&g, 97, 0, 0, 0) == CA_ERR_INVALID);
}

static void test_count_points_larger(void)
{
    /* Compare Mestre against Legendre-symbol brute force on a mid-size prime */
    uint64_t p = 100003;
    for (uint64_t b = 1; b < 6; b++) {
        uint64_t n, cnt = 1;
        ca_stats st = {0};
        CHECK(ca_ec_count_points(p, 3, b, &n, &st) == CA_OK);
        for (uint64_t x = 0; x < p; x++) {
            uint64_t rhs = ca_addmod(ca_mulmod(ca_addmod(ca_mulmod(x, x, p), 3, p), x, p), b, p);
            cnt += (uint64_t)(1 + ca_legendre(rhs, p));
        }
        CHECK_EQ_U64(n, cnt);
    }
    /* A 48-bit prime: check Hasse bound and that a random point is killed */
    uint64_t p2 = 281474976710597ULL; /* 2^48 - 59 */
    uint64_t n2;
    CHECK(ca_is_prime(p2));
    CHECK(ca_ec_count_points(p2, 1, 1, &n2, NULL) == CA_OK);
    uint64_t s = ca_isqrt(p2) + 1;
    CHECK(n2 + 2 * s >= p2 + 1 && n2 <= p2 + 1 + 2 * s);
    ca_group g;
    CHECK(ca_group_ec_init(&g, p2, 1, 1, n2) == CA_OK);
    for (int i = 0; i < 5; i++) {
        ca_elem P, R;
        ca_ec_random_point(&g, &P, 11 + i);
        ca_group_mul(&g, &R, &P, n2, NULL);
        CHECK(ca_group_is_identity(&g, &R));
    }
}

static void test_count_points_64bit(void)
{
    /* Primes above 2^63: the Hasse interval must not overflow. */
    uint64_t ps[2] = {ca_next_prime(1ULL << 63), 18446744073709551557ULL};
    for (int i = 0; i < 2; i++) {
        uint64_t p = ps[i], n;
        CHECK(ca_ec_count_points(p, 2, 3, &n, NULL) == CA_OK);
        uint64_t s = ca_isqrt(p) + 1;
        /* |n - (p+1)| <= 2 sqrt(p), evaluated without overflow */
        ca_u128 lo = (ca_u128)p + 1 - 2 * (ca_u128)s, hi = (ca_u128)p + 1 + 2 * (ca_u128)s;
        CHECK((ca_u128)n >= lo && (ca_u128)n <= hi);
        ca_group g;
        CHECK(ca_group_ec_init(&g, p, 2, 3, n) == CA_OK);
        for (int k = 0; k < 3; k++) {
            ca_elem P, R;
            ca_ec_random_point(&g, &P, 21 + k);
            ca_group_mul(&g, &R, &P, n, NULL);
            CHECK(ca_group_is_identity(&g, &R));
        }
    }
}

int main(void)
{
    test_zp();
    test_ec();
    test_count_points_larger();
    test_count_points_64bit();
    TEST_MAIN_END();
}
