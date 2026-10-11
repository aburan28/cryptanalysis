#include "constant_identity.h"
#include <cassert>
#include <iostream>
#include <random>

using namespace constant_identity;
template <class T> uint64_t controls(uint32_t limbs)
{
    std::mt19937_64 rng(665501 + sizeof(T) + limbs);
    uint64_t count = 0;
    for (uint32_t branches : {1u, 2u, 3u, 4u, 31u, 32u, 33u, 64u, 257u}) {
        for (uint32_t features : {1u, 2u, 7u, 46u, 56u}) {
            Workspace<T> work(branches, limbs);
            std::vector<T> table(size_t(branches) * features * limbs);
            std::vector<uint64_t> proof(size_t(branches) * limbs);
            std::vector<unsigned char> reuse(branches);
            auto check = [&](bool use_reuse) {
                const auto *aliases = use_reuse ? reuse.data() : nullptr;
                const auto expected =
                    original(table.data(), proof.data(), aliases, branches, features, limbs);
                work.prepare(proof.data(), aliases);
                for (const auto actual : {work.template check<false>(table.data(), features),
                                          work.template check<true>(table.data(), features)}) {
                    assert(actual.valid == expected.valid && actual.features == expected.features &&
                           actual.avoided_parities == expected.avoided_parities);
                    ++count;
                }
            };
            for (unsigned pattern = 0; pattern < 8; ++pattern) {
                for (auto &v : table) v = T(rng());
                for (auto &v : proof) v = pattern == 0 ? 0 : T(rng());
                for (auto &v : reuse) v = pattern % 3;
                if (pattern >= 3) {
                    // Every active witness is 1; coefficient bit zero alone decides the identity.
                    std::fill(proof.begin(), proof.end(), 0);
                    for (uint32_t x = 0; x < branches; ++x) proof[size_t(x) * limbs] = 1;
                    for (uint32_t f = 0; f < features; ++f)
                        for (uint32_t x = 0; x < branches; ++x) {
                            auto &v = table[size_t(f) * limbs * branches + x];
                            v = (v & ~T(1)) | T(f == 0);
                        }
                    if (pattern >= 4) {
                        const uint32_t f = pattern == 4   ? 0
                                           : pattern == 5 ? features / 2
                                                          : features - 1;
                        table[size_t(f) * limbs * branches + (branches - 1)] ^= 1;
                    }
                    if (pattern == 7) reuse.back() = 1;
                }
                check(false);
                check(true);
                // Reuse the same allocation with a fresh all-zero witness and changed aliases.
                std::fill(proof.begin(), proof.end(), 0);
                for (auto &v : reuse) v = unsigned(rng() % 3);
                check(true);
            }
        }
    }
    return count;
}
int main()
{
    const auto count = controls<uint32_t>(1) + controls<uint64_t>(1) + controls<uint64_t>(2);
    for (const auto shape : {std::pair<uint32_t, uint32_t>{0, 1}, {1u << 21, 1}, {1, 0}, {1, 3}}) {
        bool rejected = false;
        try {
            Workspace<uint64_t> bad(shape.first, shape.second);
        } catch (const std::invalid_argument &) {
            rejected = true;
        }
        assert(rejected);
    }
    bool rejected = false;
    try {
        Workspace<uint32_t> bad(2, 2);
    } catch (const std::invalid_argument &) {
        rejected = true;
    }
    assert(rejected);
    std::cout << "CONSTANT_IDENTITY_CONTROLS_PASS " << count << "\n";
}
