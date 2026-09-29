// Concatenated after round7/local_panel.metal. PANEL_WIDTH is 16 or 32.
// Prefixes of every active row are zero. Retain only rows [r,rows) and
// words [floor(c/32),words); construct earlier-row masks after the panel.
kernel void panel_active(device uint*A [[buffer(0)]], device uint*S [[buffer(1)]],
 device uint*pc [[buffer(2)]], device uint*M [[buffer(4)]], constant Params&P [[buffer(5)]],
 constant uint&capacity [[buffer(6)]], device uint*hist [[buffer(7)]], device uint*dispatch [[buffer(8)]],
 uint t [[thread_index_in_threadgroup]], uint2 group [[threadgroup_position_in_grid]],
 uint lane [[thread_index_in_simdgroup]], threadgroup uint*scratch [[threadgroup(0)]]) {
 uint batch=group.y;
 A+=batch*P.rows*P.words; S+=batch*4; pc+=batch*PANEL_WIDTH;
 M+=batch*P.rows; hist+=batch*2;
 const uint r=S[0],initial_c=S[1];
 threadgroup uint c,k,chosen,coeff,column_bits,pivots[PANEL_WIDTH];
 threadgroup uint pivot_columns[PANEL_WIDTH],transforms[PANEL_WIDTH];
 threadgroup atomic_uint best;
 if(t==0){
  c=initial_c;k=0;S[2]=r;S[3]=0;
  if(P.count==1){dispatch[0]=0;dispatch[1]=1;dispatch[2]=1;dispatch[3]=0;dispatch[4]=1;dispatch[5]=1;}
 }
 threadgroup_barrier(mem_flags::mem_threadgroup);
 if(r>=P.rows || initial_c>=P.cols)return;
 const uint active=P.rows-r, first=initial_c/32, words=P.words-first;
 // Host admits only shapes where at least 16 pivots fit at the first panel.
 // Active rows/words only shrink, so this bound remains true thereafter.
 const uint width=min(uint(PANEL_WIDTH),((capacity-2*active)/words)/16*16);
 threadgroup uint*columns=scratch;
 threadgroup uint*masks=scratch+active;
 threadgroup uint*B=scratch+2*active;
 for(uint row=t;row<active;row+=PIVOT_THREADS)masks[row]=0;
 threadgroup_barrier(mem_flags::mem_threadgroup);
 uint cached_word=0xffffffffu;
 while(k<width && r+k<P.rows && c<P.cols) {
  if(cached_word!=c/32) {
   for(uint row=t;row<active;row+=PIVOT_THREADS)
    columns[row]=row<k?B[row*words+c/32-first]:A[(r+row)*P.words+c/32];
   threadgroup_barrier(mem_flags::mem_threadgroup);
   cached_word=c/32;
  }
  if(t==0) {
   atomic_store_explicit(&best,active,memory_order_relaxed);
   column_bits=0;
   for(uint j=0;j<k;++j)column_bits|=((B[j*words+c/32-first]>>(c%32))&1u)<<j;
  }
  threadgroup_barrier(mem_flags::mem_threadgroup);
  uint local_best=active;
  for(uint row=k+t;row<active;row+=PIVOT_THREADS) {
   uint bit=((columns[row]>>(c%32))&1u)^(popcount(masks[row]&column_bits)&1u);
   if(bit)local_best=min(local_best,row);
  }
  local_best=simd_min(local_best);
  if(lane==0)atomic_fetch_min_explicit(&best,local_best,memory_order_relaxed);
  threadgroup_barrier(mem_flags::mem_threadgroup);
  if(t==0)chosen=atomic_load_explicit(&best,memory_order_relaxed);
  threadgroup_barrier(mem_flags::mem_threadgroup);
  if(chosen<active) {
   const uint panel_k=k;
   for(uint w=t;w<words;w+=PIVOT_THREADS) {
    B[k*words+w]=A[(r+chosen)*P.words+first+w];
    A[(r+chosen)*P.words+first+w]=A[(r+k)*P.words+first+w];
   }
   if(t==0) {
    uint v=masks[k];masks[k]=masks[chosen];masks[chosen]=v;
    v=columns[k];columns[k]=columns[chosen];columns[chosen]=v;
   }
   threadgroup_barrier(mem_flags::mem_threadgroup | mem_flags::mem_device);
   if(t==0)coeff=masks[k];
   threadgroup_barrier(mem_flags::mem_threadgroup);
   for(uint w=t;w<words;w+=PIVOT_THREADS) {
    uint v=B[k*words+w];
    uint mask=coeff;
    while(mask){uint j=ctz(mask);v^=B[j*words+w];mask&=mask-1;}
    B[k*words+w]=v;
   }
   threadgroup_barrier(mem_flags::mem_threadgroup);
   // B stays in forward echelon form and its previous rows never change.
   // Masks are forward-elimination coefficients, not raw pivot-column bits.
   for(uint row=panel_k+1+t;row<active;row+=PIVOT_THREADS) {
    uint bit=((columns[row]>>(c%32))&1u)^(popcount(masks[row]&column_bits)&1u);
    masks[row]|=bit<<panel_k;
   }
   if(t==0){pivots[k]=c;k++;}
   threadgroup_barrier(mem_flags::mem_threadgroup);
  }
  if(t==0)c++;
  threadgroup_barrier(mem_flags::mem_threadgroup);
 }
 // Invert the unit upper-triangular pivot submatrix. Each transform gives
 // one canonical panel row as a combination of immutable forward rows.
 for(uint col=t;col<k;col+=PIVOT_THREADS) {
  uint bits=0;
  for(uint row=0;row<=col;++row)bits|=((B[row*words+pivots[col]/32-first]>>(pivots[col]%32))&1u)<<row;
  pivot_columns[col]=bits;
 }
 threadgroup_barrier(mem_flags::mem_threadgroup);
 for(uint row=t;row<k;row+=PIVOT_THREADS) {
  uint mask=1u<<row;
  for(uint col=row+1;col<k;++col)mask|=(popcount(mask&pivot_columns[col])&1u)<<col;
  transforms[row]=mask;
 }
 threadgroup_barrier(mem_flags::mem_threadgroup);
 for(uint index=t;index<k*words;index+=PIVOT_THREADS) {
  uint v=0,mask=transforms[index/words],w=index%words;
  while(mask){uint j=ctz(mask);v^=B[j*words+w];mask&=mask-1;}
  A[(r+index/words)*P.words+first+w]=v;
 }
 // Each final panel is identity on its pivot columns. Untouched earlier
 // rows therefore have exactly these raw bits as elimination coefficients.
 for(uint row=t;row<P.rows;row+=PIVOT_THREADS) {
  if(row>=r && row<r+k){M[row]=0;continue;}
  uint mask=0;
  for(uint j=0;j<k;++j)mask|=((A[row*P.words+pivots[j]/32]>>(pivots[j]%32))&1u)<<j;
  M[row]=mask;
 }
 for(uint j=t;j<k;j+=PIVOT_THREADS)pc[j]=pivots[j];
 if(t==0){
  S[0]=r+k;S[1]=c;S[2]=r;S[3]=k;hist[width/16-1]++;
  if(P.count==1 && k) {
   uint scale=P.words%4==0?4:1;
   uint tail=P.words/scale-pivots[0]/(32*scale);
   dispatch[0]=(((k+7)/8)*256*tail+255)/256;
   dispatch[3]=(P.rows*tail+255)/256;
  }
 }
}

