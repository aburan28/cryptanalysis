// Fixed nonlinear generating-seed selector on the archived N41 relation law.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

constexpr int TRAIN = 80000;
constexpr int TOTAL = 100000;
constexpr int CLASSES = 63;
constexpr int TREES = 32;
constexpr int DEPTH = 6;
constexpr int MTRY = 16;
constexpr double PRIOR_WEIGHT = 64.0;

struct Row {
    std::array<uint64_t,6> coord{};
    uint8_t seed = 0;
};
struct Tree {
    std::array<int,DEPTH> split{};
    std::array<std::array<uint16_t,64>,1 << DEPTH> counts{};
    std::array<uint32_t,1 << DEPTH> sizes{};
};
struct Arm {
    std::string name;
    std::vector<int> coordinates;
    std::vector<Tree> trees;
};

static uint64_t mix(uint64_t& x) {
    x += 0x9e3779b97f4a7c15ULL;
    uint64_t z=x;
    z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;
    z=(z^(z>>27))*0x94d049bb133111ebULL;
    return z^(z>>31);
}
static int bit(const Row& row,const Arm& arm,int feature) {
    const int coordinate=arm.coordinates[size_t(feature/41)];
    return int((row.coord[size_t(coordinate)]>>(feature%41))&1ULL);
}
static std::vector<Row> read_rows(const std::string& path) {
    std::ifstream in(path);
    if(!in)throw std::runtime_error("source input missing");
    std::string header;
    std::getline(in,header);
    if(header!="x\ty\tr0x\tr0y\tr01x\tr01y\tseed_a\tseed_b\tp0\tp1")
        throw std::runtime_error("source header drift");
    std::vector<Row> rows;
    rows.reserve(TOTAL);
    for(int i=0;i<TOTAL;++i) {
        Row row;
        uint64_t label,seed_b,p0,p1;
        for(uint64_t& value:row.coord)in>>value;
        in>>label>>seed_b>>p0>>p1;
        if(!in||label<1||label>63||seed_b<1||seed_b>63||p0>=1956||p1>=1956)
            throw std::runtime_error("source row drift");
        for(uint64_t value:row.coord)if(value>=(1ULL<<41))
            throw std::runtime_error("coordinate outside N41 field");
        row.seed=uint8_t(label);
        rows.push_back(row);
    }
    uint64_t extra;
    if(in>>extra)throw std::runtime_error("extra source row");
    if(!in.eof())throw std::runtime_error("source parse error");
    return rows;
}
static double score_split(const std::vector<Row>& rows,const Arm& arm,
                          const std::vector<uint8_t>& assignment,
                          const std::vector<std::array<int,64>>& parent,
                          int candidate,int node_count) {
    std::vector<std::array<int,64>> on{size_t(node_count)};
    for(int i=0;i<TRAIN;++i)if(bit(rows[size_t(i)],arm,candidate))
        ++on[size_t(assignment[size_t(i)])][rows[size_t(i)].seed];
    double score=0.0;
    for(int node=0;node<node_count;++node) {
        int n_on=0,n_off=0;
        for(int label=1;label<=CLASSES;++label) {
            n_on+=on[size_t(node)][size_t(label)];
            n_off+=parent[size_t(node)][size_t(label)]-on[size_t(node)][size_t(label)];
        }
        if(!n_on||!n_off)continue;
        for(int label=1;label<=CLASSES;++label) {
            double a=on[size_t(node)][size_t(label)];
            double b=parent[size_t(node)][size_t(label)]-a;
            score+=a*a/n_on+b*b/n_off;
        }
    }
    return score;
}
static Tree train_tree(const std::vector<Row>& rows,const Arm& arm,uint64_t& rng) {
    Tree tree;
    std::vector<uint8_t> assignment(TRAIN,0);
    const int features=int(arm.coordinates.size())*41;
    for(int depth=0;depth<DEPTH;++depth) {
        const int nodes=1<<depth;
        std::vector<std::array<int,64>> parent{size_t(nodes)};
        for(int i=0;i<TRAIN;++i)
            ++parent[size_t(assignment[size_t(i)])][rows[size_t(i)].seed];
        std::vector<int> candidates;
        while(int(candidates.size())<MTRY) {
            int candidate=int(mix(rng)%uint64_t(features));
            if(std::find(candidates.begin(),candidates.end(),candidate)!=candidates.end())continue;
            if(std::find(tree.split.begin(),tree.split.begin()+depth,candidate)!=tree.split.begin()+depth)continue;
            candidates.push_back(candidate);
        }
        double best=-1.0;
        int chosen=-1;
        for(int candidate:candidates) {
            double score=score_split(rows,arm,assignment,parent,candidate,nodes);
            if(score>best || (score==best && candidate<chosen)) {
                best=score;
                chosen=candidate;
            }
        }
        if(chosen<0)throw std::runtime_error("empty feature choice");
        tree.split[size_t(depth)]=chosen;
        for(int i=0;i<TRAIN;++i)
            assignment[size_t(i)]=uint8_t((assignment[size_t(i)]<<1)|bit(rows[size_t(i)],arm,chosen));
    }
    for(int i=0;i<TRAIN;++i) {
        int leaf=assignment[size_t(i)];
        ++tree.counts[size_t(leaf)][rows[size_t(i)].seed];
        ++tree.sizes[size_t(leaf)];
    }
    return tree;
}
static std::array<int,7> predict(const Row& row,const Arm& arm,
                                 const std::array<double,64>& prior) {
    std::array<double,64> scores{};
    for(const Tree& tree:arm.trees) {
        int leaf=0;
        for(int feature:tree.split)leaf=(leaf<<1)|bit(row,arm,feature);
        double denom=double(tree.sizes[size_t(leaf)])+PRIOR_WEIGHT;
        for(int label=1;label<=CLASSES;++label)
            scores[size_t(label)]+=(tree.counts[size_t(leaf)][size_t(label)]
                                    +PRIOR_WEIGHT*prior[size_t(label)])/denom;
    }
    std::array<int,CLASSES> labels{};
    std::iota(labels.begin(),labels.end(),1);
    std::partial_sort(labels.begin(),labels.begin()+7,labels.end(),
        [&](int a,int b){return scores[size_t(a)]==scores[size_t(b)]
                                 ? a<b : scores[size_t(a)]>scores[size_t(b)];});
    std::array<int,7> top{};
    std::copy_n(labels.begin(),7,top.begin());
    return top;
}

