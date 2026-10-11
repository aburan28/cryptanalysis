#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>

// Standalone experimental kernels. A symmetric kernel requires the caller
// to have proved exact coefficient symmetry for THIS input. No producer
// certificate, cached target, or shape assumption can establish that fact.
namespace boolean_transform
{
struct Counts {
    uint64_t xors = 0;
    uint64_t copies = 0;
};

template <typename Word> void accepted_full(Word *a, uint32_t n, Counts &counts)
{
    const uint32_t words = n * n;
    // Exact loop shape used by the accepted independent round45 checker.
    for (uint32_t bit = words / 2; bit; bit >>= 1)
        for (uint32_t base = 0; base < words; base += 2 * bit) {
            for (uint32_t off = 0; off < bit; ++off) a[base + bit + off] ^= a[base + off];
            counts.xors += bit;
        }
}

template <typename Word> void full(Word *a, uint32_t n, size_t stride, Counts &counts)
{
    for (uint32_t bit = n / 2; bit; bit >>= 1)
        for (uint32_t base = 0; base < n; base += 2 * bit)
            for (uint32_t row = 0; row < bit; ++row) {
                auto *dst = a + size_t(base + bit + row) * stride;
                const auto *src = a + size_t(base + row) * stride;
                for (uint32_t col = 0; col < n; ++col) dst[col] ^= src[col];
                counts.xors += n;
            }
    for (uint32_t row = 0; row < n; ++row) {
        auto *values = a + size_t(row) * stride;
        for (uint32_t bit = n / 2; bit; bit >>= 1)
            for (uint32_t base = 0; base < n; base += 2 * bit) {
                for (uint32_t off = 0; off < bit; ++off)
                    values[base + bit + off] ^= values[base + off];
                counts.xors += bit;
            }
    }
}

template <typename Word> void triangular(Word *a, uint32_t n, Counts &counts, uint32_t tile)
{
    // Whole first axis; the second-axis subset recurrence is prefix-closed.
    for (uint32_t bit = n / 2; bit; bit >>= 1)
        for (uint32_t base = 0; base < n; base += 2 * bit)
            for (uint32_t row = 0; row < bit; ++row) {
                auto *dst = a + size_t(base + bit + row) * n;
                const auto *src = a + size_t(base + row) * n;
                for (uint32_t col = 0; col < n; ++col) dst[col] ^= src[col];
                counts.xors += n;
            }
    for (uint32_t row = 0; row < n; ++row) {
        auto *values = a + size_t(row) * n;
        for (uint32_t bit = n / 2; bit; bit >>= 1)
            for (uint32_t base = 0; base + bit <= row; base += 2 * bit) {
                const uint32_t end = std::min(bit, row + 1 - base - bit);
                for (uint32_t off = 0; off < end; ++off)
                    values[base + bit + off] ^= values[base + off];
                counts.xors += end;
            }
    }
    // All source entries are complete before any mirror write.
    for (uint32_t bi = 0; bi < n; bi += tile)
        for (uint32_t bj = 0; bj <= bi; bj += tile)
            for (uint32_t i = bi; i < std::min(n, bi + tile); ++i)
                for (uint32_t j = bj; j < std::min(i, bj + tile); ++j) {
                    a[size_t(j) * n + i] = a[size_t(i) * n + j];
                    ++counts.copies;
                }
}

template <typename Word>
void recursive(Word *a, uint32_t n, size_t stride, Counts &counts, uint32_t leaf = 1)
{
    if (n == 1) return;
    if (n <= leaf) {
        full(a, n, stride, counts);
        return;
    }
    const uint32_t h = n / 2;
    Word *e = a, *d = a + h, *f = a + size_t(h) * stride + h;
    recursive(e, h, stride, counts, leaf);
    recursive(f, h, stride, counts, leaf);
    full(d, h, stride, counts);
    // Compute F+E+D+D^T before changing D. E,F are symmetric; D need not be.
    for (uint32_t i = 0; i < h; ++i) {
        const size_t row = size_t(i) * stride;
        f[row + i] ^= e[row + i];
        ++counts.xors;
        for (uint32_t j = 0; j < i; ++j) {
            f[row + j] ^= e[row + j] ^ d[row + j] ^ d[size_t(j) * stride + i];
            f[size_t(j) * stride + i] = f[row + j];
            counts.xors += 3;
            ++counts.copies;
        }
    }
    for (uint32_t i = 0; i < h; ++i)
        for (uint32_t j = 0; j < h; ++j) {
            const size_t pos = size_t(i) * stride + j;
            d[pos] ^= e[pos];
            a[size_t(j + h) * stride + i] = d[pos];
            ++counts.xors;
            ++counts.copies;
        }
}
} // namespace boolean_transform
