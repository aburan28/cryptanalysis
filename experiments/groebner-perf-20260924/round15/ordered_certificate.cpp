// Independent packed decoder. Only monomial ordering is shared by equations;
// coefficients, input zeros and basis checks remain independently evaluated.
#include "build/sorted_core.inc"
#include <numeric>

extern "C" int packed_boolean_certificate(uint32_t n, uint32_t equations,
        const uint32_t* masks, const uint64_t* coefficients, uint32_t count,
        const uint32_t* basis, uint32_t basis_size, const uint32_t* offsets,
        uint32_t basis_count, Certificate* out) {
    if (!out) return 6;
    *out = {};
    try {
        if (n < 1 || n > 20 || equations < 1 || equations > 4096 ||
            (count && (!masks || !coefficients)))
            throw std::invalid_argument("packed dimensions");
        const size_t words = (equations + 63) / 64;
        bool sorted = true;
        for (uint32_t i = 0; i < count; ++i) {
            if (masks[i] >= (uint32_t(1) << n)) throw std::invalid_argument("mask");
            if (equations % 64 && coefficients[size_t(i)*words+words-1] >> (equations % 64))
                throw std::invalid_argument("coefficient");
            if (i && masks[i] < masks[i-1]) sorted = false;
        }
        std::vector<uint32_t> order;
        if (!sorted) {
            order.resize(count);
            std::iota(order.begin(), order.end(), uint32_t(0));
            std::sort(order.begin(), order.end(),
                      [masks](uint32_t a, uint32_t b) { return masks[a] < masks[b]; });
        }
        std::vector<uint32_t> terms, starts{0};
        // Duplicate masks are retained: the generic independent checker below
        // cancels them by parity, exactly as it does for unordered row input.
        for (uint32_t equation = 0; equation < equations; ++equation) {
            const size_t word = equation / 64;
            const uint64_t bit = uint64_t(1) << (equation % 64);
            if (sorted) {
                for (uint32_t i = 0; i < count; ++i)
                    if (coefficients[size_t(i)*words+word] & bit) terms.push_back(masks[i]);
            } else {
                for (uint32_t i : order)
                    if (coefficients[size_t(i)*words+word] & bit) terms.push_back(masks[i]);
            }
            if (terms.size() > UINT32_MAX) throw std::invalid_argument("input size");
            starts.push_back(uint32_t(terms.size()));
        }
        return boolean_certificate(n, terms.data(), uint32_t(terms.size()),
            starts.data(), equations, basis, basis_size, offsets, basis_count, out);
    } catch (const std::invalid_argument&) { return out->code = 6; }
      catch (const std::exception&) { return out->code = 7; }
}
