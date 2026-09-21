// Bounded native driver for the synthetic artifact walk. Runtime MSL compile.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>
#include <chrono>

static const char shader[] =
#include "artifact_walk_metal.inc"
;
struct State { uint32_t xy[10],history[3],mode; uint64_t seed,trailSteps,walkSteps,reseeds,trace,dpHash,dpCount; };
struct Dp { uint64_t seed,steps,lane; uint32_t xy[10],history[3],pad; };
struct Args { uint32_t lanes,cycles,branches,dpCap; int32_t dpWeight; uint32_t pad; };
static_assert(sizeof(State)==112 && sizeof(Dp)==80 && sizeof(Args)==24,"host/shader layout differs");
static void need(bool ok,const char *text) { if(!ok)throw std::runtime_error(text); }
static NSData *readFile(NSString *root,NSString *name) {
    NSData *data=[NSData dataWithContentsOfFile:[root stringByAppendingPathComponent:name]];
    need(data!=nil,"missing input file");return data;
}
static void writeFile(NSString *root,NSString *name,const void *data,size_t bytes) {
    NSData *value=[NSData dataWithBytes:data length:bytes];
    need([value writeToFile:[root stringByAppendingPathComponent:name] atomically:YES],"cannot write result file");
}
static void printJson(NSDictionary *value) {
    NSData *data=[NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:nil];
    need(data!=nil,"invalid result JSON");fwrite(data.bytes,1,data.length,stdout);puts("");
}
static id<MTLComputePipelineState> pipeline(id<MTLDevice> device,id<MTLLibrary> lib,NSString *name) {
    NSError *error=nil;
    id<MTLFunction> function=[lib newFunctionWithName:name];need(function!=nil,"missing kernel");
    id<MTLComputePipelineState> result=[device newComputePipelineStateWithFunction:function error:&error];
    if(!result)throw std::runtime_error(error.localizedDescription.UTF8String ?: "cannot create pipeline");
    return result;
}
static void finish(id<MTLCommandBuffer> command) {
    [command commit];[command waitUntilCompleted];
    if(command.status!=MTLCommandBufferStatusCompleted)
        throw std::runtime_error(command.error.localizedDescription.UTF8String ?: "GPU command failed");
}
static MTLSize groupSize(id<MTLComputePipelineState> pipeline) {
    NSUInteger n=std::min<NSUInteger>(128,pipeline.maxTotalThreadsPerThreadgroup);
    if(n>=pipeline.threadExecutionWidth)n-=n%pipeline.threadExecutionWidth;
    return MTLSizeMake(std::max<NSUInteger>(1,n),1,1);
}

