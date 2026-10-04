// Exact curve-lift predicate for nonzero x on y^2 + x*y = x^3 + 1.
#pragma once

#include "../q1420_root_theory/root_field.hpp"

namespace q1422 {

inline bool curve_lifts(q1420::Field &field, q1420::U128 x_onb) {
    q1420::require(x_onb && !(x_onb & ~field.mask), "invalid nonzero leaf x");
    q1420::U128 inverse_onb = field.to_onb(field.inv(field.to_poly(x_onb)));
    q1420::U128 trace_argument = x_onb ^ inverse_onb;
    unsigned parity = unsigned(__builtin_popcountll(uint64_t(trace_argument)) +
                               __builtin_popcountll(
                                   uint64_t(trace_argument >> 64))) & 1U;
    return parity == 0;
}

}  // namespace q1422
