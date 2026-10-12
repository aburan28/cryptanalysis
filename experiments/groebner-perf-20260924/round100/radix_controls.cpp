#define ORDER_TEST_REFERENCE 1
#include "f4_radix_radix.inc"
#include <cassert>
#include <iostream>
#include <random>
#include <thread>

static bool descending(Mask a, Mask b) { return less_monomial(b, a); }

static void sort_case(const Poly &terms, size_t minimum, size_t cap, Poly &scratch)
{
    monomial_order_stats = {};
    monomial_radix_stats = {};
    Poly expected = terms, actual = terms;
    std::sort(expected.begin(), expected.end(), descending);
    sort_radix_terms(actual, descending, scratch, minimum, cap);
    assert(actual == expected && scratch.capacity() <= cap);
    const auto &s = monomial_radix_stats;
    assert(s.overflow == 0 && s.calls == 1 && s.terms == terms.size());
    assert(s.radix_calls + s.key_fallbacks == 1);
    assert(s.key_fallbacks ==
           s.small_fallbacks + s.wide_fallbacks + s.cap_fallbacks + s.capacity_fallbacks);
    assert(s.growths + s.reused == s.radix_calls + s.capacity_fallbacks);
    assert(s.passes + s.skipped_passes == 8 * s.radix_calls);
    assert(s.scatter_terms == s.passes * terms.size());
    assert(s.copyback_terms == (s.passes % 2) * terms.size());
    assert(s.peak_capacity <= cap);
}

static void multiple_case(const Poly &terms, Mask mask, uint64_t budget, uint32_t limit)
{
    monomial_order_stats = {};
    monomial_radix_stats = {};
    Engine reference(budget, limit, 100, 1, true), candidate(budget, limit, 100, 1, true);
    reference.nodes = candidate.nodes = {{0, 0, 0}};
    Row input{terms, 0}, left = input, right = input;
    std::string left_error, right_error;
    try {
        left = reference.reference_multiple(input, mask);
    } catch (const Budget &error) {
        left_error = error.what();
    }
    try {
        right = candidate.ordered_multiple(input, mask);
    } catch (const Budget &error) {
        right_error = error.what();
    }
    assert(left_error == right_error && reference.work == candidate.work);
    assert(left.terms == right.terms && left.proof == right.proof);
    assert(reference.nodes.size() == candidate.nodes.size());
    for (size_t i = 0; i < reference.nodes.size(); ++i) {
        assert(reference.nodes[i].op == candidate.nodes[i].op);
        assert(reference.nodes[i].a == candidate.nodes[i].a);
        assert(reference.nodes[i].b == candidate.nodes[i].b);
    }
    assert(monomial_radix_stats.overflow == 0 && candidate.radix_scratch.capacity() <= 32768);
    if (mask && budget < terms.size()) assert(monomial_radix_stats.calls == 0);
}

int main()
{
    std::mt19937_64 random(9901);
    uint64_t sorts = 0, cases = 0;
    for (unsigned trial = 0; trial < 256; ++trial) {
        Poly terms;
        for (unsigned i = 0; i < trial * 2; ++i) terms.push_back(random() & order_mask57);
        if (trial % 2) terms.insert(terms.end(), {0, 0, 1, 1, order_mask57, Mask(1) << 56});
        if (trial % 3 == 0) terms.insert(terms.end(), {Mask(1) << 57, Mask(1) << 63, UINT64_MAX});
        Poly scratch;
        for (size_t cap : {size_t(0), size_t(256), size_t(32768)}) {
            for (size_t minimum : {size_t(0), size_t(128)}) {
                sort_case(terms, minimum, cap, scratch);
                ++sorts;
            }
        }
        for (Mask mask : {Mask(0), Mask(1), Mask(255), order_mask57, Mask(1) << 56, Mask(1) << 57,
                          Mask(1) << 63, UINT64_MAX}) {
            const uint64_t total = terms.size();
            for (uint64_t budget : {uint64_t(0), total ? total - 1 : 0, total, total + 1}) {
                for (uint32_t nodes : {uint32_t(1), uint32_t(1000)}) {
                    multiple_case(terms, mask, budget, nodes);
                    ++cases;
                }
            }
        }
    }
    // Reuse one workspace through capacity/cutoff boundaries. The original
    // comparator checks every output.
    Poly scratch;
    for (size_t n : {size_t(0), size_t(1), size_t(127), size_t(128), size_t(129), size_t(255),
                     size_t(256), size_t(257), size_t(32768), size_t(32769)}) {
        for (unsigned bits : {0u, 1u, 8u, 12u, 24u, 40u, 56u, 57u, 64u}) {
            const Mask support = bits == 64 ? UINT64_MAX : ((Mask(1) << bits) - 1);
            Poly terms;
            for (size_t i = 0; i < n; ++i) terms.push_back(random() & support);
            for (size_t cap : {size_t(256), size_t(32768)}) {
                sort_case(terms, 128, cap, scratch);
                ++sorts;
            }
        }
    }
    for (unsigned requested = 0; requested <= 8; ++requested) {
        Poly terms(128, 3);
        if (requested && requested < 8) {
            // Equal degree keeps the prefix constant; vary exactly the
            // requested low bytes with single-variable monomials.
            for (size_t i = 0; i < terms.size(); ++i) terms[i] = Mask(1) << (i % (8 * requested));
        } else if (requested == 8) {
            for (auto &term : terms) term = random() & order_mask57;
            terms[0] = 0;
            terms[1] = order_mask57;
        }
        sort_case(terms, 128, 32768, scratch);
        assert(monomial_radix_stats.passes == requested);
        ++sorts;
    }
    // Constant keys skip every pass. Repeated same-sized rows reuse allocation.
    Poly constant(128, 3);
    sort_case(constant, 128, 32768, scratch);
    assert(monomial_radix_stats.radix_calls == 1 && monomial_radix_stats.passes == 0);
    sort_case(constant, 128, 32768, scratch);
    assert(monomial_radix_stats.reused == 1);
    scratch.reserve(65536);
    sort_case(constant, 128, 256, scratch);
    assert(monomial_radix_stats.oversized_releases == 1);
    assert(monomial_radix_stats.peak_transient_capacity >= 65536);
    const auto before = monomial_radix_stats.calls;
    std::thread isolated([] { assert(monomial_radix_stats.calls == 0); });
    isolated.join();
    assert(monomial_radix_stats.calls == before);
    uint64_t value = UINT64_MAX;
    radix_count(value);
    assert(value == UINT64_MAX && monomial_radix_stats.overflow == 1);
    std::cout << "RADIX_CONTROLS_PASS multiplication_cases=" << cases
              << " sorting_cases=" << sorts + 3 << "\n";
}
