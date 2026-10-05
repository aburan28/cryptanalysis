\\ G6 step (6): minimal independent check of the pairing-transfer claim C3,
\\ reduced 263-Tate pairing t_263(P, Q_N) = 1  (P in E[263], Q_N of order N),
\\ on E0, A000 and B000 over L = F_{q^2} = F_{2^262}.  Plain PARI/GP only: no Sage,
\\ no sweep code.  Replaces the unfinished verify/pairing-transfer/C3-audit/t1.gp,
\\ which only built F_{2^262} and point-counted and never evaluated a pairing.
\\
\\ PARI's elltatepairing returns the unreduced Miller value (checked on a toy curve
\\ over F_{2^10}: 20/20 values had v^m != 1), so the final exponentiation
\\ (q^2-1)/263 is applied here.
\\ Inputs: pairing_c3_inputs.gp (LABS, BINT, JINT copied from ground_truth.json by
\\ run_pairing_c3.py).  Output: lines "RES <label> <key> <value>" parsed by the runner.

default(parisize, 400000000);
setrand(20260924);
read("pairing_c3_inputs.gp");
q = 2^131; t = -22283658519494248867;
N = (q + 1 - t) / 4; CL = (q + 1 - t) * (q + 1 + t); QL = q^2; ell = 263;
EXP = (QL - 1) / ell;
print("RES global N_is_prime ", isprime(N));
print("RES global v263_CL ", valuation(CL, ell));
print("RES global QL_minus_1_div_263 ", (QL - 1) % ell == 0);
print("RES global gcd_N_263 ", gcd(N, ell));
T = ffinit(2, 262, 'w); w = ffgen(T, 'w);
fq = x^131 + x^13 + x^2 + x + 1;
print("RES global fq_irreducible_mod2 ", polisirreducible(fq * Mod(1, 2)));
rr = polrootsmod(fq, [T, 2]);
r = subst(lift(lift(rr[1])), 'w, w);
print("RES global embedding_root_ok ", subst(fq, x, r) == 0);
rp = vector(131, i, r^(i - 1));
emb(n) = my(s = 0 * w); for(i = 0, 130, if(bittest(n, i), s += rp[i + 1])); s;
toF2(n) = Mod(Pol(binary(n), 'x) * Mod(1, 2), fq * Mod(1, 2));
fromF2(m) = subst(lift(lift(m)), 'x, 2);
\\ the embedding is a ring homomorphism F_2[z]/(fq) -> L (20 random products and sums)
homok = 1;
for(i = 1, 20, a = random(2^131); b = random(2^131); \
   if(emb(fromF2(toF2(a) * toF2(b))) != emb(a) * emb(b), homok = 0); \
   if(emb(bitxor(a, b)) != emb(a) + emb(b), homok = 0));
print("RES global embedding_ring_hom_20_pairs ", homok);

tate(E, P, Q) = elltatepairing(E, P, Q, ell)^EXP;
frobpt(Pt) = if(Pt == [0], Pt, [Pt[1]^q, Pt[2]^q]);

docurve(lab, bint, jint) =
{
  my(E, b, tt, c, h, S1, S2, P, Tw, QN, QN2, v, allone, nd, wp, hasfull, S, cnt);
  tt = getabstime();
  b = emb(bint);
  E = ellinit([1, 0, 0, 0, b]);
  print("RES ", lab, " j_matches_ground_truth ", E.j == emb(jint));
  print("RES ", lab, " b_times_j_is_1 ", b * emb(jint) == 1);
  c = ellcard(E);
  print("RES ", lab, " card_L_equals_(q+1-t)(q+1+t) ", c == CL);
  h = CL / ell^2;
  \\ Q_N: points of exact order N (N prime; [N]Q = O and Q != O)
  QN = [0]; while(QN == [0], QN = ellmul(E, random(E), CL / N));
  QN2 = [0]; while(QN2 == [0], QN2 = ellmul(E, random(E), CL / N));
  print("RES ", lab, " QN_order_N ", ellmul(E, QN, N) == [0] && ellmul(E, QN2, N) == [0]);
  \\ 263-Sylow: E0 -> (Z/263)^2 (two points with Weil pairing != 1); floor -> cyclic Z/263^2
  S1 = [0]; while(S1 == [0], S1 = ellmul(E, random(E), h));
  hasfull = 0; cnt = 0;
  while(cnt < 30 && !hasfull, cnt++; S = [0]; while(S == [0], S = ellmul(E, random(E), h)); \
        if(ellmul(E, S, ell) != [0], hasfull = 1; S1 = S));
  if(hasfull,
     print("RES ", lab, " sylow263 Z/263^2_cyclic");
     P = ellmul(E, S1, ell);
     Tw = S1,
     \\ no point of order 263^2 among 30 samples: expect (Z/263)^2
     S2 = [0]; wp = 1; cnt = 0;
     while(wp == 1 && cnt < 30, cnt++; S2 = [0]; while(S2 == [0], S2 = ellmul(E, random(E), h)); \
           wp = ellweilpairing(E, S1, S2, ell));
     print("RES ", lab, " sylow263 ", if(wp != 1 && wp^ell == 1, "(Z/263)^2", "undetermined"));
     P = S1;
     Tw = [0];
     foreach([S1, S2, elladd(E, S1, S2), elladd(E, S1, ellmul(E, S2, 2))], U, if(Tw == [0] && tate(E, P, U) != 1, Tw = U)));
  print("RES ", lab, " P_order_263 ", P != [0] && ellmul(E, P, ell) == [0]);
  print("RES ", lab, " frobenius_acts_as_minus1_on_P ", frobpt(P) == ellneg(E, P));
  \\ the claim: t_263(P, Q_N) = 1 for several Q_N and several P
  allone = 1;
  foreach([QN, QN2, ellmul(E, QN, 12345), elladd(E, QN, QN2)], Q, if(tate(E, P, Q) != 1, allone = 0));
  foreach([ellmul(E, P, 2), ellmul(E, P, 100)], PP, if(tate(E, PP, QN) != 1, allone = 0));
  print("RES ", lab, " tate_P_QN_all_1 ", allone);
  \\ controls: the reduced pairing is non-trivial on the 263-part, invariant under +Q_N, bilinear
  if(Tw == [0], print("RES ", lab, " nondegenerate_witness_found 0"),
     v = tate(E, P, Tw);
     print("RES ", lab, " nondegenerate_witness_found 1");
     print("RES ", lab, " tate_P_T_ne_1 ", v != 1);
     print("RES ", lab, " tate_value_is_263rd_root_of_unity ", v^ell == 1);
     print("RES ", lab, " shift_invariant_T_plus_QN ", tate(E, P, elladd(E, Tw, QN)) == v);
     print("RES ", lab, " bilinear_second_slot ", tate(E, P, ellmul(E, Tw, 2)) == v^2);
     print("RES ", lab, " bilinear_first_slot ", tate(E, ellmul(E, P, 3), Tw) == v^3));
  print("RES ", lab, " seconds ", (getabstime() - tt) / 1000.);
}

for(i = 1, #LABS, docurve(LABS[i], BINT[i], JINT[i]));
print("RES global done 1");
quit;
