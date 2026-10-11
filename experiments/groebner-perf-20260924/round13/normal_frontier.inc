    // Equivalent to a*b successive charge(1) calls. On exhaustion the old
    // loop has consumed every remaining unit. Divide first to avoid overflow.
    // This is intentionally different from the all-or-nothing charge(amount).
    void charge_ones_product(uint64_t a, uint64_t b) {
        if (a && b > (max_work-work)/a) {
            work=max_work;
            throw Budget("native work budget");
        }
        work+=a*b;
    }
    // Return the priority rank of the same first divisor as the scalar scan.
    // Small/early hits use the scalar path. For a larger reducer set, each
    // bitset marks the priority ranks whose leading monomial requires a bit.
    size_t indexed_divisor(Mask term, const std::vector<Mask>& leads,
                           const std::vector<size_t>& choices,
                           std::vector<Mask>& required, Mask& support) {
        const size_t probe=std::min<size_t>(8, choices.size());
        for (size_t rank=0;rank<probe;++rank) {
            charge();
            if (divides(leads[choices[rank]],term)) return rank;
        }
        if (choices.size()<=64) {
            for (size_t rank=probe;rank<choices.size();++rank) {
                charge();
                if (divides(leads[choices[rank]],term)) return rank;
            }
            return SIZE_MAX;
        }
        const size_t words=(choices.size()+63)/64;
        if (required.empty()) {
            required.assign(64*words,0);
            support=0;
            for (size_t rank=0;rank<choices.size();++rank) {
                Mask bits=leads[choices[rank]];
                support|=bits;
                while (bits) {
                    const unsigned bit=__builtin_ctzll(bits);
                    bits&=bits-1;
                    required[bit*words+rank/64]|=Mask(1)<<(rank%64);
                }
            }
        }
        for (size_t word=0;word<words;++word) {
            Mask candidates=~Mask(0);
            if (word+1==words && choices.size()%64)
                candidates=(Mask(1)<<(choices.size()%64))-1;
            if (!word) candidates&=~((Mask(1)<<probe)-1);
            Mask absent=support&~term;
            while (absent && candidates) {
                const unsigned bit=__builtin_ctzll(absent);
                absent&=absent-1;
                candidates&=~required[bit*words+word];
            }
            if (candidates) {
                const size_t rank=word*64+__builtin_ctzll(candidates);
                charge_ones_product(1,rank-probe+1);
                return rank;
            }
        }
        charge_ones_product(1,choices.size()-probe);
        return SIZE_MAX;
    }
    Row normal(Row value,const std::vector<Row>& reducers,size_t skip=SIZE_MAX) {
        std::vector<Mask> leads;
        for (const auto& g:reducers) leads.push_back(lead(g.terms));
        std::vector<size_t> choices;
        for (size_t i=0;i<reducers.size();++i) if(i!=skip) choices.push_back(i);
        std::stable_sort(choices.begin(),choices.end(),[&](size_t a,size_t b){return reducers[a].terms.size()<reducers[b].terms.size();});
        std::sort(value.terms.begin(),value.terms.end(),[](Mask a,Mask b){return less_monomial(b,a);});
        size_t prefix=0;
#if INDEXED_REDUCERS
        std::vector<Mask> required;
        Mask support=0;
#endif
        while (!value.terms.empty()) {
            charge(value.terms.size());
            charge_ones_product(prefix, choices.size());
            bool changed=false;
            for (size_t cursor=prefix;cursor<value.terms.size();++cursor) {
                Mask term=value.terms[cursor];
#if INDEXED_REDUCERS
                size_t rank=indexed_divisor(term,leads,choices,required,support);
                if (rank!=SIZE_MAX) {
                    size_t i=choices[rank];
                    value=ordered_add(value,ordered_multiple(reducers[i],term&~leads[i]));
                    changed=true;
                }
#else
                for (size_t i:choices) {
                    charge();
                    if (!divides(leads[i],term)) continue;
                    value=ordered_add(value,ordered_multiple(reducers[i],term&~leads[i]));
                    changed=true;
                    break;
                }
#endif
                if (changed) break;
                ++prefix; // fixed reducers; later reductions change lower terms only
            }
            if (!changed) break;
        }
        std::sort(value.terms.begin(),value.terms.end());
        return value;
    }
