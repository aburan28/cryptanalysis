/*
 * pdp_ps5_slp.h - host-side reader for the `pdp-slp/1` straight-line program
 * that the `crypto` repository's `pdp_speedup export-program` writes
 * (examples/pdp_speedup/bitslice.rs `program_bytes`), a SHA-256, and an
 * interpreter that runs the program on 32-bit words (32 lanes).
 *
 * Host tools only (the emitter and the self-test).  The device source,
 * pdp_ps5_device.cuh, never includes this file.
 *
 * Byte format (from `program_bytes`): per operation a tag byte and its
 * operands as u32 little-endian, then the tag 255 and the output wires as
 * u32 little-endian to the end of the file.
 *   tag 0 input k        1 zero        2 ones        3 not a
 *   tag 4 xor a b        5 and a b     6 or a b      7 xand a b c = a ^ (b & c)
 * A wire is the position of its operation in the list.
 */
#ifndef PDP_PS5_SLP_H
#define PDP_PS5_SLP_H

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── SHA-256 ─────────────────────────────────────────────────────────── */

typedef struct {
    uint32_t h[8];
    uint64_t len;
    uint8_t buf[64];
    size_t fill;
} Ps5Sha;

static const uint32_t ps5_sha_k[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u, 0x923f82a4u,
    0xab1c5ed5u, 0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u, 0x72be5d74u, 0x80deb1feu,
    0x9bdc06a7u, 0xc19bf174u, 0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu,
    0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau, 0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
    0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u, 0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu,
    0x53380d13u, 0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u, 0xa2bfe8a1u, 0xa81a664bu,
    0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u, 0x19a4c116u,
    0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u, 0x90befffau, 0xa4506cebu, 0xbef9a3f7u,
    0xc67178f2u};

