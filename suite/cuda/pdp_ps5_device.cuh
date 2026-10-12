/*
 * pdp_ps5_device.cuh - the PS-5 kernel: PS-3's straight-line program run on
 * 32-bit words, one pair per bit lane, logic mapped to `lop3`.
 *
 * What the kernel computes (PDP oracle, pairs-and-solve by the group law;
 * the algebra is in the `crypto` repository, research/pdp_oracle_speedup_20261011,
 * ps1_algebra and ps2_scalar).  For a target R and the rational base points
 * P_0 < P_1 < ... (abscissa below 2^l, ascending), a pair (P_i1, P_i2) with
 * i1 <= i2 *hits* when one of x(P_i1 + P_i2 +- R), x(P_i1 - P_i2 +- R) is
 * below 2^l.  With the row points U+- = P_i1 +- R, the straight-line program
 * takes per task (a block of 32 pairs sharing a row) the bit-planes
 *   xu, yu, xv, yv  (the row's two points, the same word in every lane) and
 *   x2, y2          (the 32 partners P_i2, bit j of plane i = bit i of lane j)
 * and returns two masks: lanes that hit, and lanes whose denominator
 * x_U + x2 or x_V + x2 is zero ("exceptional", decided by the host).
 *
 * Mapping to the device:
 *   lane   = bit j of a 32-bit word = one pair
 *   task   = (row i1, block of 32 consecutive partners)
 *   job    = PS5_TASKS tasks of one row = one thread's work for one program run
 *            (the tasks share one bit-sliced Montgomery inversion per chain)
 * The program has no memory access and no divergence: a warp executes the
 * same instruction stream, and a job is 8 x 32 = 256 pairs.  Hits are
 * appended to a global list with one atomic increment per non-empty task.
 * (The protocol's "Gray position per warp" belongs to the incremental-update
 * formulation that PS-2 did not build; see the experiment README.)
 *
 * The file is written in the common subset of C11 and CUDA C++, like
 * f4_gf2_device.cuh: pdp_ps5_emulate.c compiles this very source, and the
 * very generated program, as C, with `lop3` replaced by a bitwise model of
 * the PTX instruction (the same immediate), so the host runs the kernel's
 * arithmetic.  The kernel's program is generated, not written: see
 * pdp_ps5_emit.c.  The includer defines PS5_PARAMS_H (a generated header
 * naming n, l, the counts and PS5_BODY_INC, the generated statements)
 * before this file.
 */
#ifndef PDP_PS5_DEVICE_CUH
#define PDP_PS5_DEVICE_CUH

#include PS5_PARAMS_H

typedef unsigned int ps5_u32;
typedef unsigned long long ps5_u64;

#if defined(__CUDACC__) || defined(__CUDA_ARCH__)
#    define PS5_DEV __device__
#    define PS5_INLINE __forceinline__
#    define PS5_RESTRICT __restrict__
#else
#    define PS5_DEV
#    define PS5_INLINE static inline
#    define PS5_RESTRICT
#endif

#define PS5_LANES 32u

/* The truth tables.  `lop3.b32 d, a, b, c, lut` returns, per bit, the bit of
 * `lut` indexed by 4*a + 2*b + c; with a = 0xF0, b = 0xCC, c = 0xAA the lut
 * of a function is the function applied to those three bytes.  Two-input
 * functions repeat an operand as the third. */
#define PS5_LUT_XOR 0x3c  /* a ^ b            */
#define PS5_LUT_AND 0xc0  /* a & b            */
#define PS5_LUT_OR 0xfc   /* a | b            */
#define PS5_LUT_NOT 0x0f  /* ~a               */
#define PS5_LUT_XAND 0x78 /* a ^ (b & c): the fused gate of the program */

#define PS5_STR2(x) #x
#define PS5_STR(x) PS5_STR2(x)

