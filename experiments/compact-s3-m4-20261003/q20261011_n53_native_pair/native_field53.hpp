#pragma once
// Native N53 type-II ONB and Koblitz group arithmetic, Q1454.
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
using U = unsigned __int128;
constexpr unsigned N=107, M=53;
constexpr U MASK=(U(1)<<N)-1;
constexpr U ONE=MASK^1;
unsigned degree(U a){ if(!a)return 0; unsigned i=0; while(a>>=1)++i; return i; }
U norm(U a){a&=MASK; return (a&1)?a^MASK:a;}
U rot(U a,unsigned k){k%=N; return k?((a<<k)|(a>>(N-k)))&MASK:a;}
U mul(U a,U b){U r=0; while(b){unsigned k=(uint64_t)b?__builtin_ctzll((uint64_t)b):64+__builtin_ctzll((uint64_t)(b>>64)); r^=rot(a,k); b&=b-1;} return norm(r);}
U sqr(U a){U r=0; while(a){unsigned k=(uint64_t)a?__builtin_ctzll((uint64_t)a):64+__builtin_ctzll((uint64_t)(a>>64)); r|=U(1)<<((2*k)%N);a&=a-1;} return norm(r);}
U inv(U a){if(!a)throw std::runtime_error("division by zero"); U e=(U(1)<<M)-2, r=ONE; while(e){if(e&1)r=mul(r,a); a=sqr(a); e>>=1;} return r;}
struct P {U x=0,y=0;bool inf=true;};
P neg(P p){if(!p.inf)p.y^=p.x;return p;}
P dbl(P p){if(p.inf||!p.x)return {}; U lam=p.x^mul(p.y,inv(p.x));U x=sqr(lam)^lam;U y=sqr(p.x)^mul(lam^ONE,x);return {x,y,false};}
P add(P p,P q){if(p.inf)return q;if(q.inf)return p;if(p.x==q.x)return p.y==q.y?dbl(p):P{};U d=p.x^q.x;U lam=mul(p.y^q.y,inv(d));U x=sqr(lam)^lam^d;U y=mul(lam,p.x^x)^x^p.y;return {x,y,false};}

struct Key {U value=0;unsigned exponent=0;int sign=1;};
uint64_t cycle_bits(U a){
    uint64_t coords=(uint64_t)(norm(a)>>1)&((uint64_t(1)<<M)-1);
    uint64_t out=0;
    unsigned index=1;
    for(unsigned pos=0;pos<M;++pos){
        out|=((coords>>(index-1))&1)<<pos;
        unsigned doubled=(2*index)%N;
        index=std::min(doubled,N-doubled);
    }
    if(index!=1)throw std::runtime_error("bad cycle");
    return out;
}
Key canonical(P p){
    if(p.inf)return {};
    uint64_t x=cycle_bits(p.x),y=cycle_bits(p.y),mask=(uint64_t(1)<<M)-1;
    Key best{(U(1)<<127),0,1};
    for(unsigned j=0;j<M;++j){
        U positive=(U(x)<<M)|y,negative=(U(x)<<M)|(x^y);
        if(positive<best.value)best={positive,j,1};
        if(negative<best.value)best={negative,j,-1};
        x=((x<<1)|(x>>(M-1)))&mask;
        y=((y<<1)|(y>>(M-1)))&mask;
    }
    return best;
}

U readhex(const std::string&s){U x=0;for(char c:s){unsigned d= c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:100;if(d>15)throw std::runtime_error("bad hex");x=(x<<4)|d;}return x;}
std::string hex(U x){if(!x)return "0";std::string s;while(x){unsigned d=x&15;s.push_back("0123456789abcdef"[d]);x>>=4;}return {s.rbegin(),s.rend()};}
