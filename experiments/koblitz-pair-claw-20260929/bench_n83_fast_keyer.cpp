// Standalone exact-key and conversion-cost control without a factor base.
#define main native_pairs_main
#include "native_n83_pairs.cpp"
#undef main

V canonical_reference(const Keyer &keyer, F x) {
    V bits = keyer.cycle_bits_reference(x);
    V best = bits;
    for (unsigned j = 1; j < N; ++j) {
        bits = ((bits << 1) | (bits >> (N - 1))) & CYCLE_MASK;
        if (bits < best) best = bits;
    }
    return best;
}

int main() {
    try {
        Keyer keyer;
        constexpr size_t samples = 1 << 20;
        std::vector<F> inputs;
        inputs.reserve(samples);
        U seed = 0x1056830abca55eedull;
        for (size_t i = 0; i < samples; ++i) {
            seed = seed * 6364136223846793005ull + 1442695040888963407ull;
            U lo = seed;
            seed = seed * 6364136223846793005ull + 1442695040888963407ull;
            inputs.push_back(F{lo, seed & HIGH_MASK});
        }
        for (size_t i = 0; i < inputs.size(); ++i) {
            V slow = canonical_reference(keyer, inputs[i]);
            V fast = keyer.canonical_x(inputs[i]);
            need(slow == fast, "fast canonical key disagrees with reference");
            if (i < 1024)
                need(keyer.canonical_x(sqr(inputs[i])) == fast,
                     "fast canonical key changes under Frobenius");
        }
        const std::array<bool, 8> order{
            false, true, true, false, true, false, false, true};
        std::array<double, 8> seconds{};
        V checksum = 0;
        for (unsigned trial = 0; trial < order.size(); ++trial) {
            auto started = std::chrono::steady_clock::now();
            V local = 0;
            if (order[trial]) {
                for (F x : inputs) local ^= keyer.canonical_x(x);
            } else {
                for (F x : inputs) local ^= canonical_reference(keyer, x);
            }
            seconds[trial] = std::chrono::duration<double>(
                std::chrono::steady_clock::now() - started).count();
            if (!trial) checksum = local;
            need(local == checksum, "timed key checksum mismatch");
        }
        std::cout << "{\"samples\":" << samples
                  << ",\"all_keys_equal\":true"
                  << ",\"frobenius_checks\":1024"
                  << ",\"variant_order\":[\"reference\",\"fast\",\"fast\",\"reference\",\"fast\",\"reference\",\"reference\",\"fast\"]"
                  << ",\"seconds\":[";
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
