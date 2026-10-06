// Compare the cyclic zero-run key minimum with every Frobenius rotation.
#define main native_pairs_main
#include "native_n83_pairs.cpp"
#undef main

V cycle_reference(V bits) {
    V best = bits;
    for (unsigned j = 1; j < N; ++j) {
        bits = ((bits << 1) | (bits >> (N - 1))) & CYCLE_MASK;
        if (bits < best) best = bits;
    }
    return best;
}

V cycle_gap(V bits) {
    if (bits == 0 || bits == CYCLE_MASK) return bits;
    auto bit_position = [](V value) {
        U lo = U(value);
        return lo ? unsigned(__builtin_ctzll(lo)) :
                    64 + unsigned(__builtin_ctzll(U(value >> 64)));
    };
    V remaining = bits;
    unsigned first = bit_position(remaining);
    unsigned previous = first;
    remaining &= remaining - 1;
    unsigned longest = 0;
    V best = CYCLE_MASK;
    auto consider = [&](unsigned next, unsigned zeros) {
        if (zeros < longest) return;
        unsigned shift = next ? N - next : 0;
        V candidate = ((bits << shift) | (bits >> (N - shift))) & CYCLE_MASK;
        if (zeros > longest || candidate < best) {
            longest = zeros;
            best = candidate;
        }
    };
    while (remaining) {
        unsigned next = bit_position(remaining);
        consider(next, next - previous - 1);
        previous = next;
        remaining &= remaining - 1;
    }
    consider(first, first + N - previous - 1);
    return best;
}

int main() {
    try {
        Keyer keyer;
        for (unsigned i = 0; i < N; ++i)
            for (unsigned j = i + 1; j < N; ++j) {
                V bits = (V(1) << i) | (V(1) << j);
                need(cycle_gap(bits) == cycle_reference(bits),
                     "two-bit cyclic minimum mismatch");
            }
        constexpr size_t samples = 1 << 20;
        std::vector<F> inputs;
        inputs.reserve(samples);
        U seed = 0x105783cc83cc1057ull;
        for (size_t i = 0; i < samples; ++i) {
            seed = seed * 6364136223846793005ull + 1442695040888963407ull;
            U lo = seed;
            seed = seed * 6364136223846793005ull + 1442695040888963407ull;
            inputs.push_back(F{lo, seed & HIGH_MASK});
        }
        auto key = [&](F x, unsigned variant) {
            V bits = variant == 0 ? keyer.cycle_bits_reference(x) :
                                    keyer.cycle_bits_lookup(x);
            return variant == 2 ? cycle_gap(bits) : cycle_reference(bits);
        };
        for (size_t i = 0; i < samples; ++i) {
            V reference = key(inputs[i], 0);
            need(key(inputs[i], 1) == reference &&
                 key(inputs[i], 2) == reference &&
                 keyer.canonical_x(inputs[i]) == reference,
                 "gap quotient key mismatch");
            if (i < 1024)
                need(keyer.canonical_x(sqr(inputs[i])) == reference,
                     "gap quotient key changes under Frobenius");
        }
        const std::array<unsigned, 12> order{
            0, 1, 2, 2, 1, 0, 0, 1, 2, 2, 1, 0};
        std::array<double, 12> seconds{};
        V checksum = 0;
        for (unsigned trial = 0; trial < order.size(); ++trial) {
            auto started = std::chrono::steady_clock::now();
            V local = 0;
            for (F x : inputs) local ^= key(x, order[trial]);
            seconds[trial] = std::chrono::duration<double>(
                std::chrono::steady_clock::now() - started).count();
            if (!trial) checksum = local;
            need(local == checksum, "timed gap key checksum mismatch");
        }
        std::cout << "{\"samples\":" << samples
                  << ",\"all_keys_equal\":true"
                  << ",\"two_bit_patterns_checked\":" << N * (N - 1) / 2
                  << ",\"frobenius_checks\":1024"
                  << ",\"variant_order\":[";
        for (unsigned i = 0; i < order.size(); ++i) {
            if (i) std::cout << ',';
            std::cout << order[i];
        }
        std::cout << "],\"seconds\":[";
        for (unsigned i = 0; i < seconds.size(); ++i) {
            if (i) std::cout << ',';
            std::cout << std::setprecision(12) << seconds[i];
        }
        std::cout << "],\"checksum_hex\":\"" << hex(checksum)
                  << "\"}" << std::endl;
    } catch (const std::exception &exc) {
        std::cerr << exc.what() << std::endl;
        return 1;
    }
    return 0;
}
