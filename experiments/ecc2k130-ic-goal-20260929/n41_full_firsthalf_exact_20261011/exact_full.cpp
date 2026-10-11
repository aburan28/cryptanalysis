// Exact transported W6 pair states and target-conditioned two-pair join.
#define main frozen_three_pair_main
#include "../../koblitz-s5-invariant-20260924/three_pair_s7_native.cpp"
#undef main

#include <algorithm>
#include <chrono>
#include <map>
#include <set>
#include <unordered_set>

using Clock=std::chrono::steady_clock;
static uint64_t elapsed(Clock::time_point start){
    return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-start).count();
}
static uint64_t rss(){
    rusage usage{};getrusage(RUSAGE_SELF,&usage);
#if defined(__APPLE__)
    return uint64_t(usage.ru_maxrss);
#else
    return uint64_t(usage.ru_maxrss)*1024;
#endif
}
static uint64_t trace41(uint64_t x){
    uint64_t result=0;
    for(int i=0;i<41;++i){result^=x;x=sq(x);}
    if(result>1)throw std::runtime_error("field trace invalid");
    return result;
}
static uint64_t halftrace41(uint64_t x){
    uint64_t result=0;
    for(int i=0;i<21;++i){result^=x;x=sq(sq(x));}
    return result;
}
static uint64_t frob(uint64_t x,int rotation){
    for(int i=0;i<rotation;++i)x=sq(x);
    return x;
}
struct Source{
    uint8_t column,mask,sign;
    Point raw,transported;
    uint64_t reciprocal;
};
struct ExactPair{
    uint16_t first,second;
    Point point;
    uint64_t reciprocal;
    uint8_t branch;
};
static void source_json(std::ostream& out,const Source& source){
    out<<"{\"column\":"<<unsigned(source.column)
       <<",\"mask\":"<<unsigned(source.mask)
       <<",\"sign\":"<<unsigned(source.sign)
       <<",\"raw\":["<<source.raw.x<<","<<source.raw.y
       <<"],\"transported\":["<<source.transported.x<<","
       <<source.transported.y<<"]}";
}
static std::vector<ExactPair> make_pairs(
    const std::vector<Source>& sources,int rotation,uint64_t& skipped_columns){
    std::vector<ExactPair> result;
    for(size_t i=0;i<sources.size();++i){
        for(size_t j=i+1;j<sources.size();++j){
            const auto& a=sources[i];const auto& b=sources[j];
            if(a.column==b.column){++skipped_columns;continue;}
            Point point=add(a.transported,b.transported);
            if(point.infinity||!point.x)throw std::runtime_error("exceptional exact pair");
            if(!on_curve(point))throw std::runtime_error("exact pair off curve");
            uint64_t z=inv(point.x),s=a.reciprocal^b.reciprocal;
            uint64_t p=mul(a.reciprocal,b.reciprocal);
            if(z==0||trace41(z)||trace41(s^z))
                throw std::runtime_error("exact pair missing trace condition");
            uint64_t branch=mul(p,z)^halftrace41(sq(s^z));
            if(branch>1)throw std::runtime_error("exact pair outside relaxed equation");
            if(frob(uint64_t(a.mask^b.mask)<<1,rotation)!=s)
                throw std::runtime_error("seed-sum transport mismatch");
            result.push_back({uint16_t(i),uint16_t(j),point,z,uint8_t(branch)});
        }
    }
    return result;
}
int main(int argc,char** argv){
    try{
        if(argc!=3)throw std::runtime_error("usage: exact_join input.txt receipt.json");
        std::ifstream in(argv[1]);if(!in)throw std::runtime_error("input open");
        int count;in>>count;if(!in||count!=1712)throw std::runtime_error("full first-half target count");
        struct Target{std::string label;Point point;};
        std::vector<Target> targets;
        for(int i=0;i<count;++i){
            std::string label;uint64_t x,y;in>>label>>x>>y;
            Point point=finite(x,y);
            if(!in||!on_curve(point))throw std::runtime_error("invalid target");
            targets.push_back({label,point});
        }
        auto setup_start=Clock::now();
        std::array<std::vector<Source>,2> sources;
        for(int block=0;block<2;++block){
            int rotation,size;in>>rotation>>size;
            if(!in||rotation!=(block?30:20)||size!=64)
                throw std::runtime_error("source header mismatch");
            std::set<Point,bool(*)(const Point&,const Point&)> seen(
                [](const Point& a,const Point& b){return a.x==b.x?a.y<b.y:a.x<b.x;});
            for(int i=0;i<size;++i){
                uint64_t x,y;int col,mask,branch,sign;
                in>>x>>y>>col>>mask>>branch>>sign;
                Point p=finite(x,y);
                if(!in||!on_curve(p)||col<0||col>255||mask<1||mask>63||
                   branch!=0||sign<0||sign>1||!seen.insert(p).second)
                    throw std::runtime_error("source row invalid");
                Point pi=finite(sq(x),sq(y));
                Point d=add(p,pi);
                uint64_t w=frob(uint64_t(mask)<<1,rotation);
                if(d.infinity||!d.x||!on_curve(d)||inv(d.x)!=w)
                    throw std::runtime_error("source transport mismatch");
                sources[block].push_back({uint8_t(col),uint8_t(mask),uint8_t(sign),p,d,w});
            }
        }
        std::string extra;if(in>>extra)throw std::runtime_error("trailing input");
        uint64_t excluded20=0,excluded30=0;
        auto left=make_pairs(sources[0],20,excluded20);
        auto right=make_pairs(sources[1],30,excluded30);
        std::unordered_set<Point,PointHash> distinct_left,distinct_right;
        for(const auto& pair:left)distinct_left.insert(pair.point);
        for(const auto& pair:right)distinct_right.insert(pair.point);
        std::unordered_map<Point,std::vector<size_t>,PointHash> right_index;
        right_index.reserve(distinct_right.size()*2);
        for(size_t i=0;i<right.size();++i)right_index[right[i].point].push_back(i);
        if(elapsed(setup_start)>120000000000ULL||rss()>4ULL*1024*1024*1024)
            throw std::runtime_error("setup cap");
        const uint64_t setup_ns=elapsed(setup_start);
        std::ofstream out(argv[2]);if(!out)throw std::runtime_error("receipt open");
        out<<"{\"status\":\"COMPLETE_EXACT_TRANSPORT_PAIR_PANEL\","
           <<"\"candidate_id\":null,\"source_points_per_rotation\":64,"
           <<"\"same_column_exclusions\":["<<excluded20<<","<<excluded30<<"],"
           <<"\"exact_pair_witnesses\":["<<left.size()<<","<<right.size()<<"],"
           <<"\"distinct_exact_pair_points\":["<<distinct_left.size()<<","
           <<distinct_right.size()<<"],\"reusable_setup_ns\":"<<setup_ns
           <<",\"queries\":[";
        for(size_t qi=0;qi<targets.size();++qi){
            const auto& target=targets[qi];auto start=Clock::now();
            uint64_t probes=0,group_hits=0,column_compatible_hits=0;
            size_t found_left=left.size(),found_right=right.size();
            for(size_t i=0;i<left.size();++i){
                ++probes;
                Point needed=add(target.point,neg(left[i].point));
                auto it=right_index.find(needed);
                if(it==right_index.end())continue;
                group_hits+=it->second.size();
                for(size_t j:it->second){
                    const auto& a=sources[0][left[i].first];
                    const auto& b=sources[0][left[i].second];
                    const auto& c=sources[1][right[j].first];
                    const auto& d=sources[1][right[j].second];
                    std::set<int> columns={a.column,b.column,c.column,d.column};
                    if(columns.size()!=4)continue;
                    ++column_compatible_hits;
                    if(found_left==left.size()){found_left=i;found_right=j;}
                }
            }
            const bool hit=found_left!=left.size();
            if(qi==0&&!hit)throw std::runtime_error("frozen positive missing");
            if(hit && !(add(left[found_left].point,right[found_right].point)==target.point))
                throw std::runtime_error("exact group replay failed");
            out<<(qi?",":"")<<"{\"label\":\""<<target.label
               <<"\",\"status\":\""
               <<(hit?"EXACT_FOUR_ATOM_HIT":"COMPLETE_EXACT_NO_SUM")
               <<"\",\"target\":["<<target.point.x<<","<<target.point.y
               <<"],\"pair_probes\":"<<probes<<",\"group_hits\":"<<group_hits
               <<",\"column_compatible_hits\":"<<column_compatible_hits
               <<",\"online_ns\":"<<elapsed(start);
            if(hit){
                const auto& a=left[found_left];const auto& b=right[found_right];
                out<<",\"left_pair_point\":["<<a.point.x<<","<<a.point.y
                   <<"],\"right_pair_point\":["<<b.point.x<<","<<b.point.y
                   <<"],\"left_branch\":"<<unsigned(a.branch)
                   <<",\"right_branch\":"<<unsigned(b.branch)
                   <<",\"source_witnesses\":[";
                source_json(out,sources[0][a.first]);out<<",";
                source_json(out,sources[0][a.second]);out<<",";
                source_json(out,sources[1][b.first]);out<<",";
                source_json(out,sources[1][b.second]);out<<"]";
            }
            out<<"}";
        }
        out<<"],\"peak_rss_bytes\":"<<rss()
           <<",\"limits\":{\"workers\":1,\"setup_seconds\":120,"
             "\"online_seconds_per_query\":120,\"rss_bytes\":4294967296}}\n";
        std::cout<<"COMPLETE_EXACT_TRANSPORT_PAIR_PANEL pairs="<<left.size()
                 <<","<<right.size()<<" unique="<<distinct_left.size()
                 <<","<<distinct_right.size()<<"\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<"error: "<<e.what()<<"\n";return 2;}
}
