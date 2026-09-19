/*
 * ca_ffi.h - flat, opaque-handle C ABI for language bindings.
 *
 * The rest of the library exposes structs whose layout may change; this
 * header only uses opaque pointers, plain integers, uint64_t[4] element
 * words and two POD structs (ca_stats, ca_ffi_options) whose sizes can be
 * checked at runtime with ca_ffi_options_size()/ca_stats_size().  The Rust,
 * Go and Python bindings under bindings/ are written against this header.
 *
 * Element words (public form, never Montgomery):
 *   Z_p^* : w[0] = residue in [1, p), w[1..3] = 0
 *   E(F_p): w[0] = x, w[1] = y, w[2] = 1 for the point at infinity
 *
 * Every function returning int returns a ca_status (0 = CA_OK); the
 * message for the last failure on this thread is in ca_last_error().
 */
#ifndef CA_FFI_H
#define CA_FFI_H

#include "ca_types.h"
#include "ca_indexcalc.h"
#include "ca_gpu.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ca_ctx ca_ctx;

/* ---- groups ------------------------------------------------------------- */
CA_API ca_ctx *ca_ctx_new_zp(uint64_t p, uint64_t order);
CA_API ca_ctx *ca_ctx_new_ec(uint64_t p, uint64_t a, uint64_t b, uint64_t order);
CA_API void ca_ctx_free(ca_ctx *ctx);
CA_API int ca_ctx_kind(const ca_ctx *ctx);          /* 1 = Z_p^*, 2 = EC */
CA_API uint64_t ca_ctx_p(const ca_ctx *ctx);
CA_API uint64_t ca_ctx_order(const ca_ctx *ctx);
CA_API uint64_t ca_ctx_cofactor(const ca_ctx *ctx);
CA_API void ca_ctx_set_order(ca_ctx *ctx, uint64_t order, uint64_t cofactor);
CA_API uint64_t ca_ctx_curve_a(const ca_ctx *ctx);
CA_API uint64_t ca_ctx_curve_b(const ca_ctx *ctx);

/* ---- elements ----------------------------------------------------------- */
CA_API int ca_ctx_validate(const ca_ctx *ctx, const uint64_t w[4]);   /* 1 if a valid element */
CA_API int ca_ctx_identity(const ca_ctx *ctx, uint64_t out[4]);
CA_API int ca_ctx_is_identity(const ca_ctx *ctx, const uint64_t w[4]);
CA_API int ca_ctx_op(const ca_ctx *ctx, uint64_t out[4], const uint64_t a[4], const uint64_t b[4]);
CA_API int ca_ctx_inv(const ca_ctx *ctx, uint64_t out[4], const uint64_t a[4]);
CA_API int ca_ctx_mul(const ca_ctx *ctx, uint64_t out[4], const uint64_t a[4], uint64_t k);
CA_API int ca_ctx_equal(const ca_ctx *ctx, const uint64_t a[4], const uint64_t b[4]);
CA_API int ca_ctx_elem_order(const ca_ctx *ctx, const uint64_t a[4], uint64_t *order);
CA_API int ca_ctx_find_generator(const ca_ctx *ctx, uint64_t out[4], uint64_t seed);
CA_API int ca_ctx_random_element(const ca_ctx *ctx, uint64_t out[4], uint64_t seed);
CA_API int ca_ctx_lift_x(const ca_ctx *ctx, uint64_t out[4], uint64_t x);  /* EC only */
CA_API int ca_ec_order(uint64_t p, uint64_t a, uint64_t b, uint64_t *order); /* point counting */

/* ---- solver options ----------------------------------------------------- */
typedef struct ca_ffi_options {
    uint32_t threads;            /* rho: worker threads (0 => 1) */
    uint32_t reserved0;
    uint64_t seed;               /* 0 => random */
    uint64_t max_ops;            /* 0 => unlimited */
    /* bsgs */
    uint64_t bsgs_table_size;    /* 0 => sqrt(width) */
    /* rho */
    uint32_t rho_r;              /* 0 => auto */
    int32_t  rho_dp_bits;        /* -1 => auto */
    uint32_t rho_walks_per_thread;
    int32_t  rho_negation_map;   /* 1 => use when available */
    uint64_t rho_max_table_entries;
    /* kangaroo */
    uint32_t kangaroo_herd_size; /* 0 => auto */
    int32_t  kangaroo_dp_bits;   /* -1 => auto */
    uint32_t kangaroo_jumps;     /* 0 => auto */
    uint32_t reserved1;
    /* grumpy giants */
    uint64_t grumpy_m;           /* 0 => alpha*sqrt(width) */
    double   grumpy_alpha;       /* 0 => 0.7 */
    /* dlog driver */
    int32_t  solver;             /* ca_solver: 0 auto, 1 bsgs, 2 rho, 3 kangaroo, 4 grumpy, 5 brute */
    int32_t  reserved2;
    uint64_t bsgs_max_prime;     /* auto: BSGS for prime factors <= this (0 => 2^36) */
} ca_ffi_options;

