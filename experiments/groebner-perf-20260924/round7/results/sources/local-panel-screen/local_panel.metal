#ifndef PIVOT_THREADS
#define PIVOT_THREADS 256
#endif
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
 uint t [[thread_index_in_threadgroup]], uint2 group [[threadgroup_position_in_grid]],
 uint lane [[thread_index_in_simdgroup]], threadgroup uint*columns [[threadgroup(0)]]) {
 uint batch=group.y;
 A+=batch*P.rows*P.words;S+=batch*4;pc+=batch*8;M+=batch*P.rows;
 threadgroup uint r,c,k,chosen,coeff,back,column_bits;
 threadgroup atomic_uint best;
 if(t==0){r=S[0];c=S[1];k=0;S[2]=r;S[3]=0;}
 for(uint row=t;row<P.rows;row+=PIVOT_THREADS)M[row]=0;
 SYNC;
 uint cached_word=0xffffffffu; // private, identical value in every lane
 while(k<8 && r+k<P.rows && c<P.cols){
  // Cache one 32-column slice. Its rows fit on chip even though the whole
  // matrix does not. Swaps and updates below keep this slice coherent.
  if(P.rows<=4096 && cached_word!=c/32){
   for(uint row=t;row<P.rows;row+=PIVOT_THREADS)columns[row]=A[row*P.words+c/32];
   SYNC;
   cached_word=c/32;
  }
  if(t==0){
   atomic_store_explicit(&best,P.rows,memory_order_relaxed);
   column_bits=0;
   for(uint j=0;j<k;j++)column_bits|=((A[(r+j)*P.words+c/32]>>(c%32))&1u)<<j;
  }
  SYNC;
  uint local_best=P.rows;
  for(uint i=r+k+t;i<P.rows;i+=PIVOT_THREADS){
   uint bit=((P.rows<=4096?columns[i]:A[i*P.words+c/32])>>(c%32))&1u;
   bit^=popcount(M[i]&column_bits)&1u;
   if(bit)local_best=min(local_best,i);
  }
  local_best=simd_min(local_best);
  if(lane==0)atomic_fetch_min_explicit(&best,local_best,memory_order_relaxed);
  SYNC;
  if(t==0)chosen=atomic_load_explicit(&best,memory_order_relaxed);
  SYNC;
  if(chosen<P.rows){
   const uint panel_k=k; // private copy established before the swap barrier
   for(uint w=t;w<P.words;w+=PIVOT_THREADS){
    uint v=A[(r+k)*P.words+w];A[(r+k)*P.words+w]=A[chosen*P.words+w];A[chosen*P.words+w]=v;
   }
   if(t==0){
    uint cached=M[r+k];M[r+k]=M[chosen];M[chosen]=cached;
    if(P.rows<=4096){uint v=columns[r+k];columns[r+k]=columns[chosen];columns[chosen]=v;}
   }
   SYNC;
   if(t==0){
    coeff=0;back=0;
    for(uint j=0;j<k;j++){
     coeff|=((A[(r+k)*P.words+pc[j]/32]>>(pc[j]%32))&1u)<<j;
     back|=((A[(r+j)*P.words+c/32]>>(c%32))&1u)<<j;
    }
   }
   SYNC;
   for(uint w=t;w<P.words;w+=PIVOT_THREADS){
    uint v=A[(r+k)*P.words+w];
    for(uint j=0;j<k;j++)if((coeff>>j)&1u)v^=A[(r+j)*P.words+w];
    A[(r+k)*P.words+w]=v;
   }
   SYNC;
   for(uint index=t;index<k*P.words;index+=PIVOT_THREADS){
    uint j=index/P.words,w=index%P.words;
    if((back>>j)&1u)A[(r+j)*P.words+w]^=A[(r+k)*P.words+w];
   }
   SYNC;
   // Unselected rows have not changed; append their new pivot-column bit.
   if(P.rows<=4096){
    for(uint j=t;j<=k;j+=PIVOT_THREADS)columns[r+j]=A[(r+j)*P.words+c/32];
   }
   SYNC;
   // Selected panel rows are excluded from later searches; their masks are
   // zeroed at panel completion before global elimination.
   for(uint row=t;row<P.rows;row+=PIVOT_THREADS)
    M[row]|=(((P.rows<=4096?columns[row]:A[row*P.words+c/32])>>(c%32))&1u)<<panel_k;
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

// Fuse lookup-table construction into elimination. New panel rows have zero
// masks and remain immutable while other threadgroups read their words.
kernel void eliminate_direct(device uint*A [[buffer(0)]],device const uint*S [[buffer(1)]],
 device const uint*M [[buffer(4)]],constant Params&P [[buffer(5)]],uint2 pos [[thread_position_in_grid]]) {
 uint i=pos.x,batch=pos.y;
 if(i>=P.rows*P.words)return;
 A+=batch*P.rows*P.words;S+=batch*4;M+=batch*P.rows;
 uint mask=M[i/P.words];
 if(!mask)return;
 uint w=i%P.words,v=0;
 for(uint j=0;j<S[3];j++)if((mask>>j)&1u)v^=A[(S[2]+j)*P.words+w];
 A[i]^=v;
}

// Cache the panel rows and all virtual reduction masks as well as one column
// slice. The host chooses this only when the complete allocation fits on chip.
// Physical row moves need device visibility once per pivot; elimination within
// the panel uses only threadgroup barriers. Commit the final panel once.
kernel void panel_local(device uint*A [[buffer(0)]],device uint*S [[buffer(1)]],
 device uint*pc [[buffer(2)]],device uint*M [[buffer(4)]],constant Params&P [[buffer(5)]],
 uint t [[thread_index_in_threadgroup]],uint2 group [[threadgroup_position_in_grid]],
 uint lane [[thread_index_in_simdgroup]],threadgroup uint*scratch [[threadgroup(0)]]) {
 uint batch=group.y;
 A+=batch*P.rows*P.words; S+=batch*4; pc+=batch*8; M+=batch*P.rows;
 threadgroup uint*columns=scratch;
 threadgroup uint*masks=scratch+P.rows;
 threadgroup uint*B=scratch+2*P.rows;
 threadgroup uint r,c,k,chosen,coeff,back,column_bits,pivots[8];
 threadgroup atomic_uint best;
 if(t==0){r=S[0];c=S[1];k=0;S[2]=r;S[3]=0;}
 for(uint row=t;row<P.rows;row+=PIVOT_THREADS)masks[row]=0;
 threadgroup_barrier(mem_flags::mem_threadgroup);
 uint cached_word=0xffffffffu;
 while(k<8 && r+k<P.rows && c<P.cols) {
  if(cached_word!=c/32) {
   for(uint row=t;row<P.rows;row+=PIVOT_THREADS)
    columns[row]=(row>=r && row<r+k)?B[(row-r)*P.words+c/32]:A[row*P.words+c/32];
   threadgroup_barrier(mem_flags::mem_threadgroup);
   cached_word=c/32;
  }
  if(t==0) {
   atomic_store_explicit(&best,P.rows,memory_order_relaxed);
   column_bits=0;
   for(uint j=0;j<k;++j)column_bits|=((B[j*P.words+c/32]>>(c%32))&1u)<<j;
  }
  threadgroup_barrier(mem_flags::mem_threadgroup);
  uint local_best=P.rows;
  for(uint row=r+k+t;row<P.rows;row+=PIVOT_THREADS) {
   uint bit=((columns[row]>>(c%32))&1u)^(popcount(masks[row]&column_bits)&1u);
   if(bit)local_best=min(local_best,row);
  }
  local_best=simd_min(local_best);
  if(lane==0)atomic_fetch_min_explicit(&best,local_best,memory_order_relaxed);
  threadgroup_barrier(mem_flags::mem_threadgroup);
  if(t==0)chosen=atomic_load_explicit(&best,memory_order_relaxed);
  threadgroup_barrier(mem_flags::mem_threadgroup);
  if(chosen<P.rows) {
   const uint panel_k=k;
   // The selected row lives only in B until panel completion. Move the row
   // displaced from r+k into chosen so future searches see the right matrix.
   for(uint w=t;w<P.words;w+=PIVOT_THREADS) {
    B[k*P.words+w]=A[chosen*P.words+w];
    A[chosen*P.words+w]=A[(r+k)*P.words+w];
   }
   if(t==0) {
    uint v=masks[r+k];masks[r+k]=masks[chosen];masks[chosen]=v;
    v=columns[r+k];columns[r+k]=columns[chosen];columns[chosen]=v;
   }
   threadgroup_barrier(mem_flags::mem_threadgroup | mem_flags::mem_device);
   if(t==0) {
    coeff=0;back=0;
    for(uint j=0;j<k;++j) {
     coeff|=((B[k*P.words+pivots[j]/32]>>(pivots[j]%32))&1u)<<j;
     back|=((B[j*P.words+c/32]>>(c%32))&1u)<<j;
    }
   }
   threadgroup_barrier(mem_flags::mem_threadgroup);
   for(uint w=t;w<P.words;w+=PIVOT_THREADS) {
    uint v=B[k*P.words+w];
    for(uint j=0;j<k;++j)if((coeff>>j)&1u)v^=B[j*P.words+w];
    B[k*P.words+w]=v;
   }
   threadgroup_barrier(mem_flags::mem_threadgroup);
   for(uint index=t;index<k*P.words;index+=PIVOT_THREADS) {
    uint j=index/P.words,w=index%P.words;
    if((back>>j)&1u)B[index]^=B[k*P.words+w];
   }
   threadgroup_barrier(mem_flags::mem_threadgroup);
   for(uint j=t;j<=k;j+=PIVOT_THREADS)columns[r+j]=B[j*P.words+c/32];
   threadgroup_barrier(mem_flags::mem_threadgroup);
   for(uint row=t;row<P.rows;row+=PIVOT_THREADS)
    masks[row]|=((columns[row]>>(c%32))&1u)<<panel_k;
   if(t==0){pivots[k]=c;k++;}
   threadgroup_barrier(mem_flags::mem_threadgroup);
  }
  if(t==0)c++;
  threadgroup_barrier(mem_flags::mem_threadgroup);
 }
 for(uint index=t;index<k*P.words;index+=PIVOT_THREADS)A[r*P.words+index]=B[index];
 for(uint row=t;row<P.rows;row+=PIVOT_THREADS)M[row]=(row>=r && row<r+k)?0:masks[row];
 for(uint j=t;j<k;j+=PIVOT_THREADS)pc[j]=pivots[j];
 if(t==0){S[0]=r+k;S[1]=c;S[2]=r;S[3]=k;}
}
