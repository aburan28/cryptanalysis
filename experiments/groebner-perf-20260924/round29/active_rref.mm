// Opt-in single-matrix experiment. CPU dispatch in the solver is unchanged.
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
#include <unistd.h>
#include <mach-o/dyld.h>
#ifndef ACTIVE_THREADS
#define ACTIVE_THREADS 256
#endif
#ifndef ACTIVE_INDIRECT
#define ACTIVE_INDIRECT 1
#endif
static_assert(ACTIVE_THREADS==32 || ACTIVE_THREADS==64 || ACTIVE_THREADS==128 || ACTIVE_THREADS==256 || ACTIVE_THREADS==512 || ACTIVE_THREADS==1024,
              "active pivot threads must be 32, 64, 128, 256, 512 or 1024");
#define PANEL_WIDTH 16
namespace baseline {
#define main unused_screen_main
#include "../round7/local_rref.mm"
#undef main
}
using baseline::Case;
using baseline::Clock;
using baseline::Params;
using baseline::Result;

struct ActiveResult {
    Result result;
    std::vector<uint32_t> panel_histogram;
    bool local=false;
};
static ActiveResult active_gpu(const std::vector<uint64_t>& input, Params p,
    id<MTLDevice> device,id<MTLCommandQueue> queue,NSArray* pipelines,
    uint32_t width,size_t scratch_limit=32768) {
    auto start=Clock::now();
    if((width!=16 && width!=32) || p.rows>8192 || p.cols>8192 || p.count>256 ||
       p.words!=2*((p.cols+63)/64) || input.size()!=size_t(p.rows)*p.count*p.words/2)
        throw std::runtime_error("invalid matrix shape or panel width");
    if(p.cols%64) for(size_t row=0;row<size_t(p.rows)*p.count;++row)
        if(input[row*(p.words/2)+p.words/2-1]>>(p.cols%64))
            throw std::runtime_error("nonzero matrix padding");
    ActiveResult out;
    out.result.data.resize(input.size());out.result.ranks.resize(p.count);
    out.panel_histogram.resize(p.count*2);
    @autoreleasepool {
        if(p.rows && p.cols && p.count) {
            id<MTLBuffer> a=[device newBufferWithBytes:input.data() length:input.size()*8 options:MTLResourceStorageModeShared];
            id<MTLBuffer> state=[device newBufferWithLength:p.count*16 options:MTLResourceStorageModeShared];
            id<MTLBuffer> pc=[device newBufferWithLength:p.count*width*4 options:MTLResourceStorageModeShared];
            id<MTLBuffer> table=[device newBufferWithLength:size_t(p.count)*(width/8)*256*p.words*4 options:MTLResourceStorageModeShared];
            id<MTLBuffer> masks=[device newBufferWithLength:size_t(p.count)*p.rows*4 options:MTLResourceStorageModeShared];
            id<MTLBuffer> hist=[device newBufferWithLength:p.count*8 options:MTLResourceStorageModeShared];
            id<MTLBuffer> indirect=[device newBufferWithLength:24 options:MTLResourceStorageModeShared];
            if(!a||!state||!pc||!table||!masks||!hist||!indirect)throw std::runtime_error("buffer allocation failed");
            memset(state.contents,0,p.count*16);memset(hist.contents,0,p.count*8);
            id<MTLComputePipelineState> pivot=pipelines[0],cached=pipelines[1];
            size_t budget=std::min(scratch_limit,size_t(device.maxThreadgroupMemoryLength));
            size_t local=budget>pivot.staticThreadgroupMemoryLength?
                (budget-pivot.staticThreadgroupMemoryLength)/16*16:0;
            out.local=p.rows<=4096 && local>=size_t(2*p.rows+16*p.words)*4;
            if(!out.local) {
                pivot=cached;local=(size_t(std::min(p.rows,4096u))*4+15)/16*16;
            }
            if(local+pivot.staticThreadgroupMemoryLength>device.maxThreadgroupMemoryLength)
                throw std::runtime_error("insufficient pivot threadgroup memory");
            uint32_t capacity=uint32_t(local/4);
            bool vec=p.words%4==0;
            id<MTLCommandBuffer> command=[queue commandBuffer];
            id<MTLComputeCommandEncoder> encoder=[command computeCommandEncoder];
            if(!command||!encoder)throw std::runtime_error("command allocation failed");
            [encoder setBuffer:a offset:0 atIndex:0];[encoder setBuffer:state offset:0 atIndex:1];
            [encoder setBuffer:pc offset:0 atIndex:2];[encoder setBuffer:table offset:0 atIndex:3];
            [encoder setBuffer:masks offset:0 atIndex:4];[encoder setBytes:&p length:sizeof(p) atIndex:5];
            [encoder setBytes:&capacity length:sizeof(capacity) atIndex:6];[encoder setBuffer:hist offset:0 atIndex:7];
            [encoder setBuffer:indirect offset:0 atIndex:8];
            [encoder setThreadgroupMemoryLength:local atIndex:0];
            // Active panels have at least 16 pivots unless they finish the matrix.
            // Extra encoded dispatches are no-ops after rank/column exhaustion.
            uint32_t minimum=out.local?16:width;
            for(uint32_t panel=0;panel<(std::min(p.rows,p.cols)+minimum-1)/minimum;++panel) {
                for(uint32_t stage=0;stage<3;++stage) {
                    [encoder setComputePipelineState:stage?pipelines[(vec?4:2)+stage-1]:pivot];
                    if(!stage)[encoder dispatchThreadgroups:MTLSizeMake(1,p.count,1) threadsPerThreadgroup:MTLSizeMake(ACTIVE_THREADS,1,1)];
                    else if(ACTIVE_INDIRECT && out.local && p.count==1)
                        [encoder dispatchThreadgroupsWithIndirectBuffer:indirect indirectBufferOffset:(stage-1)*12 threadsPerThreadgroup:MTLSizeMake(256,1,1)];
                    else [encoder dispatchThreads:MTLSizeMake((stage==1?(width/8)*256:p.rows)*(p.words/(vec?4:1)),p.count,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];
                    [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
                }
            }
            [encoder endEncoding];[command commit];[command waitUntilCompleted];
            if(command.status!=MTLCommandBufferStatusCompleted)
                throw std::runtime_error(command.error.description.UTF8String);
            out.result.gpu_ms=1000*(command.GPUEndTime-command.GPUStartTime);
            memcpy(out.result.data.data(),a.contents,input.size()*8);
            memcpy(out.panel_histogram.data(),hist.contents,p.count*8);
            for(uint32_t b=0;b<p.count;++b)out.result.ranks[b]=((uint32_t*)state.contents)[b*4];
        }
    }
    out.result.ms=baseline::elapsed(start);return out;
}

static NSArray* compile_pipelines(id<MTLDevice> device,const char* old_path,
                                  const char* active_path,uint32_t width) {
    NSError* error=nil;
    NSString* old=[NSString stringWithContentsOfFile:@(old_path) encoding:NSUTF8StringEncoding error:&error];
    if(!old)throw std::runtime_error(error.description.UTF8String);
    NSString* src=[NSString stringWithFormat:@"#define PANEL_WIDTH %u\n#define PIVOT_THREADS %u\n",width,active_path?ACTIVE_THREADS:256];
    src=[src stringByAppendingString:old];
    if(active_path) {
        NSString* active=[NSString stringWithContentsOfFile:@(active_path) encoding:NSUTF8StringEncoding error:&error];
        if(!active)throw std::runtime_error(error.description.UTF8String);
        src=[src stringByAppendingFormat:@"\n%@",active];
    }
    id<MTLLibrary> library=[device newLibraryWithSource:src options:nil error:&error];
    if(!library)throw std::runtime_error(error.description.UTF8String);
    NSArray* names=active_path?@[@"panel_active",@"panel_cached",@"table_active",@"eliminate_active",@"table_active_vec",@"eliminate_active_vec"]:
        @[@"panel_cached",@"table_rows",@"eliminate",@"panel_local",@"table_vec",@"eliminate_vec"];
    NSMutableArray* out=[NSMutableArray array];
    for(NSString* name in names) {
        id<MTLComputePipelineState> p=[device newComputePipelineStateWithFunction:[library newFunctionWithName:name] error:&error];
        uint32_t required=active_path && [name hasPrefix:@"panel_"]?ACTIVE_THREADS:256;
        if(!p||p.maxTotalThreadsPerThreadgroup<required)
            throw std::runtime_error(error?error.description.UTF8String:"unsupported pipeline");
        [out addObject:p];
    }
    return out;
}
static void output(NSDictionary* report) {
    NSError* error=nil;
    NSData* data=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:&error];
    if(!data)throw std::runtime_error(error.description.UTF8String);
    std::cout.write((const char*)data.bytes,data.length);std::cout<<'\n';
}
static double thread_ms() {
    timespec t;
    if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t))throw std::runtime_error("thread clock failed");
    return 1000.0*t.tv_sec+t.tv_nsec/1e6;
}
static double load() {
    double values[3];if(getloadavg(values,3)!=3)throw std::runtime_error("load unavailable");
    return values[0];
}
static NSString* m4ri_path() {
    for(uint32_t i=0;i<_dyld_image_count();++i) {
        const char* name=_dyld_get_image_name(i);
        if(name && strstr(name,"libm4ri"))return @(name);
    }
    throw std::runtime_error("loaded M4RI image not identified");
}
static std::vector<Case> load_cases(const char* path) {
    NSError* error=nil;NSData* data=[NSData dataWithContentsOfFile:@(path)];
    if(!data)throw std::runtime_error("matrix file missing");
    NSArray* inputs=[NSJSONSerialization JSONObjectWithData:data options:0 error:&error];
    if(![inputs isKindOfClass:[NSArray class]])throw std::runtime_error("invalid matrix JSON");
    std::vector<Case> cases;
    for(NSDictionary* d in inputs) {
        Case c={[d[@"name"] UTF8String],[d[@"rows"] unsignedIntValue],[d[@"cols"] unsignedIntValue],{}};
        for(NSString* w in d[@"words_hex"])c.data.push_back(std::stoull(w.UTF8String,nullptr,16));
        if(c.data.size()!=size_t(c.rows)*((c.cols+63)/64))throw std::runtime_error("matrix shape mismatch");
        cases.push_back(std::move(c));
    }
    if(cases.empty())throw std::runtime_error("no captured matrices");
    return cases;
}

