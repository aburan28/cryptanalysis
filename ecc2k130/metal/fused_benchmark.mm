// Exact two-step Metal A/B: ordinary directions versus an h128 pair-sum lookup.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>

static const char shader[] =
#include "fused_benchmark_metal.inc"
;

struct State { uint32_t xy[10],history[3],mode; uint64_t seed,trailSteps,walkSteps,reseeds,trace,dpHash,dpCount; };
struct Result { uint32_t xy[10],history[3],first,second,pad; };
static_assert(sizeof(State)==112&&sizeof(Result)==64,"host/shader layout differs");

static void need(bool ok,const char *message){if(!ok)throw std::runtime_error(message);}
static NSData *readFile(NSString *root,NSString *name){
    NSData *value=[NSData dataWithContentsOfFile:[root stringByAppendingPathComponent:name]];
    need(value!=nil,"missing benchmark input");return value;
}
static void printJson(NSDictionary *value){
    NSData *data=[NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:nil];
    need(data!=nil,"cannot encode result");fwrite(data.bytes,1,data.length,stdout);puts("");
}
static id<MTLComputePipelineState> makePipeline(id<MTLDevice> device,id<MTLLibrary> library,NSString *name){
    NSError *error=nil;id<MTLFunction> function=[library newFunctionWithName:name];need(function!=nil,"missing benchmark kernel");
    id<MTLComputePipelineState> pipeline=[device newComputePipelineStateWithFunction:function error:&error];
    if(!pipeline)throw std::runtime_error(error.localizedDescription.UTF8String?:"cannot create benchmark pipeline");
    return pipeline;
}
static MTLSize groupSize(id<MTLComputePipelineState> pipeline){
    NSUInteger n=std::min<NSUInteger>(256,pipeline.maxTotalThreadsPerThreadgroup);
    if(n>=pipeline.threadExecutionWidth)n-=n%pipeline.threadExecutionWidth;
    return MTLSizeMake(std::max<NSUInteger>(1,n),1,1);
}
static double finish(id<MTLCommandBuffer> command){
    [command commit];[command waitUntilCompleted];
    if(command.status!=MTLCommandBufferStatusCompleted)
        throw std::runtime_error(command.error.localizedDescription.UTF8String?:"benchmark command failed");
    const double seconds=command.GPUEndTime-command.GPUStartTime;
    need(std::isfinite(seconds)&&seconds>0,"invalid benchmark GPU time");return seconds;
}
static double median(std::vector<double> values){
    std::sort(values.begin(),values.end());
    const size_t n=values.size();return n&1?values[n/2]:(values[n/2-1]+values[n/2])/2;
}
static NSDictionary *stats(const std::vector<double> &values){
    return @{@"medianSeconds":@(median(values)),
             @"minimumSeconds":@(*std::min_element(values.begin(),values.end())),
             @"maximumSeconds":@(*std::max_element(values.begin(),values.end())),
             @"samples":@(values.size())};
}

