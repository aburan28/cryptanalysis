// Fixed-capacity reusable Metal GF(2) RREF, with fresh numerical state per call.
// The shader is the independently qualified round-seven sixteen-pivot kernel.
#pragma once
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

namespace reusable_rref {
using Clock=std::chrono::steady_clock;
inline double elapsed(Clock::time_point t) {
    return std::chrono::duration<double,std::milli>(Clock::now()-t).count();
}
struct Params { uint32_t rows,cols,words,count; };
struct Stats {
    uint32_t rank=0;
    bool local_panel=false;
    double prepare_ms=0,encode_ms=0,execute_ms=0,device_ms=0,extract_ms=0,total_ms=0;
};

class Workspace {
    static constexpr uint32_t width=16;
    uint32_t capacity_,cols_,words_,max_local_rows_=0,commands_=0;
    size_t local_bytes_=0,global_bytes_=0;
    bool vectorized_;
    id<MTLDevice> device_;
    id<MTLCommandQueue> queue_;
    NSArray* pipelines_;
    id<MTLBuffer> a_,state_,pivots_,table_,masks_,params_;
    id<MTLIndirectCommandBuffer> local_commands_,global_commands_;
    std::mutex mutex_;

    id<MTLIndirectCommandBuffer> encode_plan(bool local) {
        MTLIndirectCommandBufferDescriptor* desc=[MTLIndirectCommandBufferDescriptor new];
        desc.commandTypes=MTLIndirectCommandTypeConcurrentDispatchThreads;
        desc.inheritPipelineState=NO;desc.inheritBuffers=NO;
        desc.maxKernelBufferBindCount=6;desc.maxKernelThreadgroupMemoryBindCount=1;
        id<MTLIndirectCommandBuffer> icb=[device_ newIndirectCommandBufferWithDescriptor:desc
                    maxCommandCount:commands_ options:MTLResourceStorageModeShared];
        if(!icb) throw std::runtime_error("indirect command buffer allocation failed");
        for(uint32_t index=0;index<commands_;++index) {
            uint32_t stage=index%3;
            id<MTLIndirectComputeCommand> command=[icb indirectComputeCommandAtIndex:index];
            [command setComputePipelineState:pipelines_[stage?(vectorized_?stage+3:stage):(local?3:0)]];
            [command setKernelBuffer:a_ offset:0 atIndex:0];
            [command setKernelBuffer:state_ offset:0 atIndex:1];
            [command setKernelBuffer:pivots_ offset:0 atIndex:2];
            [command setKernelBuffer:table_ offset:0 atIndex:3];
            [command setKernelBuffer:masks_ offset:0 atIndex:4];
            [command setKernelBuffer:params_ offset:0 atIndex:5];
            if(!stage) {
                [command setThreadgroupMemoryLength:local?local_bytes_:global_bytes_ atIndex:0];
                [command concurrentDispatchThreads:MTLSizeMake(256,1,1)
                             threadsPerThreadgroup:MTLSizeMake(256,1,1)];
            } else {
                uint32_t items=(stage==1?512:capacity_)*(words_/(vectorized_?4:1));
                [command concurrentDispatchThreads:MTLSizeMake(items,1,1)
                             threadsPerThreadgroup:MTLSizeMake(256,1,1)];
            }
            // Serialize dependent kernels and make their buffer writes visible.
            [command setBarrier];
        }
        return icb;
    }

public:
    double initialization_ms=0;
    Workspace(uint32_t capacity,uint32_t cols,const char* shader)
      :capacity_(capacity),cols_(cols),words_(2*((cols+63)/64)),vectorized_(words_%4==0) {
      @autoreleasepool {
        auto start=Clock::now();
        if(!capacity || capacity>8192 || !cols || cols>8192)
            throw std::invalid_argument("workspace bounds: rows and columns 1..8192");
        device_=MTLCreateSystemDefaultDevice();
        if(!device_) throw std::runtime_error("no Metal device");
        NSError* error=nil;
        NSString* source=[NSString stringWithContentsOfFile:@(shader) encoding:NSUTF8StringEncoding error:&error];
        if(!source) throw std::runtime_error(error.description.UTF8String);
        source=[@"#define PANEL_WIDTH 16\n#define PIVOT_THREADS 256\n" stringByAppendingString:source];
        id<MTLLibrary> library=[device_ newLibraryWithSource:source options:nil error:&error];
        if(!library) throw std::runtime_error(error.description.UTF8String);
        NSMutableArray* pipelines=[NSMutableArray array];
        for(NSString* name in @[@"panel_cached",@"table_rows",@"eliminate",@"panel_local",@"table_vec",@"eliminate_vec"]) {
            MTLComputePipelineDescriptor* desc=[MTLComputePipelineDescriptor new];
            desc.computeFunction=[library newFunctionWithName:name];desc.supportIndirectCommandBuffers=YES;
            id<MTLComputePipelineState> pipeline=[device_ newComputePipelineStateWithDescriptor:desc
                                              options:MTLPipelineOptionNone reflection:nil error:&error];
            if(!pipeline || pipeline.maxTotalThreadsPerThreadgroup<256)
                throw std::runtime_error(error?error.description.UTF8String:"pipeline unsupported");
            [pipelines addObject:pipeline];
        }
        pipelines_=pipelines;queue_=[device_ newCommandQueue];
        if(!queue_) throw std::runtime_error("queue allocation failed");
        auto allocate=[&](size_t bytes) {
            id<MTLBuffer> buffer=[device_ newBufferWithLength:bytes options:MTLResourceStorageModeShared];
            if(!buffer) throw std::runtime_error("workspace buffer allocation failed");
            return buffer;
        };
        a_=allocate(size_t(capacity_)*words_*4);state_=allocate(16);
        pivots_=allocate(width*4);table_=allocate(size_t(512)*words_*4);
        masks_=allocate(size_t(capacity_)*4);params_=allocate(sizeof(Params));
        id<MTLComputePipelineState> local=pipelines_[3],global=pipelines_[0];
        size_t available=device_.maxThreadgroupMemoryLength>=local.staticThreadgroupMemoryLength
            ? (device_.maxThreadgroupMemoryLength-local.staticThreadgroupMemoryLength)/16*16 : 0;
        size_t panel=size_t(width)*words_*4;
        if(available>=panel+8) {
            max_local_rows_=std::min({capacity_,4096u,uint32_t((available-panel)/8)});
            local_bytes_=(size_t(2)*max_local_rows_+size_t(width)*words_)*4;
            local_bytes_=(local_bytes_+15)/16*16;
        }
        global_bytes_=(size_t(std::min(capacity_,4096u))*4+15)/16*16;
        if(global_bytes_+global.staticThreadgroupMemoryLength>device_.maxThreadgroupMemoryLength)
            throw std::runtime_error("global panel column cache exceeds memory");
        commands_=3*((std::min(capacity_,cols_)+width-1)/width);
        global_commands_=encode_plan(false);
        if(max_local_rows_)local_commands_=encode_plan(true);
        initialization_ms=elapsed(start);
      }
    }
    Workspace(const Workspace&)=delete;
    Workspace& operator=(const Workspace&)=delete;
    uint32_t capacity()const{return capacity_;}
    uint32_t cols()const{return cols_;}

