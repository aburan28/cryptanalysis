"""G6 step (5a): scan every verify/ JSON output for corrections stated on disk.

Hits (written to scan_corrections.json):
  - keys containing correction/corrected/verdict/errat/supersed
  - dicts holding a 'claim*' value next to a recomputed/actual/corrected value that differs
  - 'excess_over_claim_bits' > 0
  - boolean keys named *match* / *agree* / *equal* / *_ok that are false
  - strings mentioning 'claim says', 'not listed', 'overstat', 'understat', 'should be', 'incorrect', 'wrong'
Run: timeout 2400 python3 scan_corrections.py
"""
import json, os, glob, re
HERE = os.path.dirname(os.path.abspath(__file__))
W = "/Volumes/SSD990/ecdlp-hardness-work"
files = sorted(set(glob.glob(W + "/verify/*/*/*.json") + glob.glob(W + "/verify/*/*/raw/*.json")))
KEYPAT = re.compile(r"(correction|corrected|verdict|errat|supersed)", re.I)
STRPAT = re.compile(r"(claim says|not listed|overstat|understat|should be|incorrect|wrong)", re.I)
BOOLPAT = re.compile(r"(match|agree|equal|_ok$|^ok$)", re.I)
hits = []
nfiles = 0

def numdiff(a, b):
    try:
        return abs(float(a) - float(b)) > 1e-9
    except Exception:
        return str(a) != str(b)

def walk(x, path, rel):
    if isinstance(x, dict):
        keys = list(x.keys())
        claim_keys = [k for k in keys if "claim" in str(k).lower() and not isinstance(x[k], (dict, list))]
        for ck in claim_keys:
            for other in keys:
                ol = str(other).lower()
                if other == ck or isinstance(x[other], (dict, list)):
                    continue
                if any(s in ol for s in ("recomputed", "actual", "corrected", "measured")) or \
                   (ol in ("total_log2", "amortized_per_instance_log2") and "claimed" in str(ck).lower()):
                    if numdiff(x[ck], x[other]):
                        hits.append({"type": "claim_vs_recomputed", "file": rel, "path": path, "claim_key": ck, "claim_value": x[ck],
                                     "other_key": other, "other_value": x[other]})
        for k, v in x.items():
            p = path + "/" + str(k)
            if KEYPAT.search(str(k)):
                hits.append({"type": "correction_key", "file": rel, "path": p, "value": v if not isinstance(v, (dict, list)) or len(json.dumps(v)) < 400 else "<large>"})
            if str(k) == "excess_over_claim_bits" and isinstance(v, (int, float)) and v > 0:
                hits.append({"type": "excess_over_claim", "file": rel, "path": p, "value": v,
                             "claimed_total": x.get("claimed_total_sqrtL_log2"), "total": x.get("total_log2"), "scenario": x.get("scenario")})
            if isinstance(v, bool) and v is False and BOOLPAT.search(str(k)):
                hits.append({"type": "false_match_flag", "file": rel, "path": p, "value": v})
            if isinstance(v, str) and STRPAT.search(v):
                hits.append({"type": "text", "file": rel, "path": p, "value": v[:500]})
            if isinstance(k, str) and STRPAT.search(k):
                hits.append({"type": "key_text", "file": rel, "path": p, "value": v if not isinstance(v, (dict, list)) else "<struct>"})
            walk(v, p, rel)
    elif isinstance(x, list):
        for i, v in enumerate(x[:2000]):
            if isinstance(v, str) and STRPAT.search(v):
                hits.append({"type": "text", "file": rel, "path": path + "[%d]" % i, "value": v[:500]})
            walk(v, path + "[%d]" % i, rel)

for f in files:
    if os.path.getsize(f) > 5_000_000:
        continue
    rel = os.path.relpath(f, W)
    try:
        d = json.load(open(f))
    except Exception as e:
        hits.append({"type": "unparseable", "file": rel, "error": str(e)[:200]})
        continue
    nfiles += 1
    walk(d, "", rel)

by_type = {}
for h in hits:
    by_type[h["type"]] = by_type.get(h["type"], 0) + 1
json.dump({"script": "scan_corrections.py", "n_files_scanned": nfiles, "n_hits": len(hits), "by_type": by_type, "hits": hits},
          open(os.path.join(HERE, "scan_corrections.json"), "w"), indent=1, default=str)
print("files", nfiles, "hits", len(hits), by_type)
