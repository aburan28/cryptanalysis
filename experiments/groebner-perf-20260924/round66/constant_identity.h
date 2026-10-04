#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>

// Kernel experiment only. The caller validates proof limbs before narrowing.
// Tables are reconstructed independently from the original polynomial input.
namespace constant_identity
{
struct Result {
    uint32_t features = 0;
    uint64_t avoided_parities = 0;
    bool valid = true;
};
template <class T> unsigned parity(T value) { return __builtin_parityll(uint64_t(value)); }
template <class T> unsigned folded_parity(T value)
{
    if constexpr (sizeof(T) == 8) value ^= value >> 32;
    value ^= value >> 16;
    value ^= value >> 8;
    value ^= value >> 4;
    value ^= value >> 2;
    value ^= value >> 1;
    return unsigned(value & 1);
}
template <class T>
Result original(const T *table, const uint64_t *proof, const unsigned char *reuse,
                uint32_t branches, uint32_t features, uint32_t limbs)
{
    Result result;
    for (uint32_t f = 0; f < features; ++f) {
        unsigned bad = 0;
        const T *low = table + size_t(f) * limbs * branches;
        const T *high = limbs == 2 ? low + branches : nullptr;
        for (uint32_t x = 0; x < branches; ++x) {
            if (reuse && reuse[x] == 1) {
                result.avoided_parities += limbs;
                continue;
            }
            const uint64_t a = proof[size_t(x) * limbs], b = high ? proof[size_t(x) * 2 + 1] : 0;
            const unsigned bit = parity(a & low[x]) ^ (high ? parity(b & high[x]) : 0);
            bad |= (bit ^ unsigned(f == 0)) & unsigned((a | b) != 0);
        }
        ++result.features;
        if (bad) {
            result.valid = false;
            return result;
        }
    }
    return result;
}
template <class T> struct Workspace {
    std::vector<T> low, high;
    uint64_t skipped = 0;
    // Hard bound: 2 * 2^20 * 8 = 16 MiB. No answer or target coefficient cache.
    explicit Workspace(uint32_t branches, uint32_t limbs)
    {
        if (!branches || branches > (1u << 20) || limbs < 1 || limbs > 2 ||
            (sizeof(T) == 4 && limbs != 1))
            throw std::invalid_argument("constant identity dimensions");
        low.resize(branches);
        if (limbs == 2) high.resize(branches);
    }
    void prepare(const uint64_t *proof, const unsigned char *reuse)
    {
        const uint32_t limbs = high.empty() ? 1 : 2;
        skipped = 0;
        for (size_t x = 0; x < low.size(); ++x) {
            const bool skip = reuse && reuse[x] == 1;
            skipped += skip;
            low[x] = skip ? 0 : T(proof[x * limbs]);
            if (limbs == 2) high[x] = skip ? 0 : T(proof[x * 2 + 1]);
        }
    }
    template <bool Folded, bool Two> Result run(const T *table, uint32_t features) const
    {
        Result result;
        const size_t branches = low.size();
        for (uint32_t f = 0; f < features; ++f) {
            const T *a = table + size_t(f) * (Two ? 2 : 1) * branches;
            const T *b = Two ? a + branches : nullptr;
            unsigned bad = 0;
            for (size_t x = 0; x < branches; ++x) {
                const T u = low[x], v = Two ? high[x] : 0;
                const T bits = (u & a[x]) ^ (Two ? v & b[x] : 0);
                const unsigned bit = Folded ? folded_parity(bits) : parity(bits);
                bad |= bit ^ (unsigned(f == 0) & unsigned((u | v) != 0));
            }
            ++result.features;
            result.avoided_parities += skipped * (Two ? 2 : 1);
            if (bad) {
                result.valid = false;
                return result;
            }
        }
        return result;
    }
    template <bool Folded> Result check(const T *table, uint32_t features) const
    {
        return high.empty() ? run<Folded, false>(table, features)
                            : run<Folded, true>(table, features);
    }
};
} // namespace constant_identity
