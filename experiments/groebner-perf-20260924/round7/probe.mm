#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <iostream>
int main() { @autoreleasepool {
 id<MTLDevice> d=MTLCreateSystemDefaultDevice();
 if(!d) return 1;
 std::cout<<d.name.UTF8String<<"\n";
 for(unsigned i=0;i<5;++i)std::cout<<"sampling "<<i<<": "<<[d supportsCounterSampling:(MTLCounterSamplingPoint)i]<<"\n";
 for(id<MTLCounterSet> s in d.counterSets) {
  std::cout<<s.name.UTF8String<<": ";
  for(id<MTLCounter> c in s.counters)std::cout<<c.name.UTF8String<<", ";
  std::cout<<"\n";
 }
}}
