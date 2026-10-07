// Independent Boolean proof values; monomial masks index coefficients directly.
// Completion and reverse ideal inclusion still use the original hash arithmetic.
struct DenseValue {
    std::vector<uint64_t> words;
    uint64_t terms = 0;
    uint64_t size() const { return terms; }
    void swap(DenseValue& other) {
        words.swap(other.words);
        std::swap(terms, other.terms);
    }
};

// The following methods are inserted inside Checker.
// BEGIN METHODS
    void dense_charge(uint64_t amount) {
        charge(amount);
        dense.word_work += amount;
    }
    DenseValue dense_allocate() {
        const uint64_t bytes = dense.words_per_value * sizeof(uint64_t);
        if (bytes > max_dense_bytes - dense.live_bytes)
            throw Exhausted("dense proof byte budget");
        DenseValue value;
        value.words.resize(dense.words_per_value, 0);
        dense.live_bytes += bytes;
        dense.peak_bytes = std::max(dense.peak_bytes, dense.live_bytes);
        ++dense.created_values;
        return value;
    }
    DenseValue dense_input(const Polynomial& original) {
        // Charge initialization and input conversion, including input copies
        // that the original checker did not account as arithmetic work.
        dense_charge(dense.words_per_value);
        charge(original.size());
        auto value = dense_allocate();
        for (uint64_t term : original)
            value.words[term >> 6] |= UINT64_C(1) << (term & 63);
        value.terms = original.size();
        return value;
    }
    DenseValue dense_add(const DenseValue& left, const DenseValue& right) {
        // Preserve the reference term charge; charge dense word work on top.
        charge(left.size() + right.size());
        dense_charge(3 * dense.words_per_value); // initialize, XOR, popcount
        auto value = dense_allocate();
        for (size_t i = 0; i < value.words.size(); ++i) {
            value.words[i] = left.words[i] ^ right.words[i];
            value.terms += __builtin_popcountll(value.words[i]);
        }
        return value;
    }
    DenseValue dense_multiply(const DenseValue& original, uint64_t monomial) {
        charge(original.size());
        dense_charge(3 * dense.words_per_value); // initialize, scan, popcount
        auto value = dense_allocate();
        for (size_t i = 0; i < original.words.size(); ++i) {
            uint64_t bits = original.words[i];
            while (bits) {
                const uint64_t term = ((i << 6) | __builtin_ctzll(bits)) | monomial;
                value.words[term >> 6] ^= UINT64_C(1) << (term & 63);
                bits &= bits - 1;
            }
        }
        for (uint64_t bits : value.words)
            value.terms += __builtin_popcountll(bits);
        return value;
    }
    bool dense_equal(const DenseValue& value, const Polynomial& expected) {
        charge(expected.size());
        if (value.size() != expected.size()) return false;
        for (uint64_t term : expected)
            if (!(value.words[term >> 6] & (UINT64_C(1) << (term & 63)))) return false;
        return true;
    }
// END METHODS
