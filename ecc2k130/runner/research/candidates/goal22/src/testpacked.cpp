#include "../include/curveparams.h"
#include "../include/packed131.h"
#include <cstdio>
using R = Ref<CfgF131>;
using P = eccPacked131::P131;
static unsigned long long state = 0x131ab123456789ULL;
static unsigned long long randomWord() { state ^= state << 13; state ^= state >> 7; state ^= state << 17; return state; }
static P pack(R::Elem a) { P p; for (int i=0;i<5;i++) p.v[i]=unsigned(a.v[i/2]>>(32*(i&1))); return p; }
static R::Elem unpack(P p) { unsigned long long a[3]={p.v[0]|(static_cast<unsigned long long>(p.v[1])<<32),p.v[2]|(static_cast<unsigned long long>(p.v[3])<<32),p.v[4]};return R::fromLimbs(a); }
struct RawPolynomial { uint32_t v[9]; };
static bool canonical(P a) { return (a.v[4] & ~7u) == 0; }
static bool same(P a, P b) {
    for (int i=0;i<5;i++) if (a.v[i]!=b.v[i]) return false;
    return canonical(a);
}
static P reduceReference(RawPolynomial h) {
    // Independent long division by the field polynomial. Both generated
    // reducers accept degree <= 260 and ignore the unused upper bits of h[8].
    h.v[8]&=31u;
    const int terms[]={0,2,3,64,66,67,96,98,99,112,114,115,120,122,123,124,128,130,131};
    for (int degree=260;degree>=131;--degree) if ((h.v[degree/32]>>(degree%32))&1u)
        for (int term:terms) {
            int bit=degree-131+term;
            h.v[bit/32]^=1u<<(bit%32);
        }
    return P{{h.v[0],h.v[1],h.v[2],h.v[3],h.v[4]}};
}
static bool reductionChecks() {
    uint32_t rng=0x261131u;
    auto next=[&]() { rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng; };
    const int cases=261+2+1000;
    for (int test=0;test<cases;test++) {
        RawPolynomial h{};
        if (test<261) h.v[test/32]=1u<<(test%32);
        else if (test==262) { for (auto &word:h.v) word=~0u;h.v[8]=31u; }
        else if (test>262) { for (auto &word:h.v) word=next();h.v[8]&=31u; }
        const P want=reduceReference(h);
        for (int poison=0;poison<2;poison++) {
            if (poison) h.v[8]|=0xffffffe0u;
            if (!same(eccPacked131::reducePolynomial131(h.v),want)) {
                printf("polynomial reduction mismatch at %d, poisoned=%d\n",test,poison);
                return false;
            }
        }
    }
    printf("PASS: %d host polynomial reductions against long division, including ignored upper-word bits and canonical outputs\n",2*cases);
    return true;
}
int main() {
    printf("packed arithmetic direct reduction: %d\n",ECC_PACKED_DIRECT_REDUCE);
    if (!reductionChecks()) return 1;
    // Check every pair of unit coefficients, including the top-three-bit
    // product and the output fold. Dense cases below also exercise carries in
    // the integer-mask carryless primitive.
    for (int i=0;i<131;i++) for (int j=0;j<131;j++) {
        unsigned long long av[3]={},bv[3]={};
        av[i/64]=1ull<<(i%64);bv[j/64]=1ull<<(j%64);
        auto a=R::fromLimbs(av),b=R::fromLimbs(bv);
        auto pa=eccPacked131::toPolynomial131(pack(a)),pb=eccPacked131::toPolynomial131(pack(b));
        auto polynomialProduct=eccPacked131::mulPolynomial131(pa,pb);
        auto product=eccPacked131::fromPolynomial131(polynomialProduct);
        if (!canonical(polynomialProduct) || unpack(eccPacked131::mul131(pack(a),pack(b)))!=R::mul(a,b) || unpack(product)!=R::mul(a,b)) {
            printf("packed basis-pair mismatch at %d,%d\n",i,j);return 1;
        }
    }
    for (int test=0;test<160;test++) {
        unsigned long long av[3]={randomWord(),randomWord(),randomWord()&7},bv[3]={randomWord(),randomWord(),randomWord()&7};
        if (test<131) {av[0]=av[1]=av[2]=0;av[test/64]=1ull<<(test%64);}
        auto a=R::fromLimbs(av),b=R::fromLimbs(bv);auto pa=pack(a),pb=pack(b);
        auto ap=eccPacked131::toPolynomial131(pa),bp=eccPacked131::toPolynomial131(pb);
        unsigned long long cv[3]={randomWord(),randomWord(),randomWord()&7};
        auto c=R::fromLimbs(cv);
        auto cp=eccPacked131::toPolynomial131(pack(c));
        auto pair=eccPacked131::mulPolynomialPair131(ap,bp,cp);
        if (!canonical(pair.first) || !canonical(pair.second) ||
            unpack(eccPacked131::fromPolynomial131(pair.first))!=R::mul(a,b) ||
            unpack(eccPacked131::fromPolynomial131(pair.second))!=R::mul(a,c)) {
            printf("paired product mismatch at case %d\n",test);return 1;
        }
        auto polynomialProduct=eccPacked131::mulPolynomial131(ap,bp);
        auto polynomialSquare=eccPacked131::squarePolynomial131(ap);
        if (!canonical(polynomialProduct) || !canonical(polynomialSquare) ||
            unpack(eccPacked131::fromPolynomial131(polynomialSquare))!=R::sqr(a) ||
            unpack(eccPacked131::fromPolynomial131(ap))!=a ||
            unpack(eccPacked131::fromPolynomial131(polynomialProduct))!=R::mul(a,b)) {
            printf("polynomial field mismatch at case %d\n",test);return 1;
        }
        if (unpack(eccPacked131::mul131(pa,pb))!=R::mul(a,b) ||
            unpack(eccPacked131::sqr131(pa))!=R::sqr(a) ||
            unpack(eccPacked131::inv131(pa))!=R::inv(a)) {
            printf("packed field mismatch at case %d\n",test);return 1;
        }
        const int powers[]={0,1,2,3,4,5,6,7,8,9,10,16,32,65,130,131};
        for (int j:powers) if (unpack(eccPacked131::sigma131(pa,j))!=R::sigma(a,j)) {
            printf("packed Frobenius mismatch at case %d, power %d\n",test,j);return 1;
        }
    }
    P zero{};auto one=pack(R::one());
    if (unpack(eccPacked131::mul131(zero,one))!=R::zero() ||
        unpack(eccPacked131::mul131(one,one))!=R::one()) return 1;
    const P polynomialEdges[]={P{},P{{1,0,0,0,0}},P{{~0u,~0u,~0u,~0u,7u}}};
    for (P a:polynomialEdges) {
        const auto square=eccPacked131::squarePolynomial131(a);
        const auto pair=eccPacked131::mulPolynomialPair131(a,polynomialEdges[0],polynomialEdges[1]);
        const auto normal=unpack(eccPacked131::fromPolynomial131(a));
        if (!canonical(square) || unpack(eccPacked131::fromPolynomial131(square))!=R::sqr(normal) ||
            !same(eccPacked131::mulPolynomial131(a,polynomialEdges[1]),a) ||
            !same(pair.first,polynomialEdges[0]) || !same(pair.second,a)) return 1;
    }
    puts("PASS: packed multiplication, squaring, inversion, walk and inversion Frobenius powers against independent reference");
}
