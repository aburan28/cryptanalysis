#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <unordered_map>
#include <vector>

static constexpr int MAX_WORDS = 64;

struct Poly {
    std::array<uint64_t, MAX_WORDS> w{};
    bool operator==(const Poly& o) const { return w == o.w; }
    bool operator!=(const Poly& o) const { return !(*this == o); }
};

struct Sig { uint32_t mon = 0; int idx = 0; };
struct Labeled { Sig sig; Poly poly; int num = 0; };
struct Pair {
    Sig s1, s2;
    uint32_t m1 = 0, m2 = 0;
    int i1 = 0, i2 = 0;
};

class Engine {
  public:
    int n, universe, words, signature_limit, completion_seed_limit;
    uint32_t full_mask;
    std::vector<uint32_t> mask_by_rank, rank_by_mask;
    std::vector<std::vector<int>> rewrites;
    std::vector<std::vector<uint8_t>> syzygies;
    long long insertions = 0, reductions = 0, pairs_processed = 0;
    double initial_seconds=0, signature_seconds=0, interreduce_seconds=0,
           completion_seconds=0, final_reduce_seconds=0;

    Engine(int nv, int limit, int seed_limit): n(nv), universe(1 << nv),
        words((universe + 63) / 64), signature_limit(limit), completion_seed_limit(seed_limit),
        full_mask((1u << nv) - 1) {
        std::vector<uint32_t> masks(universe);
        for (int i = 0; i < universe; ++i) masks[i] = i;
        std::sort(masks.begin(), masks.end(), [&](uint32_t a, uint32_t b) {
            int da = __builtin_popcount(a), db = __builtin_popcount(b);
            if (da != db) return da < db;
            return a > b;
        });
        mask_by_rank = masks;
        rank_by_mask.resize(universe);
        for (int i = 0; i < universe; ++i) rank_by_mask[masks[i]] = i;
    }

    bool zero(const Poly& p) const {
        for (int i = 0; i < words; ++i) if (p.w[i]) return false;
        return true;
    }
    int lead_rank(const Poly& p) const {
        for (int i = words - 1; i >= 0; --i)
            if (p.w[i]) return i * 64 + 63 - __builtin_clzll(p.w[i]);
        return -1;
    }
    uint32_t lead(const Poly& p) const { return mask_by_rank[lead_rank(p)]; }
    static bool divides(uint32_t a, uint32_t b) { return (a & ~b) == 0; }
    void xori(Poly& a, const Poly& b) const {
        for (int i = 0; i < words; ++i) a.w[i] ^= b.w[i];
    }
    int terms(const Poly& p) const {
        int r = 0; for (int i = 0; i < words; ++i) r += __builtin_popcountll(p.w[i]);
        return r;
    }
    int degree(const Poly& p) const {
        int d=0;
        for(int wi=0;wi<words;++wi){uint64_t x=p.w[wi];while(x){int bit=__builtin_ctzll(x);d=std::max(d,__builtin_popcount(mask_by_rank[wi*64+bit]));x&=x-1;}}
        return d;
    }
    Poly multiply(const Poly& p, uint32_t m) const {
        Poly r;
        for (int wi = 0; wi < words; ++wi) {
            uint64_t x = p.w[wi];
            while (x) {
                int b = __builtin_ctzll(x), rank = wi * 64 + b;
                uint32_t out = rank_by_mask[mask_by_rank[rank] | m];
                r.w[out >> 6] ^= uint64_t(1) << (out & 63);
                x &= x - 1;
            }
        }
        return r;
    }
    bool multiply_bounded(const Poly& p, uint32_t m, int max_degree,
                          Poly& out) const {
        out=Poly{};
        for(int wi=0;wi<words;++wi){
            uint64_t x=p.w[wi];
            while(x){
                int bit=__builtin_ctzll(x);
                uint32_t product=mask_by_rank[wi*64+bit]|m;
                if(__builtin_popcount(product)>max_degree)return false;
                uint32_t rank=rank_by_mask[product];
                out.w[rank>>6]^=uint64_t(1)<<(rank&63);
                x&=x-1;
            }
        }
        return true;
    }
    Poly monomial_poly(uint32_t m) const {
        Poly p; uint32_t r = rank_by_mask[m]; p.w[r >> 6] |= uint64_t(1) << (r & 63); return p;
    }

