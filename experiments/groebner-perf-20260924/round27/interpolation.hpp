// Buchberger-Moeller frontier interpolation adapted from round4/packed_dual.cpp.
// Only the producer uses this code. Masks are widened; no full cube is allocated.
#pragma once
#include <algorithm>
#include <set>
#include <stdexcept>
#include <vector>
using Mask = uint64_t;
using Polynomial = std::vector<Mask>;
using Bits = std::vector<uint64_t>;
struct Grevlex {
    bool operator()(Mask a, Mask b) const {
        int da = __builtin_popcountll(a), db = __builtin_popcountll(b);
        return da != db ? da < db : a > b;
    }
};
static int lead(const Bits& a) {
    for (int w = int(a.size()) - 1; w >= 0; --w)
        if (a[w]) return w*64 + 63 - __builtin_clzll(a[w]);
    return -1;
}
static void xor_bits(Bits& a, const Bits& b) {
    for (size_t i = 0; i < a.size(); ++i) a[i] ^= b[i];
}
static std::vector<Polynomial> interpolate(uint32_t n, const std::vector<Mask>& roots,
                                           BranchStats& stats) {
    const size_t r = roots.size(), words = (r + 63)/64;
    std::vector<Bits> values(r), combinations(r);
    std::vector<Mask> standard, leading;
    std::vector<Polynomial> basis;
    std::set<Mask, Grevlex> frontier{0};
    std::set<Mask> discovered{0};
    while (!frontier.empty()) {
        Mask monomial = *frontier.begin();
        frontier.erase(frontier.begin());
        ++stats.work;
        if (std::any_of(leading.begin(), leading.end(),
            [&](Mask lm) { return (lm & monomial) == lm; })) continue;
        Bits value(words), combo(words);
        for (size_t i = 0; i < r; ++i)
            if ((monomial & roots[i]) == monomial) value[i/64] |= uint64_t(1) << (i%64);
        int pivot;
        while ((pivot = lead(value)) >= 0 && !values[pivot].empty()) {
            xor_bits(value, values[pivot]);
            xor_bits(combo, combinations[pivot]);
        }
        if (pivot < 0) {
            Polynomial row{monomial};
            for (size_t j = 0; j < standard.size(); ++j)
                if ((combo[j/64] >> (j%64)) & 1) row.push_back(standard[j]);
            std::sort(row.begin(), row.end());
            basis.push_back(std::move(row));
            leading.push_back(monomial);
        } else {
            if (standard.size() >= r) throw std::runtime_error("interpolation rank invariant");
            size_t j = standard.size();
            combo[j/64] ^= uint64_t(1) << (j%64);
            values[pivot] = std::move(value);
            combinations[pivot] = std::move(combo);
            standard.push_back(monomial);
            for (uint32_t variable = 0; variable < n; ++variable) {
                Mask multiple = monomial | (uint64_t(1) << variable);
                if (discovered.insert(multiple).second) frontier.insert(multiple);
            }
        }
    }
    if (standard.size() != r) throw std::runtime_error("incomplete interpolation");
    stats.standard = standard.size();
    auto lm = [](const Polynomial& p) {
        return *std::max_element(p.begin(), p.end(), Grevlex{});
    };
    std::sort(basis.begin(), basis.end(),
              [&](const Polynomial& a, const Polynomial& b) { return Grevlex{}(lm(b), lm(a)); });
    return basis;
}
