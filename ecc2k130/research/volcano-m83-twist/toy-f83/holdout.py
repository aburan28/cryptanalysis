import json, random, statistics as st, tournament as t
D=json.load(open("results.json")); rows=D["rows"]
rng=random.Random(D["cand_seed"]); cands=[t.make_candidate(rng) for _ in range(len(rows))]
def ops(r,w): return r["group"]+w*(r["lookup"]+r["la"])
res={}
for s in ("factor_base","rho"):
  for w in (0,0.1,1):
    ms=[st.mean(ops(x,w) for x in r[s]) for r in rows]
    b=min(range(len(rows)),key=lambda i:(ms[i],i))
    fresh=[]
    for sd in range(5000,5012):
      x,C=t.SOLVERS[s](cands[b],sd); assert x==17; fresh.append(C.ops(w))
    # population mean over all candidates (same fresh seeds, sample 200 candidates)
    res[f"{s}@w={w}"]=dict(best_idx=b,tournament=ms[b],holdout=st.mean(fresh),pool_avg=st.mean(ms))
    print(f"{s}@w={w}: best #{b} tournament {ms[b]:.2f} -> fresh seeds {st.mean(fresh):.2f} (pool avg {st.mean(ms):.2f})")
json.dump(res,open("holdout.json","w"),indent=1)
