#include "constant_identity.h"
#include <array>
#include <chrono>
#include <fstream>
#include <iostream>
#include <limits>
using namespace constant_identity;
using Clock = std::chrono::steady_clock;
static uint64_t word(std::ifstream &in)
{
    unsigned char b[8];
    if (!in.read(reinterpret_cast<char *>(b), 8)) throw std::runtime_error("short input");
    uint64_t v = 0;
    for (unsigned i = 0; i < 8; ++i) v |= uint64_t(b[i]) << (8 * i);
    return v;
}
int main(int argc, char **argv)
{
    if (argc != 2) throw std::invalid_argument("one frozen input path required");
    std::ifstream in(argv[1], std::ios::binary);
    if (word(in) != UINT64_C(0x3636524e52454b)) throw std::runtime_error("kernel input magic");
    const auto x = word(in), y = word(in), equations = word(in), terms = word(in);
    // This exploratory panel uses the frozen 31-equation single-limb family.
    // Width correctness is covered separately by test_constant.cpp.
    if (x < 1 || x > 20 || y < 1 || y > 10 || equations < 1 || equations > 32 || terms > (1u << 20))
        throw std::invalid_argument("kernel input shape");
    const uint32_t branches = 1u << x;
    std::vector<uint32_t> masks, index(1u << y, UINT32_MAX);
    for (uint32_t m = 0; m < (1u << y); ++m)
        if (__builtin_popcount(m) <= 2) {
            index[m] = masks.size();
            masks.push_back(m);
        }
    if (uint64_t(masks.size()) * branches * 4 > (64u << 20)) throw std::length_error("table limit");
    std::vector<uint32_t> table(size_t(masks.size()) * branches);
    for (uint64_t i = 0; i < terms; ++i) {
        auto mask = word(in), c = word(in);
        if ((mask >> (x + y)) || (c >> equations) || index[mask >> x] == UINT32_MAX)
            throw std::invalid_argument("original ANF term");
        table[size_t(index[mask >> x]) * branches + (mask & (branches - 1))] ^= uint32_t(c);
    }
    std::vector<uint64_t> proof(branches);
    for (auto &v : proof) {
        v = word(in);
        if (v >> equations) throw std::invalid_argument("proof equation bits");
    }
    if (in.peek() != std::ifstream::traits_type::eof())
        throw std::invalid_argument("trailing input");
    // Independent ascending-bit transform, outside this kernel-only interval.
    for (uint32_t f = 0; f < masks.size(); ++f)
        for (uint32_t bit = 1; bit < branches; bit <<= 1)
            for (uint32_t base = 0; base < branches; base += 2 * bit)
                for (uint32_t a = 0; a < bit; ++a)
                    table[size_t(f) * branches + base + bit + a] ^=
                        table[size_t(f) * branches + base + a];
    Workspace<uint32_t> scratch(branches, 1);
    const auto expected = original(table.data(), proof.data(), nullptr, branches, masks.size(), 1);
    if (!expected.valid) throw std::runtime_error("original constant identities failed");
    const std::array<std::array<unsigned, 3>, 6> orders{
        {{0, 1, 2}, {0, 2, 1}, {1, 0, 2}, {1, 2, 0}, {2, 0, 1}, {2, 1, 0}}};
    std::cout << "trial,position,arm,wall_ns,features,valid\n";
    for (unsigned trial = 0; trial < 30; ++trial)
        for (unsigned position = 0; position < 3; ++position) {
            const unsigned arm = orders[trial % 6][position];
            const auto start = Clock::now();
            Result result;
            if (!arm)
                result = original(table.data(), proof.data(), nullptr, branches, masks.size(), 1);
            else {
                scratch.prepare(proof.data(), nullptr);
                result = arm == 1 ? scratch.check<false>(table.data(), masks.size())
                                  : scratch.check<true>(table.data(), masks.size());
            }
            const auto ns =
                std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count();
            if (!result.valid || result.features != expected.features || result.avoided_parities)
                throw std::runtime_error("candidate mismatch");
            std::cout << trial << ',' << position << ',' << arm << ',' << ns << ','
                      << result.features << ",1\n";
        }
}