    std::vector<Poly> reduction_table(const std::vector<Poly>& reducers) {
        std::vector<Poly> rows(universe);
        for (const Poly& g: reducers) add_reducer(rows, g);
        return rows;
    }
    void add_reducer(std::vector<Poly>& rows, const Poly& g) {
        if (zero(g)) return;
        uint32_t lm = lead(g), free = full_mask & ~lm, sub = free;
        for (;;) {
            uint32_t target = lm | sub;
            Poly p = multiply(g, target & ~lm);
            if (!zero(p) && lead(p) == target &&
                (zero(rows[target]) || terms(p) < terms(rows[target]))) rows[target] = p;
            if (!sub) break;
            sub = (sub - 1) & free;
        }
    }
    Poly normal(Poly value, const std::vector<Poly>& reducers) {
        Poly rem;
        while (!zero(value)) {
            uint32_t lm = lead(value); int found = -1;
            for (int i = 0; i < (int)reducers.size(); ++i)
                if (!zero(reducers[i]) && divides(lead(reducers[i]), lm)) { found = i; break; }
            if (found < 0) {
                int r = rank_by_mask[lm]; rem.w[r >> 6] ^= uint64_t(1) << (r & 63);
                value.w[r >> 6] ^= uint64_t(1) << (r & 63);
            } else {
                Poly p = multiply(reducers[found], lm & ~lead(reducers[found]));
                xori(value, p); ++reductions;
            }
        }
        return rem;
    }
    Poly normal_rows(Poly value, const std::vector<Poly>& rows) {
        Poly rem;
        while (!zero(value)) {
            uint32_t lm = lead(value);
            if (!zero(rows[lm])) { xori(value, rows[lm]); ++reductions; }
            else {
                int r = rank_by_mask[lm]; rem.w[r >> 6] ^= uint64_t(1) << (r & 63);
                value.w[r >> 6] ^= uint64_t(1) << (r & 63);
            }
        }
        return rem;
    }

    bool sig_less(const Sig& a, const Sig& b) const {
        if (a.idx != b.idx) return a.idx > b.idx;
        return rank_by_mask[a.mon] < rank_by_mask[b.mon];
    }
    Sig sig_mul(const Sig& s, uint32_t m) const { return {s.mon | m, s.idx}; }
    bool label_less(const Labeled& a, const Labeled& b) const {
        if (a.sig.idx != b.sig.idx || a.sig.mon != b.sig.mon) return sig_less(a.sig, b.sig);
        return a.num > b.num;
    }
    Labeled label_mul(const Labeled& a, uint32_t m) const {
        return {sig_mul(a.sig, m), multiply(a.poly, m), a.num};
    }
    Labeled label_xor(const Labeled& a, const Labeled& b) const {
        Labeled r = label_less(a,b) ? b : a; r.poly = a.poly; xori(r.poly,b.poly); return r;
    }
    Pair critical(const Labeled& a, int ia, const Labeled& b, int ib) const {
        uint32_t la=lead(a.poly), lb=lead(b.poly), common=la|lb;
        uint32_t ma=common&~la, mb=common&~lb;
        Labeled ap=label_mul({a.sig,monomial_poly(la),a.num},ma);
        Labeled bp=label_mul({b.sig,monomial_poly(lb),b.num},mb);
        if (label_less(ap,bp)) return {bp.sig,ap.sig,mb,ma,ib,ia};
        return {ap.sig,bp.sig,ma,mb,ia,ib};
    }
    bool pair_less(const Pair& a, const Pair& b, const std::vector<Labeled>& B) const {
        Labeled a1{a.s1,{},B[a.i1].num}, b1{b.s1,{},B[b.i1].num};
        if (a1.sig.idx!=b1.sig.idx || a1.sig.mon!=b1.sig.mon || a1.num!=b1.num)
            return label_less(a1,b1);
        Labeled a2{a.s2,{},B[a.i2].num}, b2{b.s2,{},B[b.i2].num};
        return label_less(a2,b2);
    }
    void ensure_sig(int idx) {
        if ((int)rewrites.size() <= idx) { rewrites.resize(idx+1); syzygies.resize(idx+1); }
        if (rewrites[idx].empty()) { rewrites[idx].assign(universe,0); syzygies[idx].assign(universe,0); }
    }
    void index_label(const Labeled& x) {
        ensure_sig(x.sig.idx); uint32_t free=full_mask&~x.sig.mon, sub=free;
        for (;;) { uint32_t m=x.sig.mon|sub; rewrites[x.sig.idx][m]=std::max(rewrites[x.sig.idx][m],x.num); if(!sub)break;sub=(sub-1)&free; }
    }
    void index_syzygy(const Sig& s) {
        ensure_sig(s.idx); uint32_t free=full_mask&~s.mon, sub=free;
        for (;;) { syzygies[s.idx][s.mon|sub]=1; if(!sub)break;sub=(sub-1)&free; }
    }
    bool redundant(const Sig& s, int num) const {
        if (s.idx >= (int)rewrites.size() || rewrites[s.idx].empty()) return false;
        return syzygies[s.idx][s.mon] || rewrites[s.idx][s.mon] > num;
    }
    Labeled signature_reduce(Labeled f, const std::vector<Labeled>& B) {
        while (!zero(f.poly)) {
            Labeled old=f; uint32_t lm=lead(f.poly);
            for (const Labeled& h:B) {
                uint32_t lh=lead(h.poly); if(!divides(lh,lm)) continue;
                uint32_t m=lm&~lh; Sig s=sig_mul(h.sig,m);
                if (sig_less(s,f.sig)) { f=label_xor(f,label_mul(h,m)); ++reductions; break; }
            }
            if (f.poly==old.poly && f.sig.mon==old.sig.mon && f.sig.idx==old.sig.idx) break;
        }
        return f;
    }