#define PS5_ROR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static void ps5_sha_block(Ps5Sha *s, const uint8_t *p)
{
    uint32_t w[64];
    for (int i = 0; i < 16; ++i)
        w[i] = ((uint32_t)p[4 * i] << 24) | ((uint32_t)p[4 * i + 1] << 16) |
               ((uint32_t)p[4 * i + 2] << 8) | (uint32_t)p[4 * i + 3];
    for (int i = 16; i < 64; ++i) {
        uint32_t s0 = PS5_ROR(w[i - 15], 7) ^ PS5_ROR(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = PS5_ROR(w[i - 2], 17) ^ PS5_ROR(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint32_t a = s->h[0], b = s->h[1], c = s->h[2], d = s->h[3];
    uint32_t e = s->h[4], f = s->h[5], g = s->h[6], h = s->h[7];
    for (int i = 0; i < 64; ++i) {
        uint32_t S1 = PS5_ROR(e, 6) ^ PS5_ROR(e, 11) ^ PS5_ROR(e, 25);
        uint32_t ch = (e & f) ^ (~e & g);
        uint32_t t1 = h + S1 + ch + ps5_sha_k[i] + w[i];
        uint32_t S0 = PS5_ROR(a, 2) ^ PS5_ROR(a, 13) ^ PS5_ROR(a, 22);
        uint32_t mj = (a & b) ^ (a & c) ^ (b & c);
        uint32_t t2 = S0 + mj;
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }
    s->h[0] += a;
    s->h[1] += b;
    s->h[2] += c;
    s->h[3] += d;
    s->h[4] += e;
    s->h[5] += f;
    s->h[6] += g;
    s->h[7] += h;
}

static void ps5_sha_init(Ps5Sha *s)
{
    static const uint32_t iv[8] = {0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
                                   0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u};
    memcpy(s->h, iv, sizeof iv);
    s->len = 0;
    s->fill = 0;
}

static void ps5_sha_update(Ps5Sha *s, const void *data, size_t n)
{
    const uint8_t *p = (const uint8_t *)data;
    s->len += n;
    while (n) {
        size_t take = 64 - s->fill;
        if (take > n) take = n;
        memcpy(s->buf + s->fill, p, take);
        s->fill += take;
        p += take;
        n -= take;
        if (s->fill == 64) {
            ps5_sha_block(s, s->buf);
            s->fill = 0;
        }
    }
}

/* Writes 64 lowercase hex digits and a NUL into `hex`. */
static void ps5_sha_final_hex(Ps5Sha *s, char hex[65])
{
    uint64_t bits = s->len * 8u;
    uint8_t pad = 0x80;
    ps5_sha_update(s, &pad, 1);
    pad = 0;
    while (s->fill != 56) ps5_sha_update(s, &pad, 1);
    uint8_t lenb[8];
    for (int i = 0; i < 8; ++i) lenb[i] = (uint8_t)(bits >> (56 - 8 * i));
    ps5_sha_update(s, lenb, 8);
    for (int i = 0; i < 8; ++i) sprintf(hex + 8 * i, "%08x", s->h[i]);
}

static void ps5_sha256_hex(const void *data, size_t n, char hex[65])
{
    Ps5Sha s;
    ps5_sha_init(&s);
    ps5_sha_update(&s, data, n);
    ps5_sha_final_hex(&s, hex);
}

/* ── files ───────────────────────────────────────────────────────────── */

static uint8_t *ps5_read_file(const char *path, size_t *len)
{
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        return NULL;
    }
    long sz = ftell(f);
    if (sz < 0) {
        fclose(f);
        return NULL;
    }
    rewind(f);
    uint8_t *buf = (uint8_t *)malloc((size_t)sz + 1u);
    if (!buf || fread(buf, 1, (size_t)sz, f) != (size_t)sz) {
        free(buf);
        fclose(f);
        return NULL;
    }
    buf[sz] = 0;
    fclose(f);
    *len = (size_t)sz;
    return buf;
}

/* The unsigned integer after `"key":` in a flat JSON object, or -1. */
static long long ps5_json_int(const char *text, const char *key)
{
    char pat[64];
    snprintf(pat, sizeof pat, "\"%s\":", key);
    const char *p = strstr(text, pat);
    if (!p) return -1;
    p += strlen(pat);
    char *end;
    long long v = strtoll(p, &end, 10);
    return end == p ? -1 : v;
}

/* The string after `"key":"` in a flat JSON object; copied into `out`. */
static int ps5_json_str(const char *text, const char *key, char *out, size_t cap)
{
    char pat[64];
    snprintf(pat, sizeof pat, "\"%s\":\"", key);
    const char *p = strstr(text, pat);
    if (!p) return -1;
    p += strlen(pat);
    const char *q = strchr(p, '"');
    if (!q || (size_t)(q - p) >= cap) return -1;
    memcpy(out, p, (size_t)(q - p));
    out[q - p] = 0;
    return 0;
}

/* ── the program ─────────────────────────────────────────────────────── */

enum { PS5_T_INPUT = 0, PS5_T_ZERO, PS5_T_ONES, PS5_T_NOT, PS5_T_XOR, PS5_T_AND, PS5_T_OR, PS5_T_XAND };

typedef struct {
    uint8_t tag;
    uint32_t a, b, c; /* operands; for an input, `a` is its number */
} Ps5Op;

typedef struct {
    Ps5Op *ops;
    size_t n_ops;
    uint32_t *outs;
    size_t n_outs;
    uint32_t n_inputs; /* 1 + the largest input number */
    size_t count[8];   /* operations per tag */
} Ps5Prog;

/* Parses and validates (wires refer only to earlier wires).  0 on success. */
static int ps5_slp_parse(const uint8_t *buf, size_t len, Ps5Prog *p, char *err, size_t errcap)
{
    memset(p, 0, sizeof *p);
    size_t cap = 1024, pos = 0;
    p->ops = (Ps5Op *)malloc(cap * sizeof(Ps5Op));
    if (!p->ops) return snprintf(err, errcap, "out of memory"), -1;
#define PS5_FAIL(...) \
    do { snprintf(err, errcap, __VA_ARGS__); return -1; } while (0)
#define PS5_U32(at) \
    ((uint32_t)buf[at] | ((uint32_t)buf[(at) + 1] << 8) | ((uint32_t)buf[(at) + 2] << 16) | \
     ((uint32_t)buf[(at) + 3] << 24))
    for (;;) {
        if (pos >= len) PS5_FAIL("missing end marker (tag 255)");
        uint8_t tag = buf[pos++];
        if (tag == 255) break;
        if (tag > 7) PS5_FAIL("unknown tag %u at op %zu", tag, p->n_ops);
        static const int nargs[8] = {1, 0, 0, 1, 2, 2, 2, 3};
        int na = nargs[tag];
        if (pos + 4u * (size_t)na > len) PS5_FAIL("truncated operands at op %zu", p->n_ops);
        Ps5Op op = {tag, 0, 0, 0};
        if (na >= 1) op.a = PS5_U32(pos);
        if (na >= 2) op.b = PS5_U32(pos + 4);
        if (na >= 3) op.c = PS5_U32(pos + 8);
        pos += 4u * (size_t)na;
        if (tag != PS5_T_INPUT) {
            if (na >= 1 && op.a >= p->n_ops) PS5_FAIL("op %zu uses wire %u not yet defined", p->n_ops, op.a);
            if (na >= 2 && op.b >= p->n_ops) PS5_FAIL("op %zu uses wire %u not yet defined", p->n_ops, op.b);
            if (na >= 3 && op.c >= p->n_ops) PS5_FAIL("op %zu uses wire %u not yet defined", p->n_ops, op.c);
        } else if (op.a + 1u > p->n_inputs) {
            p->n_inputs = op.a + 1u;
        }
        if (p->n_ops == cap) {
            cap *= 2;
            Ps5Op *q = (Ps5Op *)realloc(p->ops, cap * sizeof(Ps5Op));
            if (!q) PS5_FAIL("out of memory");
            p->ops = q;
        }
        p->ops[p->n_ops++] = op;
        p->count[tag]++;
    }
    if ((len - pos) % 4u) PS5_FAIL("output list is not a multiple of 4 bytes");
    p->n_outs = (len - pos) / 4u;
    p->outs = (uint32_t *)malloc((p->n_outs ? p->n_outs : 1u) * sizeof(uint32_t));
    if (!p->outs) PS5_FAIL("out of memory");
    for (size_t i = 0; i < p->n_outs; ++i) {
        p->outs[i] = PS5_U32(pos + 4 * i);
        if (p->outs[i] >= p->n_ops) PS5_FAIL("output %zu names wire %u, past the program", i, p->outs[i]);
    }
#undef PS5_U32
#undef PS5_FAIL
    return 0;
}

static void __attribute__((unused)) ps5_slp_free(Ps5Prog *p)
{
    free(p->ops);
    free(p->outs);
    memset(p, 0, sizeof *p);
}

/* Evaluates every wire on 32-bit words: `in[k]` is input k, `wires` has n_ops entries. */
static void __attribute__((unused)) ps5_slp_eval(const Ps5Prog *p, const uint32_t *in, uint32_t *wires)
{
    for (size_t i = 0; i < p->n_ops; ++i) {
        const Ps5Op *o = &p->ops[i];
        uint32_t v = 0;
        switch (o->tag) {
        case PS5_T_INPUT: v = in[o->a]; break;
        case PS5_T_ZERO: v = 0u; break;
        case PS5_T_ONES: v = ~0u; break;
        case PS5_T_NOT: v = ~wires[o->a]; break;
        case PS5_T_XOR: v = wires[o->a] ^ wires[o->b]; break;
        case PS5_T_AND: v = wires[o->a] & wires[o->b]; break;
        case PS5_T_OR: v = wires[o->a] | wires[o->b]; break;
        case PS5_T_XAND: v = wires[o->a] ^ (wires[o->b] & wires[o->c]); break;
        }
        wires[i] = v;
    }
}

#endif /* PDP_PS5_SLP_H */
