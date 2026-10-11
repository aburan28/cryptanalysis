q=2^131
t=-22283658519494248867
p=146505763881528721
N=680564733841876926932320129493409985129
f=263*p
assert t^2-4*q==-7*f^2
print("p prime",is_prime(p), "log2 p", RR(log(p,2)))
print("(-7|p)", kronecker(-7,p))
c=Mod(t,p)/2
print("c",c, "c^2==q", c^2==Mod(q,p))
print("p-1 factor", factor(p-1))
r=c.multiplicative_order(); print("r=ord_p(c)",r, factor(r), RR(log(r,2)))
print("ord_p(2)", Mod(2,p).multiplicative_order())
print("ord_p(q)", Mod(q,p).multiplicative_order())
print("-1 in <c>?", r%2==0 and c^(r//2)==-1)
