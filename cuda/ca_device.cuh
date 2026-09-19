/*
 * ca_device.cuh - device-side arithmetic and the Pollard rho walk kernel
 * body, shared between the CUDA build (nvcc or clang -x cuda) and the host
 * emulator (src/gpu_emulate.c).
 *
 * The file is valid C11 and valid CUDA C++.  Under CUDA every function is
 * __device__ __forceinline__; on the host it is static inline and the
 * 64x64->128 multiply uses unsigned __int128.  Keeping one body for both
 * targets means the emulator tests exercise exactly the code the GPU runs,
 * which is how this component is verified on machines without a GPU.
 *
 * Data layout (all field elements in Montgomery form, R = 2^64):
 *   multipliers  mult[4*i + {0,1,2,3}] = x_i, y_i, alpha_i, beta_i
 *   walk state   state[4*w + {0,1,2,3}] = x, y, a, b
 *   walk aux     aux[CA_GPU_AUX*w + ...]   see CA_AUX_* below
 *   DP output    dp_out[4*k + {0,1,2,3}]  = hash, a, b, walk id
 * Z_p^* uses only x (y = 0).  The point at infinity is encoded as x == p.
 */
#ifndef CA_DEVICE_CUH
#define CA_DEVICE_CUH

#include <stdint.h>

#if defined(__CUDACC__) || defined(__CUDA__)
#  define CA_DEV __device__ __forceinline__
#  define CA_DEV_CUDA 1
#else
#  define CA_DEV static inline
#  define CA_DEV_CUDA 0
#endif

#ifndef CA_GPU_W
#  define CA_GPU_W 8            /* walks per thread (compile-time) */
#endif
#define CA_GPU_AUX 8            /* aux words per walk */
#define CA_AUX_CTL 0            /* bit 63: retry pending, low 32 bits: pending idx */
#define CA_AUX_WIN 1            /* cycle-detection window countdown */
#define CA_AUX_SAVEX 2
#define CA_AUX_SAVEY 3
#define CA_AUX_SINCEDP 4
#define CA_AUX_RESTARTS 5       /* restart counter (RNG stream selector) */
#define CA_GPU_WINDOW 64
#define CA_GPU_KIND_ZP 1
#define CA_GPU_KIND_EC 2

typedef struct ca_gpu_rho_args {
    uint64_t p, pinv, one, a_mont, n;
    uint64_t dp_mask;
    uint64_t seed;
    uint64_t base_x, base_y, target_x, target_y;
    uint32_t kind, negmap, r, steps, nthreads, dp_cap;
    uint32_t abandon_shift;       /* abandon a walk after 24 << abandon_shift steps w/o DP */
    uint32_t pad;
    const uint64_t *mult;
    uint64_t *state;
    uint64_t *aux;
    uint64_t *dp_out;
    uint32_t *dp_count;
    uint8_t *restart;             /* per walk: 1 => re-seed at the start of the next launch */
} ca_gpu_rho_args;

/* ---- 64-bit Montgomery arithmetic ------------------------------------- */

CA_DEV uint64_t ca_dev_mulhi(uint64_t a, uint64_t b)
{
#if CA_DEV_CUDA
    return __umul64hi(a, b);
#else
    return (uint64_t)(((unsigned __int128)a * b) >> 64);
#endif
}

CA_DEV uint64_t ca_dev_addmod(uint64_t a, uint64_t b, uint64_t p)
{
    uint64_t s = a + b;
    if (s < a || s >= p) s -= p;
    return s;
}

CA_DEV uint64_t ca_dev_submod(uint64_t a, uint64_t b, uint64_t p)
{
    return a >= b ? a - b : a + (p - b);
}

/* Montgomery product a*b*R^-1 mod p for any odd p < 2^64. */
CA_DEV uint64_t ca_dev_mont_mul(uint64_t a, uint64_t b, uint64_t p, uint64_t pinv)
{
    uint64_t lo = a * b, hi = ca_dev_mulhi(a, b);
    uint64_t u = lo * pinv;
    uint64_t uhi = ca_dev_mulhi(u, p);
    /* lo + u*p has zero low word; the carry out is 1 iff lo != 0 */
    uint64_t c1 = lo != 0;
    uint64_t r = hi + uhi;
    uint64_t c2 = r < hi;
    r += c1;
    c2 += r < c1;
    if (c2 || r >= p) r -= p;
    return r;
}

