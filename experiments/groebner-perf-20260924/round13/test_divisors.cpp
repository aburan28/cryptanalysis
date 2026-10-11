// Scalar-reference qualification of priority selection and partial budgets.
#include "build/indexed.inc"
#include <cassert>

static uint64_t random_word() {
    static uint64_t state=0x963ae15d6ac274e1ULL;
    state^=state<<13;
    state^=state>>7;
    state^=state<<17;
    return state;
}

int main() {
    uint64_t cases=0, indexed_contexts=0;
    for (size_t count : {size_t(0),size_t(1),size_t(8),size_t(9),size_t(63),size_t(64),
                         size_t(65),size_t(127),size_t(128),size_t(129),size_t(511),size_t(4096)}) {
        std::vector<Mask> leads(count);
        for (auto& lead_mask : leads) {
            for (unsigned j=0;j<4;++j) lead_mask|=Mask(1)<<(random_word()%64);
        }
        for (unsigned mode=0;mode<3;++mode) {
            std::vector<size_t> choices;
            for (size_t i=0;i<count;++i) if (mode!=1 || i%3) choices.push_back(i);
            if (mode==2 && count) leads[count/2]=0;
            std::reverse(choices.begin(),choices.end());
            if (!choices.empty()) std::rotate(choices.begin(),choices.begin()+choices.size()/3,choices.end());
            std::vector<Mask> required;
            Mask support=0;
            for (unsigned q=0;q<20;++q) {
                Mask term=q==0 ? 0 : q==1 ? ~Mask(0) : random_word();
                if (q>=2 && q%2 && count) term=leads[random_word()%count];
                const uint64_t size=choices.size();
                const std::vector<uint64_t> limits={0,1,7,8,9,size/2,size?size-1:0,size,size+1};
                for (uint64_t limit : limits) {
                    Engine scalar(limit,100,100,1,false), indexed(limit,100,100,1,false);
                    scalar.work=indexed.work=limit/3;
                    bool scalar_done=true, indexed_done=true;
                    size_t expected=SIZE_MAX, actual=SIZE_MAX;
                    try {
                        for (size_t rank=0;rank<choices.size();++rank) {
                            scalar.charge();
                            if (divides(leads[choices[rank]],term)) { expected=rank; break; }
                        }
                    } catch (const Budget&) { scalar_done=false; }
                    try { actual=indexed.indexed_divisor(term,leads,choices,required,support); }
                    catch (const Budget&) { indexed_done=false; }
                    assert(scalar_done==indexed_done);
                    assert(scalar.work==indexed.work);
                    if (scalar_done) assert(expected==actual);
                    ++cases;
                }
            }
            if (!required.empty()) ++indexed_contexts;
        }
    }
    assert(indexed_contexts>=8);
    std::cout << "{\"divisor_cases\":" << cases
              << ",\"indexed_contexts\":" << indexed_contexts << "}\n";
}