    template<class Load,class Store>
    Stats run(uint32_t rows,Load load,Store store,bool indirect=true) {
      auto start=Clock::now();std::lock_guard<std::mutex> lock(mutex_);
      @autoreleasepool {
        if(rows>capacity_)throw std::invalid_argument("matrix exceeds prepared row capacity");
        Stats result;
        if(!rows){result.total_ms=elapsed(start);return result;}
        // No target-dependent numerical value survives into the next call.
        for(id<MTLBuffer> buffer in @[a_,state_,pivots_,table_,masks_,params_])
            memset(buffer.contents,0,buffer.length);
        Params p={rows,cols_,words_,1};memcpy(params_.contents,&p,sizeof(p));
        load((uint64_t*)a_.contents);
        result.local_panel=rows<=max_local_rows_;
        result.prepare_ms=elapsed(start);auto phase=Clock::now();
        id<MTLCommandBuffer> command=[queue_ commandBuffer];
        id<MTLComputeCommandEncoder> encoder=[command computeCommandEncoder];
        if(!command||!encoder)throw std::runtime_error("command encoder allocation failed");
        uint32_t count=3*((std::min(rows,cols_)+width-1)/width);
        if(indirect) {
            for(id<MTLBuffer> buffer in @[a_,state_,pivots_,table_,masks_])
                [encoder useResource:buffer usage:MTLResourceUsageRead|MTLResourceUsageWrite];
            [encoder useResource:params_ usage:MTLResourceUsageRead];
            [encoder executeCommandsInBuffer:result.local_panel?local_commands_:global_commands_
                                   withRange:NSMakeRange(0,count)];
        } else {
            [encoder setBuffer:a_ offset:0 atIndex:0];[encoder setBuffer:state_ offset:0 atIndex:1];
            [encoder setBuffer:pivots_ offset:0 atIndex:2];[encoder setBuffer:table_ offset:0 atIndex:3];
            [encoder setBuffer:masks_ offset:0 atIndex:4];[encoder setBuffer:params_ offset:0 atIndex:5];
            for(uint32_t index=0;index<count;++index) {
                uint32_t stage=index%3;
                [encoder setComputePipelineState:pipelines_[stage?(vectorized_?stage+3:stage):(result.local_panel?3:0)]];
                if(!stage) {
                    [encoder setThreadgroupMemoryLength:result.local_panel?local_bytes_:global_bytes_ atIndex:0];
                    [encoder dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];
                } else {
                    uint32_t items=(stage==1?512:rows)*(words_/(vectorized_?4:1));
                    [encoder dispatchThreads:MTLSizeMake(items,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];
                }
                [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
            }
        }
        [encoder endEncoding];result.encode_ms=elapsed(phase);phase=Clock::now();
        [command commit];[command waitUntilCompleted];
        if(command.status!=MTLCommandBufferStatusCompleted)
            throw std::runtime_error(command.error.description.UTF8String);
        result.execute_ms=elapsed(phase);result.device_ms=1000*(command.GPUEndTime-command.GPUStartTime);
        phase=Clock::now();result.rank=((uint32_t*)state_.contents)[0];
        store((const uint64_t*)a_.contents);result.extract_ms=elapsed(phase);
        result.total_ms=elapsed(start);return result;
      }
    }
};
}