#if defined(PS5_PLAIN_OPS)
/* C operators; for comparing what the compiler makes of them. */
#    define PS5_XOR(a, b) ((a) ^ (b))
#    define PS5_AND(a, b) ((a) & (b))
#    define PS5_OR(a, b) ((a) | (b))
#    define PS5_NOT(a) (~(a))
#    define PS5_XAND(a, b, c) ((a) ^ ((b) & (c)))
#elif defined(__CUDA_ARCH__)
PS5_DEV PS5_INLINE ps5_u32 ps5_xor(ps5_u32 a, ps5_u32 b)
{
    ps5_u32 r;
    asm("lop3.b32 %0, %1, %2, %3, " PS5_STR(PS5_LUT_XOR) ";" : "=r"(r) : "r"(a), "r"(b), "r"(b));
    return r;
}
PS5_DEV PS5_INLINE ps5_u32 ps5_and(ps5_u32 a, ps5_u32 b)
{
    ps5_u32 r;
    asm("lop3.b32 %0, %1, %2, %3, " PS5_STR(PS5_LUT_AND) ";" : "=r"(r) : "r"(a), "r"(b), "r"(b));
    return r;
}
PS5_DEV PS5_INLINE ps5_u32 ps5_or(ps5_u32 a, ps5_u32 b)
{
    ps5_u32 r;
    asm("lop3.b32 %0, %1, %2, %3, " PS5_STR(PS5_LUT_OR) ";" : "=r"(r) : "r"(a), "r"(b), "r"(b));
    return r;
}
PS5_DEV PS5_INLINE ps5_u32 ps5_not(ps5_u32 a)
{
    ps5_u32 r;
    asm("lop3.b32 %0, %1, %2, %3, " PS5_STR(PS5_LUT_NOT) ";" : "=r"(r) : "r"(a), "r"(a), "r"(a));
    return r;
}
PS5_DEV PS5_INLINE ps5_u32 ps5_xand(ps5_u32 a, ps5_u32 b, ps5_u32 c)
{
    ps5_u32 r;
    asm("lop3.b32 %0, %1, %2, %3, " PS5_STR(PS5_LUT_XAND) ";" : "=r"(r) : "r"(a), "r"(b), "r"(c));
    return r;
}
#    define PS5_XOR(a, b) ps5_xor((a), (b))
#    define PS5_AND(a, b) ps5_and((a), (b))
#    define PS5_OR(a, b) ps5_or((a), (b))
#    define PS5_NOT(a) ps5_not((a))
#    define PS5_XAND(a, b, c) ps5_xand((a), (b), (c))
#else
/* Host model of the PTX instruction: bit i of `lut` selects the minterm
 * (a, b, c) = (bit 2 of i, bit 1 of i, bit 0 of i).  Called with literal
 * tables, so the compiler reduces each call to the gate it names. */
PS5_INLINE ps5_u32 ps5_lop3(ps5_u32 a, ps5_u32 b, ps5_u32 c, unsigned lut)
{
    ps5_u32 r = 0u;
    if (lut & 0x01u) r |= ~a & ~b & ~c;
    if (lut & 0x02u) r |= ~a & ~b & c;
    if (lut & 0x04u) r |= ~a & b & ~c;
    if (lut & 0x08u) r |= ~a & b & c;
    if (lut & 0x10u) r |= a & ~b & ~c;
    if (lut & 0x20u) r |= a & ~b & c;
    if (lut & 0x40u) r |= a & b & ~c;
    if (lut & 0x80u) r |= a & b & c;
    return r;
}
#    define PS5_XOR(a, b) ps5_lop3((a), (b), (b), PS5_LUT_XOR)
#    define PS5_AND(a, b) ps5_lop3((a), (b), (b), PS5_LUT_AND)
#    define PS5_OR(a, b) ps5_lop3((a), (b), (b), PS5_LUT_OR)
#    define PS5_NOT(a) ps5_lop3((a), (a), (a), PS5_LUT_NOT)
#    define PS5_XAND(a, b, c) ps5_lop3((a), (b), (c), PS5_LUT_XAND)
#endif

