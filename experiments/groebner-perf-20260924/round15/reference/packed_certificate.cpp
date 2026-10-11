// Independent coefficient decoder followed by the unchanged direct-ANF
// verifier. No solver headers, transformed values, or solver roots are used.
#include "../../pdp-scaling/boolean_certificate.cpp"

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
        for (uint32_t i = 0; i < count; ++i) {
            if (masks[i] >= (uint32_t(1) << n)) throw std::invalid_argument("mask");
            if (equations % 64 && coefficients[size_t(i)*words+words-1] >> (equations % 64))
                throw std::invalid_argument("coefficient");
        }
        std::vector<uint32_t> terms, starts{0};
        // Decode one equation at a time; intentionally independent of the
        // solver's scatter of whole coefficient words into its transform.
        for (uint32_t equation = 0; equation < equations; ++equation) {
            for (uint32_t i = 0; i < count; ++i)
                if ((coefficients[size_t(i)*words+equation/64] >> (equation%64)) & 1)
                    terms.push_back(masks[i]);
            if (terms.size() > UINT32_MAX) throw std::invalid_argument("input size");
            starts.push_back(uint32_t(terms.size()));
        }
        return boolean_certificate(n, terms.data(), uint32_t(terms.size()),
            starts.data(), equations, basis, basis_size, offsets, basis_count, out);
    } catch (const std::invalid_argument&) { return out->code = 6; }
      catch (const std::exception&) { return out->code = 7; }
}
