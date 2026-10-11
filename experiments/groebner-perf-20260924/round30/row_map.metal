#include <metal_stdlib>
using namespace metal;
#ifndef MAP_WIDTH
#define MAP_WIDTH 16
#endif
#ifndef MAP_THREADS
#define MAP_THREADS 512
#endif
#ifndef MAP_SKIP_WORDS
#define MAP_SKIP_WORDS 1
#endif
struct Params { uint rows,cols,words,count; };
#define LOCAL threadgroup_barrier(mem_flags::mem_threadgroup)
#define BOTH threadgroup_barrier(mem_flags::mem_threadgroup | mem_flags::mem_device)

// A remains immutable through selection and table construction. O is a
// logical-to-physical permutation, reset for every new matrix invocation.
kernel void select_mapped(device const uint*A [[buffer(0)]],device uint*S [[buffer(1)]],
 device uint*pc [[buffer(2)]],device uint*M [[buffer(4)]],constant Params&P [[buffer(5)]],
 device uint*O [[buffer(6)]],device uint*D [[buffer(7)]],
 uint t [[thread_index_in_threadgroup]],uint2 group [[threadgroup_position_in_grid]],
 uint lane [[thread_index_in_simdgroup]],threadgroup uint*scratch [[threadgroup(0)]]) {
 uint batch=group.y,groups=MAP_WIDTH/8;
 A+=batch*P.rows*P.words;S+=batch*4;pc+=batch*MAP_WIDTH;
 M+=batch*P.rows;O+=batch*P.rows;D+=batch*(MAP_WIDTH+groups*256);
 const uint r=S[0],initial_c=S[1],active=P.rows-r;
 threadgroup uint c,k,chosen,pivots[MAP_WIDTH];
 threadgroup uint forward_mix[MAP_WIDTH],forward_word[MAP_WIDTH];
 threadgroup uint pivot_columns[MAP_WIDTH],canonical_mix[MAP_WIDTH];
 threadgroup atomic_uint best,remaining;
 threadgroup uint*columns=scratch;
 threadgroup uint*masks=scratch+active;
 if(t==0){c=initial_c;k=0;S[2]=r;S[3]=0;}
 LOCAL;
 if(r>=P.rows || initial_c>=P.cols)return;
 for(uint row=t;row<active;row+=MAP_THREADS)masks[row]=0;
 LOCAL;
 uint cached_word=0xffffffffu;
 while(k<MAP_WIDTH && r+k<P.rows && c<P.cols) {
  if(cached_word!=c/32) {
   for(uint row=t;row<active;row+=MAP_THREADS)columns[row]=A[O[r+row]*P.words+c/32];
   // Reconstruct the virtual forward panel in the new column word using
   // its mixing masks against immutable selected physical rows.
   for(uint row=t;row<k;row+=MAP_THREADS) {
    uint value=0,mask=forward_mix[row];
    while(mask){uint j=ctz(mask);value^=A[O[r+j]*P.words+c/32];mask&=mask-1;}
    forward_word[row]=value;
   }
   LOCAL;
   for(uint row=k+t;row<active;row+=MAP_THREADS) {
    uint value=columns[row],mask=masks[row];
    while(mask){uint j=ctz(mask);value^=forward_word[j];mask&=mask-1;}
    columns[row]=value;
   }
   LOCAL;cached_word=c/32;
  }
  if(t==0) {
   atomic_store_explicit(&best,active,memory_order_relaxed);
  }
  LOCAL;
  uint local_best=active,local_word=0;
  for(uint row=k+t;row<active;row+=MAP_THREADS) {
   uint value=columns[row],bit=(value>>(c%32))&1u;
   local_word|=value;
   if(bit)local_best=min(local_best,row);
  }
  local_best=simd_min(local_best);
  if(lane==0)atomic_fetch_min_explicit(&best,local_best,memory_order_relaxed);
  LOCAL;
  if(t==0)chosen=atomic_load_explicit(&best,memory_order_relaxed);
  LOCAL;
  if(chosen<active) {
   const uint panel_k=k;
   if(t==0) {
    uint v=O[r+k];O[r+k]=O[r+chosen];O[r+chosen]=v;
    v=masks[k];masks[k]=masks[chosen];masks[chosen]=v;
    v=columns[k];columns[k]=columns[chosen];columns[chosen]=v;
    uint mix=1u<<k,mask=masks[k];
    while(mask){uint j=ctz(mask);mix^=forward_mix[j];mask&=mask-1;}
    forward_mix[k]=mix;forward_word[k]=columns[k];
   }
   BOTH;
   for(uint row=panel_k+1+t;row<active;row+=MAP_THREADS) {
    uint bit=(columns[row]>>(c%32))&1u;
    if(bit){masks[row]|=1u<<panel_k;columns[row]^=forward_word[panel_k];}
   }
   if(t==0){pivots[k]=c;k++;}
   LOCAL;
  }
#if MAP_SKIP_WORDS
  else {
   // Only skip columns after OR-reducing every unselected virtual row.
   // This includes long dependent/zero suffixes after the final pivot.
   if(t==0)atomic_store_explicit(&remaining,0,memory_order_relaxed);
   LOCAL;
   uint word=simd_or(local_word);
   if(lane==0)atomic_fetch_or_explicit(&remaining,word,memory_order_relaxed);
   LOCAL;
   if(t==0) {
    uint bits=atomic_load_explicit(&remaining,memory_order_relaxed)&(0xffffffffu<<(c%32));
    uint next=bits?(c/32)*32+ctz(bits):min(P.cols,(c/32+1)*32);
    c=next-1; // common increment below advances to the next possible pivot
   }
   LOCAL;
  }
#endif
  if(t==0)c++;
  LOCAL;
 }
 // F = L*S_raw has a unit upper triangular pivot submatrix U. Form
 // canonical mixing masks U^{-1}*L, without materializing full F or C rows.
 for(uint col=t;col<k;col+=MAP_THREADS) {
  uint raw_bits=0,bits=0;
  for(uint j=0;j<k;++j)raw_bits|=((A[O[r+j]*P.words+pivots[col]/32]>>(pivots[col]%32))&1u)<<j;
  for(uint row=0;row<=col;++row)bits|=(popcount(raw_bits&forward_mix[row])&1u)<<row;
  pivot_columns[col]=bits;
 }
 LOCAL;
 for(uint row=t;row<k;row+=MAP_THREADS) {
  uint mask=1u<<row,mix=0;
  for(uint col=row+1;col<k;++col)mask|=(popcount(mask&pivot_columns[col])&1u)<<col;
  while(mask){uint j=ctz(mask);mix^=forward_mix[j];mask&=mask-1;}
  canonical_mix[row]=mix;D[row]=O[r+row];pc[row]=pivots[row];
 }
 LOCAL;
 for(uint index=t;index<groups*256;index+=MAP_THREADS) {
  uint block=index/256,mask=index%256,mix=0;
  for(uint j=block*8;j<min(k,block*8+8);++j)
   if((mask>>(j-block*8))&1u)mix^=canonical_mix[j];
  D[MAP_WIDTH+index]=mix;
 }
 for(uint row=t;row<P.rows;row+=MAP_THREADS) {
  uint mask=0,physical=O[row];
  for(uint j=0;j<k;++j)mask|=((A[physical*P.words+pivots[j]/32]>>(pivots[j]%32))&1u)<<j;
  // Raw selected row j equals G_j*C. Adding (G_j + e_j)*C gives C_j.
  // Omitting e_j would erase the selected row and destroy rank.
  if(row>=r && row<r+k)mask^=1u<<(row-r);
  M[row]=mask;
 }
 if(t==0){S[0]=r+k;S[1]=c;S[2]=r;S[3]=k;}
}

