// Native Metal device query and bounded lookup validation for pair-table files.
// No rho walk or full-size table allocation is performed by this executable.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <mach/mach.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

static void require(bool value, const char *message) {
    if (!value) throw std::runtime_error(message);
}
static void output(NSDictionary *value) {
    NSError *error = nil;
    NSData *data = [NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:&error];
    require(data != nil, "cannot encode report");
    fwrite(data.bytes, 1, data.length, stdout); puts("");
}
static NSDictionary *deviceInfo(id<MTLDevice> device, NSUInteger index) {
    return @{@"index":@(index), @"name":device.name, @"registryID":@(device.registryID),
        @"unifiedMemory":@(device.hasUnifiedMemory),
        @"recommendedWorkingSetBytes":@(device.recommendedMaxWorkingSetSize),
        @"currentProcessMetalBytes":@(device.currentAllocatedSize),
        @"maxBufferBytes":@(device.maxBufferLength),
        @"argumentBuffersTier":@(device.argumentBuffersSupport)};
}
static NSDictionary *hostMemory() {
    vm_statistics64_data_t vm{};
    mach_msg_type_number_t count = HOST_VM_INFO64_COUNT;
    kern_return_t status = host_statistics64(mach_host_self(), HOST_VM_INFO64, (host_info64_t)&vm, &count);
    vm_size_t page = 0; host_page_size(mach_host_self(), &page);
    return @{@"physicalMemoryBytes":@([NSProcessInfo processInfo].physicalMemory),
        @"hostMemoryQuerySucceeded":@(status == KERN_SUCCESS),
        @"freeHostPagesBytes":@(uint64_t(vm.free_count) * page),
        @"inactiveHostPagesBytes":@(uint64_t(vm.inactive_count) * page),
        @"wiredHostPagesBytes":@(uint64_t(vm.wire_count) * page)};
}
static id<MTLDevice> selectedDevice(NSArray<id<MTLDevice>> *devices, const char *selector, NSUInteger *index) {
    if (!selector) {
        id<MTLDevice> preferred = MTLCreateSystemDefaultDevice();
        if (!preferred) return nil;
        for (NSUInteger i = 0; i < devices.count; ++i)
            if (devices[i].registryID == preferred.registryID) { *index = i; return devices[i]; }
        return nil;
    }
    char *end = nullptr;
    uint64_t value = strtoull(selector, &end, 0);
    require(end && end != selector && *end == 0, "Metal device must be an index or registry ID");
    if (value < devices.count) { *index = NSUInteger(value); return devices[*index]; }
    for (NSUInteger i = 0; i < devices.count; ++i)
        if (devices[i].registryID == value) { *index = i; return devices[i]; }
    return nil;
}
static void readAll(int fd, void *data, size_t bytes, uint64_t offset) {
    char *p = static_cast<char *>(data);
    while (bytes) {
        ssize_t n = pread(fd, p, bytes, off_t(offset));
        if (n < 0 && errno == EINTR) continue;
        require(n > 0, "short table read");
        p += n; bytes -= size_t(n); offset += uint64_t(n);
    }
}

struct Query { uint32_t u, v; };
struct Parameters { uint64_t baseEntry, entries; uint32_t queries, reserved; };
static_assert(sizeof(Parameters) == 24 && sizeof(Query) == 8, "unexpected host/shader layout");

static NSString *kernelSource = @R"METAL(
#include <metal_stdlib>
using namespace metal;
struct Query { uint u, v; };
struct Parameters { ulong baseEntry, entries; uint queries, reserved; };
kernel void pair_lookup(device const uint *table [[buffer(0)]],
                        device const Query *queries [[buffer(1)]],
                        device uint *results [[buffer(2)]],
                        device ulong *indices [[buffer(3)]],
                        constant Parameters &p [[buffer(4)]],
                        uint tid [[thread_position_in_grid]]) {
    if (tid >= p.queries) return;
    const ulong u = min(queries[tid].u, queries[tid].v);
    const ulong v = max(queries[tid].u, queries[tid].v);
    const ulong index = v*(v+1ul)/2ul+u;
    indices[tid] = index;
    if (index < p.baseEntry || index-p.baseEntry >= p.entries) {
        for (uint word=0; word<9; ++word) results[9*tid+word] = 0xdeadbeefu;
        return;
    }
    const ulong row = 9ul*(index-p.baseEntry);
    for (uint word=0; word<9; ++word) results[9*tid+word] = table[row+word];
}
)METAL";

