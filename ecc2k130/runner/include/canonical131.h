#pragma once
#include <cstring>

namespace eccHost {

// Select the lexicographically smallest Frobenius conjugate by discarding
// candidates as soon as a more significant output bit rules them out.
// This helper accepts canonical 131-bit normal-basis coordinates only.
template<class R>
static typename R::Elem canonicalOnb131(const typename R::Elem &x) {
    static_assert(R::M == 131);
    if (!(x.v[0] | x.v[1] | x.v[2]) ||
        (x.v[0] == ~0ull && x.v[1] == ~0ull && x.v[2] == 7u)) return x;
    struct Sources {
        unsigned char bit[131][131];
        Sources() {
            int inversePower = 1;
            for (int k = 0; k < 131; ++k) {
                for (int output = 0; output < 131; ++output) {
                    int input = ((output + 1) * inversePower) % 263;
                    if (input > 131) input = 263 - input;
                    bit[output][k] = static_cast<unsigned char>(input - 1);
                }
                inversePower = (inversePower * 132) % 263;
            }
        }
    };
    static const Sources sources;
    unsigned char active[131], zeros[131];
    for (int k = 0; k < 131; ++k) active[k] = static_cast<unsigned char>(k);
    int count = 131;
    for (int output = 130; output >= 0 && count > 1; --output) {
        int kept = 0;
        for (int j = 0; j < count; ++j) {
            const int input = sources.bit[output][active[j]];
            if (((x.v[input >> 6] >> (input & 63)) & 1u) == 0)
                zeros[kept++] = active[j];
        }
        // If every candidate has a one here, this bit cannot distinguish them.
        if (kept) {
            std::memcpy(active, zeros, kept);
            count = kept;
        }
    }
    return active[0] ? R::sigma(x, active[0]) : x;
}

} // namespace eccHost
