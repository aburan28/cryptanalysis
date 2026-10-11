"""Add byte-table squaring to the carryless-multiply native inverse."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
source = (HERE / "native_fast.cpp").read_text()
old_member = "    std::array<Fe,131> square_basis{};\n"
assert source.count(old_member) == 1
source = source.replace(old_member, old_member +
                        "    std::array<std::array<Fe,256>,17> square_byte{};\n")
old_init = "        for(int i=1;i<n;++i)square_basis[i]=xmul(xmul(square_basis[i-1]));\n"
new_init = old_init + """        if(n==131) for(int chunk=0;chunk<17;++chunk)
            for(int mask=1;mask<256;++mask){
                int low=__builtin_ctz(unsigned(mask));
                int index=8*chunk+low;
                square_byte[chunk][mask]=xo(square_byte[chunk][mask&(mask-1)],
                                              index<n?square_basis[index]:Fe{});
            }
"""
assert source.count(old_init) == 1
source = source.replace(old_init, new_init)
old_sq = """    Fe sq(Fe a)const{
        Fe result{};
        for(int limb=0;limb<3;++limb){
            uint64_t word=limb==0?a.lo:limb==1?a.mid:a.hi;
            while(word){
                int offset=__builtin_ctzll(word),index=limb*64+offset;
                if(index<n)result=xo(result,square_basis[index]);
                word&=word-1;
            }
        }
        return result;
    }
"""
new_sq = old_sq.replace("        Fe result{};", """        Fe result{};
        if(n==131){
            for(int i=0;i<8;++i)result=xo(result,square_byte[i][(a.lo>>(8*i))&255]);
            for(int i=0;i<8;++i)result=xo(result,square_byte[i+8][(a.mid>>(8*i))&255]);
            return xo(result,square_byte[16][a.hi&7]);
        }
""")
assert source.count(old_sq) == 1
source = source.replace(old_sq, new_sq)
(HERE / "native_fast_sq.cpp").write_text(source)
