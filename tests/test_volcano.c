#include "test_fixtures.h"

/* Every vertex a distinct j, levels in [0, depth] that change by at most one
 * per edge, the floor exactly the one-kernel curves, the root counted. */
static void check_walk(uint64_t p, uint64_t a, uint64_t b, unsigned ell, unsigned want_depth)
{
    ca_volcano vo;
    CHECK(ca_volcano_walk(p, a, b, 0, ell, 2 * want_depth + 2, 0, &vo) == CA_OK);
    CHECK(vo.depth == want_depth);
    CHECK(vo.count > 1);
    unsigned seen_floor = 0, seen_crater = 0;
    for (uint32_t i = 0; i < vo.count; i++) {
        const ca_volcano_vertex *v = &vo.v[i];
        for (uint32_t k = i + 1; k < vo.count; k++) CHECK(vo.v[k].j != v->j);
        if (v->level < 0) continue;
        CHECK(v->level <= (int32_t)vo.depth);
        if (vo.depth > 0) CHECK((v->level == (int32_t)vo.depth) == (v->kernels == 1));
        seen_floor += v->level == (int32_t)vo.depth;
        seen_crater += v->level == 0;
        for (uint32_t k = 0; k < v->n_nbrs; k++) {
            int32_t lw = vo.v[v->nbrs[k]].level;
            if (lw >= 0) CHECK(lw - v->level <= 1 && v->level - lw <= 1);
        }
    }
    CHECK(seen_floor > 0 && seen_crater > 0);
    ca_volcano_free(&vo);
}

int main(void)
{
    /* Depth and crater shape from the trace alone. */
    unsigned depth;
    int crater;
    /* p = 1090993606999, #E = 1090993806052: D = -54^2 * 1482974187, 3 | D_K */
    CHECK(ca_volcano_depth(1090993606999ULL, 1090993806052ULL, 3, &depth, &crater) == CA_OK);
    CHECK(depth == 3 && crater == 0);
    /* p = 714095314843, #E = 714094928137: D = -27^2 * 3713084987, split */
    CHECK(ca_volcano_depth(714095314843ULL, 714094928137ULL, 3, &depth, &crater) == CA_OK);
    CHECK(depth == 3 && crater == 1);
    CHECK(ca_volcano_depth(1000003, 1000003 + 1 + 5000, 3, &depth, &crater) == CA_ERR_INVALID);

    /* Velu maps are homomorphisms onto their codomains, for l = 2 and 3. */
    uint64_t p = 1000033, a = 5, b = 17; /* p = 1 mod 4 */
    for (unsigned ell = 2; ell <= 3; ell++) {
        uint64_t xs[CA_VOLCANO_MAX_NBRS];
        unsigned nk = ca_isogeny_kernels(p, a, b, ell, xs);
        for (unsigned q = 0; q < nk; q++) {
            uint64_t a2, b2;
            CHECK(ca_velu_codomain(p, a, b, ell, xs[q], &a2, &b2) == CA_OK);
            ca_group g, h;
            CHECK(ca_group_ec_init(&g, p, a, b, 0) == CA_OK);
            CHECK(ca_group_ec_init(&h, p, a2, b2, 0) == CA_OK);
            for (uint64_t s = 1; s <= 8; s++) {
                ca_elem P, Q, S, iP, iQ, iS, sum;
                uint64_t w[4], m[3], ws[4];
                ca_ec_random_point(&g, &P, s);
                ca_ec_random_point(&g, &Q, s + 100);
                ca_group_op(&g, &S, &P, &Q);
                ca_group_decode(&g, w, &P);
                CHECK(ca_velu_map(p, a, b, ell, xs[q], w, m) == CA_OK);
                uint64_t mw[4] = {m[0], m[1], m[2], 0};
                CHECK(ca_group_encode(&h, &iP, mw));
                ca_group_decode(&g, w, &Q);
                CHECK(ca_velu_map(p, a, b, ell, xs[q], w, m) == CA_OK);
                uint64_t mq[4] = {m[0], m[1], m[2], 0};
                CHECK(ca_group_encode(&h, &iQ, mq));
                ca_group_decode(&g, ws, &S);
                CHECK(ca_velu_map(p, a, b, ell, xs[q], ws, m) == CA_OK);
                uint64_t ms[4] = {m[0], m[1], m[2], 0};
                CHECK(ca_group_encode(&h, &iS, ms));
                ca_group_op(&h, &sum, &iP, &iQ);
                CHECK(ca_group_equal(&h, &sum, &iS));
            }
        }
    }

    /* Walks: a depth-1 3-volcano over p = 1 mod 4, and the two depth-3
     * volcanoes of the aburan28/crypto volcano-rho study. */
    check_walk(1000033, 5, 17, 3, 1);
    check_walk(1090993606999ULL, 690282649366ULL, 1050606678233ULL, 3, 3);
    check_walk(714095314843ULL, 354455170800ULL, 66680642576ULL, 3, 3);

    /* The study's curve A volcano is whole within radius 8: 2 + 6 + 18 + 54. */
    ca_volcano vo;
    CHECK(ca_volcano_walk(1090993606999ULL, 690282649366ULL, 1050606678233ULL, 1090993806052ULL, 3,
                          8, 0, &vo) == CA_OK);
    unsigned per[4] = {0};
    for (uint32_t i = 0; i < vo.count; i++)
        if (vo.v[i].level >= 0) per[vo.v[i].level]++;
    CHECK(vo.count == 80);
    CHECK(per[0] == 2 && per[1] == 6 && per[2] == 18 && per[3] == 54);
    ca_volcano_free(&vo);

    /* A whole 2-volcano of depth 3 over p = 1 mod 8 (curve C of the study):
     * ramified crater, a binary tree, 2 + 4 + 8 + 16. */
    CHECK(ca_volcano_walk(146833024135393ULL, 14391545271884ULL, 141956518099848ULL, 0, 2, 8, 0,
                          &vo) == CA_OK);
    CHECK(vo.order == 146833030777920ULL && vo.depth == 3 && vo.crater == 0);
    unsigned per2[4] = {0};
    for (uint32_t i = 0; i < vo.count; i++)
        if (vo.v[i].level >= 0) per2[vo.v[i].level]++;
    CHECK(vo.count == 30);
    CHECK(per2[0] == 2 && per2[1] == 4 && per2[2] == 8 && per2[3] == 16);
    ca_volcano_free(&vo);
    check_walk(146833024135393ULL, 14391545271884ULL, 141956518099848ULL, 2, 3);
    TEST_MAIN_END();
}