int main(int argc,char**argv) {
    try {
        if(argc!=3)throw std::runtime_error("usage: forest residuals.tsv predictions.tsv");
        auto rows=read_rows(argv[1]);
        std::array<int,64> count{};
        for(int i=0;i<TRAIN;++i)++count[rows[size_t(i)].seed];
        for(int label=1;label<=CLASSES;++label)if(!count[size_t(label)])
            throw std::runtime_error("missing training class");
        std::array<double,64> prior{};
        for(int label=1;label<=CLASSES;++label)
            prior[size_t(label)]=double(count[size_t(label)])/TRAIN;
        std::array<int,CLASSES> labels{};
        std::iota(labels.begin(),labels.end(),1);
        std::partial_sort(labels.begin(),labels.begin()+7,labels.end(),
            [&](int a,int b){return count[size_t(a)]==count[size_t(b)]
                                     ? a<b : count[size_t(a)]>count[size_t(b)];});
        std::array<int,7> baseline{};
        std::copy_n(labels.begin(),7,baseline.begin());
        std::vector<Arm> arms={{"public",{0,1},{}},{"one_pair_residual",{2,3},{}},
                               {"two_pair_residual",{4,5},{}},
                               {"joint",{0,1,2,3,4,5},{}}};
        for(size_t arm_index=0;arm_index<arms.size();++arm_index) {
            auto& arm=arms[arm_index];
            arm.trees.reserve(TREES);
            uint64_t rng=0x202610110938ULL ^ (uint64_t(arm_index)<<40);
            auto start=std::chrono::steady_clock::now();
            for(int tree=0;tree<TREES;++tree)
                arm.trees.push_back(train_tree(rows,arm,rng));
            double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            std::cerr<<arm.name<<" trained "<<TREES<<" trees in "<<seconds<<" s\n";
        }
        std::ofstream out(argv[2]);
        if(!out)throw std::runtime_error("output open failed");
        out<<"row\tseed\tbaseline";
        for(const auto& arm:arms)out<<'\t'<<arm.name;
        out<<'\n';
        for(int i=TRAIN;i<TOTAL;++i) {
            const Row& row=rows[size_t(i)];
            out<<i<<'\t'<<int(row.seed);
            auto emit=[&](const std::array<int,7>& top){
                out<<'\t';
                for(int j=0;j<7;++j){if(j)out<<',';out<<top[size_t(j)];}
            };
            emit(baseline);
            for(const Arm& arm:arms)emit(predict(row,arm,prior));
            out<<'\n';
        }
        if(!out)throw std::runtime_error("output write failed");
        std::cout<<"COMPLETE train="<<TRAIN<<" holdout="<<(TOTAL-TRAIN)
                 <<" trees="<<TREES<<" depth="<<DEPTH<<"\n";
    } catch(const std::exception& e) {
        std::cerr<<e.what()<<'\n';
        return 1;
    }
}
