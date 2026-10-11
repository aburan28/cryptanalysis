#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

static uint32_t gpu_input_roots(uint32_t n,
    const std::vector<std::vector<uint32_t>>& equations,
    const std::array<uint64_t,64>& low, std::vector<uint64_t>& roots);
// The generated packed decoder and core preserve independent validation and
// all basis checks. Only input-zero enumeration calls the function above.
#include "build/gpu_decoder.inc"

using Clock=std::chrono::steady_clock;
static double elapsed(Clock::time_point start) {
    return std::chrono::duration<double>(Clock::now()-start).count();
}
struct GPUStats {
    double prepare=0,encode=0,execute=0,device=0,extract=0,total=0,spin=0;
    uint64_t gather_words=0,polls=0;
    uint32_t calls=0,blocking_fallback=0;
};
struct Params { uint32_t equations,blocks,mask_lo,mask_hi; };
static thread_local std::string last_error;

struct Workspace {
    uint32_t n,equations,blocks,spin_us;
    id<MTLDevice> device;
    id<MTLCommandQueue> queue;
    id<MTLComputePipelineState> gather,intersect;
    id<MTLBuffer> coefficients,values,roots,params;
    std::mutex lock;
    Workspace(uint32_t variables,uint32_t count,const char* path,uint32_t polling)
      :n(variables),equations(count),blocks(((1u<<variables)+63)/64),spin_us(polling) {
      @autoreleasepool {
        uint32_t endian=1;
        if (*reinterpret_cast<uint8_t*>(&endian)!=1) throw std::runtime_error("little-endian host required");
        uint64_t bytes=uint64_t(equations)*blocks*8;
        if(bytes>128*1024*1024) throw std::invalid_argument("GPU coefficient capacity exceeds 128 MiB");
        device=MTLCreateSystemDefaultDevice();
        if(!device) throw std::runtime_error("no Metal device");
        NSError* error=nil;
        NSString* source=[NSString stringWithContentsOfFile:@(path) encoding:NSUTF8StringEncoding error:&error];
        if(!source) throw std::runtime_error(error.description.UTF8String);
        id<MTLLibrary> library=[device newLibraryWithSource:source options:nil error:&error];
        if(!library) throw std::runtime_error(error.description.UTF8String);
        gather=[device newComputePipelineStateWithFunction:[library newFunctionWithName:@"gather_truth"] error:&error];
        intersect=[device newComputePipelineStateWithFunction:[library newFunctionWithName:@"intersect_zeros"] error:&error];
        if(!gather||!intersect) throw std::runtime_error(error.description.UTF8String);
        queue=[device newCommandQueue];
        if(!queue) throw std::runtime_error("command queue allocation failed");
        auto allocate=[&](uint64_t length) {
            id<MTLBuffer> buffer=[device newBufferWithLength:length options:MTLResourceStorageModeShared];
            if(!buffer) throw std::runtime_error("Metal buffer allocation failed");
            return buffer;
        };
        coefficients=allocate(bytes);values=allocate(bytes);roots=allocate(uint64_t(blocks)*8);
        params=allocate(sizeof(Params));
        uint64_t mask=n<6 ? (uint64_t(1)<<(1u<<n))-1 : ~uint64_t(0);
        Params p={equations,blocks,uint32_t(mask),uint32_t(mask>>32)};
        memcpy(params.contents,&p,sizeof(p));
      }
    }
    uint32_t evaluate(const Rows& rows,const std::array<uint64_t,64>& low,
                      std::vector<uint64_t>& output,GPUStats& stats) {
      @autoreleasepool {
        auto start=Clock::now();
        if(rows.size()!=equations||output.size()!=blocks) throw std::invalid_argument("GPU ring mismatch");
        // All target-dependent coefficient words are reset. Both output kernels
        // overwrite every element of their active buffers before it is read.
        memset(coefficients.contents,0,coefficients.length);
        auto* data=static_cast<uint64_t*>(coefficients.contents);
        for(uint32_t row=0;row<equations;++row)
            for(uint32_t mask:rows[row]) data[uint64_t(row)*blocks+(mask>>6)]^=low[mask&63];
        stats.prepare=elapsed(start);auto phase=Clock::now();
        id<MTLCommandBuffer> command=[queue commandBuffer];
        id<MTLComputeCommandEncoder> encoder=[command computeCommandEncoder];
        if(!command||!encoder) throw std::runtime_error("command allocation failed");
        [encoder setBuffer:coefficients offset:0 atIndex:0];
        [encoder setBuffer:values offset:0 atIndex:1];
        [encoder setBuffer:roots offset:0 atIndex:2];
        [encoder setBuffer:params offset:0 atIndex:3];
        [encoder setComputePipelineState:gather];
        [encoder dispatchThreads:MTLSizeMake(uint64_t(equations)*blocks,1,1)
              threadsPerThreadgroup:MTLSizeMake(std::min(NSUInteger(256),gather.maxTotalThreadsPerThreadgroup),1,1)];
        [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
        [encoder setComputePipelineState:intersect];
        [encoder dispatchThreads:MTLSizeMake(blocks,1,1)
              threadsPerThreadgroup:MTLSizeMake(std::min(NSUInteger(256),intersect.maxTotalThreadsPerThreadgroup),1,1)];
        [encoder endEncoding];stats.encode=elapsed(phase);phase=Clock::now();
        [command commit];
        if(spin_us) {
            auto spin_start=Clock::now();
            auto deadline=spin_start+std::chrono::microseconds(spin_us);
            while(command.status<MTLCommandBufferStatusCompleted && Clock::now()<deadline)
                ++stats.polls;
            stats.spin=elapsed(spin_start);
        }
        if(command.status<MTLCommandBufferStatusCompleted) {
            stats.blocking_fallback=1;
            [command waitUntilCompleted];
        }
        if(command.status!=MTLCommandBufferStatusCompleted)
            throw std::runtime_error(command.error.description.UTF8String);
        stats.execute=elapsed(phase);stats.device=command.GPUEndTime-command.GPUStartTime;
        phase=Clock::now();memcpy(output.data(),roots.contents,uint64_t(blocks)*8);
        uint32_t alive=0;
        for(auto bits:output) alive+=__builtin_popcountll(bits);
        stats.extract=elapsed(phase);stats.total=elapsed(start);stats.calls=1;
        stats.gather_words=equations;
        for(uint32_t i=6;i<n;++i) stats.gather_words*=3;
        return alive;
      }
    }
};
static thread_local Workspace* active_workspace=nullptr;
static thread_local GPUStats* active_stats=nullptr;
static uint32_t gpu_input_roots(uint32_t n,const Rows& equations,
    const std::array<uint64_t,64>& low,std::vector<uint64_t>& roots) {
    try {
        if(!active_workspace||!active_stats||n!=active_workspace->n)
            throw std::runtime_error("missing GPU certificate workspace");
        return active_workspace->evaluate(equations,low,roots,*active_stats);
    } catch(const std::exception& e) { last_error=e.what();throw; }
}
extern "C" {
const char* gpu_certificate_error() { return last_error.c_str(); }
uint32_t gpu_certificate_stats_size() { return sizeof(GPUStats); }
const char* gpu_certificate_device_name(void* handle) {
    return handle ? static_cast<Workspace*>(handle)->device.name.UTF8String : "";
}
void* gpu_certificate_create(uint32_t n,uint32_t equations,const char* shader,uint32_t spin_us) {
    try {
        last_error.clear();
        if(n<1||n>20||equations<1||equations>4096||!shader||spin_us>5000)
            throw std::invalid_argument("GPU dimensions");
        return new Workspace(n,equations,shader,spin_us);
    } catch(const std::exception& e) { last_error=e.what();return nullptr; }
}
void gpu_certificate_destroy(void* handle) { delete static_cast<Workspace*>(handle); }
int gpu_certificate_compute(void* handle,uint32_t n,uint32_t equations,
        const uint32_t* masks,const uint64_t* coefficients,uint32_t count,
        const uint32_t* basis,uint32_t size,const uint32_t* offsets,
        uint32_t rows,Certificate* out,GPUStats* stats) {
    if(out) *out={};
    if(stats) *stats={};
    last_error.clear();
    if(!handle||!out||!stats) return out ? out->code=6 : 6;
    auto* workspace=static_cast<Workspace*>(handle);
    std::lock_guard<std::mutex> lock(workspace->lock);
    if(workspace->n!=n||workspace->equations!=equations) return out->code=6;
    active_workspace=workspace;active_stats=stats;
    int code=packed_boolean_certificate(n,equations,masks,coefficients,count,basis,size,offsets,rows,out);
    active_workspace=nullptr;active_stats=nullptr;
    return code;
}
}
