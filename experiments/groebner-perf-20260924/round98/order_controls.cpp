#define ORDER_TEST_REFERENCE 1
#include "f4_order_keys.inc"
#include <cassert>
#include <iostream>
#include <random>
#include <thread>

static bool descending(Mask a, Mask b) { return less_monomial(b, a); }

static void multiple_case(const Poly &terms, Mask mask, uint64_t budget,
                          uint32_t limit) {
  monomial_order_stats = {};
  Engine reference(budget, limit, 100, 1, true),
      candidate(budget, limit, 100, 1, true);
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
  assert(monomial_order_stats.overflow == 0);
  assert(monomial_order_stats.calls ==
         monomial_order_stats.key_calls +
             monomial_order_stats.comparison_calls);
  assert(monomial_order_stats.terms ==
         monomial_order_stats.key_terms +
             monomial_order_stats.comparison_terms);
  if (mask && budget < terms.size())
    assert(monomial_order_stats.calls == 0);
}

int main() {
  uint64_t order_pairs = 0, cases = 0;
  for (Mask a = 0; a < 1024; ++a) {
    for (Mask b = 0; b < 1024; ++b) {
      assert(descending(a, b) == (monomial_key57(a) < monomial_key57(b)));
      ++order_pairs;
    }
  }
  std::mt19937_64 random(9801);
  for (unsigned trial = 0; trial < 512; ++trial) {
    Poly terms;
    for (unsigned i = 0; i < trial % 129; ++i)
      terms.push_back(random() & order_mask57);
    if (trial % 2)
      terms.insert(terms.end(), {0, 0, 1, 1, order_mask57, Mask(1) << 56});
    if (trial % 3 == 0)
      terms.insert(terms.end(), {Mask(1) << 57, Mask(1) << 63, UINT64_MAX});
    Poly expected = terms;
    std::sort(expected.begin(), expected.end(), descending);
    for (bool enabled : {false, true}) {
      for (size_t minimum : {size_t(0), size_t(32)}) {
        monomial_order_stats = {};
        Poly actual = terms;
        sort_ordered_terms(actual, descending, enabled, minimum);
        assert(actual == expected);
        if (!enabled)
          assert(monomial_order_stats.disabled_calls == 1);
        else if (terms.size() < minimum)
          assert(monomial_order_stats.small_calls == 1);
        else if (trial % 3 == 0)
          assert(monomial_order_stats.wide_calls == 1);
        else
          assert(monomial_order_stats.key_calls == 1);
      }
    }
    for (Mask mask : {Mask(0), Mask(1), Mask(255), order_mask57, Mask(1) << 56,
                      Mask(1) << 57, Mask(1) << 63, UINT64_MAX}) {
      const uint64_t total = terms.size();
      for (uint64_t budget :
           {uint64_t(0), total ? total - 1 : 0, total, total + 1}) {
        for (uint32_t nodes : {uint32_t(1), uint32_t(1000)}) {
          multiple_case(terms, mask, budget, nodes);
          ++cases;
        }
      }
    }
    const Mask a = random() & order_mask57, b = random() & order_mask57;
    assert((monomial_key57(a) & order_mask57) == a);
    assert(descending(a, b) == (monomial_key57(a) < monomial_key57(b)));
    ++order_pairs;
  }
  assert(monomial_key57(0) == (uint64_t(1) << 63));
  const auto before = monomial_order_stats.calls;
  std::thread isolated([] { assert(monomial_order_stats.calls == 0); });
  isolated.join();
  assert(monomial_order_stats.calls == before);
  uint64_t value = UINT64_MAX;
  order_count(value);
  assert(value == UINT64_MAX && monomial_order_stats.overflow == 1);
  std::cout << "ORDER_CONTROLS_PASS cases=" << cases
            << " order_pairs=" << order_pairs << "\n";
}
