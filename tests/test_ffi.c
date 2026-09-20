#include "cryptanalysis/cryptanalysis.h"
#include "test_util.h"

int main(void)
{
    CHECK(ca_ffi_options_size() == sizeof(ca_ffi_options));
    CHECK(ca_stats_size() == sizeof(ca_stats));
    CHECK(strcmp(ca_version(), CA_VERSION_STRING) == 0);
    /* Z_p^* */
    ca_ctx *z = ca_ctx_new_zp(2000000579ULL, 1000000289ULL);
    CHECK(z != NULL);
    CHECK(ca_ctx_new_zp(1000, 0) == NULL);
    CHECK(ca_ctx_kind(z) == 1);
    CHECK(ca_ctx_order(z) == 1000000289ULL);
    uint64_t g[4], h[4], t[4];
    CHECK(ca_ctx_find_generator(z, g, 1) == CA_OK);
    CHECK(ca_ctx_validate(z, g));
    uint64_t bad[4] = {0, 0, 0, 0};
    CHECK(!ca_ctx_validate(z, bad));
    CHECK(ca_ctx_mul(z, h, g, 123456789) == CA_OK);
    ca_ffi_options o;
    ca_ffi_options_default(&o);
    o.seed = 7;
    uint64_t x = 0;
    ca_stats st = {0};
    CHECK(ca_ffi_bsgs(z, g, h, 0, 0, &o, &x, &st) == CA_OK);
    CHECK_EQ_U64(x, 123456789);
    CHECK(st.group_ops > 0);
    x = 0;
    CHECK(ca_ffi_rho(z, g, h, &o, &x, NULL) == CA_OK);
    CHECK_EQ_U64(x, 123456789);
    x = 0;
    CHECK(ca_ffi_kangaroo(z, g, h, 123000000, 124000000, &o, &x, NULL) == CA_OK);
    CHECK_EQ_U64(x, 123456789);
    x = 0;
    CHECK(ca_ffi_grumpy(z, g, h, 123000000, 124000000, &o, &x, NULL) == CA_OK);
    CHECK_EQ_U64(x, 123456789);
    x = 0;
    CHECK(ca_ffi_dlog(z, g, h, &o, &x, NULL) == CA_OK);
    CHECK_EQ_U64(x, 123456789);
    o.solver = CA_SOLVER_GRUMPY;
    x = 0;
    CHECK(ca_ffi_dlog(z, g, h, &o, &x, NULL) == CA_OK);
    CHECK_EQ_U64(x, 123456789);
    /* precomputation solver through the FFI (one-shot, threaded build) */
    x = 0;
    CHECK(ca_ffi_precomp(z, g, h, -1, 0, 0.0, 4, 7, &x, &st) == CA_OK);
    CHECK_EQ_U64(x, 123456789);
    /* element ops */
    CHECK(ca_ctx_op(z, t, g, g) == CA_OK);
    uint64_t g2[4];
    CHECK(ca_ctx_mul(z, g2, g, 2) == CA_OK);
    CHECK(ca_ctx_equal(z, t, g2));
    CHECK(ca_ctx_inv(z, t, g) == CA_OK);
    CHECK(ca_ctx_op(z, t, t, g) == CA_OK);
    CHECK(ca_ctx_is_identity(z, t));
    uint64_t ord;
    CHECK(ca_ctx_elem_order(z, g, &ord) == CA_OK);
    CHECK_EQ_U64(ord, 1000000289ULL);
    /* Cheon through the FFI */
    uint64_t ga[4], gad[4], alpha;
    double cost;
    uint64_t d = ca_ffi_cheon_best_divisor(1000000289ULL, &cost);
    CHECK(d > 1);
    CHECK(ca_ffi_cheon_instance(z, g, 987654321, d, ga, gad) == CA_OK);
    CHECK(ca_ffi_cheon(z, g, ga, gad, d, 0, &alpha, &st) == CA_OK);
    CHECK_EQ_U64(alpha, 987654321);
    ca_ctx_free(z);

    /* EC */
    uint64_t n;
    CHECK(ca_ec_order(1000003, 1, 7, &n) == CA_OK);
    ca_ctx *e = ca_ctx_new_ec(1000003, 1, 7, n);
    CHECK(e != NULL);
    CHECK(ca_ctx_new_ec(97, 0, 0, 0) == NULL);
    uint64_t P[4], Q[4];
    CHECK(ca_ctx_random_element(e, P, 3) == CA_OK);
    CHECK(P[2] == 0);
    CHECK(ca_ctx_validate(e, P));
    uint64_t Pbad[4] = {P[0], P[1] ^ 1, 0, 0};
    CHECK(!ca_ctx_validate(e, Pbad));
    CHECK(ca_ctx_elem_order(e, P, &ord) == CA_OK);
    ca_ctx_set_order(e, ord, n / ord);
    CHECK(ca_ctx_mul(e, Q, P, 4242) == CA_OK);
    x = 0;
    CHECK(ca_ffi_dlog(e, P, Q, NULL, &x, NULL) == CA_OK);
    CHECK_EQ_U64(x, 4242 % ord);
    x = 0;
    CHECK(ca_ffi_precomp(e, P, Q, -1, 0, 0.0, 1, 7, &x, NULL) == CA_OK);
    CHECK_EQ_U64(x, 4242 % ord);
    uint64_t inf[4];
    CHECK(ca_ctx_identity(e, inf) == CA_OK);
    CHECK(inf[2] == 1);
    CHECK(ca_ctx_lift_x(e, Q, P[0]) == CA_OK);
    CHECK(Q[0] == P[0] && (Q[1] == P[1] || Q[1] == 1000003 - P[1]));
    ca_ctx_free(e);

    /* curve-aware dispatch (GLV) through the FFI */
    int32_t endo = 0;
    uint32_t am = 0;
    uint64_t beta = 0, lam = 0;
    double sp = 0;
    CHECK(ca_ffi_curve_detect(67108933, 0, 7, 16773703, &endo, &am, &beta, &lam, &sp) == CA_OK);
    CHECK(endo == 1 && am == 6 && lam > 1 && beta != 0);
    uint64_t cp = 0, cca = 0, ccb = 0, cco = 0;
    CHECK(ca_ffi_curve_by_name("glv-j0-26", &cp, &cca, &ccb, &cco) == CA_OK);
    CHECK(cp == 67108933 && cco == 16773703);
    CHECK(ca_ffi_curve_by_name("nope", &cp, &cca, &ccb, &cco) == CA_ERR_NOT_FOUND);
    CHECK(ca_ffi_curve_name(0) != NULL);
    ca_ctx *cc = ca_ctx_new_ec(67108933, 0, 7, 16773703);
    CHECK(cc != NULL);
    uint64_t Pc[4], Qc[4], gx = 0;
    CHECK(ca_ctx_find_generator(cc, Pc, 1) == CA_OK);
    CHECK(ca_ctx_mul(cc, Qc, Pc, 424242) == CA_OK);
    int32_t e2 = 0;
    uint32_t a2 = 0;
    uint64_t l2 = 0;
    CHECK(ca_ffi_curve_solve(cc, Pc, Qc, 5, &gx, &e2, &a2, &l2, NULL) == CA_OK);
    CHECK_EQ_U64(gx, 424242);
    CHECK(e2 == 1 && a2 == 6 && l2 > 1);
    ca_ctx_free(cc);

    /* GPU rho through the FFI (emulator backend: always available) */
    CHECK(ca_ffi_gpu_options_size() == sizeof(ca_ffi_gpu_options));
    z = ca_ctx_new_zp(2000000579ULL, 1000000289ULL);
    CHECK(z != NULL);
    CHECK(ca_ctx_find_generator(z, g, 1) == CA_OK);
    CHECK(ca_ctx_mul(z, h, g, 123456789) == CA_OK);
    ca_ffi_gpu_options go;
    ca_ffi_gpu_options_default(&go);
    go.backend = 2; /* emulate */
    go.seed = 5;
    x = 0;
    ca_stats gst = {0};
    CHECK(ca_ffi_gpu_rho(z, g, h, &go, &x, &gst) == CA_OK);
    CHECK_EQ_U64(x, 123456789);
    CHECK(gst.group_ops > 0);
    CHECK(gst.threads > 0);
    go.max_ops = 500;
    CHECK(ca_ffi_gpu_rho(z, g, h, &go, &x, NULL) == CA_ERR_LIMIT);
    /* the CUDA backend reports unsupported when not compiled in or absent */
    go.backend = 1;
    go.max_ops = 0;
    if (!ca_ffi_gpu_cuda_compiled() || ca_ffi_gpu_device_count() == 0) {
        CHECK(ca_ffi_gpu_rho(z, g, h, &go, &x, NULL) == CA_ERR_UNSUPPORTED);
    } else {
        CHECK(ca_ffi_gpu_rho(z, g, h, &go, &x, NULL) == CA_OK);
        CHECK_EQ_U64(x, 123456789);
        char dn[256];
        CHECK(ca_ffi_gpu_device_name(0, dn, sizeof(dn)) == 0);
    }
    CHECK(ca_ffi_gpu_device_count() >= 0);
    ca_ctx_free(z);

    /* index calculus + helpers */
    ca_ic_params ip;
    ca_ic_params_default(&ip);
    ip.seed = 3;
    ca_ic_stats ist;
    CHECK(ca_ffi_ic_solve(1000003, 2, 424242, &ip, &x, &ist) == CA_OK);
    CHECK_EQ_U64(ca_ffi_powmod(2, x, 1000003), 424242);
    CHECK(ca_ffi_is_prime(1000003));
    CHECK_EQ_U64(ca_ffi_next_prime(1000003), 1000033);
    CHECK_EQ_U64(ca_ffi_primitive_root(1000003), 2);
    CHECK_EQ_U64(ca_ffi_invmod(3, 1000003), ca_invmod(3, 1000003));
    uint64_t pr[8];
    unsigned ex[8];
    CHECK_EQ_U64(ca_ffi_factorize(1000002, pr, ex, 8), 3);
    CHECK_EQ_U64(pr[0], 2); CHECK_EQ_U64(pr[1], 3); CHECK_EQ_U64(pr[2], 166667);
    TEST_MAIN_END();
}
