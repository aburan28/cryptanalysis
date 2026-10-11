"""Transpose read-only table columns in the disposable benchmark tree.

The values, offsets of following tables, and total shared-memory extent stay
identical. Only the placement of addend words and/or sign-transform rows
changes. Packed top bits remain a separate tail with the existing encoding.
"""


def once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new)


def patch(source, addends=False, rows=False):
    if rows:
        source = once(source, 'const uint32_t *r = fromRow + p * 4;',
                      'const uint32_t *r = fromRow + p;')
        old = '(yp.v[0] & r[0]) ^ (yp.v[1] & r[1]) ^ (yp.v[2] & r[2]) ^ (yp.v[3] & r[3]) ^ (yp.v[4] & top)'
        new = '(yp.v[0] & r[0]) ^ (yp.v[1] & r[131]) ^ (yp.v[2] & r[262]) ^ (yp.v[3] & r[393]) ^ (yp.v[4] & top)'
        source = once(source, old, new)
        source = once(source, 'out[TW_ROW_OFF + p * 4 + (j >> 5)]',
                      'out[TW_ROW_OFF + (j >> 5) * 131 + p]')
    if addends:
        start = source.index('TW_FN void twAddend(')
        end = source.index('// Host: fill', start)
        old = source[start:end]
        new = '''TW_FN void twAddend(unsigned tag, const P131 &xp, const P131 &yp,
                    const uint32_t *shared, P131 *d, P131 *e) {
    const int index = eccTagK(tag) * TW_H + eccTagH(tag);
    const uint32_t *t = shared + index;
    const uint32_t top = (shared[131 * TW_H * 8 + (index >> 2)] >> ((index & 3) * 8)) & 63u;
    const uint32_t negMask = 0u - unsigned(eccTagEps(tag));
#pragma unroll
    for (int i = 0; i < 4; ++i) {
        const uint32_t tx = t[i * 131 * TW_H];
        d->v[i] = xp.v[i] ^ tx;
        e->v[i] = yp.v[i] ^ t[(4+i) * 131 * TW_H] ^ (tx & negMask);
    }
    const uint32_t tx = top & 7u;
    d->v[4] = xp.v[4] ^ tx;
    e->v[4] = yp.v[4] ^ (top >> 3) ^ (tx & negMask);
}

TW_FN void twDenominator(unsigned tag, const P131 &xp, const uint32_t *shared, P131 *d) {
    const int index = eccTagK(tag) * TW_H + eccTagH(tag);
    const uint32_t *t = shared + index;
    const uint32_t top = (shared[131 * TW_H * 8 + (index >> 2)] >> ((index & 3) * 8)) & 7u;
#pragma unroll
    for (int i = 0; i < 4; ++i) d->v[i] = xp.v[i] ^ t[i * 131 * TW_H];
    d->v[4] = xp.v[4] ^ top;
}

'''
        source = once(source, old, new)
        old = '''uint32_t *t = out + k * TW_KWORDS + h * TW_ENTRY;
            for (int i = 0; i < 4; ++i) { t[i] = x.v[i]; t[4 + i] = y.v[i]; }
            out[k * TW_KWORDS + TW_H * TW_ENTRY + (h >> 2)]'''
        new = '''const int index = k * TW_H + h;
            uint32_t *t = out + index;
            for (int i = 0; i < 4; ++i) { t[i * 131 * TW_H] = x.v[i]; t[(4+i) * 131 * TW_H] = y.v[i]; }
            out[131 * TW_H * 8 + (index >> 2)]'''
        source = once(source, old, new)
    if rows or addends:
        source = once(source, 'namespace eccPacked131 {', '''#if !ECC_TABLE_PIVOT_BYTES
#error "Transposed table experiment requires the byte-pivot layout"
#endif
namespace eccPacked131 {''')
    return source
