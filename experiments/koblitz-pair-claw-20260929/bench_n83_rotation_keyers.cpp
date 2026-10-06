// Bounded comparison of exact minimal-rotation algorithms for n=83 keys.
// This includes the frozen production keyer without changing its source.
#define main native_pair_stage_main
#include "native_n83_pairs_portable.cpp"
#undef main

#include <random>

V canonical_booth(const Keyer &keyer, F x) {
    V bits = keyer.cycle_bits_lookup(x);
    unsigned char sequence[2 * N];
    for (unsigned pos = 0; pos < N; ++pos) {
        sequence[pos] = unsigned((bits >> (N - 1 - pos)) & 1);
        sequence[N + pos] = sequence[pos];
    }
    unsigned i = 0, j = 1, k = 0;
    while (i < N && j < N && k < N) {
        unsigned a = sequence[i + k], b = sequence[j + k];
        if (a == b) {
            ++k;
        } else {
            if (a > b) {
                i += k + 1;
                if (i <= j) i = j + 1;
            } else {
                j += k + 1;
                if (j <= i) j = i + 1;
            }
            k = 0;
        }
    }
    unsigned offset = std::min(i, j);
    need(offset < N, "Booth offset out of range");
    return offset ? ((bits << offset) | (bits >> (N - offset))) & CYCLE_MASK
                  : bits;
}

V rotate_cycle(V bits, unsigned offset) {
    return offset ? ((bits << offset) | (bits >> (N - offset))) & CYCLE_MASK
                  : bits;
}

// The lexicographically least cyclic word starts at a longest zero run.
// Find every such start with whole-word cyclic ANDs, then compare the few
// remaining full rotations exactly. Constant words are handled separately.
V canonical_zero_run(const Keyer &keyer, F x) {
    V bits = keyer.cycle_bits_lookup(x);
    if (bits == 0 || bits == CYCLE_MASK) return bits;
    V zeros = (~bits) & CYCLE_MASK;
    V candidates = CYCLE_MASK;
    for (unsigned length = 0; length < N; ++length) {
        V extended = candidates & rotate_cycle(zeros, length);
        if (!extended) break;
        candidates = extended;
    }
    V best = CYCLE_MASK;
    while (candidates) {
        unsigned bit = U(candidates) ? unsigned(__builtin_ctzll(U(candidates)))
            : 64 + unsigned(__builtin_ctzll(U(candidates >> 64)));
        best = std::min(best, rotate_cycle(bits, N - 1 - bit));
        candidates &= candidates - 1;
    }
    return best;
}

int main(int argc, char **argv) {
    try {
        need(argc == 2, "usage: bench_n83_rotation_keyers SAMPLE_COUNT");
        U count = std::stoull(argv[1]);
        need(count > 0 && count <= (1 << 22), "invalid sample count");
        Keyer keyer;
        std::mt19937_64 rng(0x83b0057caa17ull);
        std::vector<F> samples;
        samples.reserve(count);
        samples.push_back({0, 0});
        if (samples.size() < count) samples.push_back(one());
        for (unsigned pos = 0; pos < N && samples.size() < count; ++pos)
            samples.push_back(pos < 64 ? F{U(1) << pos, 0}
                                       : F{0, U(1) << (pos - 64)});
        std::array<F, N> normal_basis{};
        for (unsigned pos = 0; pos < N; ++pos)
            normal_basis[pos] = {eccF83::GAMMA_TO_PB[pos][0],
                                 eccF83::GAMMA_TO_PB[pos][1]};
        need(keyer.cycle_bits_lookup(one()) == CYCLE_MASK,
             "normal-basis identity mismatch");
        for (unsigned i = 0; i < N && samples.size() < count; ++i) {
            samples.push_back(normal_basis[i]);
            if (samples.size() < count) samples.push_back(one() ^ normal_basis[i]);
            if (samples.size() < count)
                samples.push_back(normal_basis[i] ^ normal_basis[(i + 28) % N] ^
                                  normal_basis[(i + 56) % N]);
            for (unsigned j = i + 1; j < N && samples.size() < count; ++j)
                samples.push_back(normal_basis[i] ^ normal_basis[j]);
        }
        while (samples.size() < count) samples.push_back({rng(), rng() & HIGH_MASK});
        for (F x : samples)
            need(canonical_booth(keyer, x) == keyer.canonical_x(x),
                 "Booth key differs from production key");
        for (F x : samples)
            need(canonical_zero_run(keyer, x) == keyer.canonical_x(x),
                 "zero-run key differs from production key");
        auto measure = [&](unsigned algorithm) {
            V checksum = 0;
            auto start = std::chrono::steady_clock::now();
            for (F x : samples) {
                if (algorithm == 0) checksum ^= keyer.canonical_x(x);
                if (algorithm == 1) checksum ^= canonical_booth(keyer, x);
                if (algorithm == 2) checksum ^= canonical_zero_run(keyer, x);
            }
            double seconds = std::chrono::duration<double>(
                std::chrono::steady_clock::now() - start).count();
            return std::make_pair(seconds, checksum);
        };
        auto old_first = measure(0);
        auto booth_first = measure(1);
        auto zero_first = measure(2);
        auto zero_second = measure(2);
        auto booth_second = measure(1);
        auto old_second = measure(0);
        need(old_first.second == booth_first.second &&
             old_first.second == booth_second.second &&
             old_first.second == zero_first.second &&
             old_first.second == zero_second.second &&
             old_first.second == old_second.second,
             "benchmark checksum mismatch");
        std::cout << "{\"sample_count\":" << count
                  << ",\"correctness_checked\":true"
                  << ",\"original_seconds\":[" << old_first.first << ','
                  << old_second.first << "]"
                  << ",\"booth_seconds\":[" << booth_first.first << ','
                  << booth_second.first << "]"
                  << ",\"zero_run_seconds\":[" << zero_first.first << ','
                  << zero_second.first << "]"
                  << ",\"checksum_hex\":\"" << hex(old_first.second)
                  << "\"}" << std::endl;
    } catch (const std::exception &error) {
        std::cerr << error.what() << std::endl;
        return 1;
    }
}
