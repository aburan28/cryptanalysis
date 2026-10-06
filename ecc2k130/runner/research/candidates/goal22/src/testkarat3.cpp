#include "../include/packed131.h"
#include <cstdio>
using eccPacked131::P131;

// Independent unreduced bit convolution; catches recombination errors that a
// field-only check could hide by reducing two different products to one value.
static bool check(P131 a, P131 b) {
    uint32_t want[9]{};
    for (int i=0;i<131;++i) if ((a.v[i/32]>>(i%32))&1u)
        for (int j=0;j<131;++j) if ((b.v[j/32]>>(j%32))&1u)
            want[(i+j)/32]^=1u<<((i+j)%32);
    uint32_t guarded[11];
    for (auto &v:guarded) v=0xdeadbeefu;
    eccPacked131::product131(a,b,guarded+1);
    if (guarded[0]!=0xdeadbeefu || guarded[10]!=0xdeadbeefu) return false;
    for (int i=0;i<9;++i) if (guarded[i+1]!=want[i]) return false;
    return true;
}
int main() {
    static_assert(ECC_PACKED_KARAT3==1,"test the candidate, not its control");
    unsigned count=0;
    for (int i=0;i<131;++i) for (int j=0;j<131;++j) {
        P131 a{},b{}; a.v[i/32]=1u<<(i%32); b.v[j/32]=1u<<(j%32);
        if (!check(a,b)) { std::printf("basis mismatch %d,%d\n",i,j); return 1; }
        ++count;
    }
    uint32_t rng=0x13164u;
    auto next=[&]() { rng^=rng<<13; rng^=rng>>17; rng^=rng<<5; return rng; };
    for (int i=0;i<10000;++i) {
        P131 a{},b{};
        for (int w=0;w<4;++w) { a.v[w]=next(); b.v[w]=next(); }
        a.v[4]=unsigned(i)&7u; b.v[4]=(unsigned(i)>>3)&7u;
        if (!check(a,b)) { std::printf("dense mismatch %d\n",i); return 1; }
        ++count;
    }
    const P131 edges[]={P131{},P131{{1,0,0,0,0}},P131{{~0u,~0u,~0u,~0u,7}}};
    for (auto a:edges) for (auto b:edges) { if (!check(a,b)) return 1; ++count; }
    std::printf("PASS: %u unreduced Karat3 products against bit convolution, with output canaries\n",count);
}