static Query unrank(uint64_t index) {
    uint64_t v = uint64_t((std::sqrt(8.0*double(index)+1)-1)/2);
    while ((v+1)*(v+2)/2 <= index) ++v;
    while (v*(v+1)/2 > index) --v;
    return {uint32_t(index-v*(v+1)/2), uint32_t(v)};
}

static NSDictionary *smoke(id<MTLDevice> device, const char *path) {
    require(device.hasUnifiedMemory, "this shared-memory smoke test requires an Apple unified-memory GPU");
    const int fd = open(path, O_RDONLY);
    require(fd >= 0, "cannot open table");
    struct Close { int fd; ~Close() { close(fd); } } closeFile{fd};
    struct stat st{};
    require(fstat(fd, &st) == 0 && st.st_size > 0 && st.st_size % 36 == 0, "invalid table byte size");
    const uint64_t total = uint64_t(st.st_size)/36;
    require(total == 562348416ull || total == 2249360128ull, "expected a complete 128- or 256-branch table");
    NSError *error = nil;
    // Runtime compilation works without the offline `xcrun metal` utility.
    id<MTLLibrary> library = [device newLibraryWithSource:kernelSource options:nil error:&error];
    if (!library) throw std::runtime_error(error.localizedDescription.UTF8String ?: "Metal compilation failed");
    id<MTLFunction> function = [library newFunctionWithName:@"pair_lookup"];
    id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:function error:&error];
    if (!pipeline) throw std::runtime_error(error.localizedDescription.UTF8String ?: "pipeline creation failed");
    id<MTLCommandQueue> queue = [device newCommandQueue];
    require(queue != nil, "cannot create Metal queue");
    constexpr uint32_t N = 4096;
    const uint64_t windowEntries = std::min<uint64_t>(total, (4ull << 20)/36);
    const NSUInteger tableBytes = NSUInteger(windowEntries*36);
    require(tableBytes <= device.maxBufferLength, "window exceeds the device buffer limit");
    NSMutableArray *windows = [NSMutableArray array];
    for (uint64_t start : {0ull, total-windowEntries}) {
        @autoreleasepool {
            id<MTLBuffer> data = [device newBufferWithLength:tableBytes options:MTLResourceStorageModeShared];
            id<MTLBuffer> queryBuffer = [device newBufferWithLength:N*sizeof(Query) options:MTLResourceStorageModeShared];
            id<MTLBuffer> resultBuffer = [device newBufferWithLength:N*36 options:MTLResourceStorageModeShared];
            id<MTLBuffer> indexBuffer = [device newBufferWithLength:N*sizeof(uint64_t) options:MTLResourceStorageModeShared];
            require(data && queryBuffer && resultBuffer && indexBuffer, "Metal buffer allocation failed");
            readAll(fd, data.contents, tableBytes, start*36);
            Query *queries = static_cast<Query *>(queryBuffer.contents);
            std::vector<uint64_t> expected(N);
            uint64_t random = 0x20260921;
            for (uint32_t i = 0; i < N; ++i) {
                random ^= random << 13; random ^= random >> 7; random ^= random << 17;
                const uint64_t relative = i == 0 ? 0 : i == 1 ? windowEntries-1 : i == 2 ? 1 : random%windowEntries;
                expected[i] = start+relative;
                queries[i] = unrank(expected[i]);
                if (i & 1) std::swap(queries[i].u, queries[i].v);
            }
            memset(resultBuffer.contents, 0xa5, N*36);
            Parameters p{start, windowEntries, N, 0};
            id<MTLCommandBuffer> command = [queue commandBuffer];
            id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
            require(command && encoder, "cannot create Metal command");
            [encoder setComputePipelineState:pipeline];
            [encoder setBuffer:data offset:0 atIndex:0];
            [encoder setBuffer:queryBuffer offset:0 atIndex:1];
            [encoder setBuffer:resultBuffer offset:0 atIndex:2];
            [encoder setBuffer:indexBuffer offset:0 atIndex:3];
            [encoder setBytes:&p length:sizeof(p) atIndex:4];
            const NSUInteger width = std::min<NSUInteger>(256, pipeline.maxTotalThreadsPerThreadgroup);
            [encoder dispatchThreads:MTLSizeMake(N,1,1) threadsPerThreadgroup:MTLSizeMake(width,1,1)];
            [encoder endEncoding]; [command commit]; [command waitUntilCompleted];
            if (command.status != MTLCommandBufferStatusCompleted)
                throw std::runtime_error(command.error.localizedDescription.UTF8String ?: "Metal command failed");
            const uint32_t *rows = static_cast<const uint32_t *>(data.contents);
            const uint32_t *result = static_cast<const uint32_t *>(resultBuffer.contents);
            const uint64_t *indices = static_cast<const uint64_t *>(indexBuffer.contents);
            uint32_t infinities = 0;
            for (uint32_t i = 0; i < N; ++i) {
                require(indices[i] == expected[i], "GPU triangular index mismatch");
                require(memcmp(result+9*i, rows+9*(expected[i]-start), 36) == 0, "GPU pair record mismatch");
                infinities += result[9*i+8] == 0x80000000u;
            }
            [windows addObject:@{@"baseEntry":@(start), @"bytes":@(tableBytes), @"queriesChecked":@(N),
                @"infinityRecords":@(infinities), @"gpuCommandSeconds":@(command.GPUEndTime-command.GPUStartTime)}];
        }
    }
    return @{@"status":@"passed", @"kind":@"bounded-metal-table-lookup", @"tableBytes":@(uint64_t(st.st_size)),
        @"tableEntries":@(total), @"gpuQueriesChecked":@(2*N), @"windows":windows,
        @"fullTableResident":@NO, @"rhoKernelExecuted":@NO,
        @"scope":@"64-bit indexing and nine-word record access only; no arithmetic or throughput claim"};
}

