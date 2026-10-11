"""Generate a target-linear W18 all-seed inverse from the audited oracle."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n131_w18_allseed_pair_inverse_20261011/native.cpp"
OUTPUT = HERE / "native.cpp"


def main():
    source = PRIOR.read_text()
    old = """    if(!zero(trace)&&!eq(trace,Fe{1,0,0}))
        throw std::runtime_error("halftrace consistency failure");
"""
    new = """    if(!zero(trace)&&!eq(trace,Fe{1,0,0}))
        throw std::runtime_error("halftrace consistency failure");
    Fe target_constant{};
    std::vector<Fe> scaled_seeds;
    if(zero(trace)){
        std::array<Fe,18> target_basis{};
        for(int i=0;i<18;++i)target_basis[i]=field.mul(hbasis[i],inverse_c);
        target_constant=field.mul(hc,inverse_c);
        scaled_seeds.resize(262144);
        for(int s=1;s<262144;++s){
            int low=s&-s,index=__builtin_ctz(unsigned(low));
            scaled_seeds[s]=xo(scaled_seeds[s^low],target_basis[index]);
        }
    }
"""
    assert source.count(old) == 1
    source = source.replace(old, new)
    old = """        for(int root=0;root<2;++root){
            Fe product=field.mul(xo(h,Fe{uint64_t(root),0,0}),inverse_c);
"""
    new = """        Fe product_zero=xo(target_constant,scaled_seeds[s]);
        for(int root=0;root<2;++root){
            Fe product=root?xo(product_zero,inverse_c):product_zero;
"""
    assert source.count(old) == 1
    source = source.replace(old, new)
    assert "field.mul(xo(h,Fe{uint64_t(root),0,0}),inverse_c)" not in source
    with OUTPUT.open("x") as stream:
        stream.write(source)
    print(OUTPUT)


if __name__ == "__main__":
    main()