CA_API void ca_ffi_options_default(ca_ffi_options *o);
CA_API size_t ca_ffi_options_size(void);
CA_API size_t ca_stats_size(void);
CA_API size_t ca_ic_params_size(void);
CA_API size_t ca_ic_stats_size(void);

/* ---- discrete logarithm solvers ---------------------------------------- */
/* Interval solvers: x in [lo, hi]; lo == hi == 0 means the whole group. */
CA_API int ca_ffi_bsgs(const ca_ctx *ctx, const uint64_t base[4], const uint64_t target[4],
                       uint64_t lo, uint64_t hi, const ca_ffi_options *o, uint64_t *x, ca_stats *st);
CA_API int ca_ffi_kangaroo(const ca_ctx *ctx, const uint64_t base[4], const uint64_t target[4],
                           uint64_t lo, uint64_t hi, const ca_ffi_options *o, uint64_t *x, ca_stats *st);
CA_API int ca_ffi_grumpy(const ca_ctx *ctx, const uint64_t base[4], const uint64_t target[4],
                         uint64_t lo, uint64_t hi, const ca_ffi_options *o, uint64_t *x, ca_stats *st);
/* Whole-group solvers (need ctx order). */
CA_API int ca_ffi_rho(const ca_ctx *ctx, const uint64_t base[4], const uint64_t target[4],
                      const ca_ffi_options *o, uint64_t *x, ca_stats *st);
/* Pohlig-Hellman + selected solver. */
CA_API int ca_ffi_dlog(const ca_ctx *ctx, const uint64_t base[4], const uint64_t target[4],
                       const ca_ffi_options *o, uint64_t *x, ca_stats *st);

/* ---- Cheon ---------------------------------------------------------------- */
CA_API int ca_ffi_cheon(const ca_ctx *ctx, const uint64_t gen[4], const uint64_t g_alpha[4],
                        const uint64_t g_alpha_d[4], uint64_t d, uint64_t max_exps,
                        uint64_t *alpha, ca_stats *st);
CA_API int ca_ffi_cheon_instance(const ca_ctx *ctx, const uint64_t gen[4], uint64_t alpha,
                                 uint64_t d, uint64_t g_alpha[4], uint64_t g_alpha_d[4]);
CA_API uint64_t ca_ffi_cheon_best_divisor(uint64_t p, double *cost_exps);

/* ---- GPU (CUDA) Pollard rho ---------------------------------------------- */
/* backend: 0 auto, 1 cuda, 2 emulate (ca_gpu_backend).  Pass 0 for any
 * numeric field to take the automatic choice. */
typedef struct ca_ffi_gpu_options {
    int32_t backend;
    int32_t device;
    uint32_t threads_per_block;
    uint32_t blocks;
    uint32_t steps_per_launch;
    uint32_t r;
    int32_t dp_bits; /* -1 => auto */
    int32_t negation_map;
    uint64_t seed;
    uint64_t max_ops;
} ca_ffi_gpu_options;

CA_API void ca_ffi_gpu_options_default(ca_ffi_gpu_options *o);
CA_API size_t ca_ffi_gpu_options_size(void);
CA_API int ca_ffi_gpu_rho(const ca_ctx *ctx, const uint64_t base[4], const uint64_t target[4],
                          const ca_ffi_gpu_options *o, uint64_t *x, ca_stats *st);
/* 1 if the CUDA backend was compiled in; device count and names. */
CA_API int ca_ffi_gpu_cuda_compiled(void);
CA_API int ca_ffi_gpu_device_count(void);
CA_API int ca_ffi_gpu_device_name(int device, char *buf, size_t len);

/* ---- index calculus (the ca_ic_* API in ca_indexcalc.h is already flat) --- */
CA_API int ca_ffi_ic_solve(uint64_t p, uint64_t g, uint64_t h, const ca_ic_params *params,
                           uint64_t *x, ca_ic_stats *st);

/* ---- number theory helpers (also exported for bindings) ------------------- */
CA_API int ca_ffi_is_prime(uint64_t n);
CA_API uint64_t ca_ffi_next_prime(uint64_t n);
CA_API uint64_t ca_ffi_primitive_root(uint64_t p);
CA_API uint64_t ca_ffi_powmod(uint64_t b, uint64_t e, uint64_t m);
CA_API uint64_t ca_ffi_invmod(uint64_t a, uint64_t m);
/* Factor n into up to cap (prime, exponent) pairs; returns the count. */
CA_API unsigned ca_ffi_factorize(uint64_t n, uint64_t *primes, unsigned *exps, unsigned cap);

#ifdef __cplusplus
}
#endif
#endif /* CA_FFI_H */
