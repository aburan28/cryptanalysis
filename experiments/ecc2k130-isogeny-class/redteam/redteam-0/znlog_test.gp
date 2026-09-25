N=680564733841876926932320129493409985129;
g=znprimroot(N);
print(g);
x=Mod(11,N);
t0=getabstime(); d=znlog(x,g); print(d, " ms=", getabstime()-t0);
print(g^d==x);
quit