/*
 * Where the generated program keeps its wires.  The same statements serve both:
 *
 *   default (the device): every wire is a single-assignment local `wK`; the
 *     body is included inside ps5_job and the compiler allocates registers.
 *   PS5_WIRES_IN_MEMORY (the host emulation, C only): wires live in one array,
 *     and the emitter's chunk markers split the body into functions.  Host
 *     compilers do not finish a 65,000-local function in minutes (gcc -O1
 *     and clang -O2 were stopped after 4 and 2 minutes at l = 8), so this is
 *     a storage binding, not a different program: statement for statement
 *     the same operations on the same operands in the same order.
 *
 * PS5_TAP lets a test observe every wire.
 */
#ifndef PS5_TAP
#    define PS5_TAP(K, w) ((void)0)
#endif
#if defined(PS5_WIRES_IN_MEMORY)
typedef struct {
    ps5_u64 rv[4];
    ps5_u32 xo[PS5_TASKS];
    const ps5_u32 *xb;
    const ps5_u32 *yb;
} Ps5Ctx;
static _Thread_local Ps5Ctx ps5_ctx;
static _Thread_local ps5_u32 ps5_w[PS5_OPS];
static _Thread_local ps5_u32 ps5_out[2 * PS5_TASKS];
#    define PS5_W(A) ps5_w[A]
#    define PS5_DEF(K, e) ps5_w[K] = (e); PS5_TAP(K, ps5_w[K])
#    if defined(__GNUC__)
#        define PS5_NOINLINE __attribute__((noinline))
#    else
#        define PS5_NOINLINE
#    endif
#    define PS5_CHUNK_BEGIN(c) static PS5_NOINLINE void ps5_chunk_##c(void) {
#    define PS5_CHUNK_END(c) }
#    define PS5_CALL(c) ps5_chunk_##c();
#    define PS5_OUTPUT(j, K) ps5_out[j] = ps5_w[K];
#    define PS5_RV(f) ps5_ctx.rv[f]
#    define PS5_XO(t) ps5_ctx.xo[t]
#    define PS5_XB ps5_ctx.xb
#    define PS5_YB ps5_ctx.yb
#else
#    define PS5_W(A) w##A
#    define PS5_DEF(K, e) const ps5_u32 w##K = (e); PS5_TAP(K, w##K)
#    define PS5_CHUNK_BEGIN(c)
#    define PS5_CHUNK_END(c)
#    define PS5_CALL(c)
#    define PS5_OUTPUT(j, K) ps5_out[j] = w##K;
#    define PS5_RV(f) ps5_rv[f]
#    define PS5_XO(t) ps5_xo[t]
#    define PS5_XB xb
#    define PS5_YB yb
#endif

/* Lanes of block `blk` that are pairs of row i1: partner index in [i1, m). */
PS5_DEV PS5_INLINE ps5_u32 ps5_valid(ps5_u32 i1, ps5_u32 blk, ps5_u32 m)
{
    const ps5_u32 lo = blk * PS5_LANES;
    ps5_u32 v = ~0u;
    if (m <= lo) return 0u;
    if (i1 > lo) v = (i1 - lo >= PS5_LANES) ? 0u : (v << (i1 - lo));
    if (m - lo < PS5_LANES) v &= (1u << (m - lo)) - 1u;
    return v;
}

/* A task with a non-empty hit or exceptional mask. */
typedef struct {
    ps5_u32 i1;  /* row */
    ps5_u32 blk; /* block of 32 partners; partner index = 32*blk + lane */
    ps5_u32 hit; /* lanes that hit, valid and not exceptional */
    ps5_u32 exc; /* valid lanes with a zero denominator */
} Ps5Hit;

#ifndef PS5_NO_JOB
/* The program's inputs.  A row value is broadcast: the plane is all ones or
 * all zeros.  The partners' planes are read from the block table, `n` words
 * per block (plane 0 first).  A test may define PS5_INPUT itself. */
