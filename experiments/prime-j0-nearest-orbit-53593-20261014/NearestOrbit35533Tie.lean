import NearestOrbit35533Digits

namespace NearestOrbit35533Tie
open NearestOrbit35533Selector
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
    (List.range 512).all (fun i => scoreCheck (0+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_1 :
    (List.range 512).all (fun i => scoreCheck (512+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_2 :
    (List.range 512).all (fun i => scoreCheck (1024+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_3 :
    (List.range 512).all (fun i => scoreCheck (1536+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_4 :
    (List.range 512).all (fun i => scoreCheck (2048+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_5 :
    (List.range 512).all (fun i => scoreCheck (2560+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_6 :
    (List.range 512).all (fun i => scoreCheck (3072+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_7 :
    (List.range 512).all (fun i => scoreCheck (3584+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_8 :
    (List.range 512).all (fun i => scoreCheck (4096+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_9 :
    (List.range 512).all (fun i => scoreCheck (4608+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_10 :
    (List.range 512).all (fun i => scoreCheck (5120+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_11 :
    (List.range 512).all (fun i => scoreCheck (5632+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_12 :
    (List.range 512).all (fun i => scoreCheck (6144+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_13 :
    (List.range 512).all (fun i => scoreCheck (6656+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_14 :
    (List.range 512).all (fun i => scoreCheck (7168+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_15 :
    (List.range 512).all (fun i => scoreCheck (7680+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_16 :
    (List.range 512).all (fun i => scoreCheck (8192+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_17 :
    (List.range 512).all (fun i => scoreCheck (8704+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_18 :
    (List.range 512).all (fun i => scoreCheck (9216+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_19 :
    (List.range 512).all (fun i => scoreCheck (9728+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_20 :
    (List.range 512).all (fun i => scoreCheck (10240+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_21 :
    (List.range 512).all (fun i => scoreCheck (10752+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_22 :
    (List.range 512).all (fun i => scoreCheck (11264+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_23 :
    (List.range 512).all (fun i => scoreCheck (11776+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_24 :
    (List.range 512).all (fun i => scoreCheck (12288+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_25 :
    (List.range 512).all (fun i => scoreCheck (12800+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_26 :
    (List.range 512).all (fun i => scoreCheck (13312+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_27 :
    (List.range 512).all (fun i => scoreCheck (13824+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_28 :
    (List.range 512).all (fun i => scoreCheck (14336+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_29 :
    (List.range 512).all (fun i => scoreCheck (14848+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_30 :
    (List.range 512).all (fun i => scoreCheck (15360+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_31 :
    (List.range 512).all (fun i => scoreCheck (15872+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_32 :
    (List.range 512).all (fun i => scoreCheck (16384+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_33 :
    (List.range 512).all (fun i => scoreCheck (16896+i)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_34 :
    (List.range 359).all (fun i => scoreCheck (17408+i)) = true := by decide

theorem score_selected_eq (r : Nat) (hr : r < 17767) :
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
  by_cases h18 : r < 9728
  · have hstart : 9216 ≤ r := by omega
    have hi : r-9216 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_18) (r-9216)
      (List.mem_range.mpr hi)
    have heq : 9216+(r-9216) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h19 : r < 10240
  · have hstart : 9728 ≤ r := by omega
    have hi : r-9728 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_19) (r-9728)
      (List.mem_range.mpr hi)
    have heq : 9728+(r-9728) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h20 : r < 10752
  · have hstart : 10240 ≤ r := by omega
    have hi : r-10240 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_20) (r-10240)
      (List.mem_range.mpr hi)
    have heq : 10240+(r-10240) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h21 : r < 11264
  · have hstart : 10752 ≤ r := by omega
    have hi : r-10752 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_21) (r-10752)
      (List.mem_range.mpr hi)
    have heq : 10752+(r-10752) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h22 : r < 11776
  · have hstart : 11264 ≤ r := by omega
    have hi : r-11264 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_22) (r-11264)
      (List.mem_range.mpr hi)
    have heq : 11264+(r-11264) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h23 : r < 12288
  · have hstart : 11776 ≤ r := by omega
    have hi : r-11776 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_23) (r-11776)
      (List.mem_range.mpr hi)
    have heq : 11776+(r-11776) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h24 : r < 12800
  · have hstart : 12288 ≤ r := by omega
    have hi : r-12288 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_24) (r-12288)
      (List.mem_range.mpr hi)
    have heq : 12288+(r-12288) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h25 : r < 13312
  · have hstart : 12800 ≤ r := by omega
    have hi : r-12800 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_25) (r-12800)
      (List.mem_range.mpr hi)
    have heq : 12800+(r-12800) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h26 : r < 13824
  · have hstart : 13312 ≤ r := by omega
    have hi : r-13312 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_26) (r-13312)
      (List.mem_range.mpr hi)
    have heq : 13312+(r-13312) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h27 : r < 14336
  · have hstart : 13824 ≤ r := by omega
    have hi : r-13824 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_27) (r-13824)
      (List.mem_range.mpr hi)
    have heq : 13824+(r-13824) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h28 : r < 14848
  · have hstart : 14336 ≤ r := by omega
    have hi : r-14336 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_28) (r-14336)
      (List.mem_range.mpr hi)
    have heq : 14336+(r-14336) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h29 : r < 15360
  · have hstart : 14848 ≤ r := by omega
    have hi : r-14848 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_29) (r-14848)
      (List.mem_range.mpr hi)
    have heq : 14848+(r-14848) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h30 : r < 15872
  · have hstart : 15360 ≤ r := by omega
    have hi : r-15360 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_30) (r-15360)
      (List.mem_range.mpr hi)
    have heq : 15360+(r-15360) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h31 : r < 16384
  · have hstart : 15872 ≤ r := by omega
    have hi : r-15872 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_31) (r-15872)
      (List.mem_range.mpr hi)
    have heq : 15872+(r-15872) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h32 : r < 16896
  · have hstart : 16384 ≤ r := by omega
    have hi : r-16384 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_32) (r-16384)
      (List.mem_range.mpr hi)
    have heq : 16384+(r-16384) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h33 : r < 17408
  · have hstart : 16896 ≤ r := by omega
    have hi : r-16896 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_33) (r-16896)
      (List.mem_range.mpr hi)
    have heq : 16896+(r-16896) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  have hstart : 17408 ≤ r := by omega
  have hi : r-17408 < 359 := by omega
  have hc := (List.all_eq_true.mp chunk_34) (r-17408)
    (List.mem_range.mpr hi)
  have heq : 17408+(r-17408) = r := by omega
  rw [heq] at hc
  exact of_decide_eq_true (by simpa [scoreCheck] using hc)

#print axioms score_selected_eq
end NearestOrbit35533Tie