CA_DEV uint64_t ca_dev_mont_pow(uint64_t a, uint64_t e, uint64_t p, uint64_t pinv, uint64_t one)
{
    uint64_t r = one;
    while (e) {
        if (e & 1) r = ca_dev_mont_mul(r, a, p, pinv);
        a = ca_dev_mont_mul(a, a, p, pinv);
        e >>= 1;
    }
    return r;
}

/* Inverse in Montgomery form via Fermat (p prime). */
CA_DEV uint64_t ca_dev_mont_inv(uint64_t a, uint64_t p, uint64_t pinv, uint64_t one)
{
    return ca_dev_mont_pow(a, p - 2, p, pinv, one);
}

CA_DEV uint64_t ca_dev_mix64(uint64_t x)
{
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33;
    return x;
}

CA_DEV uint64_t ca_dev_splitmix(uint64_t *s)
{
    uint64_t z = (*s += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

/* Same canonical hashes as the host groups (group_zp.c / group_ec.c). */
CA_DEV uint64_t ca_dev_hash(uint32_t kind, uint64_t x, uint64_t y, uint64_t p)
{
    if (kind == CA_GPU_KIND_ZP) return ca_dev_mix64(x ^ 0x5bd1e995ULL);
    if (x == p) return 0x9e3779b97f4a7c15ULL;
    return ca_dev_mix64(x * 0x9E3779B97F4A7C15ULL ^ ca_dev_mix64(y));
}

/* ---- group operations -------------------------------------------------- */

/* Single (unbatched) group operation: (x,y) <- (x,y) op (bx,by). */
CA_DEV void ca_dev_op(const ca_gpu_rho_args *g, uint64_t *x, uint64_t *y, uint64_t bx, uint64_t by)
{
    uint64_t p = g->p, pinv = g->pinv;
    if (g->kind == CA_GPU_KIND_ZP) {
        *x = ca_dev_mont_mul(*x, bx, p, pinv);
        return;
    }
    if (*x == p) { *x = bx; *y = by; return; }
    if (bx == p) return;
    uint64_t lam;
    if (*x == bx) {
        if (*y != by || *y == 0) { *x = p; *y = 0; return; }
        uint64_t x2 = ca_dev_mont_mul(*x, *x, p, pinv);
        uint64_t num = ca_dev_addmod(ca_dev_addmod(ca_dev_addmod(x2, x2, p), x2, p), g->a_mont, p);
        uint64_t den = ca_dev_addmod(*y, *y, p);
        lam = ca_dev_mont_mul(num, ca_dev_mont_inv(den, p, pinv, g->one), p, pinv);
    } else {
        lam = ca_dev_mont_mul(ca_dev_submod(by, *y, p),
                              ca_dev_mont_inv(ca_dev_submod(bx, *x, p), p, pinv, g->one), p, pinv);
    }
    uint64_t x3 = ca_dev_submod(ca_dev_submod(ca_dev_mont_mul(lam, lam, p, pinv), *x, p), bx, p);
    uint64_t y3 = ca_dev_submod(ca_dev_mont_mul(lam, ca_dev_submod(*x, x3, p), p, pinv), *y, p);
    *x = x3;
    *y = y3;
}

CA_DEV void ca_dev_dbl(const ca_gpu_rho_args *g, uint64_t *x, uint64_t *y)
{
    uint64_t bx = *x, by = *y;
    ca_dev_op(g, x, y, bx, by);
}

/* Scalar multiplication k*(bx,by) by double-and-add (used for restarts). */
CA_DEV void ca_dev_mul(const ca_gpu_rho_args *g, uint64_t *rx, uint64_t *ry, uint64_t bx, uint64_t by,
                       uint64_t k)
{
    uint64_t ax, ay;
    if (g->kind == CA_GPU_KIND_ZP) { ax = g->one; ay = 0; }
    else { ax = g->p; ay = 0; }
    uint64_t px = bx, py = by;
    while (k) {
        if (k & 1) ca_dev_op(g, &ax, &ay, px, py);
        k >>= 1;
        if (k) ca_dev_dbl(g, &px, &py);
    }
    *rx = ax;
    *ry = ay;
}

/* Canonical member of {P, -P}; returns 1 if negated.  Z_p^* never negates. */
CA_DEV int ca_dev_canon(const ca_gpu_rho_args *g, uint64_t x, uint64_t *y)
{
    if (!g->negmap || g->kind != CA_GPU_KIND_EC || x == g->p || *y == 0) return 0;
    uint64_t ny = g->p - *y;
    if (ny < *y) { *y = ny; return 1; }
    return 0;
}

CA_DEV uint32_t ca_dev_index(const ca_gpu_rho_args *g, uint64_t h)
{
    return (uint32_t)((h >> 32) % g->r);
}

/* ---- walk state helpers ------------------------------------------------ */

typedef struct ca_dev_walk {
    uint64_t x, y, a, b;
    uint64_t savex, savey;
    uint64_t since_dp;
    uint32_t win, pend;
    uint32_t retry;
} ca_dev_walk;

CA_DEV void ca_dev_walk_negate_exps(const ca_gpu_rho_args *g, ca_dev_walk *w)
{
    w->a = w->a ? g->n - w->a : 0;
    w->b = w->b ? g->n - w->b : 0;
}

/* Fresh random start Y = a*G + b*H for walk `wid` (restart counter `ctr`). */
CA_DEV void ca_dev_walk_restart(const ca_gpu_rho_args *g, ca_dev_walk *w, uint32_t wid, uint64_t ctr)
{
    uint64_t s = g->seed ^ (0x9E3779B97F4A7C15ULL * (uint64_t)(wid + 1)) ^ (ctr * 0xD1B54A32D192ED03ULL);
    ca_dev_splitmix(&s);
    w->a = ca_dev_splitmix(&s) % g->n;
    w->b = ca_dev_splitmix(&s) % g->n;
    uint64_t x1, y1, x2, y2;
    ca_dev_mul(g, &x1, &y1, g->base_x, g->base_y, w->a);
    ca_dev_mul(g, &x2, &y2, g->target_x, g->target_y, w->b);
    ca_dev_op(g, &x1, &y1, x2, y2);
    w->x = x1;
    w->y = y1;
    if (ca_dev_canon(g, w->x, &w->y)) ca_dev_walk_negate_exps(g, w);
    w->retry = 0;
    w->pend = 0;
    w->win = 0;
    w->since_dp = 0;
}

/* One unbatched walk step (used only for cycle escapes). */
CA_DEV void ca_dev_walk_step_single(const ca_gpu_rho_args *g, ca_dev_walk *w)
{
    uint32_t i = w->retry ? w->pend : ca_dev_index(g, ca_dev_hash(g->kind, w->x, w->y, g->p));
    for (;;) {
        uint64_t nx = w->x, ny = w->y;
        ca_dev_op(g, &nx, &ny, g->mult[4 * (size_t)i], g->mult[4 * (size_t)i + 1]);
        int neg = ca_dev_canon(g, nx, &ny);
        if (g->negmap && ca_dev_index(g, ca_dev_hash(g->kind, nx, ny, g->p)) == i) {
            i = (i + 1) % g->r;
            continue;
        }
        w->x = nx;
        w->y = ny;
        w->a = ca_dev_addmod(w->a, g->mult[4 * (size_t)i + 2], g->n);
        w->b = ca_dev_addmod(w->b, g->mult[4 * (size_t)i + 3], g->n);
        if (neg) ca_dev_walk_negate_exps(g, w);
        w->retry = 0;
        return;
    }
}

/* Escape a fruitless cycle through its minimum element (deterministic). */
CA_DEV void ca_dev_walk_escape(const ca_gpu_rho_args *g, ca_dev_walk *w)
{
    ca_dev_walk cur = *w;
    cur.retry = 0;
    ca_dev_walk best = cur;
    uint64_t besth = ca_dev_hash(g->kind, cur.x, cur.y, g->p);
    for (uint32_t k = 0; k < 4 * CA_GPU_WINDOW; k++) {
        ca_dev_walk_step_single(g, &cur);
        if (cur.x == w->x && cur.y == w->y) break;
        uint64_t h = ca_dev_hash(g->kind, cur.x, cur.y, g->p);
        if (h < besth) { besth = h; best = cur; }
    }
    w->x = best.x;
    w->y = best.y;
    ca_dev_dbl(g, &w->x, &w->y);
    w->a = ca_dev_addmod(best.a, best.a, g->n);
    w->b = ca_dev_addmod(best.b, best.b, g->n);
    if (ca_dev_canon(g, w->x, &w->y)) ca_dev_walk_negate_exps(g, w);
    w->retry = 0;
    w->win = 0;
}

CA_DEV void ca_dev_walk_load(const ca_gpu_rho_args *g, ca_dev_walk *w, uint32_t wid)
{
    const uint64_t *s = g->state + 4 * (size_t)wid;
    const uint64_t *a = g->aux + CA_GPU_AUX * (size_t)wid;
    w->x = s[0]; w->y = s[1]; w->a = s[2]; w->b = s[3];
    w->pend = (uint32_t)a[CA_AUX_CTL];
    w->retry = (uint32_t)(a[CA_AUX_CTL] >> 63);
    w->win = (uint32_t)a[CA_AUX_WIN];
    w->savex = a[CA_AUX_SAVEX];
    w->savey = a[CA_AUX_SAVEY];
    w->since_dp = a[CA_AUX_SINCEDP];
}

CA_DEV void ca_dev_walk_store(const ca_gpu_rho_args *g, const ca_dev_walk *w, uint32_t wid)
{
    uint64_t *s = g->state + 4 * (size_t)wid;
    uint64_t *a = g->aux + CA_GPU_AUX * (size_t)wid;
    s[0] = w->x; s[1] = w->y; s[2] = w->a; s[3] = w->b;
    a[CA_AUX_CTL] = ((uint64_t)w->retry << 63) | w->pend;
    a[CA_AUX_WIN] = w->win;
    a[CA_AUX_SAVEX] = w->savex;
    a[CA_AUX_SAVEY] = w->savey;
    a[CA_AUX_SINCEDP] = w->since_dp;
}

/* Atomic slot reservation for distinguished-point output. */
CA_DEV uint32_t ca_dev_dp_reserve(uint32_t *counter)
{
#if CA_DEV_CUDA
    return atomicAdd(counter, 1u);
#else
    return (*counter)++;
#endif
}

/*
 * The kernel body for one thread: CA_GPU_W walks, `steps` iterations,
 * batched inversion across the thread's walks.  Identical on device and
 * in the emulator.
 */
CA_DEV void ca_dev_rho_thread(const ca_gpu_rho_args *g, uint32_t tid)
{
    if (tid >= g->nthreads) return;
    const uint64_t p = g->p, pinv = g->pinv, one = g->one;
    ca_dev_walk w[CA_GPU_W];
    uint32_t idx[CA_GPU_W];
    uint64_t den[CA_GPU_W], pre[CA_GPU_W];
    const uint32_t wid0 = tid * CA_GPU_W;
    const uint64_t abandon = (uint64_t)24 << g->abandon_shift;

    for (int k = 0; k < CA_GPU_W; k++) {
        uint32_t wid = wid0 + k;
        ca_dev_walk_load(g, &w[k], wid);
        if (g->restart[wid]) {
            g->restart[wid] = 0;
            uint64_t *ax = g->aux + CA_GPU_AUX * (size_t)wid;
            ax[CA_AUX_RESTARTS]++;
            ca_dev_walk_restart(g, &w[k], wid, ax[CA_AUX_RESTARTS]);
        }
    }

    for (uint32_t step = 0; step < g->steps; step++) {
        /* choose multipliers */
        for (int k = 0; k < CA_GPU_W; k++) {
            idx[k] = w[k].retry ? w[k].pend
                                : ca_dev_index(g, ca_dev_hash(g->kind, w[k].x, w[k].y, p));
        }
        if (g->kind == CA_GPU_KIND_ZP) {
            for (int k = 0; k < CA_GPU_W; k++) {
                uint32_t i = idx[k];
                uint64_t nx = ca_dev_mont_mul(w[k].x, g->mult[4 * (size_t)i], p, pinv);
                w[k].x = nx;
                w[k].a = ca_dev_addmod(w[k].a, g->mult[4 * (size_t)i + 2], g->n);
                w[k].b = ca_dev_addmod(w[k].b, g->mult[4 * (size_t)i + 3], g->n);
                w[k].since_dp++;
                uint64_t h = ca_dev_hash(g->kind, nx, 0, p);
                if ((h & g->dp_mask) == 0) {
                    uint32_t slot = ca_dev_dp_reserve(g->dp_count);
                    if (slot < g->dp_cap) {
                        g->dp_out[4 * (size_t)slot] = h;
                        g->dp_out[4 * (size_t)slot + 1] = w[k].a;
                        g->dp_out[4 * (size_t)slot + 2] = w[k].b;
                        g->dp_out[4 * (size_t)slot + 3] = wid0 + k;
                    }
                    w[k].since_dp = 0;
                } else if (w[k].since_dp > abandon) {
                    uint64_t *ax = g->aux + CA_GPU_AUX * (size_t)(wid0 + k);
                    ax[CA_AUX_RESTARTS]++;
                    ca_dev_walk_restart(g, &w[k], wid0 + k, ax[CA_AUX_RESTARTS]);
                }
            }
            continue;
        }
        /* elliptic curve: batched affine addition */
        for (int k = 0; k < CA_GPU_W; k++) {
            uint32_t i = idx[k];
            uint64_t bx = g->mult[4 * (size_t)i], by = g->mult[4 * (size_t)i + 1];
            uint64_t d;
            if (w[k].x == p || bx == p) d = one;
            else if (w[k].x == bx) d = (w[k].y == by && w[k].y != 0) ? ca_dev_addmod(w[k].y, w[k].y, p) : one;
            else d = ca_dev_submod(bx, w[k].x, p);
            den[k] = d;
            pre[k] = k ? ca_dev_mont_mul(pre[k - 1], d, p, pinv) : d;
        }
        uint64_t inv = ca_dev_mont_inv(pre[CA_GPU_W - 1], p, pinv, one);
        for (int k = CA_GPU_W - 1; k >= 0; k--) {
            uint64_t di = k ? ca_dev_mont_mul(inv, pre[k - 1], p, pinv) : inv;
            inv = ca_dev_mont_mul(inv, den[k], p, pinv);
            uint32_t i = idx[k];
            uint64_t bx = g->mult[4 * (size_t)i], by = g->mult[4 * (size_t)i + 1];
            uint64_t nx, ny;
            if (w[k].x == p) { nx = bx; ny = by; }
            else if (bx == p) { nx = w[k].x; ny = w[k].y; }
            else if (w[k].x == bx) {
                if (w[k].y == by && w[k].y != 0) {
                    uint64_t x2 = ca_dev_mont_mul(w[k].x, w[k].x, p, pinv);
                    uint64_t num = ca_dev_addmod(ca_dev_addmod(ca_dev_addmod(x2, x2, p), x2, p), g->a_mont, p);
                    uint64_t lam = ca_dev_mont_mul(num, di, p, pinv);
                    nx = ca_dev_submod(ca_dev_submod(ca_dev_mont_mul(lam, lam, p, pinv), w[k].x, p), bx, p);
                    ny = ca_dev_submod(ca_dev_mont_mul(lam, ca_dev_submod(w[k].x, nx, p), p, pinv), w[k].y, p);
                } else { nx = p; ny = 0; }
            } else {
                uint64_t lam = ca_dev_mont_mul(ca_dev_submod(by, w[k].y, p), di, p, pinv);
                nx = ca_dev_submod(ca_dev_submod(ca_dev_mont_mul(lam, lam, p, pinv), w[k].x, p), bx, p);
                ny = ca_dev_submod(ca_dev_mont_mul(lam, ca_dev_submod(w[k].x, nx, p), p, pinv), w[k].y, p);
            }
            int neg = ca_dev_canon(g, nx, &ny);
            uint64_t h = ca_dev_hash(g->kind, nx, ny, p);
            if (g->negmap && ca_dev_index(g, h) == i) {
                w[k].pend = (i + 1) % g->r;
                w[k].retry = 1;
                continue;
            }
            w[k].retry = 0;
            w[k].x = nx;
            w[k].y = ny;
            w[k].a = ca_dev_addmod(w[k].a, g->mult[4 * (size_t)i + 2], g->n);
            w[k].b = ca_dev_addmod(w[k].b, g->mult[4 * (size_t)i + 3], g->n);
            if (neg) ca_dev_walk_negate_exps(g, &w[k]);
            w[k].since_dp++;
            if (g->negmap) {
                if (w[k].win == 0) {
                    w[k].savex = w[k].x;
                    w[k].savey = w[k].y;
                    w[k].win = CA_GPU_WINDOW;
                } else {
                    w[k].win--;
                    if (w[k].x == w[k].savex && w[k].y == w[k].savey) {
                        ca_dev_walk_escape(g, &w[k]);
                        h = ca_dev_hash(g->kind, w[k].x, w[k].y, p);
                    }
                }
            }
            if ((h & g->dp_mask) == 0) {
                uint32_t slot = ca_dev_dp_reserve(g->dp_count);
                if (slot < g->dp_cap) {
                    g->dp_out[4 * (size_t)slot] = h;
                    g->dp_out[4 * (size_t)slot + 1] = w[k].a;
                    g->dp_out[4 * (size_t)slot + 2] = w[k].b;
                    g->dp_out[4 * (size_t)slot + 3] = wid0 + k;
                }
                w[k].since_dp = 0;
            } else if (w[k].since_dp > abandon) {
                uint64_t *ax = g->aux + CA_GPU_AUX * (size_t)(wid0 + k);
                ax[CA_AUX_RESTARTS]++;
                ca_dev_walk_restart(g, &w[k], wid0 + k, ax[CA_AUX_RESTARTS]);
            }
        }
    }
    for (int k = 0; k < CA_GPU_W; k++) ca_dev_walk_store(g, &w[k], wid0 + k);
}

#endif /* CA_DEVICE_CUH */
