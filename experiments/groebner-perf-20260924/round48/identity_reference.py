"""Independent equation-by-equation Boolean product and grouped reference formulas."""
def multiply_by_equation(y,equations,features,coefficients,witness):
    # Independent Boolean multiplication, one equation at a time. There is no
    # grouping by the output coefficient and no parity identity is assumed.
    polynomial=0
    for equation in range(equations):
        for mask,coefficient in zip(features,coefficients):
            if not (coefficient>>equation)&1:continue
            for slot,u in enumerate(witness):
                if (u>>equation)&1:
                    multiplier=0 if slot==0 else 1<<(slot-1)
                    polynomial^=1<<(mask|multiplier)
    return polynomial


def grouped(y,features,coefficients,witness,factor=False):
    original=dict(zip(features,coefficients))
    polynomial=0
    for mask in range(1<<y):
        if mask.bit_count()>3:continue
        coefficient=original.get(mask,0)
        active=[i for i in range(y) if mask&(1<<i)]
        if factor:
            u=witness[0]
            for i in active:u^=witness[i+1]
            value=u&coefficient
            for i in active:value^=witness[i+1]&original.get(mask^(1<<i),0)
        else:
            value=witness[0]&coefficient
            for i in active:value^=witness[i+1]&(coefficient^original.get(mask^(1<<i),0))
        polynomial|=(value.bit_count()&1)<<mask
    return polynomial

