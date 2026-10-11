// SPDX-License-Identifier: GPL-2.0-or-later
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include "binary_hardware_native.h"
#include <algorithm>
#include <cstring>
#include <memory>
#include <stdexcept>

struct MetalMap {
    id<MTLDevice> device;
    id<MTLCommandQueue> queue;
    id<MTLComputePipelineState> pipeline;
    id<MTLBuffer> table, input, output;
    uint32_t words, bytes;
    size_t capacity=0;
    std::string name;
};
static void require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
static std::string message(NSError* error) {
    return error ? error.localizedDescription.UTF8String : "unknown Metal error";
}
extern "C" void* bh_metal_create(const char* source,const uint32_t* table,
                                 uint32_t words,uint32_t bytes,uint32_t index) {
    @autoreleasepool { try {
        require(source && table && words>=1 && words<=8 && bytes>=1 && bytes<=32
                && (bytes+3)/4==words,"invalid Metal dimensions");
        auto context=std::make_unique<MetalMap>();
        NSArray<id<MTLDevice>>* devices=MTLCopyAllDevices();
        require(index<devices.count,"requested Metal device is unavailable");
        context->device=devices[index];
        context->name=context->device.name.UTF8String;
        context->words=words;context->bytes=bytes;
        context->queue=[context->device newCommandQueue];
        NSError* error=nil;
        id<MTLLibrary> library=[context->device newLibraryWithSource:
            [NSString stringWithUTF8String:source] options:nil error:&error];
        if (!library) throw std::runtime_error(message(error));
        id<MTLFunction> function=[library newFunctionWithName:@"bh_map"];
        context->pipeline=[context->device newComputePipelineStateWithFunction:function error:&error];
        if (!context->pipeline) throw std::runtime_error(message(error));
        context->table=[context->device newBufferWithBytes:table length:bytes*256ull*words*4
                                               options:MTLResourceStorageModeShared];
        require(context->queue && context->table,"Metal allocation failed");
        return context.release();
    } catch(const std::exception& e) {bh_set_error(e.what());return nullptr;} }
}
extern "C" void bh_metal_destroy(void* p) { delete static_cast<MetalMap*>(p); }
extern "C" const char* bh_metal_name(void* p) {
    return p ? static_cast<MetalMap*>(p)->name.c_str() : "unavailable";
}
extern "C" int bh_metal_apply(void* p,const uint32_t* input,uint32_t* output,
                              uint64_t count,double* gpu_seconds) {
    @autoreleasepool { try {
        require(p && gpu_seconds,"invalid Metal context");
        auto& c=*static_cast<MetalMap*>(p);
        *gpu_seconds=0;
        size_t table_size=c.bytes*256ull*c.words*4;
        require(count<=(512ull*1024*1024-table_size)/(8*c.words),"Metal working-set cap exceeded");
        if (!count) return 0;
        require(input && output,"null Metal data pointer");
        size_t size=count*c.words*4;
        if (size>c.capacity) {
            c.input=nil;c.output=nil;c.capacity=0;
            c.input=[c.device newBufferWithLength:size options:MTLResourceStorageModeShared];
            c.output=[c.device newBufferWithLength:size options:MTLResourceStorageModeShared];
            require(c.input && c.output,"Metal buffer allocation failed");
            c.capacity=size;
        }
        std::memcpy(c.input.contents,input,size);
        id<MTLCommandBuffer> command=[c.queue commandBuffer];
        id<MTLComputeCommandEncoder> encoder=[command computeCommandEncoder];
        require(command && encoder,"Metal command creation failed");
        [encoder setComputePipelineState:c.pipeline];
        [encoder setBuffer:c.table offset:0 atIndex:0];
        [encoder setBuffer:c.input offset:0 atIndex:1];
        [encoder setBuffer:c.output offset:0 atIndex:2];
        uint32_t args[3]={c.bytes,c.words,uint32_t(count)};
        [encoder setBytes:args length:sizeof(args) atIndex:3];
        NSUInteger width=std::min<NSUInteger>(256,c.pipeline.maxTotalThreadsPerThreadgroup);
        NSUInteger work=count*c.words;
        [encoder dispatchThreadgroups:MTLSizeMake((work+width-1)/width,1,1)
                  threadsPerThreadgroup:MTLSizeMake(width,1,1)];
        [encoder endEncoding];[command commit];[command waitUntilCompleted];
        if (command.status!=MTLCommandBufferStatusCompleted)
            throw std::runtime_error(message(command.error));
        if (command.GPUEndTime>=command.GPUStartTime)
            *gpu_seconds=command.GPUEndTime-command.GPUStartTime;
        std::memcpy(output,c.output.contents,size);
        return 0;
    } catch(const std::exception& e) {bh_set_error(e.what());return -1;} }
}
