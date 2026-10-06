// Single-matrix RREF screen, derived from the frozen round-three harness.
#ifndef FUSED
#define FUSED 0
#endif
#ifndef PIVOT_THREADS
#define PIVOT_THREADS 256
#endif
#ifndef M4RI_K
#define M4RI_K 5
#endif
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <m4ri/m4ri.h>
#include <algorithm>
#include <chrono>
#include <cstring>
#include <iostream>
#include <random>
#include <stdexcept>
#include <vector>
using Clock=std::chrono::steady_clock;
struct Params { uint32_t rows,cols,words,count; };
static double elapsed(Clock::time_point t) {
    return std::chrono::duration<double,std::milli>(Clock::now()-t).count();
}
static double median(std::vector<double> x) {
    std::sort(x.begin(),x.end()); return x[x.size()/2];
}
struct Case {
    std::string name;
    uint32_t rows,cols;
    std::vector<uint64_t> data;
};
struct Result { std::vector<uint64_t> data; std::vector<uint32_t> ranks; double ms=0,gpu_ms=0; };
static Result cpu(const std::vector<uint64_t>& input, Params p) {
    auto start=Clock::now();
    Result result; result.data.resize(input.size()); result.ranks.resize(p.count);
    size_t stride=p.words/2;
    for(uint32_t b=0;b<p.count;++b) {
        if(!p.rows || !p.cols) continue;
        mzd_t* a=mzd_init(p.rows,p.cols);
        for(uint32_t r=0;r<p.rows;++r)
            memcpy(mzd_row(a,r),input.data()+(size_t(b)*p.rows+r)*stride,stride*8);
        result.ranks[b]=mzd_echelonize_m4ri(a,1,M4RI_K);
        for(uint32_t r=0;r<p.rows;++r)
            memcpy(result.data.data()+(size_t(b)*p.rows+r)*stride,mzd_row(a,r),stride*8);
        mzd_free(a);
    }
    result.ms=elapsed(start); result.gpu_ms=0; return result;
}
static Result gpu(const std::vector<uint64_t>& input, Params p,
                  id<MTLDevice> device,id<MTLCommandQueue> queue,NSArray* pipelines) {
    auto start=Clock::now();
    Result result; result.data.resize(input.size()); result.ranks.resize(p.count);
    @autoreleasepool {
        if(p.rows && p.cols && p.count) {
            if(p.rows>8192 || p.cols>8192 || p.count>256)
                throw std::runtime_error("experimental dimensions exceed validated allocation bounds");
            id<MTLBuffer> a=[device newBufferWithBytes:input.data() length:input.size()*8 options:MTLResourceStorageModeShared];
            id<MTLBuffer> state=[device newBufferWithLength:p.count*16 options:MTLResourceStorageModeShared];
            id<MTLBuffer> pc=[device newBufferWithLength:p.count*32 options:MTLResourceStorageModeShared];
            id<MTLBuffer> table=[device newBufferWithLength:size_t(p.count)*256*p.words*4 options:MTLResourceStorageModeShared];
            id<MTLBuffer> masks=[device newBufferWithLength:size_t(p.count)*p.rows*4 options:MTLResourceStorageModeShared];
            if(!a||!state||!pc||!table||!masks) throw std::runtime_error("buffer allocation");
            memset(state.contents,0,p.count*16);
            id<MTLCommandBuffer> command=[queue commandBuffer];
            id<MTLComputeCommandEncoder> encoder=[command computeCommandEncoder];
            if(!command||!encoder) throw std::runtime_error("command allocation");
            [encoder setBuffer:a offset:0 atIndex:0];
            [encoder setBuffer:state offset:0 atIndex:1];
            [encoder setBuffer:pc offset:0 atIndex:2];
            [encoder setBuffer:table offset:0 atIndex:3];
            [encoder setBuffer:masks offset:0 atIndex:4];
            [encoder setBytes:&p length:sizeof(p) atIndex:5];
            size_t local=(size_t(std::min(p.rows,4096u))*4+15)/16*16;
            id<MTLComputePipelineState> pivot_pipeline=pipelines[0];
            id<MTLComputePipelineState> local_pipeline=pipelines[FUSED?2:3];
            size_t local_panel=(size_t(2)*p.rows+size_t(8)*p.words)*4;
            local_panel=(local_panel+15)/16*16;
            if(p.rows<=4096 && local_panel+local_pipeline.staticThreadgroupMemoryLength<=device.maxThreadgroupMemoryLength) {
                pivot_pipeline=local_pipeline; local=local_panel;
            }
            if(local+pivot_pipeline.staticThreadgroupMemoryLength>device.maxThreadgroupMemoryLength)
                throw std::runtime_error("pivot column cache exceeds threadgroup memory");
            [encoder setThreadgroupMemoryLength:local atIndex:0];
            for(uint32_t panel=0;panel<(std::min(p.rows,p.cols)+7)/8;++panel) {
                for(int stage=0;stage<(FUSED?2:3);++stage) {
                    [encoder setComputePipelineState:stage?pipelines[stage]:pivot_pipeline];
                    if(!stage) [encoder dispatchThreadgroups:MTLSizeMake(1,p.count,1) threadsPerThreadgroup:MTLSizeMake(PIVOT_THREADS,1,1)];
                    else [encoder dispatchThreads:MTLSizeMake((!FUSED && stage==1?256:p.rows)*p.words,p.count,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];
                    [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
                }
            }
            [encoder endEncoding];[command commit];[command waitUntilCompleted];
            if(command.status!=MTLCommandBufferStatusCompleted) throw std::runtime_error(command.error.description.UTF8String);
            result.gpu_ms=1000*(command.GPUEndTime-command.GPUStartTime);
            memcpy(result.data.data(),a.contents,input.size()*8);
            for(uint32_t b=0;b<p.count;++b) result.ranks[b]=((uint32_t*)state.contents)[4*b];
        }
    }
    result.ms=elapsed(start); return result;
}
static void same(const Result& a,const Result& b) {
    if(a.data!=b.data || a.ranks!=b.ranks) throw std::runtime_error("exact rank/RREF mismatch");
}
static Case random_case(uint32_t r,uint32_t c,std::mt19937_64& rng) {
    Case out={"random-"+std::to_string(r)+"-"+std::to_string(c),r,c,{}};
    uint32_t stride=(c+63)/64;out.data.resize(size_t(r)*stride);
    for(auto& w:out.data) w=rng();
    if(c%64) for(uint32_t i=0;i<r;++i) out.data[size_t(i)*stride+stride-1]&=(UINT64_C(1)<<(c%64))-1;
    return out;
}
int main(int argc,char**argv) {
  @autoreleasepool { try {
    if(argc<2 || argc>3) throw std::runtime_error("usage: tiled-rref shader.metal [matrices.json]");
    auto setup=Clock::now();
    id<MTLDevice> device=MTLCreateSystemDefaultDevice();NSError* error=nil;
    if(!device) throw std::runtime_error("no Metal device");
    NSString* src=[NSString stringWithContentsOfFile:@(argv[1]) encoding:NSUTF8StringEncoding error:&error];
    if(!src) throw std::runtime_error(error.description.UTF8String);
    id<MTLLibrary> library=[device newLibraryWithSource:src options:nil error:&error];
    if(!library) throw std::runtime_error(error.description.UTF8String);
    NSMutableArray* pipeline=[NSMutableArray array];
    for(NSString* name in (FUSED?@[@"panel_cached",@"eliminate_direct",@"panel_local"]:@[@"panel_cached",@"table_rows",@"eliminate",@"panel_local"])) {
        id<MTLComputePipelineState> p=[device newComputePipelineStateWithFunction:[library newFunctionWithName:name] error:&error];
        if(!p || p.maxTotalThreadsPerThreadgroup<256) throw std::runtime_error(error?error.description.UTF8String:"pipeline unsupported");
        [pipeline addObject:p];
    }
    id<MTLCommandQueue> queue=[device newCommandQueue];
    double setup_ms=elapsed(setup);
    std::mt19937_64 rng(2026092402);
    size_t checked=0;
    // Exhaustive tiny matrices and adversarial zero/duplicate/last-bit cases.
    auto check=[&](const Case& c) {
        Params p={c.rows,c.cols,2*((c.cols+63)/64),1};
        same(cpu(c.data,p),gpu(c.data,p,device,queue,pipeline));++checked;
    };
    for(auto shape:std::vector<std::pair<uint32_t,uint32_t>>{{0,0},{0,65},{3,0},{1,1},{2,2},{2,3},{3,3}}) {
        for(uint64_t bits=0;bits<(UINT64_C(1)<<(shape.first*shape.second));++bits) {
            Case c={"exhaustive",shape.first,shape.second,{}};
            if(c.cols) for(uint32_t i=0;i<c.rows;++i) c.data.push_back((bits>>(i*c.cols))&((UINT64_C(1)<<c.cols)-1));
            check(c);
        }
    }
    for(uint32_t cols:{7u,8u,9u,31u,32u,33u,63u,64u,65u,127u,128u,129u,255u,256u,257u}) {
        for(uint32_t rows:{1u,7u,8u,9u,17u,65u}) check(random_case(rows,cols,rng));
        Case c=random_case(19,cols,rng);std::fill(c.data.begin(),c.data.end(),0);check(c);
        uint32_t stride=(cols+63)/64;
        for(uint32_t r=0;r<c.rows;++r) c.data[r*stride+(cols-1)/64]=UINT64_C(1)<<((cols-1)%64);
        check(c);
    }
    std::mt19937_64 controls_rng(2026092406);
    check(random_case(4097,65,controls_rng)); // uncached pivot fallback
    check(random_case(8192,33,controls_rng)); // row allocation bound
    Case gaps={"gapped-panels",17,257,std::vector<uint64_t>(17*5,0)};
    for(uint32_t row=0;row<17;++row) {
        uint32_t col=(row%9)*17;
        gaps.data[row*5+col/64]=UINT64_C(1)<<(col%64);
    }
    check(gaps);
    std::vector<Case> cases;
    // Independent per-matrix state must also work when ranks and pivot gaps
    // differ inside one batch, including already-completed zero matrices.
    for(uint32_t cols:{33u,65u,129u,4096u}) {
        Params p={33,cols,2*((cols+63)/64),17};
        std::vector<uint64_t> input;
        for(uint32_t batch=0;batch<p.count;++batch) {
            Case c=random_case(p.rows,p.cols,rng);
            uint32_t stride=(cols+63)/64;
            if(batch%3==0) std::fill(c.data.begin(),c.data.end(),0);
            else if(batch%3==1) {
                std::fill(c.data.begin(),c.data.end(),0);
                for(uint32_t row=0;row<p.rows;++row)
                    c.data[row*stride+(cols-1)/64]=UINT64_C(1)<<((cols-1)%64);
            } else {
                for(uint32_t row=0;row<p.rows;++row) c.data[row*stride]&=~UINT64_C(0xffff);
            }
            input.insert(input.end(),c.data.begin(),c.data.end());
        }
        same(cpu(input,p),gpu(input,p,device,queue,pipeline));checked+=p.count;
    }
    for(auto shape:std::vector<std::pair<uint32_t,uint32_t>>{{256,1024},{512,1024},{1024,2048},{2048,4096}})
        cases.push_back(random_case(shape.first,shape.second,rng));
    if(argc==3) {
        NSData* data=[NSData dataWithContentsOfFile:@(argv[2])];
        NSArray* inputs=[NSJSONSerialization JSONObjectWithData:data options:0 error:&error];
        if(!inputs) throw std::runtime_error("invalid matrix JSON");
        for(NSDictionary* d in inputs) {
            Case c={[d[@"name"] UTF8String],[d[@"rows"] unsignedIntValue],[d[@"cols"] unsignedIntValue],{}};
            for(NSString* word in d[@"words_hex"]) c.data.push_back(std::stoull(word.UTF8String,nullptr,16));
            if(c.data.size()!=size_t(c.rows)*((c.cols+63)/64)) throw std::runtime_error("invalid matrix shape");
            cases.push_back(std::move(c));
        }
    }
    NSMutableArray* reports=[NSMutableArray array];
    for(const Case& c:cases) for(uint32_t batch:{1u}) {
        Params p={c.rows,c.cols,2*((c.cols+63)/64),batch};
        // Each named frozen matrix is timed exactly as supplied. In particular,
        // a seed label must never be paired with another seed's matrix.
        const std::vector<uint64_t>& input=c.data;
        std::vector<double> cpu_ms,gpu_ms,kernel_ms;NSMutableArray* samples=[NSMutableArray array];
        for(int rep=0;rep<10;++rep) {
            Result a,b;
            if(rep%2) {b=gpu(input,p,device,queue,pipeline);a=cpu(input,p);}
            else {a=cpu(input,p);b=gpu(input,p,device,queue,pipeline);}
            same(a,b);checked+=batch;
            if(rep) {cpu_ms.push_back(a.ms);gpu_ms.push_back(b.ms);kernel_ms.push_back(b.gpu_ms);}
            [samples addObject:@{@"warmup":@(rep==0),@"cpu_ms":@(a.ms),@"gpu_wall_ms":@(b.ms),@"gpu_kernel_ms":@(b.gpu_ms)}];
        }
        [reports addObject:@{@"name":@(c.name.c_str()),@"rows":@(p.rows),@"cols":@(p.cols),@"batch":@(batch),
            @"cpu_ms":@(median(cpu_ms)),@"gpu_wall_ms":@(median(gpu_ms)),@"gpu_kernel_ms":@(median(kernel_ms)),
            @"speedup":@(median(cpu_ms)/median(gpu_ms)),@"samples":samples}];
        std::cerr<<c.name<<" batch "<<batch<<" CPU "<<median(cpu_ms)<<" GPU "<<median(gpu_ms)<<" ms\n";
    }
    NSDictionary* report=@{@"local_panel_cache":@YES,@"fused":@(FUSED),@"pivot_threads":@(PIVOT_THREADS),@"m4ri_k":@(M4RI_K),@"scope":@"Single-matrix exact GF(2) rank/RREF screen; no complete polynomial query or IC speedup claim",
        @"timing":@"All per-call allocations, copies, dispatch, synchronization, rank/output extraction, buffer destruction included; pipeline initialization separate; correctness comparison outside timing",
        @"real_workload_reuse":@"One exact named matrix per timed invocation; repetitions are diagnostics, not new target solves",
        @"device":device.name,@"initialization_ms":@(setup_ms),@"seed":@2026092402,@"checked_matrices":@(checked),@"exact_rref_and_rank":@YES,@"cells":reports};
    NSData* json=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:&error];
    std::cout.write((const char*)json.bytes,json.length);std::cout<<'\n';
    return 0;
  } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;} }
}
