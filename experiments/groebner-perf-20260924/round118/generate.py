"""Reuse numeric buffers during certified F4 reducer multiplication and XOR."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE_SHA256 = "079a2be5e5f7e3b80d204e2d04662561deaab2a5fc477705d85b07216273830f"


def once(source, old, new):
    assert source.count(old) == 1, (old, source.count(old))
    return source.replace(old, new, 1)


def scratch_engine(source):
    old = '''    Row ordered_add(const Row& a,const Row& b) {
        charge(a.terms.size()+b.terms.size());
        Poly out;
        out.reserve(a.terms.size()+b.terms.size());
        std::set_symmetric_difference(a.terms.begin(),a.terms.end(),b.terms.begin(),b.terms.end(),
            std::back_inserter(out),[](Mask x,Mask y){return less_monomial(y,x);});
        return {std::move(out),emit(2,a.proof,b.proof)};
    }
'''
    helper = '''    // Preserve ordered_multiple() then ordered_add() arithmetic, charge and
    // proof-node order while reusing allocations within this normalization.
    void ordered_reduce(Row &value,const Row &reducer,Mask mask,
                        Poly &multiple,Poly &output) {
        multiple.assign(reducer.terms.begin(),reducer.terms.end());
        if (mask) {
            for (auto &term:multiple) term|=mask;
            charge(multiple.size());
        }
        std::sort(multiple.begin(),multiple.end(),
                  [](Mask a,Mask b){return less_monomial(b,a);});
        size_t write=0;
        for (size_t i=0;i<multiple.size();) {
            size_t j=i+1;
            while (j<multiple.size() && multiple[j]==multiple[i]) ++j;
            if ((j-i)&1) multiple[write++]=multiple[i];
            i=j;
        }
        multiple.resize(write);
        const uint32_t multiplied_proof=mask?emit(1,reducer.proof,mask):reducer.proof;
        const size_t total=value.terms.size()+multiple.size();
        charge(total);
        output.clear();
        if (output.capacity()<total) output.reserve(total);
        std::set_symmetric_difference(value.terms.begin(),value.terms.end(),
            multiple.begin(),multiple.end(),std::back_inserter(output),
            [](Mask a,Mask b){return less_monomial(b,a);});
        const uint32_t reduced_proof=emit(2,value.proof,multiplied_proof);
        value.terms.swap(output);
        value.proof=reduced_proof;
    }
'''
    source = once(source, old, old + helper)
    source = once(source, "        size_t prefix=0;\n#if INDEXED_REDUCERS",
                  "        size_t prefix=0;\n        Poly multiple_scratch, output_scratch;\n"
                  "#if INDEXED_REDUCERS")
    call = "value=ordered_add(value,ordered_multiple(reducers[i],term&~leads[i]));"
    assert source.count(call) == 2
    source = source.replace(call,
        "ordered_reduce(value,reducers[i],term&~leads[i],multiple_scratch,output_scratch);")
    return source
