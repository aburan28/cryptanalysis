#!/usr/bin/env python3
"""Inspect the object code of every arm for conditional jumps.

"Branch-free" here means: in the arm's machine code, every conditional jump
(jcc) is a backward loop edge whose flags come from an instruction on a
counter register that is written only by a `mov`/`xor` of a constant and by
`inc`/`dec`/`add`/`sub` of a constant (a fixed trip count), and the function
contains no `call` and no indirect jump.  Selections are and/andn/or
masks (or cmov); no jcc depends on the word.  The check is mechanical and
conservative: any other jcc fails the arm.

usage: asm_check.py <binary> <out.json>
"""
import json
import re
import subprocess
import sys

ARMS = ["refine_bf", "exhaustive_bf", "gap_scan", "lift_scan", "exhaustive", "null"]
REQUIRED_BRANCH_FREE = {"refine_bf", "exhaustive_bf"}

LINE = re.compile(r"^\s+([0-9a-f]+):\s+(\S+)\s*(.*)$")


def disasm(binary, sym):
    out = subprocess.run(
        ["objdump", "-d", "--no-show-raw-insn", "-M", "intel", f"--disassemble={sym}", binary],
        check=True, capture_output=True, text=True).stdout
    body, on = [], False
    for ln in out.splitlines():
        if ln.startswith(f"{0:016x}"[:0]) and ln.rstrip().endswith(f"<{sym}>:"):
            on = True
            continue
        if on:
            m = LINE.match(ln)
            if m:
                body.append((int(m.group(1), 16), m.group(2), m.group(3).split("#")[0].strip()))
            elif ln.strip() == "" and body:
                break
    return body


REG64 = {"rax": "eax", "rbx": "ebx", "rcx": "ecx", "rdx": "edx", "rsi": "esi", "rdi": "edi",
         "rbp": "ebp", "rsp": "esp", **{f"r{i}": f"r{i}d" for i in range(8, 16)}}
ALIAS = {}
for r64, r32 in REG64.items():
    ALIAS[r64] = r64
    ALIAS[r32] = r64


def dest(ops):
    return ALIAS.get(ops.split(",")[0].strip())


def is_imm(s):
    return re.fullmatch(r"-?(0x[0-9a-f]+|\d+)", s.strip()) is not None


def write_ok(mn, ops, reg, in_loop):
    parts = [p.strip() for p in ops.split(",")]
    if mn in ("cmp", "test"):
        return True  # reads only
    if in_loop:
        return mn in ("inc", "dec") or (mn in ("add", "sub") and len(parts) == 2 and is_imm(parts[1]))
    return (mn == "mov" and len(parts) == 2 and is_imm(parts[1])) or (
        mn == "xor" and len(parts) == 2 and ALIAS.get(parts[1]) == reg)


def counter_ok(body, reg, lo, hi):
    """Inside the loop [lo, hi] `reg` is only stepped by constants, and the
    last write to it before the loop is a constant load."""
    for a, mn, ops in body:
        if lo <= a <= hi and dest(ops) == reg and not write_ok(mn, ops, reg, True):
            return False, f"in-loop write {mn} {ops}"
    before = [(a, mn, ops) for a, mn, ops in body if a < lo and dest(ops) == reg
              and mn not in ("cmp", "test")]
    if not before:
        return False, "counter has no constant initialisation"
    a, mn, ops = before[-1]
    if not write_ok(mn, ops, reg, False):
        return False, f"initialised by {mn} {ops}"
    return True, ""


def analyse(binary, arm):
    sym = f"canon131_{arm}"
    body = disasm(binary, sym)
    jcc = [(i, b) for i, b in enumerate(body) if b[1].startswith("j") and b[1] != "jmp"]
    calls = [b for b in body if b[1].startswith("call")]
    indirect = [b for b in body if b[1] == "jmp" and not re.match(r"[0-9a-f]+ <", b[2])]
    report = []
    all_ok = not calls and not indirect
    for i, (addr, mn, ops) in jcc:
        target = int(ops.split()[0], 16)
        # the flag setter: nearest preceding instruction that writes flags
        k = i - 1
        while k >= 0 and body[k][1] in ("mov", "lea", "nop", "movzx", "not"):
            k -= 1
        setter = body[k]
        reg = dest(setter[2]) if setter[1] in ("dec", "inc", "cmp", "sub", "add") else None
        imm_operand = setter[1] in ("dec", "inc") or (
            setter[1] in ("cmp", "sub", "add") and len(setter[2].split(",")) == 2
            and is_imm(setter[2].split(",")[1]))
        ok, why = counter_ok(body, reg, target, addr) if (reg and target < addr) else (False, "flags not from a counter loop")
        loop_edge = target < addr and imm_operand and ok
        all_ok &= loop_edge
        report.append({"addr": hex(addr), "insn": f"{mn} {ops}",
                       "flags_from": f"{setter[1]} {setter[2]}", "backward": target < addr,
                       "fixed_counter_loop_edge": loop_edge, "why_not": "" if loop_edge else why})
    loop = None
    if jcc:
        # body of the hottest loop: from the target of the last backward jcc to it
        back = [b for _, b in jcc if int(b[2].split()[0], 16) < b[0]]
        if back:
            last = back[-1]
            t = int(last[2].split()[0], 16)
            loop = [f"{a:x}: {m} {o}" for a, m, o in body if t <= a <= last[0]]
    return {
        "symbol": sym, "instructions_static": len(body), "conditional_jumps": len(jcc),
        "cmov": sum(1 for b in body if b[1].startswith("cmov")),
        "calls": len(calls), "indirect_jumps": len(indirect),
        "jcc": report, "branch_free_by_definition": bool(all_ok),
        "hot_loop_static_instructions": len(loop) if loop else None, "hot_loop": loop,
    }


def main():
    binary, out = sys.argv[1], sys.argv[2]
    res = {a: analyse(binary, a) for a in ARMS}
    res["definition"] = __doc__.split("usage:")[0].strip()
    res["required_branch_free"] = sorted(REQUIRED_BRANCH_FREE)
    res["pass"] = all(res[a]["branch_free_by_definition"] for a in REQUIRED_BRANCH_FREE)
    json.dump(res, open(out, "w"), indent=1)
    for a in ARMS:
        r = res[a]
        print(f"{a:14s} static={r['instructions_static']:4d} jcc={r['conditional_jumps']:3d} "
              f"cmov={r['cmov']:3d} branch_free={r['branch_free_by_definition']} "
              f"hot_loop={r['hot_loop_static_instructions']}")
    print("PASS" if res["pass"] else "FAIL")
    sys.exit(0 if res["pass"] else 1)


if __name__ == "__main__":
    main()
