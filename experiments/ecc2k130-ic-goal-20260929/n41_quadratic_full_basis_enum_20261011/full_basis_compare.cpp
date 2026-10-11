// Exact quadratic-root enumeration with fixed-product root and residual bases.
#define main frozen_three_pair_main
#include "../../koblitz-s5-invariant-20260924/three_pair_s7_native.cpp"
#undef main

#include <algorithm>
#include <chrono>
#include <fstream>
#include <map>
#include <set>
#include <unordered_set>

using Clock=std::chrono::steady_clock;
static uint64_t elapsed(Clock::time_point start){
    return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-start).count();
}
static uint64_t trace41(uint64_t x){
    uint64_t sum=0;
    for(int i=0;i<41;++i){sum^=x;x=sq(x);}
    if(sum>1)throw std::runtime_error("trace out of base field");
    return sum;
}
static uint64_t halftrace41(uint64_t x){
    uint64_t sum=0;
    for(int i=0;i<21;++i){sum^=x;x=sq(sq(x));}
    return sum;
}
struct LinearMap{
    std::array<uint64_t,41> pivot{},repr{};
    std::vector<uint64_t> kernel;
    explicit LinearMap(uint64_t p,const std::array<uint64_t,41>& halfcols){
        for(int i=0;i<41;++i){
            uint64_t col=mul(p,1ULL<<i)^halfcols[i],r=1ULL<<i;
            while(col){
                int bit=63-__builtin_clzll(col);
                if(pivot[bit]){col^=pivot[bit];r^=repr[bit];}
                else{pivot[bit]=col;repr[bit]=r;break;}
            }
            if(!col)kernel.push_back(r);
        }
        if(kernel.size()>2)throw std::runtime_error("nullity over two");
    }
    bool solve(uint64_t rhs,uint64_t& z)const{
        z=0;
        while(rhs){
            int bit=63-__builtin_clzll(rhs);
            if(!pivot[bit])return false;
            rhs^=pivot[bit];z^=repr[bit];
        }
        return true;
    }
};
static void add_points(std::unordered_set<Point,PointHash>& set,uint64_t z){
    if(!z||trace41(z))return;
    uint64_t x=inv(z),rhs=x^sq(z);
    if(trace41(rhs))return;
    uint64_t y=mul(x,halftrace41(rhs));
    Point q=finite(x,y);
    if(!on_curve(q))throw std::runtime_error("curve lift failed");
    set.insert(q);set.insert(neg(q));
}
static std::unordered_set<Point,PointHash> old_enumeration(uint64_t& ns){
    auto start=Clock::now();
    std::array<uint64_t,41> cols{};
    for(int i=0;i<41;++i)cols[i]=halftrace41(sq(1ULL<<i));
    std::array<uint64_t,64> rhs{};
    for(int s=1;s<64;++s)rhs[s]=halftrace41(sq(uint64_t(s)<<1));
    std::unordered_set<Point,PointHash> set;set.reserve(140000);
    for(int pm=0;pm<2048;++pm){
        LinearMap linear(uint64_t(pm)<<2,cols);
        for(int s=1;s<64;++s)for(int eps=0;eps<2;++eps){
            uint64_t particular;
            if(!linear.solve(rhs[s]^uint64_t(eps),particular))continue;
            for(unsigned k=0;k<(1U<<linear.kernel.size());++k){
                uint64_t z=particular;
                for(size_t i=0;i<linear.kernel.size();++i)
                    if(k&(1U<<i))z^=linear.kernel[i];
                add_points(set,z);
            }
        }
    }
    ns=elapsed(start);return set;
}
static std::unordered_set<Point,PointHash> quadratic_enumeration(
    uint64_t& ns,uint64_t& root_candidates,uint64_t& passes,
    uint64_t& basis_halftraces,uint64_t& direct_halftraces_avoided,
    uint64_t& residual_basis_halftraces,uint64_t& residual_halftraces_avoided){
    auto start=Clock::now();
    std::unordered_set<Point,PointHash> set;set.reserve(140000);
    for(int pm=0;pm<2048;++pm){
        uint64_t p=uint64_t(pm)<<2,A=sq(p)^1;
        uint64_t alpha=0,factor=0;
        std::array<uint64_t,6> half_basis{},residual_basis{};
        unsigned trace_mask=0;
        uint64_t branch_residual=0;
        if(p&&A){
            alpha=mul(p,inv(A));factor=mul(A,inv(sq(p)));
            for(int bit=0;bit<6;++bit){
                uint64_t scaled=mul(factor,sq(1ULL<<(bit+1)));
                half_basis[bit]=halftrace41(scaled);
                trace_mask|=unsigned(trace41(scaled))<<bit;
                ++basis_halftraces;
                uint64_t seed=1ULL<<(bit+1);
                uint64_t root=mul(alpha,half_basis[bit]);
                residual_basis[bit]=mul(p,root)^halftrace41(sq(seed^root));
                ++residual_basis_halftraces;
            }
            branch_residual=mul(p,alpha)^halftrace41(sq(alpha));
            ++residual_basis_halftraces;
        }
        for(int sm=1;sm<64;++sm){
            uint64_t s=uint64_t(sm)<<1,C=sq(s)^trace41(s);
            if(trace41(s))throw std::runtime_error("W6 source trace changed");
            std::array<uint64_t,2> roots{},residuals{};int count=0;
            if(!p){
                uint64_t z=C;
                for(int i=0;i<40;++i)z=sq(z);
                roots[count++]=z;
            }else if(!A){
                roots[count++]=C;
            }else{
                if(!(__builtin_parity(unsigned(sm)&trace_mask))){
                    uint64_t u=0,e=0;
                    for(int bit=0;bit<6;++bit)if(sm&(1<<bit)){
                        u^=half_basis[bit];e^=residual_basis[bit];
                    }
                    ++direct_halftraces_avoided;
                    roots[count++]=mul(alpha,u);
                    roots[count++]=mul(alpha,u^1);
                    residuals[0]=e;residuals[1]=e^branch_residual;
                    residual_halftraces_avoided+=2;
                }
            }
            for(int i=0;i<count;++i){
                uint64_t z=roots[i];++root_candidates;
                if(!z||trace41(z))continue;
                uint64_t eps=(p&&A)?residuals[i]:mul(p,z)^halftrace41(sq(s^z));
                if(eps>1)throw std::runtime_error("quadratic residual outside F2");
                ++passes;add_points(set,z);
            }
        }
    }
    ns=elapsed(start);return set;
}
static std::array<uint64_t,41> frob_basis(int rotation){
    std::array<uint64_t,41> basis{};
    for(int i=0;i<41;++i){
        uint64_t x=1ULL<<i;
        for(int j=0;j<rotation;++j)x=sq(x);
        basis[i]=x;
    }
    return basis;
}
static uint64_t frob(uint64_t x,const std::array<uint64_t,41>& basis){
    uint64_t result=0;
    while(x){int i=__builtin_ctzll(x);result^=basis[i];x&=x-1;}
    return result;
}
static Point frob(Point p,const std::array<uint64_t,41>& basis){
    return finite(frob(p.x,basis),frob(p.y,basis));
}
int main(int argc,char** argv){
    try{
        if(argc!=3)throw std::runtime_error("usage: full_basis_compare targets.txt receipt.json");
        uint64_t old_ns=0,new_ns=0,roots=0,passes=0,basis_calls=0,avoided=0;
        uint64_t residual_basis_calls=0,residual_avoided=0;
        auto oldset=old_enumeration(old_ns);
        auto newset=quadratic_enumeration(new_ns,roots,passes,basis_calls,avoided,
                                          residual_basis_calls,residual_avoided);
        if(oldset!=newset)throw std::runtime_error("point sets differ");
        auto b20=frob_basis(20),b30=frob_basis(30);
        std::vector<Point> left;left.reserve(newset.size());
        std::unordered_set<Point,PointHash> right;right.reserve(newset.size()*2);
        for(const auto& p:newset){left.push_back(frob(p,b20));right.insert(frob(p,b30));}
        std::sort(left.begin(),left.end(),[](Point a,Point b){
            return a.x==b.x?a.y<b.y:a.x<b.x;
        });
        std::ifstream input(argv[1]);int n;input>>n;
        if(!input||n!=9)throw std::runtime_error("bad input count");
        std::ofstream out(argv[2]);if(!out)throw std::runtime_error("output open");
        out<<"{\"status\":\"PASS_EXACT_FULL_BASIS_QUADRATIC_ENUMERATION\","
           <<"\"old_points\":"<<oldset.size()<<",\"new_points\":"<<newset.size()
           <<",\"old_enumeration_ns\":"<<old_ns
           <<",\"quadratic_enumeration_ns\":"<<new_ns
           <<",\"halftrace_basis_calls\":"<<basis_calls
           <<",\"direct_halftrace_calls_avoided\":"<<avoided
           <<",\"residual_basis_halftrace_calls\":"<<residual_basis_calls
           <<",\"direct_residual_halftrace_calls_avoided\":"<<residual_avoided
           <<",\"quadratic_root_candidates\":"<<roots
           <<",\"quadratic_residual_passes\":"<<passes
           <<",\"full_set_equal\":true,\"queries\":[";
        for(int i=0;i<n;++i){
            std::string label;uint64_t x,y;input>>label>>x>>y;
            Point target=finite(x,y);
            if(!input||!on_curve(target))throw std::runtime_error("bad target");
            auto start=Clock::now();bool hit=false;uint64_t probes=0;
            for(const auto& l:left){
                ++probes;
                Point needed=add(target,neg(l));
                if(right.count(needed)){
                    if(!(add(l,needed)==target))throw std::runtime_error("group replay");
                    hit=true;break;
                }
            }
            if(hit!=(i==0))throw std::runtime_error("frozen control mismatch");
            out<<(i?",":"")<<"{\"label\":\""<<label<<"\",\"status\":\""
               <<(hit?"RELAXED_SUM_HIT":"COMPLETE_RELAXED_NO_SUM")
               <<"\",\"probes\":"<<probes<<",\"query_ns\":"<<elapsed(start)<<"}";
        }
        std::string extra;if(input>>extra)throw std::runtime_error("trailing input");
        out<<"]}\n";
        std::cout<<"PASS_EXACT_FULL_BASIS_QUADRATIC_ENUMERATION points="<<newset.size()
                 <<" old_ns="<<old_ns<<" quadratic_ns="<<new_ns<<"\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<"error: "<<e.what()<<"\n";return 2;}
}
