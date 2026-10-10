// Exact two-bucket S3 intersection using z=alpha*d to avoid alpha^-1.
#include <NTL/GF2E.h>
#include <NTL/GF2EX.h>
#include <NTL/ZZ.h>
#include <algorithm>
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
static ZZ read_decimal(const std::string& s) {
    std::istringstream in(s);ZZ z;in>>z;
    if(!in||z<0)throw std::runtime_error("bad decimal field element");
    char extra;if(in>>extra)throw std::runtime_error("trailing decimal data");
    return z;
}
static GF2E field_element(const ZZ& z,long n) {
    if(NumBits(z)>n)throw std::runtime_error("field element overflow");
    GF2X polynomial;
    for(long i=0;i<n;++i)if(bit(z,i))SetCoeff(polynomial,i);
    return conv<GF2E>(polynomial);
}
static GF2E frob(GF2E a,int count) {
    for(int i=0;i<count;++i)sqr(a,a);
    return a;
}
static GF2EX left_polynomial(long n,int dimension,int seed,int rotation,
                             const std::string& path) {
    GF2EX polynomial;
    if(n==131) {
        std::ifstream in(path);if(!in)throw std::runtime_error("missing sparse norm input");
        long exponent,terms=0;uint64_t lo,mid,hi;
        while(in>>exponent>>lo>>mid>>hi) {
            if(exponent<0||exponent>32768||hi>7)throw std::runtime_error("bad norm coefficient");
            GF2X bits;
            for(int i=0;i<64;++i)if((lo>>i)&1)SetCoeff(bits,i);
            for(int i=0;i<64;++i)if((mid>>i)&1)SetCoeff(bits,64+i);
            for(int i=0;i<3;++i)if((hi>>i)&1)SetCoeff(bits,128+i);
            SetCoeff(polynomial,exponent,frob(conv<GF2E>(bits),rotation));
            ++terms;
        }
        if(!in.eof()||terms!=486||deg(polynomial)!=32768)
            throw std::runtime_error("N131 sparse input drift");
    } else {
        GF2E t=field_element(ZZ(2),n),s=field_element(ZZ(seed)<<1,n);
        std::vector<GF2E> products;
        for(int mask=0;mask<(1<<dimension);++mask) {
            GF2E w=GF2E::zero();
            for(int i=0;i<dimension;++i)if(mask&(1<<i))w+=power(t,i+1);
            GF2E p=sqr(w)+s*w;
            if(std::find(products.begin(),products.end(),p)==products.end())products.push_back(p);
        }
        if(products.size()!=size_t(1<<(dimension-1)))throw std::runtime_error("N41 product rank drift");
        SetCoeff(polynomial,0);
        for(const GF2E& p:products) {
            GF2EX factor;
            SetCoeff(factor,0,sqr(s));
            SetCoeff(factor,1,p);
            SetCoeff(factor,2,GF2E(1)+sqr(p));
            polynomial*=factor;
        }
        if(deg(polynomial)!=(1<<dimension))throw std::runtime_error("N41 norm degree drift");
        for(long i=0;i<=deg(polynomial);++i)SetCoeff(polynomial,i,frob(coeff(polynomial,i),rotation));
    }
    if(IsZero(LeadCoeff(polynomial)))throw std::runtime_error("zero norm leading coefficient");
    return polynomial;
}
static std::vector<GF2E> product_basis(int dimension,int seed,long n,int rotation) {
    GF2E t=field_element(ZZ(2),n),s=field_element(ZZ(seed)<<1,n);
    std::vector<GF2X> pivots(n);std::vector<GF2E> basis;
    GF2E w=t;
    for(int i=1;i<=dimension;++i) {
        if(i>1)w*=t;
        GF2E p=sqr(w)+s*w;
        GF2X reduced=rep(p);
        while(!IsZero(reduced)) {
            int k=deg(reduced);
            if(IsZero(pivots[k])) { pivots[k]=reduced;basis.push_back(frob(p,rotation));break; }
            reduced+=pivots[k];
        }
    }
    if(basis.size()!=size_t(dimension-1))throw std::runtime_error("right product rank drift");
    return basis;
}

struct Quad { GF2EX a,b; }; // a+b*d, where d^2=u*d+v.
static Quad operator+(const Quad& x,const Quad& y) { return {x.a+y.a,x.b+y.b}; }

struct Quotient {
    const GF2EXModulus& modulus;
    GF2EX u,v;
    uint64_t start,cap_ns,rss_cap,mul_count=0;
    Quotient(const GF2EXModulus& f,GF2EX uu,GF2EX vv,
             uint64_t initial,uint64_t limit,uint64_t memory):
        modulus(f),u(std::move(uu)),v(std::move(vv)),
        start(initial),cap_ns(limit),rss_cap(memory) {}
    void guard() {
        if(tick()-start>cap_ns)throw std::runtime_error("CENSORED_TIME");
        if(rss()>rss_cap)throw std::runtime_error("OOM");
    }
    GF2EX mulr(const GF2EX& x,const GF2EX& y) {
        if((++mul_count&15)==0)guard();
        return MulMod(x,y,modulus);
    }
    GF2EX sqr_r(const GF2EX& x) {
        if((++mul_count&15)==0)guard();
        return SqrMod(x,modulus);
    }
    Quad mulq(const Quad& x,const Quad& y) {
        GF2EX ac=mulr(x.a,y.a),bd=mulr(x.b,y.b);
        GF2EX cross=mulr(x.a+x.b,y.a+y.b)+ac+bd;
        return {ac+mulr(bd,v),cross+mulr(bd,u)};
    }
    Quad sqr_q(const Quad& x) {
        GF2EX aa=sqr_r(x.a),bb=sqr_r(x.b);
        return {aa+mulr(bb,v),mulr(bb,u)};
    }
};

