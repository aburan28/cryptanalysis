// Exact XOR-correlation upper counts for cross-block translated source pairs.
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static void walsh(std::vector<int64_t>& a){
    const size_t n=a.size();
    for(size_t len=1;len<n;len*=2)
        for(size_t start=0;start<n;start+=2*len)
            for(size_t j=0;j<len;++j){
                const int64_t x=a[start+j],y=a[start+j+len];
                a[start+j]=x+y;a[start+j+len]=x-y;
            }
}

int main(int argc,char**argv){
try {
    if(argc!=4)throw std::runtime_error("usage: census dimension support.tsv output.tsv");
    int d=std::stoi(argv[1]);
    if(d!=6&&d!=18)throw std::runtime_error("dimension drift");
    const size_t n=size_t(1)<<d;
    std::vector<int> columns(n,-1);
    std::ifstream source(argv[2]);if(!source)throw std::runtime_error("support missing");
    int mask,column;size_t count=0;
    while(source>>mask>>column){
        if(mask<=0||size_t(mask)>=n||column<0||columns[size_t(mask)]!=-1)
            throw std::runtime_error("bad support row");
        columns[size_t(mask)]=column;++count;
    }
    if(!source.eof()||count!=(d==6?32U:131307U))throw std::runtime_error("support count drift");
    std::vector<int64_t> linked(n,0),at7,at15;
    uint64_t all_valid=0;
    for(int u=1;u<=31;++u){
        std::vector<int64_t> correlation(n,0);
        for(size_t w=0;w<n;++w){
            const size_t other=w^size_t(u);
            if(columns[w]>=0&&columns[other]>=0&&columns[w]!=columns[other])
                correlation[w]=1;
        }
        walsh(correlation);
        for(auto& value:correlation)value*=value;
        walsh(correlation);
        for(size_t s=1;s<n;++s){
            if(s==size_t(u))continue; // The translated pair reuses the two source masks.
            if(correlation[s]<0||correlation[s]%int64_t(n)!=0)
                throw std::runtime_error("nonintegral autocorrelation");
            const int64_t c=correlation[s]/int64_t(n);
            if(c%2)throw std::runtime_error("ordered pair parity drift");
            linked[s]+=8*c; // c/2 unordered mask quartets, 16 signed leaf choices.
        }
        if(u==7)at7=linked;
        if(u==15)at15=linked;
        ++all_valid;
    }
    if(all_valid!=31)throw std::runtime_error("translation count drift");
    std::ofstream output(argv[3]);if(!output)throw std::runtime_error("output open failed");
    output<<"seed\tlinked_u7\tlinked_u15\tlinked_u31\n";
    for(size_t s=1;s<n;++s)
        output<<s<<'\t'<<at7[s]<<'\t'<<at15[s]<<'\t'<<linked[s]<<'\n';
    if(!output)throw std::runtime_error("output write failed");
    std::cout<<"COMPLETE dimension="<<d<<" seeds="<<n-1<<" translations=31\n";
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
