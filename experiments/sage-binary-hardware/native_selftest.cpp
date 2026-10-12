// Independent polynomial squaring modulo x^m+x+1 validates the linear kernel.
// Irreducibility is not needed for this raw GF(2)-linear transformation test.
#include "binary_hardware_native.h"
#include <cstdint>
#include <cstdio>
#include <vector>
#include <algorithm>

static void reference(const uint32_t* input,uint32_t* out,unsigned m) {
    uint32_t scratch[16]={};
    for (unsigned i=0;i<m;++i)
        if ((input[i/32]>>(i%32))&1u) scratch[(2*i)/32]^=1u<<((2*i)%32);
    for (int i=int(2*m)-2;i>=int(m);--i) {
        if ((scratch[i/32]>>(i%32))&1u) {
            scratch[i/32]^=1u<<(i%32);
            unsigned j=unsigned(i)-m;
            scratch[j/32]^=1u<<(j%32);
            ++j;scratch[j/32]^=1u<<(j%32);
        }
    }
    for(unsigned w=0;w<(m+31)/32;++w) out[w]=scratch[w];
}
int main() {
    uint32_t rng=0x238fabc1;uint64_t checksum=0;unsigned cases=0;
    for(unsigned m:{3,19,31,32,33,63,64,65,67,127,128,129,131,255,256}) {
        unsigned words=(m+31)/32,bytes=(m+7)/8,count=257;
        std::vector<uint32_t> input(count*words),expected(count*words),out(count*words);
        std::vector<uint32_t> table(bytes*256*words);
        for(auto& x:input){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;x=rng;}
        if(m%32) for(unsigned e=0;e<count;++e) input[e*words+words-1]&=(1u<<(m%32))-1;
        std::fill(input.begin(),input.begin()+words,0);
        for(unsigned e=0;e<count;++e) reference(&input[e*words],&expected[e*words],m);
        for(unsigned b=0;b<bytes;++b) for(unsigned v=0;v<256;++v) {
            uint32_t x[8]={},y[8]={};
            x[b/4]=v<<(8*(b%4));
            if(m%32) x[words-1]&=(1u<<(m%32))-1;
            reference(x,y,m);
            for(unsigned w=0;w<words;++w) table[(b*256+v)*words+w]=y[w];
        }
        for(unsigned threads:{1,3}) {
            if(bh_cpu_apply(table.data(),input.data(),out.data(),count,words,bytes,threads)!=0) return 2;
            if(out!=expected) return 3;
            for(auto x:out) checksum=checksum*1099511628211ull+x;
            ++cases;
        }
        if(bh_cpu_apply(table.data(),input.data(),out.data(),count,0,bytes,1)==0) return 4;
    }
#if defined(__aarch64__)
    const char* arch="arm64";
#elif defined(__x86_64__)
    const char* arch="x86_64";
#else
    const char* arch="other";
#endif
    printf("{\"status\":\"pass\",\"architecture\":\"%s\",\"cases\":%u,\"checksum\":\"%llu\"}\n",
           arch,cases,(unsigned long long)checksum);
}
