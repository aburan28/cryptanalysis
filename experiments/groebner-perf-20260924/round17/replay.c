/* Independent curve replay. The producer does not call this field kernel. */
#include "../../pdp-degree-heuristics/pdpkernel.c"

#define REPLAY_MAX_POINTS 12
typedef struct {
    uint32_t code, signs, patterns;
    uint64_t ys[REPLAY_MAX_POINTS];
} replay_result;

static u64 replay_pmod(u64 a, u64 b)
{
    int degree = deg64(b);
    while (a && deg64(a) >= degree) a ^= b << (deg64(a) - degree);
    return a;
}

/* Ben-Or's irreducibility test, before any inversion can be attempted. */
static int replay_irreducible(int n, u64 mod)
{
    ctx_t c = {0};
    c.n = n;
    c.mod = mod;
    u64 z = 2;
    for (int i = 1; i <= n / 2; ++i) {
        z = gf_sqr(&c, z);
        u64 a = mod, b = z ^ 2;
        while (b) {
            u64 r = replay_pmod(a, b);
            a = b;
            b = r;
        }
        if (a != 1) return 0;
    }
    return 1;
}

static int replay_on_curve(const ctx_t *c, u64 x, u64 y)
{
    return (gf_sqr(c, y) ^ gf_mul(c, x, y)) == (gf_mul(c, gf_sqr(c, x), x) ^ c->b);
}

void *replay_create(uint32_t n, u64 mod, u64 b)
{
    if (n < 3 || n > 63 || !(n & 1) || deg64(mod) != (int)n || !b || b >> n ||
        !replay_irreducible((int)n, mod))
        return NULL;
    ctx_t *c = malloc(sizeof(*c));
    if (!c) return NULL;
    if (ctx_init(c, (int)n, mod, 0, b)) {
        free(c);
        return NULL;
    }
    return c;
}

void replay_destroy(void *handle) { free(handle); }
uint32_t replay_result_size(void) { return sizeof(replay_result); }

int replay_target_valid(const void *handle, u64 rx, u64 ry, uint32_t infinity)
{
    if (!handle || infinity > 1) return 0;
    if (infinity) return rx == 0 && ry == 0;
    const ctx_t *c = handle;
    if (rx >> c->n || ry >> c->n) return 0;
    return replay_on_curve(c, rx, ry);
}

/* Codes: 0 witness, 1 no matching signs, 2 an x has no lift, 3 invalid input.
 * All call-local output is reset. A live handle and buffer extents belong to
 * the C caller; the Python adapter owns them and serializes lifetime. */
int replay_match(const void *handle, const u64 *xs, uint32_t count, u64 rx, u64 ry,
                 uint32_t infinity, replay_result *out)
{
    if (!out) return 3;
    memset(out, 0, sizeof(*out));
    out->code = 3;
    out->signs = UINT32_MAX;
    if (!handle || !xs || count < 1 || count > REPLAY_MAX_POINTS ||
        !replay_target_valid(handle, rx, ry, infinity))
        return 3;
    const ctx_t *c = handle;
    u64 ys[REPLAY_MAX_POINTS];
    uint8_t ok[REPLAY_MAX_POINTS];
    for (uint32_t i = 0; i < count; ++i)
        if (xs[i] >> c->n) return 3;
    ec_lift_batch(c, xs, (int)count, ys, ok);
    for (uint32_t i = 0; i < count; ++i) {
        if (!ok[i]) return out->code = 2;
        if (!replay_on_curve(c, xs[i], ys[i])) return 3;
    }
    for (uint32_t signs = 0; signs < (1u << count); ++signs) {
        u64 qx = INF_X, qy = 0;
        ++out->patterns;
        for (uint32_t i = 0; i < count; ++i) {
            u64 y = ys[i] ^ (((signs >> i) & 1) ? xs[i] : 0);
            ec_add(c, qx, qy, xs[i], y, &qx, &qy);
        }
        if (infinity ? qx == INF_X : (qx != INF_X && qx == rx && qy == ry)) {
            out->signs = signs;
            for (uint32_t i = 0; i < count; ++i)
                out->ys[i] = ys[i] ^ (((signs >> i) & 1) ? xs[i] : 0);
            return out->code = 0;
        }
    }
    return out->code = 1;
}
