/*
 * group_zp.c - the multiplicative group (Z/pZ)^* in Montgomery form.
 */
#include "cryptanalysis/ca_group.h"
#include "ca_internal.h"

static void zp_op(const ca_group *g, ca_elem *r, const ca_elem *a, const ca_elem *b)
{
    r->w[0] = ca_mont_mul(&g->mont, a->w[0], b->w[0]);
}

static void zp_dbl(const ca_group *g, ca_elem *r, const ca_elem *a)
{
    r->w[0] = ca_mont_sqr(&g->mont, a->w[0]);
}

static void zp_inv(const ca_group *g, ca_elem *r, const ca_elem *a)
{
    r->w[0] = ca_mont_inv(&g->mont, a->w[0]);
}

static void zp_identity(const ca_group *g, ca_elem *r)
{
    r->w[0] = g->mont.r1;
    r->w[1] = r->w[2] = r->w[3] = 0;
}

static int zp_is_identity(const ca_group *g, const ca_elem *a)
{
    return a->w[0] == g->mont.r1;
}

static int zp_equal(const ca_group *g, const ca_elem *a, const ca_elem *b)
{
    (void)g;
    return a->w[0] == b->w[0];
}

static uint64_t zp_hash(const ca_group *g, const ca_elem *a)
{
    (void)g;
    return ca_mix64(a->w[0] ^ 0x5bd1e995ULL);
}

/* The scratch pointer is non-const because the vtable slot is shared with the
 * elliptic-curve implementation, which writes into the scratch space. */
/* NOLINTBEGIN(readability-non-const-parameter) */
static void zp_batch_op(const ca_group *g, ca_elem *r, const ca_elem *a, const ca_elem *b,
                        size_t n, uint64_t *scratch)
{
    (void)scratch;
    for (size_t i = 0; i < n; i++) r[i].w[0] = ca_mont_mul(&g->mont, a[i].w[0], b[i].w[0]);
}
/* NOLINTEND(readability-non-const-parameter) */

static int zp_encode(const ca_group *g, ca_elem *r, const uint64_t *words)
{
    uint64_t x = words[0] % g->p;
    if (x == 0) return 0;
    r->w[0] = ca_mont_to(&g->mont, x);
    r->w[1] = r->w[2] = r->w[3] = 0;
    return 1;
}

static void zp_decode(const ca_group *g, uint64_t *words, const ca_elem *a)
{
    words[0] = ca_mont_from(&g->mont, a->w[0]);
    words[1] = words[2] = words[3] = 0;
}

static int zp_is_valid(const ca_group *g, const ca_elem *a)
{
    return a->w[0] != 0 && a->w[0] < g->p;
}

static const ca_group_vtable zp_vt = {
    zp_op, zp_dbl, zp_inv, zp_identity, zp_is_identity, zp_equal, zp_hash,
    zp_batch_op, zp_encode, zp_decode, zp_is_valid, NULL,
};

ca_status ca_group_zp_init(ca_group *g, uint64_t p, uint64_t order)
{
    memset(g, 0, sizeof(*g));
    if (p < 3 || !ca_is_prime(p)) {
        ca_set_error("p=%llu is not an odd prime", (unsigned long long)p);
        return CA_ERR_INVALID;
    }
    if (order == 0) order = p - 1;
    if ((p - 1) % order != 0) {
        ca_set_error("order %llu does not divide p-1", (unsigned long long)order);
        return CA_ERR_INVALID;
    }
    g->vt = &zp_vt;
    g->kind = CA_GROUP_ZP;
    g->p = p;
    g->order = order;
    g->cofactor = (p - 1) / order;
    ca_mont_init(&g->mont, p);
    return CA_OK;
}
