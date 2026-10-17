import json, statistics as st, collections, tournament as t
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
D=json.load(open("results.json")); rows=D["rows"]; H=json.load(open("holdout.json"))
ops=lambda r,w:r["group"]+w*(r["lookup"]+r["la"])
def fbsize(A,B):
    C=t.Ctr(); add,neg,smul=t.mk(A,C); k=0
    for x in range(t.XB):
        r=(x**3+A*x+B)%t.p; ys=[y for y in range(t.p//2+1) if y*y%t.p==r][:1]
        k+=sum(1 for y in ys if y and add(smul(40,(x,y)),(x,y)) is None)
    return k
models=collections.defaultdict(list)
for r in rows: models[(r["A"],r["B"],r["j"])].append(st.mean(ops(x,1) for x in r["factor_base"]))
fs=[(fbsize(A,B),st.mean(v),j) for (A,B,j),v in models.items()]
fig,ax=plt.subplots(1,2,figsize=(11,4.2))
cols={"factor_base":"#3b6fb6","rho":"#d1495b","bsgs":"#2e8b57"}
for s in ("factor_base","rho","bsgs"):
    ms=[st.mean(ops(x,1) for x in r[s]) for r in rows]
    ax[0].hist(ms,bins=60,alpha=.75,color=cols[s],label=f"{s} (min {min(ms):.1f}, avg {st.mean(ms):.1f})")
ax[0].axvline(H["factor_base@w=1"]["holdout"],color=cols["factor_base"],ls="--",lw=1,label=f"FB winner, fresh seeds {H['factor_base@w=1']['holdout']:.1f}")
ax[0].axvline(H["rho@w=1"]["holdout"],color=cols["rho"],ls="--",lw=1,label=f"rho winner, fresh seeds {H['rho@w=1']['holdout']:.1f}")
ax[0].set_xscale("log"); ax[0].set_xlabel("mean ops per solve over 12 paired seeds (w=1)"); ax[0].set_ylabel("candidates (of 2000)")
ax[0].set_title("Candidate scores by solver"); ax[0].legend(fontsize=7)
for jj,c in zip((7,39,52,56),("#555","#e09f3e","#3b6fb6","#9e2a2b")):
    xs=[f for f,m,j in fs if j==jj]; ys=[m for f,m,j in fs if j==jj]
    ax[1].scatter(xs,ys,s=14,color=c,label=f"j={jj}",alpha=.8)
ax[1].set_xlabel(f"factor-base size (subgroup points with x<{t.XB}, mod ±)"); ax[1].set_ylabel("factor-base mean ops (w=1)")
ax[1].set_title(f"{len(fs)} distinct models: score tracks factor-base size"); ax[1].legend(fontsize=7)
fig.suptitle("E: y²=x³+x²+2x over F₈₃, Q=17G, n=41 — 7-isogenous + rescaled candidates",fontsize=10)
fig.tight_layout(); fig.savefig("tournament.png",dpi=150); fig.savefig("tournament.pdf")
for f,m,j in sorted(fs)[:3]+sorted(fs)[-3:]: print(f,round(m,1),j)
print("sizes by count:",collections.Counter(f for f,_,_ in fs))
