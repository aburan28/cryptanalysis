#include "../include/curveparams.h"
#include <chrono>
#include <cstdio>
#include <vector>

using R = Ref<CfgF131>;
static unsigned long long rng = 0x20260921abULL;
static unsigned long long next() { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return rng; }

static R::Elem referenceCanonical(const R::Elem &x) {
    auto best=x, cur=x;
    for (int k=1;k<131;++k) {
        cur=R::sqr(cur);
        for (int i=2;i>=0;--i) {
            if (cur.v[i]<best.v[i]) { best=cur; break; }
            if (cur.v[i]>best.v[i]) break;
        }
    }
    return best;
}

int main() {
    std::vector<R::Elem> checks{R::zero(), R::one()}, sparse;
    for (int bit = 0; bit < 131; ++bit) {
        auto x = R::zero(); R::setBit(x, bit); checks.push_back(x);
        checks.push_back(R::add(x, R::one()));
    }
    for (int i = 0; i < 2000; ++i) {
        unsigned long long words[3] = {next(), next(), next() & 7};
        checks.push_back(R::fromLimbs(words));
        auto x = R::zero();
        while (R::weight(x) < 32) R::setBit(x, int(next() % 131));
        sparse.push_back(x); checks.push_back(x);
    }
    for (int bit=3;bit<64;++bit) {
        unsigned long long words[3]={next(),next(),(next()&7)|(1ull<<bit)};
        checks.push_back(R::fromLimbs(words));
    }
    size_t orbitChecks = 0;
    for (const auto &x : checks) {
        const auto expected = referenceCanonical(x);
        if (R::canonical(x) != expected) return 1;
        if (!(x.v[2]&~7ull)) {
            if (R::canonical(R::sigma(x, int(next() % 131))) != expected) return 2;
            ++orbitChecks;
        }
    }
    volatile unsigned long long checksum = 0;
    auto measure = [&](bool fast) {
        const auto begin = std::chrono::steady_clock::now();
        for (int pass = 0; pass < 3; ++pass)
            for (const auto &x : sparse) checksum ^= (fast ? R::canonical(x) : referenceCanonical(x)).v[0];
        return std::chrono::duration<double>(std::chrono::steady_clock::now() - begin).count();
    };
    const double oldSeconds = measure(false), fastSeconds = measure(true);
    printf("{\"ok\":true,\"vectors\":%zu,\"orbit_checks\":%zu,\"timed_dp32_vectors\":%zu,\"reference_seconds\":%.9f,\"filter_seconds\":%.9f,\"speedup\":%.6f}\n",
           checks.size(), orbitChecks, sparse.size() * 3, oldSeconds, fastSeconds, oldSeconds / fastSeconds);
    (void)checksum;
}