    std::vector<Poly> interreduce(std::vector<Poly> cur) {
        std::sort(cur.begin(),cur.end(),[&](const Poly&a,const Poly&b){
            int da=0,db=0; for(uint32_t m: masks(a)) da=std::max(da,__builtin_popcount(m));
            for(uint32_t m:masks(b)) db=std::max(db,__builtin_popcount(m));
            if(da!=db)return da<db; if(terms(a)!=terms(b))return terms(a)<terms(b); return rank_by_mask[lead(a)]<rank_by_mask[lead(b)];});
        cur.erase(std::unique(cur.begin(),cur.end()),cur.end());
        std::vector<uint32_t> versions(cur.size(),0);
        std::unordered_map<uint64_t,Poly> products;
        products.reserve(65536);
        for (;;) {
            int count=cur.size(), chunks=(count+63)/64;
            std::vector<uint64_t> divisors((size_t)universe*chunks,0);
            auto remove_source=[&](int source){
                uint64_t bit=uint64_t(1)<<(source&63);int chunk=source>>6;
                for(int m=0;m<universe;++m)divisors[(size_t)m*chunks+chunk]&=~bit;
            };
            auto add_source=[&](int source){
                if(zero(cur[source]))return;uint32_t lm=lead(cur[source]);
                uint32_t free=full_mask&~lm,sub=free;uint64_t bit=uint64_t(1)<<(source&63);int chunk=source>>6;
                for(;;){uint32_t target=lm|sub;divisors[(size_t)target*chunks+chunk]|=bit;if(!sub)break;sub=(sub-1)&free;}
            };
            for(int i=0;i<count;++i)add_source(i);
            bool changed=false;
            for(int i=0;i<count;++i) {
                if(zero(cur[i]))continue;Poly value=cur[i],rem;
                while(!zero(value)){
                    uint32_t lm=lead(value);int reducer=-1;
                    for(int c=0;c<chunks;++c){uint64_t bits=divisors[(size_t)lm*chunks+c];if(c==(i>>6))bits&=~(uint64_t(1)<<(i&63));if(bits){reducer=c*64+__builtin_ctzll(bits);break;}}
                    if(reducer<0){int r=rank_by_mask[lm];uint64_t bit=uint64_t(1)<<(r&63);rem.w[r>>6]^=bit;value.w[r>>6]^=bit;}
                    else{
                        uint64_t key=(uint64_t(versions[reducer])<<32)|
                            (uint64_t(reducer)<<16)|lm;
                        auto found=products.find(key);Poly p;
                        if(found==products.end()){
                            p=multiply(cur[reducer],lm&~lead(cur[reducer]));
                            products.emplace(key,p);
                        }else p=found->second;
                        xori(value,p);++reductions;
                    }
                }
                if(rem==cur[i])continue;changed=true;remove_source(i);cur[i]=rem;++versions[i];add_source(i);
            }
            size_t before_compact=cur.size();
            cur.erase(std::remove_if(cur.begin(),cur.end(),[&](const Poly&p){return zero(p);}),cur.end());
            if(cur.size()!=before_compact){versions.assign(cur.size(),0);products.clear();}
            if(!changed)return cur;
        }
    }
    std::vector<uint32_t> masks(const Poly&p) const {
        std::vector<uint32_t> r; for(int wi=0;wi<words;++wi){uint64_t x=p.w[wi];while(x){int b=__builtin_ctzll(x);r.push_back(mask_by_rank[wi*64+b]);x&=x-1;}}return r;
    }