#    ifndef PS5_INPUT
#        define PS5_BC(v, i) (0u - (ps5_u32)(((v) >> (i)) & 1u))
#        define PS5_INPUT_F0(t, i) PS5_BC(PS5_RV(0), i)
#        define PS5_INPUT_F1(t, i) PS5_BC(PS5_RV(1), i)
#        define PS5_INPUT_F2(t, i) PS5_BC(PS5_RV(2), i)
#        define PS5_INPUT_F3(t, i) PS5_BC(PS5_RV(3), i)
#        define PS5_INPUT_F4(t, i) PS5_XB[PS5_XO(t) + (i)]
#        define PS5_INPUT_F5(t, i) PS5_YB[PS5_XO(t) + (i)]
#        define PS5_INPUT(t, f, i, k) PS5_INPUT_F##f(t, i)
#    endif

#    if defined(PS5_WIRES_IN_MEMORY)
#        include PS5_BODY_INC /* the chunk functions, at file scope */
#    endif

/*
 * One job: the row `jobs[2*job]` against the PS5_TASKS blocks starting at
 * `jobs[2*job+1]`.  `rows` holds four u64 per row (xu, yu, xv, yv; the low
 * n bits).  `xb`, `yb` hold the transposed base points, n words per block;
 * blocks past the last repeat the last block and are masked by ps5_valid.
 * Records that are not empty go to `hits` (one atomic increment each); the
 * counter keeps counting past `cap`, so the caller sees an overflow.
 */
PS5_DEV PS5_INLINE void ps5_job(ps5_u32 job, const ps5_u32 *PS5_RESTRICT jobs,
                                const ps5_u32 *PS5_RESTRICT xb, const ps5_u32 *PS5_RESTRICT yb,
                                const ps5_u64 *PS5_RESTRICT rows, ps5_u32 m, ps5_u32 nblk,
                                ps5_u32 *nhits, Ps5Hit *hits, ps5_u32 cap)
{
    const ps5_u32 i1 = jobs[2u * job];
    const ps5_u32 blk0 = jobs[2u * job + 1u];
    ps5_u32 valid[PS5_TASKS];
#    if defined(PS5_WIRES_IN_MEMORY)
    for (ps5_u32 f = 0; f < 4u; ++f) ps5_ctx.rv[f] = rows[4u * i1 + f];
    ps5_ctx.xb = xb;
    ps5_ctx.yb = yb;
    for (ps5_u32 k = 0; k < PS5_TASKS; ++k) {
        const ps5_u32 blk = blk0 + k;
        valid[k] = ps5_valid(i1, blk, m);
        ps5_ctx.xo[k] = (blk < nblk ? blk : nblk - 1u) * PS5_N;
    }
    PS5_CALL_CHUNKS
#    else
    const ps5_u64 ps5_rv[4] = {rows[4u * i1], rows[4u * i1 + 1u], rows[4u * i1 + 2u],
                               rows[4u * i1 + 3u]};
    ps5_u32 ps5_xo[PS5_TASKS];
    ps5_u32 ps5_out[2 * PS5_TASKS];
    for (ps5_u32 k = 0; k < PS5_TASKS; ++k) {
        const ps5_u32 blk = blk0 + k;
        valid[k] = ps5_valid(i1, blk, m);
        ps5_xo[k] = (blk < nblk ? blk : nblk - 1u) * PS5_N;
    }
#        include PS5_BODY_INC
#    endif
    PS5_OUTPUT_LIST
    for (ps5_u32 k = 0; k < PS5_TASKS; ++k) {
        const ps5_u32 exc = ps5_out[2u * k + 1u] & valid[k];
        const ps5_u32 hit = ps5_out[2u * k] & valid[k] & ~ps5_out[2u * k + 1u];
        if ((hit | exc) != 0u) {
#    if defined(__CUDA_ARCH__)
            const ps5_u32 at = atomicAdd(nhits, 1u);
#    else
            const ps5_u32 at = (*nhits)++;
#    endif
            if (at < cap) {
                hits[at].i1 = i1;
                hits[at].blk = blk0 + k;
                hits[at].hit = hit;
                hits[at].exc = exc;
            }
        }
    }
}
#endif /* PS5_NO_JOB */

#endif /* PDP_PS5_DEVICE_CUH */
