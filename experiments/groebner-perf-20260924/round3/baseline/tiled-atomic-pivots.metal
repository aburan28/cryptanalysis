// Batched global-memory eight-pivot panels, adapted from sage-gf2-metal-reuse.
// Each batch member has independent pivots, tables and state. Matrices need
// not fit in threadgroup memory. Elimination is tiled over row-word indices.
#include <metal_stdlib>
using namespace metal;
struct Params { uint rows, cols, words, count; };
#define SYNC threadgroup_barrier(mem_flags::mem_threadgroup | mem_flags::mem_device)
// Construct an eight-pivot panel. Other rows are reduced virtually while
// searching; only the panel rows are physically updated here.
kernel void panel_cached(device uint*A [[buffer(0)]], device uint*S [[buffer(1)]],
 device uint*pc [[buffer(2)]], device uint*M [[buffer(4)]], constant Params&P [[buffer(5)]],
 uint t [[thread_index_in_threadgroup]], uint2 group [[threadgroup_position_in_grid]]) {
 uint batch=group.y;
 A+=batch*P.rows*P.words;S+=batch*4;pc+=batch*8;M+=batch*P.rows;
 threadgroup uint r,c,k,chosen,coeff,back,column_bits;
 threadgroup atomic_uint best;
 if(t==0){r=S[0];c=S[1];k=0;S[2]=r;S[3]=0;}
 for(uint row=t;row<P.rows;row+=256)M[row]=0;
 SYNC;
 while(k<8 && r+k<P.rows && c<P.cols){
  if(t==0){
   atomic_store_explicit(&best,P.rows,memory_order_relaxed);
   column_bits=0;
   for(uint j=0;j<k;j++)column_bits|=((A[(r+j)*P.words+c/32]>>(c%32))&1u)<<j;
  }
  SYNC;
  for(uint i=r+k+t;i<P.rows;i+=256){
   uint bit=(A[i*P.words+c/32]>>(c%32))&1u;
   bit^=popcount(M[i]&column_bits)&1u;
   if(bit)atomic_fetch_min_explicit(&best,i,memory_order_relaxed);
  }
  SYNC;
  if(t==0)chosen=atomic_load_explicit(&best,memory_order_relaxed);
  SYNC;
  if(chosen<P.rows){
   const uint panel_k=k; // private copy established before the swap barrier
   for(uint w=t;w<P.words;w+=256){
    uint v=A[(r+k)*P.words+w];A[(r+k)*P.words+w]=A[chosen*P.words+w];A[chosen*P.words+w]=v;
   }
   if(t==0){uint cached=M[r+k];M[r+k]=M[chosen];M[chosen]=cached;}
   SYNC;
   if(t==0){
    coeff=0;back=0;
    for(uint j=0;j<k;j++){
     coeff|=((A[(r+k)*P.words+pc[j]/32]>>(pc[j]%32))&1u)<<j;
     back|=((A[(r+j)*P.words+c/32]>>(c%32))&1u)<<j;
    }
   }
   SYNC;
   for(uint w=t;w<P.words;w+=256){
    uint v=A[(r+k)*P.words+w];
    for(uint j=0;j<k;j++)if((coeff>>j)&1u)v^=A[(r+j)*P.words+w];
    A[(r+k)*P.words+w]=v;
   }
   SYNC;
   for(uint index=t;index<k*P.words;index+=256){
    uint j=index/P.words,w=index%P.words;
    if((back>>j)&1u)A[(r+j)*P.words+w]^=A[(r+k)*P.words+w];
   }
   SYNC;
   // Unselected rows have not changed; append their new pivot-column bit.
   // Selected panel rows are excluded from later searches; their masks are
   // zeroed at panel completion before global elimination.
   for(uint row=t;row<P.rows;row+=256)M[row]|=((A[row*P.words+c/32]>>(c%32))&1u)<<panel_k;
   if(t==0){pc[k]=c;k++;}
   SYNC;
  }
  if(t==0)c++;
  SYNC;
 }
 if(t==0){S[0]=r+k;S[1]=c;S[2]=r;S[3]=k;for(uint j=0;j<k;j++)M[r+j]=0;}
}
kernel void table_rows(device const uint*A [[buffer(0)]],device const uint*S [[buffer(1)]],
 device uint*T [[buffer(3)]],constant Params&P [[buffer(5)]],uint2 pos [[thread_position_in_grid]]){
 uint i=pos.x,batch=pos.y;
 A+=batch*P.rows*P.words;S+=batch*4;T+=batch*256*P.words;
 uint k=S[3];if(!k || i>=(1u<<k)*P.words)return;
 uint mask=i/P.words,w=i%P.words,v=0;
 for(uint j=0;j<k;j++)if((mask>>j)&1u)v^=A[(S[2]+j)*P.words+w];
 T[i]=v;
}
kernel void eliminate(device uint*A [[buffer(0)]],device const uint*T [[buffer(3)]],
 device const uint*M [[buffer(4)]],constant Params&P [[buffer(5)]],uint2 pos [[thread_position_in_grid]]){
 uint i=pos.x,batch=pos.y;
 A+=batch*P.rows*P.words;T+=batch*256*P.words;M+=batch*P.rows;
 if(i>=P.rows*P.words)return;uint mask=M[i/P.words];
 if(mask)A[i]^=T[mask*P.words+i%P.words];
}
