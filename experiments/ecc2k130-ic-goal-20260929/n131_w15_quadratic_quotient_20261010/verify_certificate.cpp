// Independent parser and modular-unit check for saved N131 bucket remainders.
#include <NTL/GF2E.h>
#include <NTL/GF2EX.h>
#include <NTL/ZZ.h>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <vector>

using namespace NTL;

static uint64_t tick() { return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::steady_clock::now().time_since_epoch()).count()); }
static uint64_t rss() { rusage u{};getrusage(RUSAGE_SELF,&u);
#ifdef __APPLE__
    return uint64_t(u.ru_maxrss);
#else
    return uint64_t(u.ru_maxrss)*1024;
#endif
}
static GF2E from_decimal(const std::string& value) {
    std::istringstream in(value);ZZ integer;in>>integer;
    if(!in||integer<0||NumBits(integer)>131)throw std::runtime_error("invalid field decimal");
    GF2X bits;
    for(int i=0;i<131;++i)if(bit(integer,i))SetCoeff(bits,i);
    return conv<GF2E>(bits);
}
static GF2E rotate(GF2E value,int count) {
    for(int i=0;i<count;++i)sqr(value,value);
    return value;
}
static GF2EX read_left(const char* path) {
    std::ifstream in(path);if(!in)throw std::runtime_error("missing left coefficient TSV");
    GF2EX left;int terms=0;long exponent;uint64_t lo,mid,hi;
    while(in>>exponent>>lo>>mid>>hi) {
        if(exponent<0||exponent>32768||hi>7)throw std::runtime_error("bad left coefficient");
        GF2X bits;
        for(int i=0;i<64;++i)if((lo>>i)&1)SetCoeff(bits,i);
        for(int i=0;i<64;++i)if((mid>>i)&1)SetCoeff(bits,64+i);
        for(int i=0;i<3;++i)if((hi>>i)&1)SetCoeff(bits,128+i);
        SetCoeff(left,exponent,rotate(conv<GF2E>(bits),26));
        ++terms;
    }
    if(!in.eof()||terms!=486||deg(left)!=32768)
        throw std::runtime_error("left polynomial drift");
    return left;
}
static GF2EX read_remainder(const char* path) {
    std::ifstream in(path,std::ios::binary|std::ios::ate);
    if(!in||in.tellg()!=std::streampos(32768*17))throw std::runtime_error("bad remainder bytes");
    in.seekg(0);GF2EX remainder;
    for(int i=0;i<32768;++i) {
        GF2X bits;
        for(int byte=0;byte<17;++byte) {
            int value=in.get();if(value<0)throw std::runtime_error("short remainder");
            if(byte==16&&(value&~7))throw std::runtime_error("noncanonical field element");
            for(int j=0;j<8;++j)if((value>>j)&1)SetCoeff(bits,8*byte+j);
        }
        if(!IsZero(bits))SetCoeff(remainder,i,conv<GF2E>(bits));
    }
    if(in.peek()!=EOF)throw std::runtime_error("trailing remainder bytes");
    return remainder;
}
int main(int argc,char**argv) {
try {
    if(argc!=8)throw std::runtime_error("usage: verify left.tsv positive.bin negative.bin known_c known_d residual output.json");
    uint64_t start=tick();GF2X modulus;
    for(int bit_index:{0,1,2,13,131})SetCoeff(modulus,bit_index);
    GF2E::init(modulus);
    GF2EX left=read_left(argv[1]);
    GF2EX positive=read_remainder(argv[2]);
    GF2EX negative=read_remainder(argv[3]);
    GF2E c=from_decimal(argv[4]),d=from_decimal(argv[5]),r=from_decimal(argv[6]);
    if(!IsZero(eval(left,c)))throw std::runtime_error("known left output outside left bucket");
    GF2E s3=(GF2E(1)+sqr(c)*sqr(d))*sqr(r)+c*d*r+sqr(c+d);
    if(!IsZero(s3))throw std::runtime_error("known S3 link failed");
    GF2EX gp=GCD(left,positive),gn=GCD(left,negative);
    if(deg(gp)!=1||!IsZero(eval(gp,c))||deg(gn)!=0)
        throw std::runtime_error("certificate GCD decisions failed");
    GF2EX inverse=InvMod(negative,left);
    if(!IsOne(MulMod(negative,inverse,left)))
        throw std::runtime_error("negative Bézout unit replay failed");
    uint64_t elapsed=tick()-start;
    std::ofstream out(argv[7]);if(!out)throw std::runtime_error("output open failed");
    out<<"{\"status\":\"PASS_N131_REMAINDER_CERTIFICATE_CHECK\""
       <<",\"left_degree\":"<<deg(left)
       <<",\"positive_remainder_degree\":"<<deg(positive)
       <<",\"negative_remainder_degree\":"<<deg(negative)
       <<",\"positive_gcd_degree\":"<<deg(gp)
       <<",\"negative_gcd_degree\":"<<deg(gn)
       <<",\"known_left_root\":true,\"known_s3\":true"
       <<",\"negative_inverse_unit\":true"
       <<",\"elapsed_ns\":"<<elapsed<<",\"peak_rss_bytes\":"<<rss()<<"}\n";
    if(!out)throw std::runtime_error("output write failed");
    std::cout<<"PASS_N131_REMAINDER_CERTIFICATE_CHECK elapsed_s="<<double(elapsed)/1e9
             <<" peak_rss="<<rss()<<std::endl;
} catch(const std::exception& e) {std::cerr<<e.what()<<std::endl;return 1;}
}
