default(parisizemax, 24*10^9);
D=-7*6473^2;
t0=getabstime();
H=polclass(D,5);
t1=getabstime();
print("{\"D\":",D,",\"degree\":",poldegree(H),",\"seconds\":",(t1-t0)/1000.0,",\"max_coeff_bits\":",vecmax(apply(c->if(c,exponent(c)+1,0),Vec(H))),"}");
V=Vec(H);  \\ leading first
M=vector(#V,i,V[#V+1-i]%2);  \\ ascending coefficients mod 2
write("H83-mod2-ascending.txt", M);
for(i=0,poldegree(H), c=polcoef(H,i); s=if(c<0,"-",""); write("H83-gamma2-coefficients.txt", Str(s, Strprintf("%x", abs(c)))));
print("done");
