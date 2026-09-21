"""Expose disjoint walk buffers as restricted kernel parameters.

Only the packed walk changes. Initialization/reseed still use WalkParams.
The packed engine allocates disjoint x/y/prefix regions, separate live metadata,
and separate report buffers. Every walk access is redirected to the restricted
arguments, including the inlined selection helpers, so there is no second
unrestricted access path to a writable buffer.
"""
import re


FIELDS = {
    "x": ("unsigned", "stateX"),
    "y": ("unsigned", "stateY"),
    "pchain": ("unsigned", "statePrefix"),
    "dead": ("unsigned", "stateDead"),
    "hist": ("unsigned long long", "stateHistory"),
    "seed": ("const unsigned long long", "stateSeed"),
    "startIter": ("const unsigned long long", "stateStart"),
    "dp": ("DpRecord", "reports"),
    "dpCount": ("unsigned", "reportCounts"),
    "twConsts": ("const unsigned", "walkConstants"),
}


def patch(content):
    content = dict(content)
    path = "include/packedkernels.cuh"
    source = content[path]
    begin = source.index("__device__ __forceinline__ void tableSelectSlot(")
    end = source.index("#endif  // ECC_TABLE_FUSED", begin)
    body = source[begin:end]
    params = ", ".join(t + " *__restrict__ " + name for t, name in FIELDS.values())
    args = ", ".join(name for _, name in FIELDS.values())
    for helper in ("tableSelectSlot", "fusedSelect"):
        signature = helper + "(const WalkParams<unsigned> &p,"
        assert body.count(signature) == 1
        body = body.replace(signature, signature + " " + params + ",")
        body = body.replace(helper + "(p,", helper + "(p, " + args + ",")
    signature = "walk(WalkParams<unsigned> p, unsigned *denominators)"
    assert body.count(signature) == 2
    body = body.replace(signature, "walk(WalkParams<unsigned> p, " + params
                        + ", unsigned *__restrict__ denominators)")
    for field, (_, name) in FIELDS.items():
        body = re.sub(r"\bp\." + field + r"\b", name, body)
    assert not any(re.search(r"\bp\." + f + r"\b", body) for f in FIELDS)
    content[path] = source[:begin] + body + source[end:]
    path = "include/packedengine.cuh"
    old = "dynamicSharedBytes()>>>(P, denominators);"
    assert content[path].count(old) == 1
    content[path] = content[path].replace(old, "dynamicSharedBytes()>>>(P, "
        + ", ".join("P." + field for field in FIELDS) + ", denominators);")
    return content