int main(int argc,char **argv) {
    @autoreleasepool {
        try {
            need(argc==3,"usage: metal-artifact-walk INPUT_DIRECTORY OUTPUT_DIRECTORY");
            NSString *input=[NSString stringWithUTF8String:argv[1]], *output=[NSString stringWithUTF8String:argv[2]];
            NSDictionary *config=[NSJSONSerialization JSONObjectWithData:readFile(input,@"config.json") options:0 error:nil];
            need([config isKindOfClass:[NSDictionary class]],"invalid configuration");
            const uint32_t lanes=[config[@"lanes"] unsignedIntValue],cycles=[config[@"cycles"] unsignedIntValue];
            const uint32_t launches=[config[@"launches"] unsignedIntValue],branches=[config[@"branches"] unsignedIntValue];
            const uint32_t cap=[config[@"dpCap"] unsignedIntValue],batch=[config[@"batch"] unsignedIntValue];
            const int dpWeight=[config[@"dpWeight"] intValue];
            need(lanes>0&&lanes<=65536&&cycles>0&&cycles<=128&&launches>0&&launches<=10000,"invalid workload bounds");
            need((branches==128||branches==256)&&cap>0&&cap<=1000000&&dpWeight>=-1&&dpWeight<=130,"invalid table/report bounds");
            need(batch==1||batch==4||batch==8||batch==16||batch==32,"invalid batch");
            id<MTLDevice> device=MTLCreateSystemDefaultDevice();
            if(!device){printJson(@{@"status":@"unavailable",@"error":@"No Metal GPU; run natively outside the sandbox"});return 77;}
            need(device.hasUnifiedMemory,"the artifact driver requires unified-memory Metal");
            MTLCompileOptions *options=[MTLCompileOptions new];options.preprocessorMacros=@{@"ARTIFACT_BATCH":@(batch)};
            NSError *error=nil;
            id<MTLLibrary> lib=[device newLibraryWithSource:[NSString stringWithUTF8String:shader] options:options error:&error];
            if(!lib)throw std::runtime_error(error.localizedDescription.UTF8String ?: "shader compilation failed");
            auto arithmetic=pipeline(device,lib,@"artifact_arithmetic"),walk=pipeline(device,lib,@"artifact_walk");
            id<MTLCommandQueue> queue=[device newCommandQueue];need(queue!=nil,"no command queue");
            NSData *ai=readFile(input,@"arithmetic-in.bin"),*ae=readFile(input,@"arithmetic-expected.bin");
            need(ai.length%128==0&&ai.length>0,"bad arithmetic vectors");
            const uint32_t cases=uint32_t(ai.length/128);
            need(cases<=4096&&ae.length==size_t(cases)*104,"bad arithmetic expected size");
            id<MTLBuffer> ain=[device newBufferWithBytes:ai.bytes length:ai.length options:MTLResourceStorageModeShared];
            id<MTLBuffer> aout=[device newBufferWithLength:ae.length options:MTLResourceStorageModeShared];
            need(ain&&aout,"arithmetic allocation failed");
            id<MTLCommandBuffer> test=[queue commandBuffer];auto enc=[test computeCommandEncoder];
            [enc setComputePipelineState:arithmetic];[enc setBuffer:ain offset:0 atIndex:0];[enc setBuffer:aout offset:0 atIndex:1];
            [enc setBytes:&cases length:4 atIndex:2];
            [enc dispatchThreads:MTLSizeMake(cases,1,1) threadsPerThreadgroup:groupSize(arithmetic)];[enc endEncoding];finish(test);
            need(memcmp(aout.contents,ae.bytes,ae.length)==0,"GPU arithmetic differs from independent Python vectors");
            NSData *initial=readFile(input,@"initial.bin"),*directions=readFile(input,@"directions.bin"),*constants=readFile(input,@"selector.bin");
            need(initial.length==size_t(lanes)*sizeof(State),"bad initial state size");
            need(directions.length==size_t(262)*branches*36&&constants.length==13708,"bad table/selector sizes");
            auto make=[&](NSData *data){return [device newBufferWithBytes:data.bytes length:data.length options:MTLResourceStorageModeShared];};
            id<MTLBuffer> states=make(initial),dirs=make(directions),consts=make(constants);
            id<MTLBuffer> records=[device newBufferWithLength:size_t(cap)*sizeof(Dp) options:MTLResourceStorageModeShared];
            id<MTLBuffer> counts=[device newBufferWithLength:8 options:MTLResourceStorageModeShared];
            need(states&&dirs&&consts&&records&&counts,"walk allocation failed");
            NSString *recordPath=[output stringByAppendingPathComponent:@"reports.bin"];
            FILE *reportFile=fopen(recordPath.fileSystemRepresentation,"wb");need(reportFile!=nullptr,"cannot create report file");
            struct Close {FILE *f;~Close(){fclose(f);}} close{reportFile};
            uint64_t totalReports=0,dispatches=0;double gpuSeconds=0,maxDispatch=0;
            uint32_t chunkLimit=1;
            const auto started=std::chrono::steady_clock::now();
            for(uint32_t launch=0;launch<launches;++launch) {
                memset(counts.contents,0,8);
                for(uint32_t done=0;done<cycles;) {
                    const uint32_t chunk=std::min(chunkLimit,cycles-done);
                    Args args{lanes,chunk,branches,cap,dpWeight,0};
                    id<MTLCommandBuffer> command=[queue commandBuffer];auto encoder=[command computeCommandEncoder];
                    [encoder setComputePipelineState:walk];[encoder setBuffer:states offset:0 atIndex:0];
                    [encoder setBuffer:dirs offset:0 atIndex:1];[encoder setBuffer:consts offset:0 atIndex:2];
                    [encoder setBuffer:records offset:0 atIndex:3];[encoder setBuffer:counts offset:0 atIndex:4];
                    [encoder setBytes:&args length:sizeof(args) atIndex:5];
                    [encoder dispatchThreads:MTLSizeMake((lanes+batch-1)/batch,1,1) threadsPerThreadgroup:groupSize(walk)];
                    [encoder endEncoding];finish(command);done+=chunk;++dispatches;
                    double seconds=command.GPUEndTime-command.GPUStartTime;
                    need(std::isfinite(seconds)&&seconds>=0,"invalid GPU event timing");
                    gpuSeconds+=seconds;maxDispatch=std::max(maxDispatch,seconds);
                    // Aim below 50 ms; retain a factor-four margin for the
                    // selector cost when the first dispatch only seeds lanes.
                    if(seconds>0)chunkLimit=std::max(1u,std::min(128u,uint32_t(0.0125*chunk/seconds)));
                }
                const uint32_t *count=static_cast<const uint32_t *>(counts.contents);
                need(count[1]==0&&count[0]<=cap,"DP buffer overflow; increase dpCap");
                need(fwrite(records.contents,sizeof(Dp),count[0],reportFile)==count[0],"report write failed");
                totalReports+=count[0];
            }
            need(fflush(reportFile)==0,"report flush failed");
            uint64_t updates=0,reseedAdds=0,halted=0,exhausted=0,dpCount=0;
            const State *final=static_cast<const State *>(states.contents);
            for(uint32_t i=0;i<lanes;++i){updates+=final[i].walkSteps;reseedAdds+=final[i].reseeds;dpCount+=final[i].dpCount;halted+=final[i].mode==2;exhausted+=final[i].mode==3;}
            need(dpCount==totalReports,"report count/state count disagree");
            writeFile(output,@"state.bin",states.contents,initial.length);
            const double wall=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
            printJson(@{@"status":@"ok",@"scope":@"synthetic signed-Frobenius artifact walk",
                @"device":device.name,@"branches":@(branches),@"lanes":@(lanes),@"batch":@(batch),
                @"cyclesPerLaunch":@(cycles),@"launches":@(launches),@"dispatches":@(dispatches),
                @"walkUpdates":@(updates),@"seedAdditions":@(reseedAdds),@"groupOperations":@(updates+reseedAdds),
                @"dpRecords":@(totalReports),@"droppedRecords":@0,@"haltedLanes":@(halted),@"exhaustedLanes":@(exhausted),
                @"gpuSeconds":@(gpuSeconds),@"maximumDispatchSeconds":@(maxDispatch),@"dispatchWallSeconds":@(wall),
                @"independentArithmeticCases":@(cases),@"pairTableLoaded":@NO,
                @"residentDataBytes":@(states.length+dirs.length+consts.length+records.length+counts.length)});
        } catch(const std::exception &error) {
            printJson(@{@"status":@"error",@"error":[NSString stringWithUTF8String:error.what()]});return 1;
        }
    }
}