// Actual panel width varies. Do not build or read unused table blocks.
kernel void table_active(device const uint*A [[buffer(0)]],device const uint*S [[buffer(1)]],
 device const uint*pc [[buffer(2)]],device uint*T [[buffer(3)]],constant Params&P [[buffer(5)]],
 uint2 pos [[thread_position_in_grid]]) {
 uint i=pos.x,batch=pos.y,groups=(PANEL_WIDTH+7)/8;
 A+=batch*P.rows*P.words;S+=batch*4;pc+=batch*PANEL_WIDTH;T+=batch*groups*256*P.words;
 if(!S[3])return;
 uint first=pc[0]/32,tail=P.words-first;
 if(i>=((S[3]+7)/8)*256*tail)return;
 uint block=i/(256*tail),mask=(i/tail)%256,w=first+i%tail,v=0;
 for(uint j=block*8;j<min(S[3],block*8+8);++j)
  if((mask>>(j-block*8))&1u)v^=A[(S[2]+j)*P.words+w];
 T[(block*256+mask)*P.words+w]=v;
}
kernel void eliminate_active(device uint*A [[buffer(0)]],device const uint*S [[buffer(1)]],
 device const uint*pc [[buffer(2)]],device const uint*T [[buffer(3)]],device const uint*M [[buffer(4)]],
 constant Params&P [[buffer(5)]],uint2 pos [[thread_position_in_grid]]) {
 uint i=pos.x,batch=pos.y,groups=(PANEL_WIDTH+7)/8;
 A+=batch*P.rows*P.words;S+=batch*4;pc+=batch*PANEL_WIDTH;
 T+=batch*groups*256*P.words;M+=batch*P.rows;
 if(!S[3])return;
 uint first=pc[0]/32,tail=P.words-first;
 if(i>=P.rows*tail)return;
 uint mask=M[i/tail];
 if(mask) {
  uint v=0,w=first+i%tail;
  for(uint block=0;block<(S[3]+7)/8;++block)v^=T[(block*256+((mask>>(8*block))&255))*P.words+w];
  A[(i/tail)*P.words+w]^=v;
 }
}
kernel void table_active_vec(device const uint4*A [[buffer(0)]],device const uint*S [[buffer(1)]],
 device const uint*pc [[buffer(2)]],device uint4*T [[buffer(3)]],constant Params&P [[buffer(5)]],
 uint2 pos [[thread_position_in_grid]]) {
 uint i=pos.x,batch=pos.y,groups=(PANEL_WIDTH+7)/8,words=P.words/4;
 A+=batch*P.rows*words;S+=batch*4;pc+=batch*PANEL_WIDTH;T+=batch*groups*256*words;
 if(!S[3])return;
 uint first=pc[0]/128,tail=words-first;
 if(i>=((S[3]+7)/8)*256*tail)return;
 uint block=i/(256*tail),mask=(i/tail)%256,w=first+i%tail;
 uint4 v=uint4(0);
 for(uint j=block*8;j<min(S[3],block*8+8);++j)
  if((mask>>(j-block*8))&1u)v^=A[(S[2]+j)*words+w];
 T[(block*256+mask)*words+w]=v;
}
kernel void eliminate_active_vec(device uint4*A [[buffer(0)]],device const uint*S [[buffer(1)]],
 device const uint*pc [[buffer(2)]],device const uint4*T [[buffer(3)]],device const uint*M [[buffer(4)]],
 constant Params&P [[buffer(5)]],uint2 pos [[thread_position_in_grid]]) {
 uint i=pos.x,batch=pos.y,groups=(PANEL_WIDTH+7)/8,words=P.words/4;
 A+=batch*P.rows*words;S+=batch*4;pc+=batch*PANEL_WIDTH;
 T+=batch*groups*256*words;M+=batch*P.rows;
 if(!S[3])return;
 uint first=pc[0]/128,tail=words-first;
 if(i>=P.rows*tail)return;
 uint mask=M[i/tail],w=first+i%tail;
 if(mask) {
  uint4 v=uint4(0);
  for(uint block=0;block<(S[3]+7)/8;++block)v^=T[(block*256+((mask>>(8*block))&255))*words+w];
  A[(i/tail)*words+w]^=v;
 }
}
