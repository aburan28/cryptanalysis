// Directly compare the target-split identity with the original quadratic solver.
#define main legacy_resultant_main
#include "../n131_w14_coupled_fouratom_inverse_20261010/native.cpp"
#undef main

#include <random>

struct FeLess {
    bool operator()(Fe a,Fe b)const{
        if(a.hi!=b.hi)return a.hi<b.hi;
        if(a.mid!=b.mid)return a.mid<b.mid;
        return a.lo<b.lo;
    }
};

static Fe halftrace(const Field&f,Fe a){
    Fe h=a,power=a;
    for(int i=1;i<=(f.n-1)/2;++i){power=f.sq(f.sq(power));h=xo(h,power);}
    return h;
}

static unsigned char halftrace_trace(const Field&f,Fe a,Fe h){
    Fe tr=xo(xo(f.sq(h),h),a);
    if(eq(tr,Fe{}))return 0;
    if(eq(tr,Fe{1,0,0}))return 1;
    throw std::runtime_error("half-trace trace identity failed");
}

static std::vector<Fe> original_roots(const Field&f,Fe a,Fe b,Fe c){
    if(zero(a)){
        if(zero(b))return {};
        return {f.mul(c,f.inverse(b))};
    }
    if(zero(b)){
        Fe root=f.mul(c,f.inverse(a));
        for(int i=1;i<f.n;++i)root=f.sq(root);
        return {root};
    }
    Fe alpha=f.mul(f.mul(a,c),f.sq(f.inverse(b)));
    Fe h=halftrace(f,alpha);
    if(!eq(xo(f.sq(h),h),alpha))return {};
    Fe scale=f.mul(b,f.inverse(a)),root=f.mul(scale,h);
    return {root,xo(root,scale)};
}

static std::vector<Fe> split_roots(const Field&f,Fe c,Fe z){
    Fe one{1,0,0},u=f.mul(c,z),k=xo(one,u);
    Fe constant=xo(f.sq(c),f.sq(z));
    if(zero(k))return original_roots(f,Fe{},u,constant);
    Fe ac=f.sq(xo(c,f.inverse(c)));
    Fe az=f.sq(xo(z,f.inverse(z)));
    Fe hc=halftrace(f,ac),hz=halftrace(f,az);
    if(halftrace_trace(f,ac,hc)!=halftrace_trace(f,az,hz))return {};
    Fe scale=f.mul(u,f.sq(f.inverse(k)));
    Fe root=f.mul(scale,xo(hc,hz));
    return {root,xo(root,scale)};
}

static Fe random_nonzero(std::mt19937_64&gen,int n){
    Fe result{};
    do {
        result.lo=gen();
        if(n==41){result.lo&=(1ULL<<41)-1;result.mid=result.hi=0;}
        else {result.mid=gen();result.hi=gen()&7;}
    } while(zero(result));
    return result;
}

int main(int argc,char**argv){
try {
    if(argc!=3)throw std::runtime_error("usage: audit_roots input_root output_json");
    std::string root=argv[1];
    std::mt19937_64 gen(20261010);
    std::ofstream out(argv[2]);
    if(!out)throw std::runtime_error("cannot write audit output");
    out<<"{\"status\":\"PASS_ALL_SPLIT_ROOT_COMPARISONS\",\"cases\":[";
    int panels=0;
    for(int n:{41,131})for(const char*label:{"positive","trace_zero_control"}){
        std::ifstream input(root+"/n"+std::to_string(n)+"_"+label+".txt");
        int parsed_n,d,r1,r2;std::string source,z_text;
        input>>parsed_n>>d>>source>>r1>>r2>>z_text;
        if(!input||parsed_n!=n)throw std::runtime_error("bad frozen input");
        Field f(n);Fe z=decimal(z_text);
        size_t checked=0,zero_root=0,one_root=0,two_roots=0;
        auto compare=[&](Fe c){
            Fe u=f.mul(c,z),k=xo(Fe{1,0,0},u);
            auto old=original_roots(f,f.sq(k),u,xo(f.sq(c),f.sq(z)));
            auto now=split_roots(f,c,z);
            FeLess less;
            std::sort(old.begin(),old.end(),less);
            std::sort(now.begin(),now.end(),less);
            if(old.size()!=now.size())throw std::runtime_error("root count mismatch");
            for(size_t i=0;i<old.size();++i)
                if(!eq(old[i],now[i]))throw std::runtime_error("root value mismatch");
            ++checked;
            if(now.empty())++zero_root;
            else if(now.size()==1)++one_root;
            else if(now.size()==2)++two_roots;
            else throw std::runtime_error("unexpected root count");
        };
        compare(f.inverse(z)); // The degenerate 1+cz=0 branch.
        compare(z);
        for(int i=0;i<1024;++i)compare(random_nonzero(gen,n));
        if(panels++)out<<",";
        out<<"{\"field_degree\":"<<n<<",\"case\":\""<<label
           <<"\",\"checked\":"<<checked<<",\"zero_roots\":"<<zero_root
           <<",\"one_root\":"<<one_root<<",\"two_roots\":"<<two_roots<<"}";
    }
    out<<"]}\n";
    std::cout<<"PASS_ALL_SPLIT_ROOT_COMPARISONS panels="<<panels<<"\n";
} catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
