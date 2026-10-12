// A bounded semantic obstruction for an incomplete Boolean Groebner seed.
// The final independent certificate checker remains the authority on success.
#include "proof_abi.h"
#include <array>
#include <cstdint>
#include <utility>
#include <vector>

struct FieldObstruction {
    uint64_t work, field_pairs, reduction_steps, witness_row, witness_term;
    uint32_t witness_bit, status;
};

namespace {
struct Budget {};
struct Invalid {};
struct Polynomial {
    std::array<uint64_t,64> words{};
    uint32_t count=0;
    void toggle(uint64_t term) {
        const uint64_t bit=UINT64_C(1)<<(term%64);
        const bool present=words[term/64]&bit;
        words[term/64]^=bit;
        if (present) --count;
        else ++count;
    }
    template<class F> void each(F fn) const {
        for (uint32_t word=0;word<64;++word) {
            uint64_t bits=words[word];
            while (bits) {
                const unsigned bit=__builtin_ctzll(bits);
                fn(uint64_t(word)*64+bit);
                bits&=bits-1;
            }
        }
    }
};
struct Probe {
    uint64_t cap;
    FieldObstruction &stats;
    void charge(uint64_t amount=1) {
        if (amount>cap-stats.work) throw Budget{};
        stats.work+=amount;
    }
    uint64_t leading(const Polynomial &row) {
        if (!row.count) throw Invalid{};
        charge(row.count);
        uint64_t best=0;
        int degree=-1;
        row.each([&](uint64_t term) {
            const int next=__builtin_popcountll(term);
            if (next>degree || (next==degree && term<best)) {
                best=term;
                degree=next;
            }
        });
        return best;
    }
    Polynomial multiply(const Polynomial &row,uint64_t mask) {
        charge(row.count);
        Polynomial result;
        row.each([&](uint64_t term) { result.toggle(term|mask); });
        return result;
    }
    void add(Polynomial &left,const Polynomial &right) {
        charge(left.count+right.count);
        right.each([&](uint64_t term) { left.toggle(term); });
    }
    bool nonzero_remainder(Polynomial value,const std::vector<Polynomial> &basis,
                           const std::vector<uint64_t> &leads,uint64_t &witness) {
        while (value.count) {
            const uint64_t head=leading(value);
            bool reduced=false;
            for (size_t i=0;i<basis.size();++i) {
                charge();
                if ((head&leads[i])!=leads[i]) continue;
                auto product=multiply(basis[i],head&~leads[i]);
                if (!product.count || leading(product)!=head) throw Invalid{};
                add(value,product);
                ++stats.reduction_steps;
                reduced=true;
                break;
            }
            if (!reduced) {
                // Later reductions are strictly below head, so this term
                // remains in the normal form and proves non-completion.
                witness=head;
                return true;
            }
        }
        return false;
    }
};
}

extern "C" int find_field_obstruction(const PackedInput *input,const ProofView *proof,
                                        uint64_t max_work,FieldObstruction *out) {
    if (!out) return -1;
    *out={};
    if (!input || !proof || input->nvars<1 || input->nvars>12 ||
        proof->version!=1 || proof->order!=1 || proof->reserved ||
        proof->nvars!=input->nvars || proof->rows>128 || proof->terms>20000 ||
        !proof->offsets || (proof->terms && !proof->basis_terms)) return 0;
    try {
        Probe probe{max_work,*out};
        const uint64_t limit=UINT64_C(1)<<input->nvars;
        if (proof->offsets[0] || proof->offsets[proof->rows]!=proof->terms) throw Invalid{};
        std::vector<Polynomial> basis;
        std::vector<uint64_t> leads;
        basis.reserve(proof->rows);
        leads.reserve(proof->rows);
        for (uint64_t i=0;i<proof->rows;++i) {
            const auto begin=proof->offsets[i],end=proof->offsets[i+1];
            if (begin>=end || end>proof->terms) throw Invalid{};
            probe.charge(end-begin);
            Polynomial row;
            for (uint64_t j=begin;j<end;++j) {
                const uint64_t term=proof->basis_terms[j];
                if (term>=limit) throw Invalid{};
                row.toggle(term);
            }
            if (!row.count) throw Invalid{};
            leads.push_back(probe.leading(row));
            basis.push_back(std::move(row));
        }
        for (size_t i=0;i<basis.size();++i) {
            for (uint32_t bit=0;bit<input->nvars;++bit) {
                if (!(leads[i]&(UINT64_C(1)<<bit))) continue;
                ++out->field_pairs;
                auto pair=probe.multiply(basis[i],UINT64_C(1)<<bit);
                uint64_t witness=0;
                if (probe.nonzero_remainder(std::move(pair),basis,leads,witness)) {
                    out->status=1;
                    out->witness_row=i;
                    out->witness_bit=bit;
                    out->witness_term=witness;
                    return 1;
                }
            }
        }
        return 0;
    } catch (const Budget &) {
        out->status=2;
        return 0;
    } catch (const Invalid &) {
        out->status=3;
        return 0;
    }
}
