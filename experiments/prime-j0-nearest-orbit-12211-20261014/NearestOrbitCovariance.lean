import NearestOrbit12211

namespace NearestOrbitCovariance
open SplitPrime12211NearestStep
open SplitPrimeRadix

noncomputable def covarianceCheck (r : Nat) : Bool :=
  decide (nearestDigit ((12100*r) % 12211) =
    omegaMul (nearestDigit r))

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_0 :
    (List.range 128).all (fun k => covarianceCheck (0+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_1 :
    (List.range 128).all (fun k => covarianceCheck (128+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_2 :
    (List.range 128).all (fun k => covarianceCheck (256+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_3 :
    (List.range 128).all (fun k => covarianceCheck (384+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_4 :
    (List.range 128).all (fun k => covarianceCheck (512+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_5 :
    (List.range 128).all (fun k => covarianceCheck (640+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_6 :
    (List.range 128).all (fun k => covarianceCheck (768+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_7 :
    (List.range 128).all (fun k => covarianceCheck (896+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_8 :
    (List.range 128).all (fun k => covarianceCheck (1024+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_9 :
    (List.range 128).all (fun k => covarianceCheck (1152+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_10 :
    (List.range 128).all (fun k => covarianceCheck (1280+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_11 :
    (List.range 128).all (fun k => covarianceCheck (1408+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_12 :
    (List.range 128).all (fun k => covarianceCheck (1536+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_13 :
    (List.range 128).all (fun k => covarianceCheck (1664+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_14 :
    (List.range 128).all (fun k => covarianceCheck (1792+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_15 :
    (List.range 128).all (fun k => covarianceCheck (1920+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_16 :
    (List.range 128).all (fun k => covarianceCheck (2048+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_17 :
    (List.range 128).all (fun k => covarianceCheck (2176+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_18 :
    (List.range 128).all (fun k => covarianceCheck (2304+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_19 :
    (List.range 128).all (fun k => covarianceCheck (2432+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_20 :
    (List.range 128).all (fun k => covarianceCheck (2560+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_21 :
    (List.range 128).all (fun k => covarianceCheck (2688+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_22 :
    (List.range 128).all (fun k => covarianceCheck (2816+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_23 :
    (List.range 128).all (fun k => covarianceCheck (2944+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_24 :
    (List.range 128).all (fun k => covarianceCheck (3072+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_25 :
    (List.range 128).all (fun k => covarianceCheck (3200+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_26 :
    (List.range 128).all (fun k => covarianceCheck (3328+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_27 :
    (List.range 128).all (fun k => covarianceCheck (3456+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_28 :
    (List.range 128).all (fun k => covarianceCheck (3584+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_29 :
    (List.range 128).all (fun k => covarianceCheck (3712+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_30 :
    (List.range 128).all (fun k => covarianceCheck (3840+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_31 :
    (List.range 128).all (fun k => covarianceCheck (3968+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_32 :
    (List.range 128).all (fun k => covarianceCheck (4096+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_33 :
    (List.range 128).all (fun k => covarianceCheck (4224+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_34 :
    (List.range 128).all (fun k => covarianceCheck (4352+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_35 :
    (List.range 128).all (fun k => covarianceCheck (4480+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_36 :
    (List.range 128).all (fun k => covarianceCheck (4608+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_37 :
    (List.range 128).all (fun k => covarianceCheck (4736+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_38 :
    (List.range 128).all (fun k => covarianceCheck (4864+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_39 :
    (List.range 128).all (fun k => covarianceCheck (4992+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_40 :
    (List.range 128).all (fun k => covarianceCheck (5120+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_41 :
    (List.range 128).all (fun k => covarianceCheck (5248+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_42 :
    (List.range 128).all (fun k => covarianceCheck (5376+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_43 :
    (List.range 128).all (fun k => covarianceCheck (5504+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_44 :
    (List.range 128).all (fun k => covarianceCheck (5632+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_45 :
    (List.range 128).all (fun k => covarianceCheck (5760+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_46 :
    (List.range 128).all (fun k => covarianceCheck (5888+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_47 :
    (List.range 128).all (fun k => covarianceCheck (6016+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_48 :
    (List.range 128).all (fun k => covarianceCheck (6144+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_49 :
    (List.range 128).all (fun k => covarianceCheck (6272+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_50 :
    (List.range 128).all (fun k => covarianceCheck (6400+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_51 :
    (List.range 128).all (fun k => covarianceCheck (6528+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_52 :
    (List.range 128).all (fun k => covarianceCheck (6656+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_53 :
    (List.range 128).all (fun k => covarianceCheck (6784+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_54 :
    (List.range 128).all (fun k => covarianceCheck (6912+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_55 :
    (List.range 128).all (fun k => covarianceCheck (7040+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_56 :
    (List.range 128).all (fun k => covarianceCheck (7168+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_57 :
    (List.range 128).all (fun k => covarianceCheck (7296+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_58 :
    (List.range 128).all (fun k => covarianceCheck (7424+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_59 :
    (List.range 128).all (fun k => covarianceCheck (7552+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_60 :
    (List.range 128).all (fun k => covarianceCheck (7680+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_61 :
    (List.range 128).all (fun k => covarianceCheck (7808+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_62 :
    (List.range 128).all (fun k => covarianceCheck (7936+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_63 :
    (List.range 128).all (fun k => covarianceCheck (8064+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_64 :
    (List.range 128).all (fun k => covarianceCheck (8192+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_65 :
    (List.range 128).all (fun k => covarianceCheck (8320+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_66 :
    (List.range 128).all (fun k => covarianceCheck (8448+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_67 :
    (List.range 128).all (fun k => covarianceCheck (8576+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_68 :
    (List.range 128).all (fun k => covarianceCheck (8704+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_69 :
    (List.range 128).all (fun k => covarianceCheck (8832+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_70 :
    (List.range 128).all (fun k => covarianceCheck (8960+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_71 :
    (List.range 128).all (fun k => covarianceCheck (9088+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_72 :
    (List.range 128).all (fun k => covarianceCheck (9216+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_73 :
    (List.range 128).all (fun k => covarianceCheck (9344+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_74 :
    (List.range 128).all (fun k => covarianceCheck (9472+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_75 :
    (List.range 128).all (fun k => covarianceCheck (9600+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_76 :
    (List.range 128).all (fun k => covarianceCheck (9728+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_77 :
    (List.range 128).all (fun k => covarianceCheck (9856+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_78 :
    (List.range 128).all (fun k => covarianceCheck (9984+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_79 :
    (List.range 128).all (fun k => covarianceCheck (10112+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_80 :
    (List.range 128).all (fun k => covarianceCheck (10240+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_81 :
    (List.range 128).all (fun k => covarianceCheck (10368+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_82 :
    (List.range 128).all (fun k => covarianceCheck (10496+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_83 :
    (List.range 128).all (fun k => covarianceCheck (10624+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_84 :
    (List.range 128).all (fun k => covarianceCheck (10752+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_85 :
    (List.range 128).all (fun k => covarianceCheck (10880+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_86 :
    (List.range 128).all (fun k => covarianceCheck (11008+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_87 :
    (List.range 128).all (fun k => covarianceCheck (11136+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_88 :
    (List.range 128).all (fun k => covarianceCheck (11264+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_89 :
    (List.range 128).all (fun k => covarianceCheck (11392+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_90 :
    (List.range 128).all (fun k => covarianceCheck (11520+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_91 :
    (List.range 128).all (fun k => covarianceCheck (11648+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_92 :
    (List.range 128).all (fun k => covarianceCheck (11776+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_93 :
    (List.range 128).all (fun k => covarianceCheck (11904+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_94 :
    (List.range 128).all (fun k => covarianceCheck (12032+k)) = true := by decide

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem covariance_chunk_95 :
    (List.range 51).all (fun k => covarianceCheck (12160+k)) = true := by decide

private theorem from_chunk (start len : Nat)
    (hc : (List.range len).all (fun k => covarianceCheck (start+k)) = true)
    (r : Nat) (hlo : start ≤ r) (hhi : r < start+len) :
    covarianceCheck r = true := by
  have h := (List.all_eq_true.mp hc) (r-start)
    (List.mem_range.mpr (by omega))
  have heq : start+(r-start)=r := by omega
  simpa [heq] using h

theorem all_runtime_digits_covariant (r : Nat) (hr : r < 12211) :
    covarianceCheck r = true := by
  by_cases h0 : r < 128
  · exact from_chunk 0 128 covariance_chunk_0 r (by omega) (by omega)
  by_cases h1 : r < 256
  · exact from_chunk 128 128 covariance_chunk_1 r (by omega) (by omega)
  by_cases h2 : r < 384
  · exact from_chunk 256 128 covariance_chunk_2 r (by omega) (by omega)
  by_cases h3 : r < 512
  · exact from_chunk 384 128 covariance_chunk_3 r (by omega) (by omega)
  by_cases h4 : r < 640
  · exact from_chunk 512 128 covariance_chunk_4 r (by omega) (by omega)
  by_cases h5 : r < 768
  · exact from_chunk 640 128 covariance_chunk_5 r (by omega) (by omega)
  by_cases h6 : r < 896
  · exact from_chunk 768 128 covariance_chunk_6 r (by omega) (by omega)
  by_cases h7 : r < 1024
  · exact from_chunk 896 128 covariance_chunk_7 r (by omega) (by omega)
  by_cases h8 : r < 1152
  · exact from_chunk 1024 128 covariance_chunk_8 r (by omega) (by omega)
  by_cases h9 : r < 1280
  · exact from_chunk 1152 128 covariance_chunk_9 r (by omega) (by omega)
  by_cases h10 : r < 1408
  · exact from_chunk 1280 128 covariance_chunk_10 r (by omega) (by omega)
  by_cases h11 : r < 1536
  · exact from_chunk 1408 128 covariance_chunk_11 r (by omega) (by omega)
  by_cases h12 : r < 1664
  · exact from_chunk 1536 128 covariance_chunk_12 r (by omega) (by omega)
  by_cases h13 : r < 1792
  · exact from_chunk 1664 128 covariance_chunk_13 r (by omega) (by omega)
  by_cases h14 : r < 1920
  · exact from_chunk 1792 128 covariance_chunk_14 r (by omega) (by omega)
  by_cases h15 : r < 2048
  · exact from_chunk 1920 128 covariance_chunk_15 r (by omega) (by omega)
  by_cases h16 : r < 2176
  · exact from_chunk 2048 128 covariance_chunk_16 r (by omega) (by omega)
  by_cases h17 : r < 2304
  · exact from_chunk 2176 128 covariance_chunk_17 r (by omega) (by omega)
  by_cases h18 : r < 2432
  · exact from_chunk 2304 128 covariance_chunk_18 r (by omega) (by omega)
  by_cases h19 : r < 2560
  · exact from_chunk 2432 128 covariance_chunk_19 r (by omega) (by omega)
  by_cases h20 : r < 2688
  · exact from_chunk 2560 128 covariance_chunk_20 r (by omega) (by omega)
  by_cases h21 : r < 2816
  · exact from_chunk 2688 128 covariance_chunk_21 r (by omega) (by omega)
  by_cases h22 : r < 2944
  · exact from_chunk 2816 128 covariance_chunk_22 r (by omega) (by omega)
  by_cases h23 : r < 3072
  · exact from_chunk 2944 128 covariance_chunk_23 r (by omega) (by omega)
  by_cases h24 : r < 3200
  · exact from_chunk 3072 128 covariance_chunk_24 r (by omega) (by omega)
  by_cases h25 : r < 3328
  · exact from_chunk 3200 128 covariance_chunk_25 r (by omega) (by omega)
  by_cases h26 : r < 3456
  · exact from_chunk 3328 128 covariance_chunk_26 r (by omega) (by omega)
  by_cases h27 : r < 3584
  · exact from_chunk 3456 128 covariance_chunk_27 r (by omega) (by omega)
  by_cases h28 : r < 3712
  · exact from_chunk 3584 128 covariance_chunk_28 r (by omega) (by omega)
  by_cases h29 : r < 3840
  · exact from_chunk 3712 128 covariance_chunk_29 r (by omega) (by omega)
  by_cases h30 : r < 3968
  · exact from_chunk 3840 128 covariance_chunk_30 r (by omega) (by omega)
  by_cases h31 : r < 4096
  · exact from_chunk 3968 128 covariance_chunk_31 r (by omega) (by omega)
  by_cases h32 : r < 4224
  · exact from_chunk 4096 128 covariance_chunk_32 r (by omega) (by omega)
  by_cases h33 : r < 4352
  · exact from_chunk 4224 128 covariance_chunk_33 r (by omega) (by omega)
  by_cases h34 : r < 4480
  · exact from_chunk 4352 128 covariance_chunk_34 r (by omega) (by omega)
  by_cases h35 : r < 4608
  · exact from_chunk 4480 128 covariance_chunk_35 r (by omega) (by omega)
  by_cases h36 : r < 4736
  · exact from_chunk 4608 128 covariance_chunk_36 r (by omega) (by omega)
  by_cases h37 : r < 4864
  · exact from_chunk 4736 128 covariance_chunk_37 r (by omega) (by omega)
  by_cases h38 : r < 4992
  · exact from_chunk 4864 128 covariance_chunk_38 r (by omega) (by omega)
  by_cases h39 : r < 5120
  · exact from_chunk 4992 128 covariance_chunk_39 r (by omega) (by omega)
  by_cases h40 : r < 5248
  · exact from_chunk 5120 128 covariance_chunk_40 r (by omega) (by omega)
  by_cases h41 : r < 5376
  · exact from_chunk 5248 128 covariance_chunk_41 r (by omega) (by omega)
  by_cases h42 : r < 5504
  · exact from_chunk 5376 128 covariance_chunk_42 r (by omega) (by omega)
  by_cases h43 : r < 5632
  · exact from_chunk 5504 128 covariance_chunk_43 r (by omega) (by omega)
  by_cases h44 : r < 5760
  · exact from_chunk 5632 128 covariance_chunk_44 r (by omega) (by omega)
  by_cases h45 : r < 5888
  · exact from_chunk 5760 128 covariance_chunk_45 r (by omega) (by omega)
  by_cases h46 : r < 6016
  · exact from_chunk 5888 128 covariance_chunk_46 r (by omega) (by omega)
  by_cases h47 : r < 6144
  · exact from_chunk 6016 128 covariance_chunk_47 r (by omega) (by omega)
  by_cases h48 : r < 6272
  · exact from_chunk 6144 128 covariance_chunk_48 r (by omega) (by omega)
  by_cases h49 : r < 6400
  · exact from_chunk 6272 128 covariance_chunk_49 r (by omega) (by omega)
  by_cases h50 : r < 6528
  · exact from_chunk 6400 128 covariance_chunk_50 r (by omega) (by omega)
  by_cases h51 : r < 6656
  · exact from_chunk 6528 128 covariance_chunk_51 r (by omega) (by omega)
  by_cases h52 : r < 6784
  · exact from_chunk 6656 128 covariance_chunk_52 r (by omega) (by omega)
  by_cases h53 : r < 6912
  · exact from_chunk 6784 128 covariance_chunk_53 r (by omega) (by omega)
  by_cases h54 : r < 7040
  · exact from_chunk 6912 128 covariance_chunk_54 r (by omega) (by omega)
  by_cases h55 : r < 7168
  · exact from_chunk 7040 128 covariance_chunk_55 r (by omega) (by omega)
  by_cases h56 : r < 7296
  · exact from_chunk 7168 128 covariance_chunk_56 r (by omega) (by omega)
  by_cases h57 : r < 7424
  · exact from_chunk 7296 128 covariance_chunk_57 r (by omega) (by omega)
  by_cases h58 : r < 7552
  · exact from_chunk 7424 128 covariance_chunk_58 r (by omega) (by omega)
  by_cases h59 : r < 7680
  · exact from_chunk 7552 128 covariance_chunk_59 r (by omega) (by omega)
  by_cases h60 : r < 7808
  · exact from_chunk 7680 128 covariance_chunk_60 r (by omega) (by omega)
  by_cases h61 : r < 7936
  · exact from_chunk 7808 128 covariance_chunk_61 r (by omega) (by omega)
  by_cases h62 : r < 8064
  · exact from_chunk 7936 128 covariance_chunk_62 r (by omega) (by omega)
  by_cases h63 : r < 8192
  · exact from_chunk 8064 128 covariance_chunk_63 r (by omega) (by omega)
  by_cases h64 : r < 8320
  · exact from_chunk 8192 128 covariance_chunk_64 r (by omega) (by omega)
  by_cases h65 : r < 8448
  · exact from_chunk 8320 128 covariance_chunk_65 r (by omega) (by omega)
  by_cases h66 : r < 8576
  · exact from_chunk 8448 128 covariance_chunk_66 r (by omega) (by omega)
  by_cases h67 : r < 8704
  · exact from_chunk 8576 128 covariance_chunk_67 r (by omega) (by omega)
  by_cases h68 : r < 8832
  · exact from_chunk 8704 128 covariance_chunk_68 r (by omega) (by omega)
  by_cases h69 : r < 8960
  · exact from_chunk 8832 128 covariance_chunk_69 r (by omega) (by omega)
  by_cases h70 : r < 9088
  · exact from_chunk 8960 128 covariance_chunk_70 r (by omega) (by omega)
  by_cases h71 : r < 9216
  · exact from_chunk 9088 128 covariance_chunk_71 r (by omega) (by omega)
  by_cases h72 : r < 9344
  · exact from_chunk 9216 128 covariance_chunk_72 r (by omega) (by omega)
  by_cases h73 : r < 9472
  · exact from_chunk 9344 128 covariance_chunk_73 r (by omega) (by omega)
  by_cases h74 : r < 9600
  · exact from_chunk 9472 128 covariance_chunk_74 r (by omega) (by omega)
  by_cases h75 : r < 9728
  · exact from_chunk 9600 128 covariance_chunk_75 r (by omega) (by omega)
  by_cases h76 : r < 9856
  · exact from_chunk 9728 128 covariance_chunk_76 r (by omega) (by omega)
  by_cases h77 : r < 9984
  · exact from_chunk 9856 128 covariance_chunk_77 r (by omega) (by omega)
  by_cases h78 : r < 10112
  · exact from_chunk 9984 128 covariance_chunk_78 r (by omega) (by omega)
  by_cases h79 : r < 10240
  · exact from_chunk 10112 128 covariance_chunk_79 r (by omega) (by omega)
  by_cases h80 : r < 10368
  · exact from_chunk 10240 128 covariance_chunk_80 r (by omega) (by omega)
  by_cases h81 : r < 10496
  · exact from_chunk 10368 128 covariance_chunk_81 r (by omega) (by omega)
  by_cases h82 : r < 10624
  · exact from_chunk 10496 128 covariance_chunk_82 r (by omega) (by omega)
  by_cases h83 : r < 10752
  · exact from_chunk 10624 128 covariance_chunk_83 r (by omega) (by omega)
  by_cases h84 : r < 10880
  · exact from_chunk 10752 128 covariance_chunk_84 r (by omega) (by omega)
  by_cases h85 : r < 11008
  · exact from_chunk 10880 128 covariance_chunk_85 r (by omega) (by omega)
  by_cases h86 : r < 11136
  · exact from_chunk 11008 128 covariance_chunk_86 r (by omega) (by omega)
  by_cases h87 : r < 11264
  · exact from_chunk 11136 128 covariance_chunk_87 r (by omega) (by omega)
  by_cases h88 : r < 11392
  · exact from_chunk 11264 128 covariance_chunk_88 r (by omega) (by omega)
  by_cases h89 : r < 11520
  · exact from_chunk 11392 128 covariance_chunk_89 r (by omega) (by omega)
  by_cases h90 : r < 11648
  · exact from_chunk 11520 128 covariance_chunk_90 r (by omega) (by omega)
  by_cases h91 : r < 11776
  · exact from_chunk 11648 128 covariance_chunk_91 r (by omega) (by omega)
  by_cases h92 : r < 11904
  · exact from_chunk 11776 128 covariance_chunk_92 r (by omega) (by omega)
  by_cases h93 : r < 12032
  · exact from_chunk 11904 128 covariance_chunk_93 r (by omega) (by omega)
  by_cases h94 : r < 12160
  · exact from_chunk 12032 128 covariance_chunk_94 r (by omega) (by omega)
  exact from_chunk 12160 51 covariance_chunk_95 r (by omega) (by omega)

theorem runtime_digit_covariant (r : Nat) (hr : r < 12211) :
    nearestDigit ((12100*r) % 12211) =
      omegaMul (nearestDigit r) := by
  exact of_decide_eq_true (by simpa [covarianceCheck] using
    all_runtime_digits_covariant r hr)

#print axioms runtime_digit_covariant
end NearestOrbitCovariance