int main(int argc,char **argv){
    @autoreleasepool{try{
        need(argc==3,"usage: metal-fused-benchmark INPUT_DIRECTORY PAIRS_FILE");
        NSString *root=[NSString stringWithUTF8String:argv[1]],*pairPath=[NSString stringWithUTF8String:argv[2]];
        NSData *configData=readFile(root,@"fused-config.json");
        NSDictionary *config=[NSJSONSerialization JSONObjectWithData:configData options:0 error:nil];
        need([config isKindOfClass:[NSDictionary class]],"invalid fused configuration");
        const uint32_t count=[config[@"cases"] unsignedIntValue],repeats=[config[@"repeats"] unsignedIntValue];
        const uint32_t warmups=[config[@"warmups"] unsignedIntValue];
        const uint32_t inner=config[@"innerIterations"]?[config[@"innerIterations"] unsignedIntValue]:1;
        need(count>0&&count<=262144&&repeats>0&&repeats<=100&&warmups<=20&&inner>0&&inner<=1024,
             "invalid fused benchmark bounds");
        need([config[@"branches"] unsignedIntValue]==128,"fused benchmark requires h128");

        NSData *input=readFile(root,@"fused-input.bin"),*expected=readFile(root,@"fused-expected.bin");
        NSData *directions=readFile(root,@"directions.bin"),*constants=readFile(root,@"selector.bin");
        need(input.length==size_t(count)*sizeof(State)&&expected.length==size_t(count)*sizeof(Result),"bad benchmark vector size");
        need(directions.length==size_t(262)*128*36&&constants.length==13708,"bad benchmark table/selector size");
        const uint64_t pairBytes=[config[@"pairPayloadBytes"] unsignedLongLongValue];
        need(pairBytes==20244542976ull,"unexpected h128 pair payload size");
        NSError *mapError=nil;
        NSData *pairData=[NSData dataWithContentsOfFile:pairPath options:NSDataReadingMappedAlways error:&mapError];
        if(!pairData)throw std::runtime_error(mapError.localizedDescription.UTF8String?:"cannot map pair payload");
        need(pairData.length==pairBytes,"mapped pair payload size differs");

        id<MTLDevice> device=MTLCreateSystemDefaultDevice();
        if(!device){printJson(@{@"status":@"unavailable",@"error":@"No Metal GPU"});return 77;}
        need(device.hasUnifiedMemory,"benchmark requires unified-memory Metal");
        need(pairBytes<=device.maxBufferLength,"pair payload exceeds one Metal buffer");
        NSError *error=nil;
        id<MTLLibrary> library=[device newLibraryWithSource:[NSString stringWithUTF8String:shader] options:nil error:&error];
        if(!library)throw std::runtime_error(error.localizedDescription.UTF8String?:"benchmark shader compilation failed");
        auto baseline=makePipeline(device,library,@"fused_bench_baseline");
        auto selector=makePipeline(device,library,@"fused_bench_selector");
        auto pairFinish=makePipeline(device,library,@"fused_bench_pair_finish");
        id<MTLCommandQueue> queue=[device newCommandQueue];need(queue!=nil,"cannot create benchmark queue");
        auto make=[&](NSData *data){return [device newBufferWithBytes:data.bytes length:data.length options:MTLResourceStorageModeShared];};
        id<MTLBuffer> inputBuffer=make(input),dirs=make(directions),consts=make(constants);
        id<MTLBuffer> baselineOut=[device newBufferWithLength:expected.length options:MTLResourceStorageModeShared];
        id<MTLBuffer> selected=[device newBufferWithLength:expected.length options:MTLResourceStorageModeShared];
        id<MTLBuffer> fusedOut=[device newBufferWithLength:expected.length options:MTLResourceStorageModeShared];
        need(inputBuffer&&dirs&&consts&&baselineOut&&selected&&fusedOut,"small benchmark allocation failed");
        const uint64_t allocatedBeforePair=device.currentAllocatedSize;
        id<MTLBuffer> pairs=[device newBufferWithBytesNoCopy:(void *)pairData.bytes length:pairData.length
                                                     options:MTLResourceStorageModeShared deallocator:nil];
        need(pairs!=nil,"Metal rejected the mapped full pair payload");
        const uint64_t allocatedAfterPair=device.currentAllocatedSize;

        auto encodeBaseline=[&](){
            id<MTLCommandBuffer> command=[queue commandBuffer];auto encoder=[command computeCommandEncoder];
            [encoder setComputePipelineState:baseline];[encoder setBuffer:inputBuffer offset:0 atIndex:0];
            [encoder setBuffer:dirs offset:0 atIndex:1];[encoder setBuffer:consts offset:0 atIndex:2];
            [encoder setBuffer:baselineOut offset:0 atIndex:3];[encoder setBytes:&count length:4 atIndex:4];
            for(uint32_t i=0;i<inner;++i)
                [encoder dispatchThreads:MTLSizeMake(count,1,1) threadsPerThreadgroup:groupSize(baseline)];
            [encoder endEncoding];
            return finish(command);
        };
        auto encodeSelector=[&](){
            id<MTLCommandBuffer> command=[queue commandBuffer];auto encoder=[command computeCommandEncoder];
            [encoder setComputePipelineState:selector];[encoder setBuffer:inputBuffer offset:0 atIndex:0];
            [encoder setBuffer:dirs offset:0 atIndex:1];[encoder setBuffer:consts offset:0 atIndex:2];
            [encoder setBuffer:selected offset:0 atIndex:3];[encoder setBytes:&count length:4 atIndex:4];
            [encoder dispatchThreads:MTLSizeMake(count,1,1) threadsPerThreadgroup:groupSize(selector)];[encoder endEncoding];
            return finish(command);
        };
        auto encodeFinish=[&](){
            id<MTLCommandBuffer> command=[queue commandBuffer];auto encoder=[command computeCommandEncoder];
            [encoder setComputePipelineState:pairFinish];[encoder setBuffer:inputBuffer offset:0 atIndex:0];
            [encoder setBuffer:pairs offset:0 atIndex:1];[encoder setBuffer:selected offset:0 atIndex:2];
            [encoder setBuffer:fusedOut offset:0 atIndex:3];[encoder setBytes:&count length:4 atIndex:4];
            [encoder dispatchThreads:MTLSizeMake(count,1,1) threadsPerThreadgroup:groupSize(pairFinish)];[encoder endEncoding];
            return finish(command);
        };
        auto encodeFused=[&](){
            id<MTLCommandBuffer> command=[queue commandBuffer];auto encoder=[command computeCommandEncoder];
            for(uint32_t i=0;i<inner;++i){
                [encoder setComputePipelineState:selector];[encoder setBuffer:inputBuffer offset:0 atIndex:0];
                [encoder setBuffer:dirs offset:0 atIndex:1];[encoder setBuffer:consts offset:0 atIndex:2];
                [encoder setBuffer:selected offset:0 atIndex:3];[encoder setBytes:&count length:4 atIndex:4];
                [encoder dispatchThreads:MTLSizeMake(count,1,1) threadsPerThreadgroup:groupSize(selector)];
                [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
                [encoder setComputePipelineState:pairFinish];[encoder setBuffer:inputBuffer offset:0 atIndex:0];
                [encoder setBuffer:pairs offset:0 atIndex:1];[encoder setBuffer:selected offset:0 atIndex:2];
                [encoder setBuffer:fusedOut offset:0 atIndex:3];[encoder setBytes:&count length:4 atIndex:4];
                [encoder dispatchThreads:MTLSizeMake(count,1,1) threadsPerThreadgroup:groupSize(pairFinish)];
                if(i+1<inner)[encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
            }
            [encoder endEncoding];
            return finish(command);
        };

        const double firstBaseline=encodeBaseline();
        need(memcmp(baselineOut.contents,expected.bytes,expected.length)==0,"baseline GPU result differs from Python");
        const double coldFused=encodeFused();
        need(memcmp(fusedOut.contents,expected.bytes,expected.length)==0,"fused GPU result differs from Python");
        for(uint32_t i=0;i<warmups;++i){encodeBaseline();encodeFused();}
        std::vector<double> baselineTimes,fusedTimes;
        for(uint32_t i=0;i<repeats;++i){
            if(i&1){fusedTimes.push_back(encodeFused());baselineTimes.push_back(encodeBaseline());}
            else {baselineTimes.push_back(encodeBaseline());fusedTimes.push_back(encodeFused());}
        }
        need(memcmp(baselineOut.contents,expected.bytes,expected.length)==0,"final baseline result mismatch");
        need(memcmp(fusedOut.contents,expected.bytes,expected.length)==0,"final fused result mismatch");
        const double selectorSeconds=encodeSelector(),finishSeconds=encodeFinish();
        need(memcmp(fusedOut.contents,expected.bytes,expected.length)==0,"diagnostic fused result mismatch");
        const double baselineMedian=median(baselineTimes),fusedMedian=median(fusedTimes);
        const double logical=double(count)*2*inner;
        NSMutableArray *rawBaseline=[NSMutableArray array],*rawFused=[NSMutableArray array],*paired=[NSMutableArray array];
        for(size_t i=0;i<baselineTimes.size();++i){
            [rawBaseline addObject:@(baselineTimes[i])];[rawFused addObject:@(fusedTimes[i])];
            [paired addObject:@(fusedTimes[i]/baselineTimes[i])];
        }
        printJson(@{@"status":@"passed",@"scope":@"exact synthetic two-step selector/pair A/B",
            @"device":device.name,@"cases":@(count),@"correctResults":@(count),
            @"logicalUpdatesPerCase":@2,@"runtimeAdditionsPerCase":@2,@"pairLookupsPerCase":@1,
            @"innerIterationsPerSample":@(inner),@"rawBaselineSeconds":rawBaseline,
            @"rawFusedSeconds":rawFused,@"rawFusedToBaselineRatios":paired,
            @"baseline":stats(baselineTimes),@"fused":stats(fusedTimes),
            @"firstBaselineSeconds":@(firstBaseline),@"coldFusedSeconds":@(coldFused),
            @"selectorOnlySeconds":@(selectorSeconds),@"pairFinishOnlySeconds":@(finishSeconds),
            @"baselineLogicalUpdatesPerSecond":@(logical/baselineMedian),
            @"fusedLogicalUpdatesPerSecond":@(logical/fusedMedian),
            @"fusedToBaselineTimeRatio":@(fusedMedian/baselineMedian),
            @"fusedSpeedup":@(baselineMedian/fusedMedian),
            @"pairTableLoaded":@YES,@"pairTableBytes":@(pairBytes),
            @"fullPairAddressSpaceMapped":@YES,@"fullPairResidencyMeasured":@NO,
            @"metalAllocatedBytesBeforePair":@(allocatedBeforePair),
            @"metalAllocatedBytesAfterPair":@(allocatedAfterPair),
            @"recommendedWorkingSetBytes":@(device.recommendedMaxWorkingSetSize),
            @"maximumBufferBytes":@(device.maxBufferLength),
            @"input":config});
        return 0;
    }catch(const std::exception &exception){
        printJson(@{@"status":@"error",@"error":[NSString stringWithUTF8String:exception.what()]});return 1;
    }}
}