    std::vector<Poly> complete(std::vector<Poly> B) {
        auto rows=reduction_table(B); std::vector<std::pair<int,int>> ps;
        for(int i=0;i<(int)B.size();++i)for(int j=i+1;j<(int)B.size();++j)if(lead(B[i])&lead(B[j]))ps.push_back({i,j});
        while(!ps.empty()) {
            auto [i,j]=ps.back();ps.pop_back();uint32_t c=lead(B[i])|lead(B[j]);
            Poly s=multiply(B[i],c&~lead(B[i]));xori(s,multiply(B[j],c&~lead(B[j])));Poly r=normal_rows(s,rows);
            if(zero(r)||std::find(B.begin(),B.end(),r)!=B.end())continue;int pos=B.size();B.push_back(r);add_reducer(rows,r);
            for(int k=0;k<pos;++k)if(lead(B[k])&lead(r))ps.push_back({k,pos});
        }
        return B;
    }
    std::vector<Poly> reduce_basis(std::vector<Poly> B) {
        std::vector<Poly> min;
        std::sort(B.begin(),B.end(),[&](const Poly&a,const Poly&b){return rank_by_mask[lead(a)]<rank_by_mask[lead(b)];});
        while(!B.empty()){Poly p=B.back();B.pop_back();bool red=false;for(const Poly&q:B)if(divides(lead(q),lead(p)))red=true;for(const Poly&q:min)if(divides(lead(q),lead(p)))red=true;if(!red)min.push_back(p);}
        std::vector<Poly> out;for(int i=0;i<(int)min.size();++i){std::vector<Poly> o;for(int j=0;j<(int)min.size();++j)if(i!=j)o.push_back(min[j]);Poly r=normal(min[i],o);if(!zero(r))out.push_back(r);}
        std::sort(out.begin(),out.end(),[&](const Poly&a,const Poly&b){return rank_by_mask[lead(a)]>rank_by_mask[lead(b)];});return out;
    }




