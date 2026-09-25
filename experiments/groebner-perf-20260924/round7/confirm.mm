// Interleave all three arms in one process with exact frozen input parity.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <m4ri/m4ri.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstring>
#include <iostream>
#include <random>
#include <stdexcept>
#include <vector>
#include <pthread/qos.h>
#include <time.h>

namespace baseline {
#define main unused_screen_main
#include "../round6/fused_rref.mm"
#undef main
}
namespace revised {
#define main unused_screen_main
#include "local_rref.mm"
#undef main
}

static double thread_ms() {
    timespec t;
    if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t)) throw std::runtime_error("thread CPU clock failed");
    return 1000.0*t.tv_sec+t.tv_nsec/1e6;
}

static NSArray* pipelines(id<MTLDevice> device,const char* path,bool local) {
    NSError* error=nil;
    NSString* src=[NSString stringWithContentsOfFile:@(path) encoding:NSUTF8StringEncoding error:&error];
    if(!src) throw std::runtime_error(error.description.UTF8String);
    id<MTLLibrary> lib=[device newLibraryWithSource:src options:nil error:&error];
    if(!lib) throw std::runtime_error(error.description.UTF8String);
    NSMutableArray* out=[NSMutableArray array];
    NSArray* names=local?@[@"panel_cached",@"table_rows",@"eliminate",@"panel_local",@"table_vec",@"eliminate_vec"]:
                         @[@"panel_cached",@"table_rows",@"eliminate"];
    for(NSString* name in names) {
        id<MTLComputePipelineState> pipeline=[device newComputePipelineStateWithFunction:[lib newFunctionWithName:name] error:&error];
        if(!pipeline || pipeline.maxTotalThreadsPerThreadgroup<256)
            throw std::runtime_error(error?error.description.UTF8String:"unsupported threadgroup size");
        [out addObject:pipeline];
    }
    return out;
}

int main(int argc,char**argv) {
 @autoreleasepool { try {
    if(argc!=4) throw std::runtime_error("usage: confirm revised.metal matrices.json baseline.metal");
    int qos=pthread_set_qos_class_self_np(QOS_CLASS_USER_INITIATED,0);
    if(qos) throw std::runtime_error("cannot establish declared CPU QoS");
    auto setup=baseline::Clock::now();
    id<MTLDevice> device=MTLCreateSystemDefaultDevice();
    if(!device) throw std::runtime_error("no Metal device");
    NSArray* old_pipe=pipelines(device,argv[3],false);
    NSArray* new_pipe=pipelines(device,argv[1],true);
    id<MTLCommandQueue> queue=[device newCommandQueue];
    if(!queue) throw std::runtime_error("queue allocation");
    double setup_ms=baseline::elapsed(setup);
    NSError* error=nil;
    NSData* raw=[NSData dataWithContentsOfFile:@(argv[2])];
    if(!raw) throw std::runtime_error("matrix file missing");
    NSArray* inputs=[NSJSONSerialization JSONObjectWithData:raw options:0 error:&error];
    if(!inputs || ![inputs isKindOfClass:[NSArray class]]) throw std::runtime_error("invalid matrix JSON");
    std::vector<baseline::Case> cases;
    for(NSDictionary* d in inputs) {
        baseline::Case c={[d[@"name"] UTF8String],[d[@"rows"] unsignedIntValue],[d[@"cols"] unsignedIntValue],{}};
        for(NSString* w in d[@"words_hex"])c.data.push_back(std::stoull(w.UTF8String,nullptr,16));
        if(c.data.size()!=size_t(c.rows)*((c.cols+63)/64)) throw std::runtime_error("matrix shape mismatch");
        cases.push_back(std::move(c));
    }
    // Additional independent matrices exercise different shapes and rank laws.
    std::mt19937_64 rng(2026092507);
    for(auto shape:std::vector<std::pair<uint32_t,uint32_t>>{{256,1024},{1536,3072},{2048,4096}})
        cases.push_back(baseline::random_case(shape.first,shape.second,rng));
    baseline::Case low=cases[0];low.name="captured-seed1-duplicate-row-control";
    uint32_t stride=(low.cols+63)/64;
    for(uint32_t row=low.rows/2;row<low.rows;++row)
        std::copy_n(low.data.data()+(row%(low.rows/2))*stride,stride,low.data.data()+row*stride);
    cases.push_back(std::move(low));
    NSMutableArray* reports=[NSMutableArray array];
    size_t checked=0;
    for(const auto& c:cases) {
        baseline::Params p={c.rows,c.cols,2*((c.cols+63)/64),1};
        revised::Params q={p.rows,p.cols,p.words,1};
        NSMutableArray* samples=[NSMutableArray array];
        for(int rep=0;rep<16;++rep) {
            std::array<int,3> order={0,1,2};std::shuffle(order.begin(),order.end(),rng);
            baseline::Result cpu,old;revised::Result fresh;double cpu_thread=0;
            for(int arm:order) {
                if(arm==0) {double start=thread_ms();cpu=baseline::cpu(c.data,p);cpu_thread=thread_ms()-start;}
                else if(arm==1)old=baseline::gpu(c.data,p,device,queue,old_pipe);
                else fresh=revised::gpu(c.data,q,device,queue,new_pipe);
            }
            baseline::same(cpu,old);
            if(cpu.data!=fresh.data || cpu.ranks!=fresh.ranks) throw std::runtime_error("revised RREF/rank mismatch");
            checked+=2;
            [samples addObject:@{@"warmup":@(rep==0),@"order":@[@(order[0]),@(order[1]),@(order[2])],
                @"rank":@(cpu.ranks[0]),@"cpu_wall_ms":@(cpu.ms),@"cpu_thread_ms":@(cpu_thread),
                @"baseline_gpu_wall_ms":@(old.ms),@"baseline_gpu_device_ms":@(old.gpu_ms),
                @"revised_gpu_wall_ms":@(fresh.ms),@"revised_gpu_device_ms":@(fresh.gpu_ms)}];
        }
        [reports addObject:@{@"name":@(c.name.c_str()),@"rows":@(c.rows),@"cols":@(c.cols),@"target_count":@1,@"samples":samples}];
        std::cerr<<c.name<<" exact comparisons passed\n";
    }
    NSDictionary* report=@{@"scope":@"Single-matrix confirmation; not full polynomial-query or IC performance",
        @"cpu_qos":@"USER_INITIATED, relative priority 0",@"m4ri_k":@5,@"panel_width":@(PANEL_WIDTH),
        @"timing":@"Fresh per-call allocations, transfers, dispatch, synchronization and output extraction included; initialization and exact comparison outside; CPU thread time is a scheduling diagnostic, never substituted for wall time",
        @"device":device.name,@"initialization_ms":@(setup_ms),@"seed":@2026092507,
        @"checked_matrices":@(checked),@"exact_rref_and_rank":@YES,@"cells":reports};
    NSData* out=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:&error];
    if(!out) throw std::runtime_error("JSON serialization failed");
    std::cout.write((const char*)out.bytes,out.length);std::cout<<'\n';
    return 0;
 } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;} }
}
