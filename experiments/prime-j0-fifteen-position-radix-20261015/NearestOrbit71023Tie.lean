import NearestOrbit71023Digits

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
    (List.range 512).all (fun j => scoreCheck (9216+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_19 :
    (List.range 512).all (fun j => scoreCheck (9728+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_20 :
    (List.range 512).all (fun j => scoreCheck (10240+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_21 :
    (List.range 512).all (fun j => scoreCheck (10752+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_22 :
    (List.range 512).all (fun j => scoreCheck (11264+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_23 :
    (List.range 512).all (fun j => scoreCheck (11776+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_24 :
    (List.range 512).all (fun j => scoreCheck (12288+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_25 :
    (List.range 512).all (fun j => scoreCheck (12800+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_26 :
    (List.range 512).all (fun j => scoreCheck (13312+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_27 :
    (List.range 512).all (fun j => scoreCheck (13824+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_28 :
    (List.range 512).all (fun j => scoreCheck (14336+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_29 :
    (List.range 512).all (fun j => scoreCheck (14848+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_30 :
    (List.range 512).all (fun j => scoreCheck (15360+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_31 :
    (List.range 512).all (fun j => scoreCheck (15872+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_32 :
    (List.range 512).all (fun j => scoreCheck (16384+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_33 :
    (List.range 512).all (fun j => scoreCheck (16896+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_34 :
    (List.range 512).all (fun j => scoreCheck (17408+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_35 :
    (List.range 512).all (fun j => scoreCheck (17920+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_36 :
    (List.range 512).all (fun j => scoreCheck (18432+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_37 :
    (List.range 512).all (fun j => scoreCheck (18944+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_38 :
    (List.range 512).all (fun j => scoreCheck (19456+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_39 :
    (List.range 512).all (fun j => scoreCheck (19968+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_40 :
    (List.range 512).all (fun j => scoreCheck (20480+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_41 :
    (List.range 512).all (fun j => scoreCheck (20992+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_42 :
    (List.range 512).all (fun j => scoreCheck (21504+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_43 :
    (List.range 512).all (fun j => scoreCheck (22016+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_44 :
    (List.range 512).all (fun j => scoreCheck (22528+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_45 :
    (List.range 512).all (fun j => scoreCheck (23040+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_46 :
    (List.range 512).all (fun j => scoreCheck (23552+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_47 :
    (List.range 512).all (fun j => scoreCheck (24064+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_48 :
    (List.range 512).all (fun j => scoreCheck (24576+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_49 :
    (List.range 512).all (fun j => scoreCheck (25088+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_50 :
    (List.range 512).all (fun j => scoreCheck (25600+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_51 :
    (List.range 512).all (fun j => scoreCheck (26112+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_52 :
    (List.range 512).all (fun j => scoreCheck (26624+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_53 :
    (List.range 512).all (fun j => scoreCheck (27136+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_54 :
    (List.range 512).all (fun j => scoreCheck (27648+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_55 :
    (List.range 512).all (fun j => scoreCheck (28160+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_56 :
    (List.range 512).all (fun j => scoreCheck (28672+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_57 :
    (List.range 512).all (fun j => scoreCheck (29184+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_58 :
    (List.range 512).all (fun j => scoreCheck (29696+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_59 :
    (List.range 512).all (fun j => scoreCheck (30208+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_60 :
    (List.range 512).all (fun j => scoreCheck (30720+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_61 :
    (List.range 512).all (fun j => scoreCheck (31232+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_62 :
    (List.range 512).all (fun j => scoreCheck (31744+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_63 :
    (List.range 512).all (fun j => scoreCheck (32256+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_64 :
    (List.range 512).all (fun j => scoreCheck (32768+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_65 :
    (List.range 512).all (fun j => scoreCheck (33280+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_66 :
    (List.range 512).all (fun j => scoreCheck (33792+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_67 :
    (List.range 512).all (fun j => scoreCheck (34304+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_68 :
    (List.range 512).all (fun j => scoreCheck (34816+j)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem chunk_69 :
    (List.range 184).all (fun j => scoreCheck (35328+j)) = true := by decide

theorem score_selected_eq (r : Nat) (hr : r < 35512) :
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
  by_cases h34 : r < 17920
  · have hstart : 17408 ≤ r := by omega
    have hi : r-17408 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_34) (r-17408)
      (List.mem_range.mpr hi)
    have heq : 17408+(r-17408) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h35 : r < 18432
  · have hstart : 17920 ≤ r := by omega
    have hi : r-17920 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_35) (r-17920)
      (List.mem_range.mpr hi)
    have heq : 17920+(r-17920) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h36 : r < 18944
  · have hstart : 18432 ≤ r := by omega
    have hi : r-18432 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_36) (r-18432)
      (List.mem_range.mpr hi)
    have heq : 18432+(r-18432) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h37 : r < 19456
  · have hstart : 18944 ≤ r := by omega
    have hi : r-18944 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_37) (r-18944)
      (List.mem_range.mpr hi)
    have heq : 18944+(r-18944) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h38 : r < 19968
  · have hstart : 19456 ≤ r := by omega
    have hi : r-19456 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_38) (r-19456)
      (List.mem_range.mpr hi)
    have heq : 19456+(r-19456) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h39 : r < 20480
  · have hstart : 19968 ≤ r := by omega
    have hi : r-19968 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_39) (r-19968)
      (List.mem_range.mpr hi)
    have heq : 19968+(r-19968) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h40 : r < 20992
  · have hstart : 20480 ≤ r := by omega
    have hi : r-20480 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_40) (r-20480)
      (List.mem_range.mpr hi)
    have heq : 20480+(r-20480) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h41 : r < 21504
  · have hstart : 20992 ≤ r := by omega
    have hi : r-20992 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_41) (r-20992)
      (List.mem_range.mpr hi)
    have heq : 20992+(r-20992) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h42 : r < 22016
  · have hstart : 21504 ≤ r := by omega
    have hi : r-21504 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_42) (r-21504)
      (List.mem_range.mpr hi)
    have heq : 21504+(r-21504) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h43 : r < 22528
  · have hstart : 22016 ≤ r := by omega
    have hi : r-22016 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_43) (r-22016)
      (List.mem_range.mpr hi)
    have heq : 22016+(r-22016) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h44 : r < 23040
  · have hstart : 22528 ≤ r := by omega
    have hi : r-22528 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_44) (r-22528)
      (List.mem_range.mpr hi)
    have heq : 22528+(r-22528) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h45 : r < 23552
  · have hstart : 23040 ≤ r := by omega
    have hi : r-23040 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_45) (r-23040)
      (List.mem_range.mpr hi)
    have heq : 23040+(r-23040) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h46 : r < 24064
  · have hstart : 23552 ≤ r := by omega
    have hi : r-23552 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_46) (r-23552)
      (List.mem_range.mpr hi)
    have heq : 23552+(r-23552) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h47 : r < 24576
  · have hstart : 24064 ≤ r := by omega
    have hi : r-24064 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_47) (r-24064)
      (List.mem_range.mpr hi)
    have heq : 24064+(r-24064) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h48 : r < 25088
  · have hstart : 24576 ≤ r := by omega
    have hi : r-24576 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_48) (r-24576)
      (List.mem_range.mpr hi)
    have heq : 24576+(r-24576) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h49 : r < 25600
  · have hstart : 25088 ≤ r := by omega
    have hi : r-25088 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_49) (r-25088)
      (List.mem_range.mpr hi)
    have heq : 25088+(r-25088) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h50 : r < 26112
  · have hstart : 25600 ≤ r := by omega
    have hi : r-25600 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_50) (r-25600)
      (List.mem_range.mpr hi)
    have heq : 25600+(r-25600) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h51 : r < 26624
  · have hstart : 26112 ≤ r := by omega
    have hi : r-26112 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_51) (r-26112)
      (List.mem_range.mpr hi)
    have heq : 26112+(r-26112) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h52 : r < 27136
  · have hstart : 26624 ≤ r := by omega
    have hi : r-26624 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_52) (r-26624)
      (List.mem_range.mpr hi)
    have heq : 26624+(r-26624) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h53 : r < 27648
  · have hstart : 27136 ≤ r := by omega
    have hi : r-27136 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_53) (r-27136)
      (List.mem_range.mpr hi)
    have heq : 27136+(r-27136) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h54 : r < 28160
  · have hstart : 27648 ≤ r := by omega
    have hi : r-27648 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_54) (r-27648)
      (List.mem_range.mpr hi)
    have heq : 27648+(r-27648) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h55 : r < 28672
  · have hstart : 28160 ≤ r := by omega
    have hi : r-28160 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_55) (r-28160)
      (List.mem_range.mpr hi)
    have heq : 28160+(r-28160) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h56 : r < 29184
  · have hstart : 28672 ≤ r := by omega
    have hi : r-28672 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_56) (r-28672)
      (List.mem_range.mpr hi)
    have heq : 28672+(r-28672) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h57 : r < 29696
  · have hstart : 29184 ≤ r := by omega
    have hi : r-29184 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_57) (r-29184)
      (List.mem_range.mpr hi)
    have heq : 29184+(r-29184) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h58 : r < 30208
  · have hstart : 29696 ≤ r := by omega
    have hi : r-29696 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_58) (r-29696)
      (List.mem_range.mpr hi)
    have heq : 29696+(r-29696) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h59 : r < 30720
  · have hstart : 30208 ≤ r := by omega
    have hi : r-30208 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_59) (r-30208)
      (List.mem_range.mpr hi)
    have heq : 30208+(r-30208) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h60 : r < 31232
  · have hstart : 30720 ≤ r := by omega
    have hi : r-30720 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_60) (r-30720)
      (List.mem_range.mpr hi)
    have heq : 30720+(r-30720) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h61 : r < 31744
  · have hstart : 31232 ≤ r := by omega
    have hi : r-31232 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_61) (r-31232)
      (List.mem_range.mpr hi)
    have heq : 31232+(r-31232) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h62 : r < 32256
  · have hstart : 31744 ≤ r := by omega
    have hi : r-31744 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_62) (r-31744)
      (List.mem_range.mpr hi)
    have heq : 31744+(r-31744) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h63 : r < 32768
  · have hstart : 32256 ≤ r := by omega
    have hi : r-32256 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_63) (r-32256)
      (List.mem_range.mpr hi)
    have heq : 32256+(r-32256) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h64 : r < 33280
  · have hstart : 32768 ≤ r := by omega
    have hi : r-32768 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_64) (r-32768)
      (List.mem_range.mpr hi)
    have heq : 32768+(r-32768) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h65 : r < 33792
  · have hstart : 33280 ≤ r := by omega
    have hi : r-33280 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_65) (r-33280)
      (List.mem_range.mpr hi)
    have heq : 33280+(r-33280) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h66 : r < 34304
  · have hstart : 33792 ≤ r := by omega
    have hi : r-33792 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_66) (r-33792)
      (List.mem_range.mpr hi)
    have heq : 33792+(r-33792) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h67 : r < 34816
  · have hstart : 34304 ≤ r := by omega
    have hi : r-34304 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_67) (r-34304)
      (List.mem_range.mpr hi)
    have heq : 34304+(r-34304) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  by_cases h68 : r < 35328
  · have hstart : 34816 ≤ r := by omega
    have hi : r-34816 < 512 := by omega
    have hc := (List.all_eq_true.mp chunk_68) (r-34816)
      (List.mem_range.mpr hi)
    have heq : 34816+(r-34816) = r := by omega
    rw [heq] at hc
    exact of_decide_eq_true (by simpa [scoreCheck] using hc)
  have hstart : 35328 ≤ r := by omega
  have hi : r-35328 < 184 := by omega
  have hc := (List.all_eq_true.mp chunk_69) (r-35328)
    (List.mem_range.mpr hi)
  have heq : 35328+(r-35328) = r := by omega
  rw [heq] at hc
  exact of_decide_eq_true (by simpa [scoreCheck] using hc)

#print axioms score_selected_eq
end NearestOrbit71023Tie