int main(int argc, char **argv) {
    @autoreleasepool {
        try {
            require(argc >= 2, "usage: metal-pair-table info [device] | smoke TABLE [device]");
            const std::string mode = argv[1];
            require(mode == "info" || mode == "smoke", "unknown command");
            require((mode == "info" && argc <= 3) || (mode == "smoke" && argc >= 3 && argc <= 4), "invalid arguments");
            NSArray<id<MTLDevice>> *devices = MTLCopyAllDevices();
            NSUInteger index = 0;
            const char *selector = argc == (mode == "info" ? 3 : 4) ? argv[argc-1] : nullptr;
            id<MTLDevice> device = selectedDevice(devices, selector, &index);
            if (!device) {
                output(@{@"status":@"unavailable", @"devicesVisible":@(devices.count), @"host":hostMemory(),
                    @"error":@"No selected Metal GPU is visible. Run natively on macOS outside a GPU-restricted sandbox."});
                return 1;
            }
            NSDictionary *result = mode == "info" ? @{@"status":@"ok", @"device":deviceInfo(device,index), @"host":hostMemory()}
                                                  : @{@"device":deviceInfo(device,index), @"result":smoke(device,argv[2])};
            output(result); return 0;
        } catch (const std::exception &error) {
            output(@{@"status":@"error", @"error":[NSString stringWithUTF8String:error.what()]}); return 2;
        }
    }
}
