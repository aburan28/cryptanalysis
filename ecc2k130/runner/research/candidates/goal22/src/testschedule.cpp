// Compare recursive products to independent schoolbook convolution, including
// odd padding, even splits, both device/host word widths and output canaries.
#include <array>
#include <cstdio>
#include "../include/fieldbs.h"

struct ScheduleCfg {
    template <class W>
    static ECC_HD void mulLeaf(const W *a, const W *b, W *r) { r[0] = a[0] & b[0]; }
};
ECC_DEFINE_LEAF(ScheduleCfg, 1)

static uint64_t rngState = 0x83ec131;
static uint64_t randomWord() {
    rngState ^= rngState << 13;
    rngState ^= rngState >> 7;
    rngState ^= rngState << 17;
    return rngState;
}

template <class W, int N>
bool check() {
    for (int trial = 0; trial < 20; ++trial) {
        std::array<W, N> a, b;
        std::array<W, 2 * N + 1> storage;
        std::array<W, 2 * N - 1> want{};
        const W canary = (W)0x9e3779b97f4a7c15ULL;
        storage.fill(canary);
        for (int i = 0; i < N; ++i) {
            a[i] = trial == 0 ? 0 : trial == 1 ? ~(W)0 : (W)randomWord();
            b[i] = (W)randomWord();
        }
        const auto savedA = a, savedB = b;
        for (int i = 0; i < N; ++i)
            for (int j = 0; j < N; ++j) want[i + j] ^= a[i] & b[j];
        Karat<ScheduleCfg, W, N>::mul(a.data(), b.data(), storage.data() + 1);
        if (storage.front() != canary || storage.back() != canary || a != savedA || b != savedB)
            return false;
        for (int i = 0; i < 2 * N - 1; ++i)
            if (storage[i + 1] != want[i]) return false;
    }
    return true;
}

template <class W>
bool checkSizes() {
    return check<W, 2>() && check<W, 3>() && check<W, 4>() && check<W, 5>() &&
           check<W, 8>() && check<W, 9>() && check<W, 17>() && check<W, 33>() &&
           check<W, 66>() && check<W, 131>();
}

int main() {
    const bool ok = checkSizes<uint32_t>() && checkSizes<uint64_t>();
    printf("Karatsuba schedule %d: %s (400 convolutions, 32/64-bit words, guarded outputs)\n",
           ECC_STREAM_KARAT, ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
}
