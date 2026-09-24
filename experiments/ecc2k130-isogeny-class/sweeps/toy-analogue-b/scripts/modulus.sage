R.<x>=GF(2)[]
tri=[k for k in range(1,179) if (x^179+x^k+1).is_irreducible()]
print('trinomials x^179+x^k+1 irreducible for k in',tri)
pent=[]
for k1 in range(1,20):
  for k2 in range(1,k1):
    for k3 in range(1,k2):
      if (x^179+x^k1+x^k2+x^k3+1).is_irreducible(): pent.append((k1,k2,k3))
print('first pentanomials',pent[:5])
print('ord_359(2)=',Mod(2,359).multiplicative_order(), ' 359 mod 8 =',359%8, ' kron(-7,359)=',kronecker(-7,359))
