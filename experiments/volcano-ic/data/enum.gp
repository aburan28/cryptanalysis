n=19; g=ffgen(2^n,'z); q=2^n; N0=ellcard(ellinit([1,0,0,0,1],g)); tw=2*q+2-N0;
print("N0=",N0," factor ",factor(N0));
t0=getwalltime(); found=List(); b=g^0; e=g;
\\ iterate over all nonzero b via generator powers
o = fforder(e); print("gen order ",o);
x=e; for(i=1,q-1, c=ellcard(ellinit([1,0,0,0,x])); if(c==N0, listput(found,[x,0]), if(c==tw, listput(found,[x,1]))); x*=e; if(i%100000==0, print(i," ",getwalltime()-t0)));
print("count=",#found," ms=",getwalltime()-t0);
write("isoclass19.txt", Vec(found));
