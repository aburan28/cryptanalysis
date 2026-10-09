"""Use a bounded grevlex bitset inside exact F4 normalization."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE_SHA256 = "eeb7e09ce6893cb5ba52eca24cc1c25b84266279bd6b55a80ea4005f123ff933"


def once(source, old, new):
    assert source.count(old) == 1, (old, source.count(old))
    return source.replace(old, new, 1)


def bitset_engine(source):
    source = once(source, "#include <algorithm>\n", "#include <algorithm>\n#include <array>\n")
    source = once(source, "    std::vector<Mask> basis_leads;\n", '''    std::vector<Mask> basis_leads;
    // Per-query order maps; no coefficient data survive this Engine instance.
    std::array<uint16_t,4096> bit_rank;
    std::array<Mask,4096> bit_monomial;
    bool bit_ready=false;
''')
    marker = "    // Equivalent to a*b successive charge(1) calls. On exhaustion the old\n"
    helper = '''    bool fits_bitset(const Row& value,const std::vector<Row>& reducers) const {
        for (Mask term:value.terms) if (term & ~Mask(4095)) return false;
        for (const Row& row:reducers)
            for (Mask term:row.terms) if (term & ~Mask(4095)) return false;
        return true;
    }
    void initialize_bitset() {
        if (bit_ready) return;
        for (size_t i=0;i<4096;++i) bit_monomial[i]=i;
        std::sort(bit_monomial.begin(),bit_monomial.end(),
                  [](Mask a,Mask b){return less_monomial(b,a);});
        for (size_t i=0;i<4096;++i) bit_rank[bit_monomial[i]]=uint16_t(i);
        bit_ready=true;
    }
    Row normal_bitset(Row value,const std::vector<Row>& reducers,
                      const std::vector<Mask>& leads,
                      const std::vector<size_t>& choices) {
        initialize_bitset();
        std::array<Mask,64> bits{};
        for (Mask term:value.terms)
            bits[bit_rank[term]/64]^=Mask(1)<<(bit_rank[term]%64);
        size_t count=0;
        for (Mask word:bits) count+=__builtin_popcountll(word);
        size_t prefix=0, prefix_rank=0;
        while (count) {
            charge(count);
            charge_ones_product(prefix,choices.size());
            bool changed=false;
            size_t scan=prefix_rank;
            while (scan<4096) {
                const size_t word=scan/64;
                const Mask possible=bits[word] & (~Mask(0)<<(scan%64));
                if (!possible) { scan=(word+1)*64; continue; }
                const size_t rank=word*64+__builtin_ctzll(possible);
                const Mask term=bit_monomial[rank];
                for (size_t i:choices) {
                    charge();
                    if (!divides(leads[i],term)) continue;
                    const Mask mask=term&~leads[i];
                    std::array<Mask,64> multiple{};
                    for (Mask part:reducers[i].terms) {
                        const auto target=bit_rank[part|mask];
                        multiple[target/64]^=Mask(1)<<(target%64);
                    }
                    if (mask) charge(reducers[i].terms.size());
                    const uint32_t multiplied=mask?emit(1,reducers[i].proof,mask):reducers[i].proof;
                    size_t multiple_count=0;
                    for (Mask m:multiple) multiple_count+=__builtin_popcountll(m);
                    charge(count+multiple_count);
                    count=0;
                    for (size_t j=0;j<64;++j) {
                        bits[j]^=multiple[j];
                        count+=__builtin_popcountll(bits[j]);
                    }
                    value.proof=emit(2,value.proof,multiplied);
                    changed=true;
                    break;
                }
                if (changed) break;
                ++prefix;
                prefix_rank=rank+1;
                scan=rank+1;
            }
            if (!changed) break;
        }
        value.terms.clear();
        value.terms.reserve(count);
        for (size_t j=0;j<64;++j) {
            Mask word=bits[j];
            while (word) {
                const size_t bit=__builtin_ctzll(word);
                value.terms.push_back(bit_monomial[j*64+bit]);
                word&=word-1;
            }
        }
        std::sort(value.terms.begin(),value.terms.end());
        return value;
    }
'''
    source = once(source, marker, helper + marker)
    marker = '''        std::stable_sort(choices.begin(),choices.end(),[&](size_t a,size_t b){return reducers[a].terms.size()<reducers[b].terms.size();});
        std::sort(value.terms.begin(),value.terms.end(),[](Mask a,Mask b){return less_monomial(b,a);});
'''
    replacement = '''        std::stable_sort(choices.begin(),choices.end(),[&](size_t a,size_t b){return reducers[a].terms.size()<reducers[b].terms.size();});
        if (fits_bitset(value,reducers))
            return normal_bitset(std::move(value),reducers,leads,choices);
        std::sort(value.terms.begin(),value.terms.end(),[](Mask a,Mask b){return less_monomial(b,a);});
'''
    source = once(source, marker, replacement)
    return source
