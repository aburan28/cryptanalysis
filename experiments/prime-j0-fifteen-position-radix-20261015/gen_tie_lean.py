#!/usr/bin/env python3
"""Generate bounded Lean certificates for the exact runtime tie-rule selector."""
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIMIT = 35512
CHUNK = 512

HEADER = '''import NearestOrbit71023Digits

namespace NearestOrbit71023Tie
open NearestOrbit71023Selector
open SplitPrime12211Nearest

-- Runtime key (norm, |b|, |a|, a, b), retaining the first equal key.
def better (p q : Int × Int) : Bool :=
  let np := nrm p.1 p.2
  let nq := nrm q.1 q.2
  if np != nq then decide (np < nq)
  else if p.2.natAbs != q.2.natAbs then decide (p.2.natAbs < q.2.natAbs)
  else if p.1.natAbs != q.1.natAbs then decide (p.1.natAbs < q.1.natAbs)
  else if p.1 != q.1 then decide (p.1 < q.1)
  else decide (p.2 < q.2)

def scorePick (p q : Int × Int) : Int × Int :=
  if better q p then q else p

def scoreDigit (r : Nat) : Int × Int :=
  match candidates r with
  | [] => (0, 0)
  | p :: ps => ps.foldl scorePick p

def scoreCheck (r : Nat) : Bool :=
  decide (scoreDigit r = selectedDigit r)

'''


def main():
    pieces = [HEADER]
    for i,start in enumerate(range(0,LIMIT,CHUNK)):
        count = min(CHUNK,LIMIT-start)
        pieces.append(f'''set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_{i} :
    (List.range {count}).all (fun j => scoreCheck ({start}+j)) = true := by decide

''')
    pieces.append(f'''theorem score_selected_eq (r : Nat) (hr : r < {LIMIT}) :
    scoreDigit r = selectedDigit r := by
''')
    starts = list(range(0,LIMIT,CHUNK))
    for i,start in enumerate(starts):
        count = min(CHUNK,LIMIT-start)
        if i < len(starts)-1:
            pieces.append(f'''  by_cases h{i} : r < {start+count}
  · have hstart : {start} ≤ r := by omega
    have hi : r-{start} < {count} := by omega
    have hc := (List.all_eq_true.mp chunk_{i}) (r-{start})
      (List.mem_range.mpr hi)
    have heq : {start}+(r-{start}) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
''')
        else:
            pieces.append(f'''  have hstart : {start} ≤ r := by omega
  have hi : r-{start} < {count} := by omega
  have hc := (List.all_eq_true.mp chunk_{i}) (r-{start})
    (List.mem_range.mpr hi)
  have heq : {start}+(r-{start}) = r := by omega
  rw [heq] at hc
  exact of_decide_eq_true (by simpa [scoreCheck] using hc)

''')
    pieces.append('#print axioms score_selected_eq\nend NearestOrbit71023Tie\n')
    output = ''.join(pieces)
    path = HERE / 'NearestOrbit71023Tie.lean'
    path.write_text(output)
    print(sha256(output.encode()).hexdigest(),len(starts),'chunks')


if __name__ == '__main__':
    main()
