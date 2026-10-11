#pragma once
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <stdexcept>

// Exact Boolean multiplication from independently reconstructed coefficients.
// Features have degree <=2, witnesses degree <=1. No producer layout is used.
namespace independent_identity
{
constexpr uint32_t MODE_COUNT = 8;
struct Term {
    uint16_t feature = 0, slot = 0;
};
struct Group {
    uint16_t mask = 0, main = UINT16_MAX;
    uint8_t degree = 0, count = 0;
    std::array<Term, 5> terms{};
    std::array<Term, 3> lower{};
};
struct Counts {
    uint64_t ands = 0, accumulator_xors = 0, witness_xors = 0;
    uint64_t identity_xors = 0, parities = 0;
    uint64_t table_loads = 0, cached_loads = 0, copy_words = 0;
};
struct Layout {
    uint32_t y, features = 0, groups = 0;
    std::array<uint16_t, 56> masks{};
    std::array<Group, 176> group{};
    explicit Layout(uint32_t variables) : y(variables)
    {
        if (y < 1 || y > 10) throw std::invalid_argument("identity shape");
        std::array<uint16_t, 1024> index;
        index.fill(UINT16_MAX);
        for (uint32_t mask = 0; mask < (1u << y); ++mask)
            if (__builtin_popcount(mask) <= 2) {
                index[mask] = uint16_t(features);
                masks[features++] = uint16_t(mask);
            }
        for (uint32_t mask = 0; mask < (1u << y); ++mask) {
            if (__builtin_popcount(mask) > 3) continue;
            auto &g = group[groups++];
            g.mask = uint16_t(mask);
            g.main = index[mask];
            if (g.main != UINT16_MAX) g.terms[g.count++] = {g.main, 0};
            for (uint32_t i = 0; i < y; ++i) {
                if (!(mask & (1u << i))) continue;
                const uint16_t slot = uint16_t(i + 1);
                if (g.main != UINT16_MAX) g.terms[g.count++] = {g.main, slot};
                const Term term{index[mask ^ (1u << i)], slot};
                g.terms[g.count++] = term;
                g.lower[g.degree++] = term;
            }
        }
    }
    static bool copied(uint32_t mode) { return mode == 3 || mode == 5 || mode == 7; }
    uint64_t dense_parities(uint32_t limbs) const { return uint64_t(y + 1) * features * limbs; }
    Counts counts(uint32_t mode, uint32_t limbs) const
    {
        if (mode >= MODE_COUNT || limbs < 1 || limbs > 2)
            throw std::invalid_argument("identity mode or limbs");
        Counts c;
        c.ands = dense_parities(limbs);
        if (mode >= 6) {
            c.ands = 0;
            for (uint32_t i = 0; i < groups; ++i) {
                const auto &g = group[i];
                c.ands += (g.degree + uint32_t(g.main != UINT16_MAX)) * limbs;
                if (g.main != UINT16_MAX) c.witness_xors += g.degree * limbs;
            }
        }
        c.accumulator_xors = c.ands;
        c.parities = mode >= 4 ? groups : dense_parities(limbs);
        c.identity_xors = mode < 4 ? uint64_t(y + 1) * features : 0;
        c.table_loads = c.ands;
        if (copied(mode)) {
            c.table_loads = c.copy_words = uint64_t(features) * limbs;
            c.cached_loads = c.ands;
        }
        return c;
    }
};
static_assert(sizeof(Layout) <= 16384, "bounded invariant identity layout");

struct CheckSink {
    unsigned bad = 0;
    bool dense(const unsigned char *identity, uint32_t n, bool reduce)
    {
        if (!reduce) {
            if (identity[0] != 1) return false;
            for (uint32_t m = 1; m < n; ++m)
                if (identity[m]) return false;
            return true;
        }
        unsigned difference = identity[0] ^ 1u;
        for (uint32_t m = 1; m < n; ++m) difference |= identity[m];
        return difference == 0;
    }
    bool packed(const uint64_t *identity, uint32_t n)
    {
        uint64_t difference = identity[0] ^ 1u;
        for (uint32_t i = 1; i < (n + 63) / 64; ++i) difference |= identity[i];
        return difference == 0;
    }
    void coefficient(uint32_t mask, unsigned value) { bad |= value ^ unsigned(mask == 0); }
    bool finish() const { return bad == 0; }
};
struct OutputSink {
    unsigned char *output;
    bool dense(const unsigned char *identity, uint32_t n, bool)
    {
        std::copy_n(identity, n, output);
        return true;
    }
    bool packed(const uint64_t *identity, uint32_t n)
    {
        for (uint32_t m = 0; m < n; ++m) output[m] = (identity[m / 64] >> (m % 64)) & 1u;
        return true;
    }
    void coefficient(uint32_t mask, unsigned value) { output[mask] = value; }
    bool finish() const { return true; }
};

template <typename Get, typename Sink>
bool evaluate_direct(const Layout &layout, uint32_t mode, Get get, const uint64_t *u,
                     uint32_t limbs, Sink &sink)
{
    if (mode >= 4) {
        for (uint32_t i = 0; i < layout.groups; ++i) {
            const auto &g = layout.group[i];
            uint64_t value = 0;
            if (mode < 6) {
                for (uint32_t j = 0; j < g.count; ++j)
                    for (uint32_t l = 0; l < limbs; ++l) {
                        const auto term = g.terms[j];
                        value ^= u[size_t(term.slot) * limbs + l] & get(term.feature, l);
                    }
            } else {
                for (uint32_t l = 0; l < limbs; ++l) {
                    if (g.main != UINT16_MAX) {
                        uint64_t combined = u[l];
                        for (uint32_t j = 0; j < g.degree; ++j)
                            combined ^= u[size_t(g.lower[j].slot) * limbs + l];
                        value ^= combined & get(g.main, l);
                    }
                    for (uint32_t j = 0; j < g.degree; ++j) {
                        const auto term = g.lower[j];
                        value ^= u[size_t(term.slot) * limbs + l] & get(term.feature, l);
                    }
                }
            }
            sink.coefficient(g.mask, __builtin_parityll(value));
        }
        return sink.finish();
    }
    if (mode == 2) {
        std::array<uint64_t, 16> identity{};
        for (uint32_t slot = 0; slot <= layout.y; ++slot) {
            const uint32_t multiplier = slot ? 1u << (slot - 1) : 0;
            for (uint32_t feature = 0; feature < layout.features; ++feature) {
                unsigned parity = 0;
                for (uint32_t l = 0; l < limbs; ++l)
                    parity ^= __builtin_parityll(u[size_t(slot) * limbs + l] & get(feature, l));
                const uint32_t mask = layout.masks[feature] | multiplier;
                identity[mask / 64] ^= uint64_t(parity) << (mask % 64);
            }
        }
        return sink.packed(identity.data(), 1u << layout.y);
    }
    std::array<unsigned char, 1024> identity{};
    for (uint32_t slot = 0; slot <= layout.y; ++slot) {
        const uint32_t multiplier = slot ? 1u << (slot - 1) : 0;
        for (uint32_t feature = 0; feature < layout.features; ++feature) {
            unsigned parity = 0;
            for (uint32_t l = 0; l < limbs; ++l)
                parity ^= __builtin_parityll(u[size_t(slot) * limbs + l] & get(feature, l));
            identity[layout.masks[feature] | multiplier] ^= parity;
        }
    }
    return sink.dense(identity.data(), 1u << layout.y, mode == 1);
}

template <typename Get, typename Sink>
bool evaluate(const Layout &layout, uint32_t mode, Get get, const uint64_t *u, uint32_t limbs,
              Sink &sink)
{
    if (Layout::copied(mode)) {
        // Every used word is overwritten for THIS branch and THIS proof.
        std::array<uint64_t, 112> local;
        for (uint32_t f = 0; f < layout.features; ++f)
            for (uint32_t l = 0; l < limbs; ++l) local[size_t(f) * limbs + l] = get(f, l);
        auto cached = [&](uint32_t f, uint32_t l) { return local[size_t(f) * limbs + l]; };
        return evaluate_direct(layout, mode, cached, u, limbs, sink);
    }
    return evaluate_direct(layout, mode, get, u, limbs, sink);
}
} // namespace independent_identity