kernel void table_mapped(device const uint*A [[buffer(0)]],device const uint*S [[buffer(1)]],
 device const uint*pc [[buffer(2)]],device uint*T [[buffer(3)]],constant Params&P [[buffer(5)]],
 device const uint*D [[buffer(7)]],uint2 pos [[thread_position_in_grid]]) {
 uint i=pos.x,batch=pos.y,groups=MAP_WIDTH/8;
 A+=batch*P.rows*P.words;S+=batch*4;pc+=batch*MAP_WIDTH;T+=batch*groups*256*P.words;
 D+=batch*(MAP_WIDTH+groups*256);
 if(!S[3])return;
 uint first=pc[0]/32,tail=P.words-first;
 if(i>=((S[3]+7)/8)*256*tail)return;
 uint index=i/tail,w=first+i%tail,mask=D[MAP_WIDTH+index],v=0;
 while(mask){uint j=ctz(mask);v^=A[D[j]*P.words+w];mask&=mask-1;}
 T[index*P.words+w]=v;
}
kernel void table_mapped_vec(device const uint4*A [[buffer(0)]],device const uint*S [[buffer(1)]],
 device const uint*pc [[buffer(2)]],device uint4*T [[buffer(3)]],constant Params&P [[buffer(5)]],
 device const uint*D [[buffer(7)]],uint2 pos [[thread_position_in_grid]]) {
 uint i=pos.x,batch=pos.y,groups=MAP_WIDTH/8,words=P.words/4;
 A+=batch*P.rows*words;S+=batch*4;pc+=batch*MAP_WIDTH;T+=batch*groups*256*words;
 D+=batch*(MAP_WIDTH+groups*256);
 if(!S[3])return;
 uint first=pc[0]/128,tail=words-first;
 if(i>=((S[3]+7)/8)*256*tail)return;
 uint index=i/tail,w=first+i%tail,mask=D[MAP_WIDTH+index];uint4 v=uint4(0);
 while(mask){uint j=ctz(mask);v^=A[D[j]*words+w];mask&=mask-1;}
 T[index*words+w]=v;
}
kernel void eliminate_mapped(device uint*A [[buffer(0)]],device const uint*S [[buffer(1)]],
 device const uint*pc [[buffer(2)]],device const uint*T [[buffer(3)]],device const uint*M [[buffer(4)]],
 constant Params&P [[buffer(5)]],device const uint*O [[buffer(6)]],uint2 pos [[thread_position_in_grid]]) {
 uint i=pos.x,batch=pos.y,groups=MAP_WIDTH/8;
 A+=batch*P.rows*P.words;S+=batch*4;pc+=batch*MAP_WIDTH;T+=batch*groups*256*P.words;M+=batch*P.rows;O+=batch*P.rows;
 if(!S[3])return;
 uint first=pc[0]/32,tail=P.words-first;if(i>=P.rows*tail)return;
 uint row=i/tail,mask=M[row],w=first+i%tail,v=0;
 if(mask) {
  for(uint block=0;block<(S[3]+7)/8;++block)v^=T[(block*256+((mask>>(8*block))&255))*P.words+w];
  A[O[row]*P.words+w]^=v;
 }
}
kernel void eliminate_mapped_vec(device uint4*A [[buffer(0)]],device const uint*S [[buffer(1)]],
 device const uint*pc [[buffer(2)]],device const uint4*T [[buffer(3)]],device const uint*M [[buffer(4)]],
 constant Params&P [[buffer(5)]],device const uint*O [[buffer(6)]],uint2 pos [[thread_position_in_grid]]) {
 uint i=pos.x,batch=pos.y,groups=MAP_WIDTH/8,words=P.words/4;
 A+=batch*P.rows*words;S+=batch*4;pc+=batch*MAP_WIDTH;T+=batch*groups*256*words;M+=batch*P.rows;O+=batch*P.rows;
 if(!S[3])return;
 uint first=pc[0]/128,tail=words-first;if(i>=P.rows*tail)return;
 uint row=i/tail,mask=M[row],w=first+i%tail;uint4 v=uint4(0);
 if(mask) {
  for(uint block=0;block<(S[3]+7)/8;++block)v^=T[(block*256+((mask>>(8*block))&255))*words+w];
  A[O[row]*words+w]^=v;
 }
}
