#pragma once
#include "monomial_order.h"
#include <array>

struct MonomialRadixStats {
    uint64_t calls = 0, terms = 0, radix_calls = 0, radix_terms = 0;
    uint64_t key_fallbacks = 0, small_fallbacks = 0, wide_fallbacks = 0;
    uint64_t cap_fallbacks = 0, capacity_fallbacks = 0, growths = 0, reused = 0;
    uint64_t passes = 0, skipped_passes = 0, scatter_terms = 0, copyback_terms = 0;
    uint64_t peak_capacity = 0, peak_transient_capacity = 0, oversized_releases = 0;
    uint64_t overflow = 0;
};
static thread_local MonomialRadixStats monomial_radix_stats{};

inline void radix_count(uint64_t &value, uint64_t amount = 1) noexcept
{
    if (amount > std::numeric_limits<uint64_t>::max() - value) {
        value = std::numeric_limits<uint64_t>::max();
        monomial_radix_stats.overflow = 1;
    } else
        value += amount;
}

template <typename Compare>
void sort_radix_terms(std::vector<uint64_t> &terms, Compare compare, std::vector<uint64_t> &scratch,
                      size_t minimum, size_t cap)
{
    auto &stats = monomial_radix_stats;
    radix_count(stats.calls);
    radix_count(stats.terms, terms.size());
    stats.peak_transient_capacity =
        std::max<uint64_t>(stats.peak_transient_capacity, scratch.capacity());
    if (scratch.capacity() > cap) {
        std::vector<uint64_t>{}.swap(scratch);
        radix_count(stats.oversized_releases);
    }
    auto fallback = [&] {
        radix_count(stats.key_fallbacks);
        sort_ordered_terms(terms, compare, true, 0);
    };
    if (terms.size() < minimum || terms.size() < 2) {
        radix_count(stats.small_fallbacks);
        fallback();
        return;
    }
    uint64_t support = 0;
    for (uint64_t term : terms) support |= term;
    if (support & ~order_mask57) {
        radix_count(stats.wide_fallbacks);
        fallback();
        return;
    }
    if (terms.size() > cap) {
        radix_count(stats.cap_fallbacks);
        fallback();
        return;
    }
    // Explicit reserve avoids resize's geometric growth crossing the cap.
    // Check actual capacity as the standard permits over-allocation.
    if (scratch.capacity() < terms.size()) {
        scratch.reserve(terms.size());
        radix_count(stats.growths);
    } else
        radix_count(stats.reused);
    stats.peak_transient_capacity =
        std::max<uint64_t>(stats.peak_transient_capacity, scratch.capacity());
    if (scratch.capacity() > cap) {
        std::vector<uint64_t>{}.swap(scratch);
        radix_count(stats.oversized_releases);
        radix_count(stats.capacity_fallbacks);
        fallback();
        return;
    }
    scratch.resize(terms.size());
    stats.peak_capacity = std::max<uint64_t>(stats.peak_capacity, scratch.capacity());
    radix_count(stats.radix_calls);
    radix_count(stats.radix_terms, terms.size());
    order_count(monomial_order_stats.calls);
    order_count(monomial_order_stats.terms, terms.size());
    order_count(monomial_order_stats.key_calls);
    order_count(monomial_order_stats.key_terms, terms.size());

    const uint64_t first = monomial_key57(terms.front());
    uint64_t varying = 0;
    for (auto &term : terms) {
        term = monomial_key57(term);
        varying |= term ^ first;
    }
    auto *source = terms.data();
    auto *destination = scratch.data();
    for (unsigned shift = 0; shift < 64; shift += 8) {
        if (((varying >> shift) & 255) == 0) {
            radix_count(stats.skipped_passes);
            continue;
        }
        std::array<size_t, 256> positions{};
        for (size_t i = 0; i < terms.size(); ++i) ++positions[(source[i] >> shift) & 255];
        size_t start = 0;
        for (auto &count : positions) {
            const size_t length = count;
            count = start;
            start += length;
        }
        for (size_t i = 0; i < terms.size(); ++i) {
            const auto key = source[i];
            destination[positions[(key >> shift) & 255]++] = key;
        }
        std::swap(source, destination);
        radix_count(stats.passes);
        radix_count(stats.scatter_terms, terms.size());
    }
    if (source != terms.data()) {
        std::copy(source, source + terms.size(), terms.begin());
        radix_count(stats.copyback_terms, terms.size());
    }
    for (auto &term : terms) term &= order_mask57;
}
