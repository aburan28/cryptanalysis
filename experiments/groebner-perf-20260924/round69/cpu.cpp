#include "api.h"
#include "../round48/multiplier.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <limits>

namespace multiplier_gpu
{
using Clock = std::chrono::steady_clock;
static double elapsed(Clock::time_point start)
{
    return std::chrono::duration<double>(Clock::now() - start).count();
}

Shape::Shape(uint32_t a, uint32_t b, uint32_t e, size_t cap)
    : x(a), y(b), equations(e), limbs((e + 63) / 64), word_bits(e <= 32 ? 32 : 64), branches(0),
      features(0), groups(0), coefficient_bytes(0), capacity(cap), cpu_layout(b)
{
    if (x < 1 || x > 20 || y < 1 || y > 10 || x + y > 30 || e < 1 || e > 128)
        throw std::invalid_argument("multiplier shape");
    branches = 1u << x;
    if (capacity > branches) throw std::length_error("multiplier capacity");
    std::vector<uint32_t> indices(1u << y, UINT32_MAX);
    for (uint32_t mask = 0; mask < (1u << y); ++mask)
        if (__builtin_popcount(mask) <= 2) {
            indices[mask] = features++;
            masks.push_back(mask);
        }
    // This layout enumerates numeric Boolean masks, not producer columns.
    for (uint32_t mask = 0; mask < (1u << y); ++mask) {
        if (__builtin_popcount(mask) > 3) continue;
        Group g;
        g.mask = mask;
        g.main = indices[mask];
        for (uint32_t bit = 0; bit < y; ++bit)
            if (mask & (1u << bit)) {
                g.feature[g.degree] = indices[mask ^ (1u << bit)];
                g.slot[g.degree++] = bit + 1;
            }
        layout.push_back(g);
    }
    groups = uint32_t(layout.size());
    coefficient_bytes = size_t(features) * limbs * branches * (word_bits / 8);
    if (coefficient_bytes > (64u << 20) || capacity * (y + 1) * limbs * 8 > (64u << 20))
        throw std::length_error("multiplier storage limit");
}

static bool overlaps(const void *a, size_t an, const void *b, size_t bn)
{
    if (!an || !bn) return false;
    const auto x = reinterpret_cast<uintptr_t>(a), y = reinterpret_cast<uintptr_t>(b);
    if (an > UINTPTR_MAX - x || bn > UINTPTR_MAX - y)
        throw std::invalid_argument("multiplier address extent overflow");
    return x < y + bn && y < x + an;
}

void validate(const Shape &s, const Input &in, const Output &out)
{
    if (in.records > s.capacity || in.coefficient_bytes != s.coefficient_bytes ||
        !in.coefficients || in.witness_words != in.records * (s.y + 1) * s.limbs ||
        out.records != in.records ||
        (in.records && (!in.branches || !in.witnesses || !out.first_bad)))
        throw std::invalid_argument("multiplier input/output extent");
    if (reinterpret_cast<uintptr_t>(in.coefficients) % (s.word_bits / 8) ||
        reinterpret_cast<uintptr_t>(in.witnesses) % 8 ||
        reinterpret_cast<uintptr_t>(in.branches) % 4 ||
        reinterpret_cast<uintptr_t>(out.first_bad) % 4)
        throw std::invalid_argument("multiplier alignment");
    if ((out.coefficients && out.coefficient_bytes != in.records * s.groups) ||
        (!out.coefficients && out.coefficient_bytes) || out.coefficient_bytes > (64u << 20))
        throw std::invalid_argument("multiplier materialized extent");
    const std::array<std::pair<const void *, size_t>, 3> inputs{
        {{in.coefficients, in.coefficient_bytes},
         {in.branches, in.records * 4},
         {in.witnesses, in.witness_words * 8}}};
    for (const auto &v : inputs)
        if (overlaps(v.first, v.second, out.first_bad, out.records * 4) ||
            overlaps(v.first, v.second, out.coefficients, out.coefficient_bytes))
            throw std::invalid_argument("multiplier output aliases input");
    if (overlaps(out.first_bad, out.records * 4, out.coefficients, out.coefficient_bytes))
        throw std::invalid_argument("multiplier output alias");
    for (size_t r = 0; r < in.records; ++r) {
        if (in.branches[r] >= s.branches || (r && in.branches[r] <= in.branches[r - 1]))
            throw std::invalid_argument("multiplier branch order/range");
        const uint32_t used = s.equations - (s.limbs - 1) * 64;
        if (used < 64)
            for (uint32_t slot = 0; slot <= s.y; ++slot)
                if (in.witnesses[(r * (s.y + 1) + slot) * s.limbs + s.limbs - 1] >> used)
                    throw std::invalid_argument("multiplier witness equation bits");
    }
}

uint64_t coefficient(const Shape &s, const Input &in, uint32_t f, uint32_t limb, uint32_t branch)
{
    const size_t index = (size_t(f) * s.limbs + limb) * s.branches + branch;
    return s.word_bits == 32 ? static_cast<const uint32_t *>(in.coefficients)[index]
                             : static_cast<const uint64_t *>(in.coefficients)[index];
}

void finish_stats(const Shape &s, const Input &in, const Output &out, Stats &stats)
{
    stats.records = in.records;
    stats.coefficient_checks = in.records * s.groups;
    for (size_t r = 0; r < in.records; ++r)
        if (out.first_bad[r] != valid_identity) {
            stats.first_invalid_record = r;
            stats.records_after_first_invalid = in.records - r - 1;
            break;
        }
}

template <bool reference>
static void execute(const Shape &s, const Input &in, const Output &out, Stats &stats)
{
    stats = {};
    const auto started = Clock::now();
    validate(s, in, out);
    stats.validation = elapsed(started);
    for (size_t r = 0; r < in.records; ++r) {
        const uint64_t *u = in.witnesses + r * (s.y + 1) * s.limbs;
        auto get = [&](uint32_t f, uint32_t l) { return coefficient(s, in, f, l, in.branches[r]); };
        if constexpr (reference) {
            std::array<uint8_t, 1024> identity{};
            for (uint32_t slot = 0; slot <= s.y; ++slot)
                for (uint32_t f = 0; f < s.features; ++f) {
                    unsigned parity = 0;
                    for (uint32_t l = 0; l < s.limbs; ++l)
                        parity ^= __builtin_parityll(u[slot * s.limbs + l] & get(f, l));
                    identity[s.masks[f] | (slot ? 1u << (slot - 1) : 0)] ^= parity;
                }
            uint32_t first = valid_identity;
            for (uint32_t g = 0; g < s.groups; ++g) {
                const uint32_t mask = s.layout[g].mask;
                const uint8_t value = identity[mask];
                if (out.coefficients) out.coefficients[r * s.groups + g] = value;
                if (value != unsigned(mask == 0) && first == valid_identity) first = mask;
            }
            out.first_bad[r] = first;
        } else {
            struct Sink : independent_identity::CheckSink {
                uint32_t first = valid_identity, group = 0;
                uint8_t *materialized = nullptr;
                void coefficient(uint32_t mask, unsigned value)
                {
                    if (materialized) materialized[group] = uint8_t(value);
                    ++group;
                    const unsigned difference = value ^ unsigned(mask == 0);
                    bad |= difference;
                    if (difference) first = std::min(first, mask);
                }
            } sink;
            sink.materialized = out.coefficients ? out.coefficients + r * s.groups : nullptr;
            independent_identity::evaluate(s.cpu_layout, 7, get, u, s.limbs, sink);
            out.first_bad[r] = sink.first;
        }
    }
    finish_stats(s, in, out, stats);
    stats.wall = elapsed(started);
}

void oracle(const Shape &s, const Input &i, const Output &o, Stats &t)
{
    execute<true>(s, i, o, t);
}
void cpu(const Shape &s, const Input &i, const Output &o, Stats &t) { execute<false>(s, i, o, t); }
} // namespace multiplier_gpu