    std::vector<Poly> basis(std::vector<Poly> F) {
        auto phase=std::chrono::steady_clock::now();
        for(;;){
            std::vector<Poly> R;
            std::vector<Poly> rows(universe);
            for(int i=0;i<(int)F.size();++i){
                Poly r=normal_rows(F[i],rows);
                if(!zero(r)){R.push_back(r);add_reducer(rows,r);}
            }
            if(R==F)break;
            F=R;
        }
        initial_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-phase).count();phase=std::chrono::steady_clock::now();
        std::vector<Labeled>B;for(int i=0;i<(int)F.size();++i){B.push_back({{0,i+1},F[i],i+1});index_label(B.back());}
        std::sort(B.begin(),B.end(),[&](const Labeled&a,const Labeled&b){return rank_by_mask[lead(a.poly)]>rank_by_mask[lead(b.poly)];});
        std::vector<Poly> basis_polys;for(auto&x:B)basis_polys.push_back(x.poly);auto reducer_rows=reduction_table(basis_polys);
        std::vector<Pair> P;for(int i=0;i<(int)B.size();++i)for(int j=i+1;j<(int)B.size();++j)if(lead(B[i].poly)&lead(B[j].poly))P.push_back(critical(B[i],i,B[j],j));
        auto sortp=[&](){std::sort(P.begin(),P.end(),[&](const Pair&a,const Pair&b){return pair_less(b,a,B);});};sortp();int number=B.size();
        while(!P.empty()&&insertions<signature_limit){Pair p=P.back();P.pop_back();++pairs_processed;if(redundant(p.s1,B[p.i1].num)||redundant(p.s2,B[p.i2].num))continue;
            Labeled s=label_xor(label_mul(B[p.i1],p.m1),label_mul(B[p.i2],p.m2));Labeled c=signature_reduce(s,B);c.poly=normal_rows(c.poly,reducer_rows);if(zero(c.poly)){index_syzygy(c.sig);continue;}
            c.num=++number;index_label(c);add_reducer(reducer_rows,c.poly);int ni=B.size();B.push_back(c);++insertions;
            std::vector<Pair> keep;for(auto&q:P)if(!redundant(q.s1,B[q.i1].num)&&!redundant(q.s2,B[q.i2].num))keep.push_back(q);P.swap(keep);
            for(int i=0;i<ni;++i)if(lead(B[i].poly)&lead(c.poly)){Pair q=critical(c,ni,B[i],i);if(!redundant(q.s1,B[q.i1].num)&&!redundant(q.s2,B[q.i2].num))P.push_back(q);}sortp();
        }
        signature_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-phase).count();phase=std::chrono::steady_clock::now();
        std::vector<Poly> raw=F, derived;
        if(completion_seed_limit<0){
            for(auto&x:B)if(std::find(raw.begin(),raw.end(),x.poly)==raw.end())raw.push_back(x.poly);
        }else{
            std::vector<Poly> best(universe);
            for(auto&x:B){uint32_t lm=lead(x.poly);if(zero(best[lm])||terms(x.poly)<terms(best[lm]))best[lm]=x.poly;}
            for(auto&p:best)if(!zero(p)&&std::find(raw.begin(),raw.end(),p)==raw.end())derived.push_back(p);
            std::sort(derived.begin(),derived.end(),[&](const Poly&a,const Poly&b){if(degree(a)!=degree(b))return degree(a)<degree(b);if(terms(a)!=terms(b))return terms(a)<terms(b);return rank_by_mask[lead(a)]<rank_by_mask[lead(b)];});
            if(completion_seed_limit<(int)derived.size())derived.resize(completion_seed_limit);
        raw.insert(raw.end(),derived.begin(),derived.end());
        }
        auto ir=interreduce(raw);
        interreduce_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-phase).count();phase=std::chrono::steady_clock::now();auto done=complete(ir);
        completion_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-phase).count();phase=std::chrono::steady_clock::now();auto out=reduce_basis(done);
        final_reduce_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-phase).count();return out;
    }
};

#ifndef BOOLEAN_F5B_NO_MAIN
int main(){std::ios::sync_with_stdio(false);int n,g,limit,seed_limit;if(!(std::cin>>n>>g>>limit>>seed_limit)||n<1||n>12)return 2;Engine e(n,limit,seed_limit);std::vector<Poly> F;for(int i=0;i<g;++i){int k;std::cin>>k;Poly p;for(int j=0;j<k;++j){uint32_t m;std::cin>>m;uint32_t r=e.rank_by_mask[m];p.w[r>>6]^=uint64_t(1)<<(r&63);}F.push_back(p);}auto t=std::chrono::steady_clock::now();auto B=e.basis(F);double sec=std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count();std::cout<<"OK "<<B.size()<<" "<<sec<<" "<<e.insertions<<" "<<e.reductions<<" "<<e.initial_seconds<<" "<<e.signature_seconds<<" "<<e.interreduce_seconds<<" "<<e.completion_seconds<<" "<<e.final_reduce_seconds<<"\n";for(auto&p:B){auto ms=e.masks(p);std::sort(ms.begin(),ms.end());std::cout<<ms.size();for(auto m:ms)std::cout<<" "<<m;std::cout<<"\n";} }
#endif
