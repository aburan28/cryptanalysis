// Derive Q-P0 and Q-P0-P1 from frozen exact twelve-column source rows.
#include "../n41_w6_public_seed_predictor_20261011/base.hpp"
#include <sstream>

int main(int argc,char**argv){
try {
    if(argc!=4)throw std::runtime_error("usage: extract source_input rows.tsv residuals.tsv");
    std::ifstream input(argv[1]);if(!input)throw std::runtime_error("source input missing");
    uint64_t qx,qy,order;int blocks;input>>qx>>qy>>order>>blocks;
    if(!input||order!=549756390943ULL||blocks!=6)throw std::runtime_error("source header drift");
    std::array<std::vector<Atom>,6> atoms;
    for(int block=0;block<6;++block){
        int rotation,size;input>>rotation>>size;
        if(!input||rotation!=block*5||size!=64)throw std::runtime_error("rotation drift");
        for(int i=0;i<size;++i){
            uint64_t x,y;int mask,sign,column;input>>x>>y>>mask>>sign>>column;
            Point point=finite(x,y);
            if(!input||!on_curve(point)||mask<1||mask>=64||sign<0||sign>1||column<0||column>=26)
                throw std::runtime_error("invalid atom");
            atoms[block].push_back({point,uint8_t(mask),uint8_t(sign),uint8_t(column)});
        }
    }
    std::string extra;if(input>>extra)throw std::runtime_error("source trailing data");
    auto first=make_pairs(atoms[0]);auto second=make_pairs(atoms[1]);
    if(first.size()!=1956||second.size()!=1956)throw std::runtime_error("pair count drift");
    std::ifstream rows(argv[2]);if(!rows)throw std::runtime_error("rows missing");
    std::string line;std::getline(rows,line);
    if(line!="x\ty\tseed_a\tseed_b\tp0\tp1\ta0\ta1\tb0\tb1")
        throw std::runtime_error("row header drift");
    std::ofstream out(argv[3]);if(!out)throw std::runtime_error("output open failed");
    out<<"x\ty\tr0x\tr0y\tr01x\tr01y\tseed_a\tseed_b\tp0\tp1\n";
    uint64_t count=0,identity=0;
    while(std::getline(rows,line)){
        if(line.empty())throw std::runtime_error("empty row");
        std::istringstream cell(line);uint64_t x,y;int sa,sb,p0,p1,a0,a1,b0,b1;
        if(!(cell>>x>>y>>sa>>sb>>p0>>p1>>a0>>a1>>b0>>b1))
            throw std::runtime_error("bad row");
        std::string tail;if(cell>>tail)throw std::runtime_error("extra row data");
        if(x>MASK||y>MASK||!on_curve(finite(x,y))||sa<1||sa>=64||sb<1||sb>=64||
           (sa^sb)>=8||p0<0||p0>=1956||p1<0||p1>=1956||
           a0<0||a1<0||b0<0||b1<0)throw std::runtime_error("row drift");
        Point q=finite(x,y);
        Point r0=add(q,neg(first[size_t(p0)].sum));
        Point r01=add(r0,neg(second[size_t(p1)].sum));
        if(r0.infinity||r01.infinity){++identity;throw std::runtime_error("identity residual");}
        if(!on_curve(r0)||!on_curve(r01)||
           !(add(r0,first[size_t(p0)].sum)==q)||
           !(add(add(r01,second[size_t(p1)].sum),first[size_t(p0)].sum)==q))
            throw std::runtime_error("residual replay failure");
        out<<x<<'\t'<<y<<'\t'<<r0.x<<'\t'<<r0.y<<'\t'
           <<r01.x<<'\t'<<r01.y<<'\t'<<sa<<'\t'<<sb<<'\t'<<p0<<'\t'<<p1<<'\n';
        ++count;
    }
    if(!rows.eof()||count!=100000||identity)throw std::runtime_error("row count drift");
    std::cout<<"COMPLETE rows="<<count<<" identity="<<identity<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