int main(int argc,char**argv) {
try {
    if(argc!=12)throw std::runtime_error("usage: quotient n dim seed left_rotation right_rotation residual known_left_or_dash norm_tsv_or_dash output cap_s rss_cap");
    int n=std::stoi(argv[1]),dimension=std::stoi(argv[2]),seed=std::stoi(argv[3]);
    int left_rotation=std::stoi(argv[4]),right_rotation=std::stoi(argv[5]);
    if(!((n==41&&dimension==6&&seed==2&&left_rotation==20&&right_rotation==25)||
         (n==131&&dimension==15&&seed==13686&&left_rotation==26&&right_rotation==39)))
        throw std::runtime_error("unsupported frozen panel");
    uint64_t cap_ns=uint64_t(std::stoull(argv[10]))*1000000000ULL;
    uint64_t rss_cap=std::stoull(argv[11]),start=tick();
    GF2X field_modulus;SetCoeff(field_modulus,n);SetCoeff(field_modulus,0);
    if(n==41)SetCoeff(field_modulus,3);
    else {SetCoeff(field_modulus,1);SetCoeff(field_modulus,2);SetCoeff(field_modulus,13);}
    GF2E::init(field_modulus);
    GF2E r=field_element(read_decimal(argv[6]),n);
    GF2EX F=left_polynomial(n,dimension,seed,left_rotation,argv[8]);
    GF2EXModulus mod(F);
    GF2EX c;SetCoeff(c,1);
    GF2EX alpha=GF2EX(1)+sqr(r)*sqr(c);
    GF2EX beta=r*c,gamma=sqr(c)+to_GF2EX(sqr(r));
    GF2EX exception=GCD(F,alpha);
    if(deg(exception)>0)throw std::runtime_error("quadratic leading coefficient is not a unit in left quotient");
    // U(c,d,r)=alpha*d^2+beta*d+gamma.  With z=alpha*d,
    // z^2+beta*z+alpha*gamma=0; alpha is a unit modulo F.
    GF2EX u=beta,v=MulMod(alpha,gamma,mod);
    uint64_t setup_ns=tick()-start;
    Quotient q(mod,u,v,start,cap_ns,rss_cap);
    auto basis=product_basis(dimension,seed,n,right_rotation);
    GF2E s=frob(field_element(ZZ(seed)<<1,n),right_rotation);
    std::vector<Quad> coefficients(1);SetCoeff(coefficients[0].a,0);
    for(size_t round=0;round<basis.size();++round) {
        GF2E p=basis[round],p2=sqr(p);
        // alpha^2*g_p(z/alpha)=(1+p^2)z^2+p*alpha*z+s^2*alpha^2.
        Quad input{p2*v,p2*u+p*alpha};
        Quad power=input,value;
        for(size_t j=0;j<coefficients.size();++j) {
            value=value+q.mulq(coefficients[j],power);
            power=q.sqr_q(power);
        }
        std::vector<Quad> next(coefficients.size()+1);
        for(size_t j=0;j<coefficients.size();++j) {
            next[j]=next[j]+q.mulq(coefficients[j],value);
            next[j+1]=next[j+1]+q.sqr_q(coefficients[j]);
        }
        coefficients=std::move(next);
        std::cout<<"round="<<round+1<<" elapsed_s="<<double(tick()-start)/1e9
            <<" rss="<<rss()<<" ring_ops="<<q.mul_count<<std::endl;
        q.guard();
    }
    Quad h{v+sqr(s)*MulMod(alpha,alpha,mod),u},power=h,answer;
    for(const Quad& coefficient:coefficients) {
        answer=answer+q.mulq(coefficient,power);
        power=q.sqr_q(power);
    }
    GF2EX aa=q.sqr_r(answer.a),bb=q.sqr_r(answer.b);
    GF2EX norm=aa+q.mulr(q.mulr(answer.a,answer.b),u)+q.mulr(bb,v);
    GF2EX common=GCD(F,norm);
    bool known=false;
    if(std::string(argv[7])!="-") {
        GF2E known_left=field_element(read_decimal(argv[7]),n);
        known=IsZero(eval(common,known_left));
    }
    uint64_t elapsed_ns=tick()-start;
    std::ofstream out(argv[9]);
    if(!out)throw std::runtime_error("output open failed");
    out<<"{\"status\":\"COMPLETE_QUOTIENT_INTERSECTION\",\"field_degree\":"<<n
       <<",\"seed\":"<<seed<<",\"left_degree\":"<<deg(F)
       <<",\"intersection_degree\":"<<deg(common)
       <<",\"known_left_root_in_intersection\":"<<(known?"true":"false")
       <<",\"setup_ns\":"<<setup_ns<<",\"elapsed_ns\":"<<elapsed_ns
       <<",\"ring_ops\":"<<q.mul_count<<",\"peak_rss_bytes\":"<<rss()<<"}\n";
    if(!out)throw std::runtime_error("output write failed");
    std::cout<<"status=COMPLETE degree="<<deg(common)<<" known="<<known
        <<" elapsed_s="<<double(elapsed_ns)/1e9<<" peak_rss="<<rss()<<std::endl;
} catch(const std::exception& e) {std::cerr<<e.what()<<std::endl;return 1;}
}