int main(int argc,char**argv) {
 @autoreleasepool {try {
    if(argc!=5)throw std::runtime_error("usage: active-rref round7.metal active.metal matrices.json correctness|measure");
    std::string mode=argv[4];
    if(mode!="correctness"&&mode!="measure")throw std::runtime_error("invalid mode");
    if(pthread_set_qos_class_self_np(QOS_CLASS_USER_INITIATED,0))throw std::runtime_error("CPU QoS failed");
    auto start=Clock::now();id<MTLDevice> device=MTLCreateSystemDefaultDevice();
    if(!device)throw std::runtime_error("no Metal device");
    NSArray* old=compile_pipelines(device,argv[1],nullptr,16);
    NSArray* narrow=compile_pipelines(device,argv[1],argv[2],16);
    NSArray* wide=compile_pipelines(device,argv[1],argv[2],32);
    id<MTLCommandQueue> queue=[device newCommandQueue];
    if(!queue)throw std::runtime_error("queue allocation failed");
    double setup=baseline::elapsed(start);
    size_t checked=0,local_runs=0,fallback_runs=0,wide_panels=0;
    auto check=[&](const Case& c,uint32_t count=1) {
        Params p={c.rows,c.cols,2*((c.cols+63)/64),count};
        auto ref=baseline::cpu(c.data,p);
        for(uint32_t width:{16u,32u})for(size_t budget:{size_t(32768),size_t(0)}) {
            auto got=active_gpu(c.data,p,device,queue,width==16?narrow:wide,width,budget);
            baseline::same(ref,got.result);checked+=count;
            (got.local?local_runs:fallback_runs)++;
            for(uint32_t b=0;b<count;++b)wide_panels+=got.panel_histogram[2*b+1];
        }
    };
    auto cases=load_cases(argv[3]);
    if(mode=="correctness") {
        std::mt19937_64 rng(2026092929);
        for(auto shape:std::vector<std::pair<uint32_t,uint32_t>>{{0,0},{0,65},{3,0},{1,1},{2,2},{2,3},{3,3}}) {
            for(uint64_t bits=0;bits<(UINT64_C(1)<<(shape.first*shape.second));++bits) {
                Case c={"exhaustive",shape.first,shape.second,{}};
                if(c.cols)for(uint32_t r=0;r<c.rows;++r)c.data.push_back((bits>>(r*c.cols))&((UINT64_C(1)<<c.cols)-1));
                check(c);
            }
        }
        for(uint32_t cols:{7u,15u,16u,17u,31u,32u,33u,63u,64u,65u,127u,128u,129u,255u,256u,257u}) {
            for(uint32_t rows:{1u,15u,16u,17u,31u,32u,33u,65u})check(baseline::random_case(rows,cols,rng));
            Case zero={"zero",67,cols,std::vector<uint64_t>(67*((cols+63)/64),0)};check(zero);
            for(uint32_t row=0;row<zero.rows;++row)zero.data[row*((cols+63)/64)+(cols-1)/64]=UINT64_C(1)<<((cols-1)%64);
            check(zero);
        }
        for(auto shape:std::vector<std::pair<uint32_t,uint32_t>>{{4096,4096},{4097,65},{8192,33},{65,8192}})
            check(baseline::random_case(shape.first,shape.second,rng));
        Case gaps={"gapped-panels",79,4097,std::vector<uint64_t>(79*65,0)};
        for(uint32_t row=0;row<79;++row) {
            uint32_t col=(row%71)*53;gaps.data[row*65+col/64]=UINT64_C(1)<<(col%64);
            gaps.data[row*65+64]=1;
        }
        check(gaps);
        for(uint32_t cols:{33u,65u,129u,4096u}) {
            Case batch={"unequal-ranks",65,cols,{}};
            for(uint32_t b=0;b<7;++b) {
                auto c=baseline::random_case(65,cols,rng);uint32_t stride=(cols+63)/64;
                if(b%3==0)std::fill(c.data.begin(),c.data.end(),0);
                else if(b%3==1)for(uint32_t r=0;r<65;++r)c.data[r*stride]&=~UINT64_C(0xffffffff);
                batch.data.insert(batch.data.end(),c.data.begin(),c.data.end());
            }
            check(batch,7);
        }
        for(const auto& c:cases)check(c);
        // Reject shape/padding corruption before allocating or launching.
        size_t rejected=0;
        for(auto p:std::vector<Params>{{1,1,2,1},{8193,1,2,1},{1,1,4,1}}) {
            try{active_gpu({2},p,device,queue,wide,32);}
            catch(const std::runtime_error&){++rejected;}
        }
        if(rejected!=3 || !local_runs || !fallback_runs || !wide_panels)
            throw std::runtime_error("correctness coverage incomplete");
        output(@{@"schema":@"active-rref-correctness/1",@"device":device.name,@"m4ri_library":m4ri_path(),
            @"checked_matrices":@(checked),@"exact_rank_and_rref":@YES,@"local_runs":@(local_runs),
            @"fallback_runs":@(fallback_runs),@"wide_panels":@(wide_panels),@"invalid_inputs_rejected":@(rejected),
            @"timing_eligible":@NO,@"pivot_threads":@ACTIVE_THREADS,@"indirect_dispatch":@(bool(ACTIVE_INDIRECT)),@"seed":@2026092929});return 0;
    }
    std::mt19937_64 rng(2026092507);
    for(auto shape:std::vector<std::pair<uint32_t,uint32_t>>{{256,1024},{1536,3072},{2048,4096}})
        cases.push_back(baseline::random_case(shape.first,shape.second,rng));
    Case low=cases[0];low.name="captured-seed1-duplicate-row-control";
    uint32_t stride=(low.cols+63)/64;
    for(uint32_t row=low.rows/2;row<low.rows;++row)
        std::copy_n(low.data.data()+(row%(low.rows/2))*stride,stride,low.data.data()+row*stride);
    cases.push_back(std::move(low));
    long cpus=sysconf(_SC_NPROCESSORS_ONLN);double initial=load();
    if(cpus<=0 || initial>cpus)throw std::runtime_error("initial load admission rejected");
    NSMutableArray* cells=[NSMutableArray array];
    for(const auto& c:cases) {
        Params p={c.rows,c.cols,2*((c.cols+63)/64),1};NSMutableArray* samples=[NSMutableArray array];
        for(int rep=0;rep<32;++rep) {
            double group_load=load();if(group_load>cpus)throw std::runtime_error("group load admission rejected");
            std::array<int,4> order={0,1,2,3};std::shuffle(order.begin(),order.end(),rng);
            Result cpu,previous;ActiveResult a,b;double cpu_thread=0;
            for(int arm:order) {
                if(arm==0){double t=thread_ms();cpu=baseline::cpu(c.data,p);cpu_thread=thread_ms()-t;}
                else if(arm==1)previous=baseline::gpu(c.data,p,device,queue,old);
                else if(arm==2)a=active_gpu(c.data,p,device,queue,narrow,16);
                else b=active_gpu(c.data,p,device,queue,wide,32);
            }
            baseline::same(cpu,previous);baseline::same(cpu,a.result);baseline::same(cpu,b.result);checked+=3;
            [samples addObject:@{@"warmup":@(rep==0),@"order":@[@(order[0]),@(order[1]),@(order[2]),@(order[3])],
                @"load1":@(group_load),@"rank":@(cpu.ranks[0]),@"cpu_wall_ms":@(cpu.ms),@"cpu_thread_ms":@(cpu_thread),
                @"previous_wall_ms":@(previous.ms),@"previous_device_ms":@(previous.gpu_ms),
                @"active16_wall_ms":@(a.result.ms),@"active16_device_ms":@(a.result.gpu_ms),
                @"active32_wall_ms":@(b.result.ms),@"active32_device_ms":@(b.result.gpu_ms),
                @"active16_local":@(a.local),@"active32_local":@(b.local),
                @"active32_panels16":@(b.panel_histogram[0]),@"active32_panels32":@(b.panel_histogram[1])}];
        }
        [cells addObject:@{@"name":@(c.name.c_str()),@"rows":@(c.rows),@"cols":@(c.cols),@"matrix_count":@1,@"samples":samples}];
        std::cerr<<c.name<<" exact comparisons passed\n";
    }
    double final_load=load();if(final_load>cpus)throw std::runtime_error("final load admission rejected");
    output(@{@"schema":@"active-rref-measurement/1",@"scope":@"single-matrix RREF only; no full polynomial query or IC claim",
        @"device":device.name,@"m4ri_library":m4ri_path(),@"logical_cpus":@(cpus),@"load_initial":@(initial),@"load_final":@(final_load),
        @"initialization_ms":@(setup),@"checked_matrices":@(checked),@"exact_rank_and_rref":@YES,@"timing_eligible":@YES,
        @"seed":@2026092507,@"cpu_qos":@"USER_INITIATED",@"m4ri_k":@5,@"pivot_threads":@ACTIVE_THREADS,@"indirect_dispatch":@(bool(ACTIVE_INDIRECT)),
        @"timing":@"fresh allocations, copies, dispatch, synchronization, output extraction and buffer destruction included; setup, input loading and exact comparison excluded",
        @"cells":cells});return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
}
