#include "f4_normal_scratch.inc"
#include <cassert>
#include <iostream>
#include <random>
#include <thread>

static Poly ordered(Poly terms)
{
    std::sort(terms.begin(), terms.end(), [](Mask a, Mask b) { return less_monomial(b, a); });
    terms.erase(std::unique(terms.begin(), terms.end()), terms.end());
    return terms;
}
static void compare_case(const Poly &a, const Poly &b, size_t cap, uint64_t budget, uint32_t nodes)
{
    normal_scratch_stats = {};
    Engine reference(budget, nodes, 100, 1, true), candidate(budget, nodes, 100, 1, true);
    reference.nodes = candidate.nodes = {{0, 0, 0}, {0, 1, 0}};
    Row old{a, 0}, actual{a, 0}, other{b, 1};
    Poly scratch;
    std::string left_error, right_error;
    try {
        old = reference.ordered_add(old, other);
    } catch (const Budget &error) {
        left_error = error.what();
    }
    try {
        candidate.ordered_scratch_add(actual, other, scratch, cap);
    } catch (const Budget &error) {
        right_error = error.what();
    }
    assert(left_error == right_error && reference.work == candidate.work);
    assert(old.terms == actual.terms && old.proof == actual.proof);
    assert(reference.nodes.size() == candidate.nodes.size());
    for (size_t i = 0; i < reference.nodes.size(); ++i) {
        assert(reference.nodes[i].op == candidate.nodes[i].op);
        assert(reference.nodes[i].a == candidate.nodes[i].a);
        assert(reference.nodes[i].b == candidate.nodes[i].b);
    }
    assert(normal_scratch_stats.overflow == 0);
    assert(normal_scratch_stats.charged_terms == candidate.work);
    assert(normal_scratch_stats.calls == normal_scratch_stats.fresh_vectors +
                                             normal_scratch_stats.growths +
                                             normal_scratch_stats.reused);
    assert(normal_scratch_stats.completed == (left_error.empty() ? 1 : 0));
    if (right_error.empty())
        assert(scratch.capacity() <= cap);
    else
        assert(actual.terms == a && actual.proof == 0);
}
int main()
{
    std::mt19937_64 random(9701);
    uint64_t cases = 0;
    for (unsigned trial = 0; trial < 256; ++trial) {
        Poly a, b;
        for (unsigned i = 0; i < trial % 33; ++i) {
            a.push_back(random() & 255);
            b.push_back(random() & 255);
        }
        if (trial % 2) {
            a.push_back(Mask(1) << 63);
            b.push_back(UINT64_MAX);
        }
        a = ordered(a);
        b = ordered(b);
        const uint64_t total = a.size() + b.size();
        for (size_t cap : {size_t(0), size_t(4), size_t(32768)}) {
            for (uint64_t budget : {uint64_t(0), total ? total - 1 : 0, total, total + 1}) {
                for (uint32_t nodes : {uint32_t(2), uint32_t(1000)}) {
                    compare_case(a, b, cap, budget, nodes);
                    ++cases;
                }
            }
        }
    }
    normal_scratch_stats = {};
    Engine engine(100000, 10000, 100, 1, true);
    engine.nodes = {{0, 0, 0}, {0, 1, 0}};
    Row row{ordered({0, 1}), 0}, other{ordered({2}), 1};
    row.terms.reserve(128);
    Poly scratch;
    engine.ordered_scratch_add(row, other, scratch, 8);
    assert(normal_scratch_stats.oversized_releases == 1 && scratch.capacity() == 0);
    assert(normal_scratch_stats.released_capacity_words >= 128);
    assert(normal_scratch_stats.peak_scratch_capacity >= 128);
    for (unsigned i = 0; i < 100; ++i) engine.ordered_scratch_add(row, other, scratch, 8);
    assert(normal_scratch_stats.reused > 90 && scratch.capacity() <= 8);
    assert(normal_scratch_stats.peak_retained_scratch_capacity <= 8);
    // Aliased polynomial operands remain valid; the proof operands are read
    // before row replacement, and equal polynomials cancel to zero.
    engine.ordered_scratch_add(row, row, scratch, 8);
    assert(row.terms.empty());
    const auto before = normal_scratch_stats.calls;
    std::thread isolated([] { assert(normal_scratch_stats.calls == 0); });
    isolated.join();
    assert(normal_scratch_stats.calls == before);
    uint64_t saturated = UINT64_MAX;
    normal_count(saturated);
    assert(saturated == UINT64_MAX && normal_scratch_stats.overflow == 1);
    std::cout << "NORMAL_CONTROLS_PASS cases=" << cases << "\n";
}
