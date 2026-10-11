"""Copy the frozen inverse and replace only its N131 field multiply call."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = Path("/Volumes/SSD990/cryptanalysis/experiments/ecc2k130-ic-goal-20260929/n131_w15_rotated_fouratom_inverse_20261010/native.cpp")
source = OLD.read_text()
after = "static Fe xo(Fe a,Fe b){return {a.lo^b.lo,a.mid^b.mid,a.hi^b.hi};}\n"
assert source.count(after) == 1
source = source.replace(after, after + '#include "field_fast.hpp"\n')
old = """    Fe mul(Fe a,Fe b)const{
        Fe result{};
        for(int i=0;i<n;++i){
            if(bit(a,i))result=xo(result,b);
            b=xmul(b);
        }
        return result;
    }
"""
new = old.replace("        Fe result{};", "        if(n==131)return mul131_fast(a,b);\n        Fe result{};")
assert source.count(old) == 1
source = source.replace(old, new)
(HERE / "native_fast.cpp").write_text(source)
