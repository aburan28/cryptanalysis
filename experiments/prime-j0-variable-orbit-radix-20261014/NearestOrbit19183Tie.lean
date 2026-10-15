import NearestOrbit19183Digits

namespace NearestOrbit19183Tie
open NearestOrbit19183Selector
open SplitPrime12211Nearest

-- Match the runtime key (norm, |b|, |a|, a, b), with first occurrence
-- retained when two keys are equal.
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

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_0 :
    (List.range 512).all (fun j => scoreCheck (0+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_1 :
    (List.range 512).all (fun j => scoreCheck (512+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_2 :
    (List.range 512).all (fun j => scoreCheck (1024+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_3 :
    (List.range 512).all (fun j => scoreCheck (1536+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_4 :
    (List.range 512).all (fun j => scoreCheck (2048+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_5 :
    (List.range 512).all (fun j => scoreCheck (2560+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_6 :
    (List.range 512).all (fun j => scoreCheck (3072+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_7 :
    (List.range 512).all (fun j => scoreCheck (3584+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_8 :
    (List.range 512).all (fun j => scoreCheck (4096+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_9 :
    (List.range 512).all (fun j => scoreCheck (4608+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_10 :
    (List.range 512).all (fun j => scoreCheck (5120+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_11 :
    (List.range 512).all (fun j => scoreCheck (5632+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_12 :
    (List.range 512).all (fun j => scoreCheck (6144+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_13 :
    (List.range 512).all (fun j => scoreCheck (6656+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_14 :
    (List.range 512).all (fun j => scoreCheck (7168+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_15 :
    (List.range 512).all (fun j => scoreCheck (7680+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_16 :
    (List.range 512).all (fun j => scoreCheck (8192+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_17 :
    (List.range 512).all (fun j => scoreCheck (8704+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_18 :
    (List.range 376).all (fun j => scoreCheck (9216+j)) = true := by decide

theorem score_selected_eq (r : Nat) (hr : r < 9592) :
    scoreDigit r = selectedDigit r := by
  by_cases h0 : r < 512
  · have hstart : 0 ≤ r := by omega
    have hi : r-0 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_0) (r-0)
      (List.mem_range.mpr hi)
    have heq : 0+(r-0) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h1 : r < 1024
  · have hstart : 512 ≤ r := by omega
    have hi : r-512 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_1) (r-512)
      (List.mem_range.mpr hi)
    have heq : 512+(r-512) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h2 : r < 1536
  · have hstart : 1024 ≤ r := by omega
    have hi : r-1024 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_2) (r-1024)
      (List.mem_range.mpr hi)
    have heq : 1024+(r-1024) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h3 : r < 2048
  · have hstart : 1536 ≤ r := by omega
    have hi : r-1536 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_3) (r-1536)
      (List.mem_range.mpr hi)
    have heq : 1536+(r-1536) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h4 : r < 2560
  · have hstart : 2048 ≤ r := by omega
    have hi : r-2048 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_4) (r-2048)
      (List.mem_range.mpr hi)
    have heq : 2048+(r-2048) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h5 : r < 3072
  · have hstart : 2560 ≤ r := by omega
    have hi : r-2560 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_5) (r-2560)
      (List.mem_range.mpr hi)
    have heq : 2560+(r-2560) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h6 : r < 3584
  · have hstart : 3072 ≤ r := by omega
    have hi : r-3072 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_6) (r-3072)
      (List.mem_range.mpr hi)
    have heq : 3072+(r-3072) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h7 : r < 4096
  · have hstart : 3584 ≤ r := by omega
    have hi : r-3584 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_7) (r-3584)
      (List.mem_range.mpr hi)
    have heq : 3584+(r-3584) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h8 : r < 4608
  · have hstart : 4096 ≤ r := by omega
    have hi : r-4096 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_8) (r-4096)
      (List.mem_range.mpr hi)
    have heq : 4096+(r-4096) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h9 : r < 5120
  · have hstart : 4608 ≤ r := by omega
    have hi : r-4608 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_9) (r-4608)
      (List.mem_range.mpr hi)
    have heq : 4608+(r-4608) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h10 : r < 5632
  · have hstart : 5120 ≤ r := by omega
    have hi : r-5120 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_10) (r-5120)
      (List.mem_range.mpr hi)
    have heq : 5120+(r-5120) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h11 : r < 6144
  · have hstart : 5632 ≤ r := by omega
    have hi : r-5632 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_11) (r-5632)
      (List.mem_range.mpr hi)
    have heq : 5632+(r-5632) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h12 : r < 6656
  · have hstart : 6144 ≤ r := by omega
    have hi : r-6144 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_12) (r-6144)
      (List.mem_range.mpr hi)
    have heq : 6144+(r-6144) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h13 : r < 7168
  · have hstart : 6656 ≤ r := by omega
    have hi : r-6656 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_13) (r-6656)
      (List.mem_range.mpr hi)
    have heq : 6656+(r-6656) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h14 : r < 7680
  · have hstart : 7168 ≤ r := by omega
    have hi : r-7168 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_14) (r-7168)
      (List.mem_range.mpr hi)
    have heq : 7168+(r-7168) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h15 : r < 8192
  · have hstart : 7680 ≤ r := by omega
    have hi : r-7680 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_15) (r-7680)
      (List.mem_range.mpr hi)
    have heq : 7680+(r-7680) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h16 : r < 8704
  · have hstart : 8192 ≤ r := by omega
    have hi : r-8192 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_16) (r-8192)
      (List.mem_range.mpr hi)
    have heq : 8192+(r-8192) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h17 : r < 9216
  · have hstart : 8704 ≤ r := by omega
    have hi : r-8704 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_17) (r-8704)
      (List.mem_range.mpr hi)
    have heq : 8704+(r-8704) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  have hstart : 9216 ≤ r := by omega
  have hi : r-9216 < 376 := by omega
  have hc := (List.all_eq_true.mp chunk_18) (r-9216)
    (List.mem_range.mpr hi)
  have heq : 9216+(r-9216) = r := by omega
  rw [heq] at hc
  exact of_decide_eq_true (by simpa [scoreCheck] using hc)

#print axioms score_selected_eq
end NearestOrbit19183Tie
