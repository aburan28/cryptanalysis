"""Optional O3 C kernels for packed Boolean polynomial operations."""

from __future__ import annotations

import os
import tempfile


def _load():
    try:
        from cffi import FFI
    except ImportError:
        return None, None
    ffi = FFI()
    ffi.cdef("""
        int boolean_interreduce(
            uint64_t *polys, int count, int capacity, int words, int universe,
            const uint32_t *mask_by_rank, const uint32_t *rank_by_mask,
            uint64_t *reductions, uint64_t *passes, uint64_t *removed);
    """)
    source = r"""
        #include <stdint.h>
        #include <string.h>

        #define MAX_WORDS 64

        static int highest(const uint64_t *p, int words) {
            for (int w = words - 1; w >= 0; --w) {
                uint64_t x = p[w];
                if (x) return w * 64 + 63 - __builtin_clzll(x);
            }
            return -1;
        }

        static int is_zero(const uint64_t *p, int words) {
            for (int w = 0; w < words; ++w) if (p[w]) return 0;
            return 1;
        }

        static int same(const uint64_t *a, const uint64_t *b, int words) {
            return memcmp(a, b, (size_t)words * sizeof(uint64_t)) == 0;
        }

        static void multiply(
            uint64_t *out, const uint64_t *p, uint32_t multiplier, int words,
            const uint32_t *mask_by_rank, const uint32_t *rank_by_mask) {
            memset(out, 0, (size_t)words * sizeof(uint64_t));
            for (int w = 0; w < words; ++w) {
                uint64_t x = p[w];
                while (x) {
                    int bit = __builtin_ctzll(x);
                    int rank = w * 64 + bit;
                    uint32_t product = mask_by_rank[rank] | multiplier;
                    uint32_t product_rank = rank_by_mask[product];
                    out[product_rank >> 6] ^= UINT64_C(1) << (product_rank & 63);
                    x &= x - 1;
                }
            }
        }

        int boolean_interreduce(
            uint64_t *polys, int count, int capacity, int words, int universe,
            const uint32_t *mask_by_rank, const uint32_t *rank_by_mask,
            uint64_t *reductions, uint64_t *passes, uint64_t *removed) {
            (void)universe;
            if (words <= 0 || words > MAX_WORDS || count < 0 || count > capacity)
                return -1;
            uint64_t value[MAX_WORDS], remainder[MAX_WORDS], product[MAX_WORDS];
            int leads[8192];
            if (capacity > 8192) return -2;
            for (;;) {
                ++*passes;
                for (int j = 0; j < count; ++j)
                    leads[j] = highest(polys + (size_t)j * words, words);
                int changed = 0;
                int i = 0;
                while (i < count) {
                    uint64_t *original = polys + (size_t)i * words;
                    memcpy(value, original, (size_t)words * sizeof(uint64_t));
                    memset(remainder, 0, (size_t)words * sizeof(uint64_t));
                    for (;;) {
                        int lead_rank = highest(value, words);
                        if (lead_rank < 0) break;
                        uint32_t lead_mask = mask_by_rank[lead_rank];
                        int reducer = -1;
                        for (int j = 0; j < count; ++j) {
                            if (j == i || leads[j] < 0) continue;
                            uint32_t reducer_mask = mask_by_rank[leads[j]];
                            if ((reducer_mask & ~lead_mask) == 0) {
                                reducer = j;
                                break;
                            }
                        }
                        if (reducer < 0) {
                            uint64_t bit = UINT64_C(1) << (lead_rank & 63);
                            remainder[lead_rank >> 6] ^= bit;
                            value[lead_rank >> 6] ^= bit;
                        } else {
                            uint32_t reducer_mask = mask_by_rank[leads[reducer]];
                            multiply(product,
                                polys + (size_t)reducer * words,
                                lead_mask & ~reducer_mask, words,
                                mask_by_rank, rank_by_mask);
                            for (int w = 0; w < words; ++w) value[w] ^= product[w];
                            ++*reductions;
                        }
                    }
                    if (same(remainder, original, words)) {
                        ++i;
                        continue;
                    }
                    changed = 1;
                    if (!is_zero(remainder, words)) {
                        memcpy(original, remainder, (size_t)words * sizeof(uint64_t));
                        leads[i] = highest(original, words);
                        ++i;
                    } else {
                        if (i + 1 < count) {
                            memmove(original, original + words,
                                (size_t)(count - i - 1) * words * sizeof(uint64_t));
                            memmove(leads + i, leads + i + 1,
                                (size_t)(count - i - 1) * sizeof(int));
                        }
                        --count;
                        ++*removed;
                    }
                }
                if (!changed) return count;
            }
        }
    """
    try:
        build_dir = os.path.join(tempfile.gettempdir(), "boolean-f5b-cffi")
        os.makedirs(build_dir, exist_ok=True)
        lib = ffi.verify(source, extra_compile_args=["-O3"], tmpdir=build_dir)
    except Exception:
        return None, None
    return ffi, lib


ffi, lib = _load()


def available() -> bool:
    return ffi is not None and lib is not None


def interreduce(polynomials, mask_by_rank, rank_by_mask):
    if not available():
        return None
    count = len(polynomials)
    universe = len(mask_by_rank)
    words = max(1, (universe + 63) // 64)
    if words > 64 or count > 8192:
        return None
    data = ffi.new("uint64_t[]", max(1, count * words))
    for i, polynomial in enumerate(polynomials):
        value = polynomial
        for w in range(words):
            data[i * words + w] = value & ((1 << 64) - 1)
            value >>= 64
    masks = ffi.new("uint32_t[]", mask_by_rank)
    ranks = ffi.new("uint32_t[]", rank_by_mask)
    reductions = ffi.new("uint64_t *")
    passes = ffi.new("uint64_t *")
    removed = ffi.new("uint64_t *")
    final_count = lib.boolean_interreduce(
        data, count, count, words, universe, masks, ranks,
        reductions, passes, removed)
    if final_count < 0:
        return None
    output = []
    for i in range(final_count):
        value = 0
        for w in range(words - 1, -1, -1):
            value = (value << 64) | int(data[i * words + w])
        output.append(value)
    return output, int(reductions[0]), int(passes[0]), int(removed[0])
