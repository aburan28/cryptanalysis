    // Head reduction preserves the complete polynomial witness. Once the head
    // is irreducible, defer tail work until the final full interreduction. A
    // newly installed head strictly enlarges the current leading ideal.
    Row top_normal(Row value) {
        ++top_stats.calls;
        std::vector<size_t> choices;
        for (size_t i=0;i<basis.size();++i) choices.push_back(i);
        std::stable_sort(choices.begin(),choices.end(),[&](size_t a,size_t b){
            return basis[a].terms.size()<basis[b].terms.size();
        });
        while (!value.terms.empty()) {
            charge(value.terms.size());
            const Mask term=lead(value.terms);
            bool changed=false;
            for (size_t i:choices) {
                charge();
                if (!divides(basis_leads[i],term)) continue;
                value=add(value,multiply(basis[i],term&~basis_leads[i]));
                ++top_stats.reductions;
                changed=true;
                break;
            }
            if (!changed) {
                ++top_stats.irreducible_heads;
                top_stats.deferred_terms+=value.terms.size()-1;
                return value;
            }
        }
        ++top_stats.zero_rows;
        return value;
    }
