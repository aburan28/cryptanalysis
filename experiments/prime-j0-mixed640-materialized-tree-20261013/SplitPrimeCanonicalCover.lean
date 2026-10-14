import SplitPrimeCanonicalSeeds
set_option maxHeartbeats 0
namespace SplitPrimeCanonicalCover
open SplitPrimeCanonicalSeeds

-- Each witness is checked against the canonical minimum-orbit predicate.
def covered (r : Nat) : Prop :=
  ∃ m : Nat, m ≤ 1064 ∧ (m = 0 ∨ isCanonical m = true) ∧ (
    r = m ∨ r = (3300*m)%3301 ∨ r = (1726*m)%3301 ∨
    r = (1575*m)%3301 ∨ r = (1574*m)%3301 ∨ r = (1727*m)%3301)

theorem slice_0 (r : Nat) (lo : 0 ≤ r) (hi : r ≤ 49) : covered r := by
  have h : r = 0 ∨ r = 1 ∨ r = 2 ∨ r = 3 ∨ r = 4 ∨ r = 5 ∨ r = 6 ∨ r = 7 ∨ r = 8 ∨ r = 9 ∨ r = 10 ∨ r = 11 ∨ r = 12 ∨ r = 13 ∨ r = 14 ∨ r = 15 ∨ r = 16 ∨ r = 17 ∨ r = 18 ∨ r = 19 ∨ r = 20 ∨ r = 21 ∨ r = 22 ∨ r = 23 ∨ r = 24 ∨ r = 25 ∨ r = 26 ∨ r = 27 ∨ r = 28 ∨ r = 29 ∨ r = 30 ∨ r = 31 ∨ r = 32 ∨ r = 33 ∨ r = 34 ∨ r = 35 ∨ r = 36 ∨ r = 37 ∨ r = 38 ∨ r = 39 ∨ r = 40 ∨ r = 41 ∨ r = 42 ∨ r = 43 ∨ r = 44 ∨ r = 45 ∨ r = 46 ∨ r = 47 ∨ r = 48 ∨ r = 49 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨0, by decide, by decide, by decide⟩
  · subst r; exact ⟨1, by decide, by decide, by decide⟩
  · subst r; exact ⟨2, by decide, by decide, by decide⟩
  · subst r; exact ⟨3, by decide, by decide, by decide⟩
  · subst r; exact ⟨4, by decide, by decide, by decide⟩
  · subst r; exact ⟨5, by decide, by decide, by decide⟩
  · subst r; exact ⟨6, by decide, by decide, by decide⟩
  · subst r; exact ⟨7, by decide, by decide, by decide⟩
  · subst r; exact ⟨8, by decide, by decide, by decide⟩
  · subst r; exact ⟨9, by decide, by decide, by decide⟩
  · subst r; exact ⟨10, by decide, by decide, by decide⟩
  · subst r; exact ⟨11, by decide, by decide, by decide⟩
  · subst r; exact ⟨12, by decide, by decide, by decide⟩
  · subst r; exact ⟨13, by decide, by decide, by decide⟩
  · subst r; exact ⟨14, by decide, by decide, by decide⟩
  · subst r; exact ⟨15, by decide, by decide, by decide⟩
  · subst r; exact ⟨16, by decide, by decide, by decide⟩
  · subst r; exact ⟨17, by decide, by decide, by decide⟩
  · subst r; exact ⟨18, by decide, by decide, by decide⟩
  · subst r; exact ⟨19, by decide, by decide, by decide⟩
  · subst r; exact ⟨20, by decide, by decide, by decide⟩
  · subst r; exact ⟨21, by decide, by decide, by decide⟩
  · subst r; exact ⟨22, by decide, by decide, by decide⟩
  · subst r; exact ⟨23, by decide, by decide, by decide⟩
  · subst r; exact ⟨24, by decide, by decide, by decide⟩
  · subst r; exact ⟨25, by decide, by decide, by decide⟩
  · subst r; exact ⟨26, by decide, by decide, by decide⟩
  · subst r; exact ⟨27, by decide, by decide, by decide⟩
  · subst r; exact ⟨28, by decide, by decide, by decide⟩
  · subst r; exact ⟨29, by decide, by decide, by decide⟩
  · subst r; exact ⟨30, by decide, by decide, by decide⟩
  · subst r; exact ⟨31, by decide, by decide, by decide⟩
  · subst r; exact ⟨32, by decide, by decide, by decide⟩
  · subst r; exact ⟨33, by decide, by decide, by decide⟩
  · subst r; exact ⟨34, by decide, by decide, by decide⟩
  · subst r; exact ⟨35, by decide, by decide, by decide⟩
  · subst r; exact ⟨36, by decide, by decide, by decide⟩
  · subst r; exact ⟨37, by decide, by decide, by decide⟩
  · subst r; exact ⟨38, by decide, by decide, by decide⟩
  · subst r; exact ⟨39, by decide, by decide, by decide⟩
  · subst r; exact ⟨40, by decide, by decide, by decide⟩
  · subst r; exact ⟨41, by decide, by decide, by decide⟩
  · subst r; exact ⟨42, by decide, by decide, by decide⟩
  · subst r; exact ⟨43, by decide, by decide, by decide⟩
  · subst r; exact ⟨21, by decide, by decide, by decide⟩
  · subst r; exact ⟨45, by decide, by decide, by decide⟩
  · subst r; exact ⟨46, by decide, by decide, by decide⟩
  · subst r; exact ⟨47, by decide, by decide, by decide⟩
  · subst r; exact ⟨48, by decide, by decide, by decide⟩
  · subst r; exact ⟨49, by decide, by decide, by decide⟩

theorem slice_1 (r : Nat) (lo : 50 ≤ r) (hi : r ≤ 99) : covered r := by
  have h : r = 50 ∨ r = 51 ∨ r = 52 ∨ r = 53 ∨ r = 54 ∨ r = 55 ∨ r = 56 ∨ r = 57 ∨ r = 58 ∨ r = 59 ∨ r = 60 ∨ r = 61 ∨ r = 62 ∨ r = 63 ∨ r = 64 ∨ r = 65 ∨ r = 66 ∨ r = 67 ∨ r = 68 ∨ r = 69 ∨ r = 70 ∨ r = 71 ∨ r = 72 ∨ r = 73 ∨ r = 74 ∨ r = 75 ∨ r = 76 ∨ r = 77 ∨ r = 78 ∨ r = 79 ∨ r = 80 ∨ r = 81 ∨ r = 82 ∨ r = 83 ∨ r = 84 ∨ r = 85 ∨ r = 86 ∨ r = 87 ∨ r = 88 ∨ r = 89 ∨ r = 90 ∨ r = 91 ∨ r = 92 ∨ r = 93 ∨ r = 94 ∨ r = 95 ∨ r = 96 ∨ r = 97 ∨ r = 98 ∨ r = 99 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨50, by decide, by decide, by decide⟩
  · subst r; exact ⟨51, by decide, by decide, by decide⟩
  · subst r; exact ⟨52, by decide, by decide, by decide⟩
  · subst r; exact ⟨53, by decide, by decide, by decide⟩
  · subst r; exact ⟨54, by decide, by decide, by decide⟩
  · subst r; exact ⟨55, by decide, by decide, by decide⟩
  · subst r; exact ⟨56, by decide, by decide, by decide⟩
  · subst r; exact ⟨57, by decide, by decide, by decide⟩
  · subst r; exact ⟨58, by decide, by decide, by decide⟩
  · subst r; exact ⟨59, by decide, by decide, by decide⟩
  · subst r; exact ⟨60, by decide, by decide, by decide⟩
  · subst r; exact ⟨61, by decide, by decide, by decide⟩
  · subst r; exact ⟨62, by decide, by decide, by decide⟩
  · subst r; exact ⟨63, by decide, by decide, by decide⟩
  · subst r; exact ⟨64, by decide, by decide, by decide⟩
  · subst r; exact ⟨21, by decide, by decide, by decide⟩
  · subst r; exact ⟨66, by decide, by decide, by decide⟩
  · subst r; exact ⟨67, by decide, by decide, by decide⟩
  · subst r; exact ⟨68, by decide, by decide, by decide⟩
  · subst r; exact ⟨69, by decide, by decide, by decide⟩
  · subst r; exact ⟨70, by decide, by decide, by decide⟩
  · subst r; exact ⟨71, by decide, by decide, by decide⟩
  · subst r; exact ⟨72, by decide, by decide, by decide⟩
  · subst r; exact ⟨73, by decide, by decide, by decide⟩
  · subst r; exact ⟨74, by decide, by decide, by decide⟩
  · subst r; exact ⟨75, by decide, by decide, by decide⟩
  · subst r; exact ⟨76, by decide, by decide, by decide⟩
  · subst r; exact ⟨77, by decide, by decide, by decide⟩
  · subst r; exact ⟨78, by decide, by decide, by decide⟩
  · subst r; exact ⟨79, by decide, by decide, by decide⟩
  · subst r; exact ⟨80, by decide, by decide, by decide⟩
  · subst r; exact ⟨81, by decide, by decide, by decide⟩
  · subst r; exact ⟨82, by decide, by decide, by decide⟩
  · subst r; exact ⟨83, by decide, by decide, by decide⟩
  · subst r; exact ⟨84, by decide, by decide, by decide⟩
  · subst r; exact ⟨85, by decide, by decide, by decide⟩
  · subst r; exact ⟨23, by decide, by decide, by decide⟩
  · subst r; exact ⟨87, by decide, by decide, by decide⟩
  · subst r; exact ⟨42, by decide, by decide, by decide⟩
  · subst r; exact ⟨89, by decide, by decide, by decide⟩
  · subst r; exact ⟨90, by decide, by decide, by decide⟩
  · subst r; exact ⟨91, by decide, by decide, by decide⟩
  · subst r; exact ⟨92, by decide, by decide, by decide⟩
  · subst r; exact ⟨93, by decide, by decide, by decide⟩
  · subst r; exact ⟨94, by decide, by decide, by decide⟩
  · subst r; exact ⟨95, by decide, by decide, by decide⟩
  · subst r; exact ⟨96, by decide, by decide, by decide⟩
  · subst r; exact ⟨97, by decide, by decide, by decide⟩
  · subst r; exact ⟨98, by decide, by decide, by decide⟩
  · subst r; exact ⟨99, by decide, by decide, by decide⟩

theorem slice_2 (r : Nat) (lo : 100 ≤ r) (hi : r ≤ 149) : covered r := by
  have h : r = 100 ∨ r = 101 ∨ r = 102 ∨ r = 103 ∨ r = 104 ∨ r = 105 ∨ r = 106 ∨ r = 107 ∨ r = 108 ∨ r = 109 ∨ r = 110 ∨ r = 111 ∨ r = 112 ∨ r = 113 ∨ r = 114 ∨ r = 115 ∨ r = 116 ∨ r = 117 ∨ r = 118 ∨ r = 119 ∨ r = 120 ∨ r = 121 ∨ r = 122 ∨ r = 123 ∨ r = 124 ∨ r = 125 ∨ r = 126 ∨ r = 127 ∨ r = 128 ∨ r = 129 ∨ r = 130 ∨ r = 131 ∨ r = 132 ∨ r = 133 ∨ r = 134 ∨ r = 135 ∨ r = 136 ∨ r = 137 ∨ r = 138 ∨ r = 139 ∨ r = 140 ∨ r = 141 ∨ r = 142 ∨ r = 143 ∨ r = 144 ∨ r = 145 ∨ r = 146 ∨ r = 147 ∨ r = 148 ∨ r = 149 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨100, by decide, by decide, by decide⟩
  · subst r; exact ⟨101, by decide, by decide, by decide⟩
  · subst r; exact ⟨102, by decide, by decide, by decide⟩
  · subst r; exact ⟨103, by decide, by decide, by decide⟩
  · subst r; exact ⟨104, by decide, by decide, by decide⟩
  · subst r; exact ⟨105, by decide, by decide, by decide⟩
  · subst r; exact ⟨106, by decide, by decide, by decide⟩
  · subst r; exact ⟨67, by decide, by decide, by decide⟩
  · subst r; exact ⟨108, by decide, by decide, by decide⟩
  · subst r; exact ⟨23, by decide, by decide, by decide⟩
  · subst r; exact ⟨110, by decide, by decide, by decide⟩
  · subst r; exact ⟨111, by decide, by decide, by decide⟩
  · subst r; exact ⟨112, by decide, by decide, by decide⟩
  · subst r; exact ⟨113, by decide, by decide, by decide⟩
  · subst r; exact ⟨114, by decide, by decide, by decide⟩
  · subst r; exact ⟨115, by decide, by decide, by decide⟩
  · subst r; exact ⟨116, by decide, by decide, by decide⟩
  · subst r; exact ⟨117, by decide, by decide, by decide⟩
  · subst r; exact ⟨118, by decide, by decide, by decide⟩
  · subst r; exact ⟨119, by decide, by decide, by decide⟩
  · subst r; exact ⟨120, by decide, by decide, by decide⟩
  · subst r; exact ⟨121, by decide, by decide, by decide⟩
  · subst r; exact ⟨122, by decide, by decide, by decide⟩
  · subst r; exact ⟨123, by decide, by decide, by decide⟩
  · subst r; exact ⟨124, by decide, by decide, by decide⟩
  · subst r; exact ⟨125, by decide, by decide, by decide⟩
  · subst r; exact ⟨126, by decide, by decide, by decide⟩
  · subst r; exact ⟨127, by decide, by decide, by decide⟩
  · subst r; exact ⟨111, by decide, by decide, by decide⟩
  · subst r; exact ⟨129, by decide, by decide, by decide⟩
  · subst r; exact ⟨42, by decide, by decide, by decide⟩
  · subst r; exact ⟨131, by decide, by decide, by decide⟩
  · subst r; exact ⟨63, by decide, by decide, by decide⟩
  · subst r; exact ⟨133, by decide, by decide, by decide⟩
  · subst r; exact ⟨134, by decide, by decide, by decide⟩
  · subst r; exact ⟨135, by decide, by decide, by decide⟩
  · subst r; exact ⟨136, by decide, by decide, by decide⟩
  · subst r; exact ⟨137, by decide, by decide, by decide⟩
  · subst r; exact ⟨138, by decide, by decide, by decide⟩
  · subst r; exact ⟨139, by decide, by decide, by decide⟩
  · subst r; exact ⟨140, by decide, by decide, by decide⟩
  · subst r; exact ⟨141, by decide, by decide, by decide⟩
  · subst r; exact ⟨142, by decide, by decide, by decide⟩
  · subst r; exact ⟨143, by decide, by decide, by decide⟩
  · subst r; exact ⟨144, by decide, by decide, by decide⟩
  · subst r; exact ⟨145, by decide, by decide, by decide⟩
  · subst r; exact ⟨146, by decide, by decide, by decide⟩
  · subst r; exact ⟨147, by decide, by decide, by decide⟩
  · subst r; exact ⟨148, by decide, by decide, by decide⟩
  · subst r; exact ⟨149, by decide, by decide, by decide⟩

theorem slice_3 (r : Nat) (lo : 150 ≤ r) (hi : r ≤ 199) : covered r := by
  have h : r = 150 ∨ r = 151 ∨ r = 152 ∨ r = 153 ∨ r = 154 ∨ r = 155 ∨ r = 156 ∨ r = 157 ∨ r = 158 ∨ r = 159 ∨ r = 160 ∨ r = 161 ∨ r = 162 ∨ r = 163 ∨ r = 164 ∨ r = 165 ∨ r = 166 ∨ r = 167 ∨ r = 168 ∨ r = 169 ∨ r = 170 ∨ r = 171 ∨ r = 172 ∨ r = 173 ∨ r = 174 ∨ r = 175 ∨ r = 176 ∨ r = 177 ∨ r = 178 ∨ r = 179 ∨ r = 180 ∨ r = 181 ∨ r = 182 ∨ r = 183 ∨ r = 184 ∨ r = 185 ∨ r = 186 ∨ r = 187 ∨ r = 188 ∨ r = 189 ∨ r = 190 ∨ r = 191 ∨ r = 192 ∨ r = 193 ∨ r = 194 ∨ r = 195 ∨ r = 196 ∨ r = 197 ∨ r = 198 ∨ r = 199 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨150, by decide, by decide, by decide⟩
  · subst r; exact ⟨2, by decide, by decide, by decide⟩
  · subst r; exact ⟨152, by decide, by decide, by decide⟩
  · subst r; exact ⟨2, by decide, by decide, by decide⟩
  · subst r; exact ⟨154, by decide, by decide, by decide⟩
  · subst r; exact ⟨149, by decide, by decide, by decide⟩
  · subst r; exact ⟨156, by decide, by decide, by decide⟩
  · subst r; exact ⟨157, by decide, by decide, by decide⟩
  · subst r; exact ⟨158, by decide, by decide, by decide⟩
  · subst r; exact ⟨159, by decide, by decide, by decide⟩
  · subst r; exact ⟨160, by decide, by decide, by decide⟩
  · subst r; exact ⟨161, by decide, by decide, by decide⟩
  · subst r; exact ⟨162, by decide, by decide, by decide⟩
  · subst r; exact ⟨163, by decide, by decide, by decide⟩
  · subst r; exact ⟨164, by decide, by decide, by decide⟩
  · subst r; exact ⟨165, by decide, by decide, by decide⟩
  · subst r; exact ⟨166, by decide, by decide, by decide⟩
  · subst r; exact ⟨167, by decide, by decide, by decide⟩
  · subst r; exact ⟨168, by decide, by decide, by decide⟩
  · subst r; exact ⟨169, by decide, by decide, by decide⟩
  · subst r; exact ⟨170, by decide, by decide, by decide⟩
  · subst r; exact ⟨171, by decide, by decide, by decide⟩
  · subst r; exact ⟨46, by decide, by decide, by decide⟩
  · subst r; exact ⟨173, by decide, by decide, by decide⟩
  · subst r; exact ⟨67, by decide, by decide, by decide⟩
  · subst r; exact ⟨175, by decide, by decide, by decide⟩
  · subst r; exact ⟨84, by decide, by decide, by decide⟩
  · subst r; exact ⟨177, by decide, by decide, by decide⟩
  · subst r; exact ⟨178, by decide, by decide, by decide⟩
  · subst r; exact ⟨179, by decide, by decide, by decide⟩
  · subst r; exact ⟨180, by decide, by decide, by decide⟩
  · subst r; exact ⟨181, by decide, by decide, by decide⟩
  · subst r; exact ⟨182, by decide, by decide, by decide⟩
  · subst r; exact ⟨183, by decide, by decide, by decide⟩
  · subst r; exact ⟨184, by decide, by decide, by decide⟩
  · subst r; exact ⟨185, by decide, by decide, by decide⟩
  · subst r; exact ⟨186, by decide, by decide, by decide⟩
  · subst r; exact ⟨187, by decide, by decide, by decide⟩
  · subst r; exact ⟨188, by decide, by decide, by decide⟩
  · subst r; exact ⟨189, by decide, by decide, by decide⟩
  · subst r; exact ⟨190, by decide, by decide, by decide⟩
  · subst r; exact ⟨191, by decide, by decide, by decide⟩
  · subst r; exact ⟨192, by decide, by decide, by decide⟩
  · subst r; exact ⟨90, by decide, by decide, by decide⟩
  · subst r; exact ⟨194, by decide, by decide, by decide⟩
  · subst r; exact ⟨63, by decide, by decide, by decide⟩
  · subst r; exact ⟨196, by decide, by decide, by decide⟩
  · subst r; exact ⟨19, by decide, by decide, by decide⟩
  · subst r; exact ⟨198, by decide, by decide, by decide⟩
  · subst r; exact ⟨170, by decide, by decide, by decide⟩

theorem slice_4 (r : Nat) (lo : 200 ≤ r) (hi : r ≤ 249) : covered r := by
  have h : r = 200 ∨ r = 201 ∨ r = 202 ∨ r = 203 ∨ r = 204 ∨ r = 205 ∨ r = 206 ∨ r = 207 ∨ r = 208 ∨ r = 209 ∨ r = 210 ∨ r = 211 ∨ r = 212 ∨ r = 213 ∨ r = 214 ∨ r = 215 ∨ r = 216 ∨ r = 217 ∨ r = 218 ∨ r = 219 ∨ r = 220 ∨ r = 221 ∨ r = 222 ∨ r = 223 ∨ r = 224 ∨ r = 225 ∨ r = 226 ∨ r = 227 ∨ r = 228 ∨ r = 229 ∨ r = 230 ∨ r = 231 ∨ r = 232 ∨ r = 233 ∨ r = 234 ∨ r = 235 ∨ r = 236 ∨ r = 237 ∨ r = 238 ∨ r = 239 ∨ r = 240 ∨ r = 241 ∨ r = 242 ∨ r = 243 ∨ r = 244 ∨ r = 245 ∨ r = 246 ∨ r = 247 ∨ r = 248 ∨ r = 249 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨200, by decide, by decide, by decide⟩
  · subst r; exact ⟨201, by decide, by decide, by decide⟩
  · subst r; exact ⟨202, by decide, by decide, by decide⟩
  · subst r; exact ⟨203, by decide, by decide, by decide⟩
  · subst r; exact ⟨204, by decide, by decide, by decide⟩
  · subst r; exact ⟨205, by decide, by decide, by decide⟩
  · subst r; exact ⟨206, by decide, by decide, by decide⟩
  · subst r; exact ⟨207, by decide, by decide, by decide⟩
  · subst r; exact ⟨208, by decide, by decide, by decide⟩
  · subst r; exact ⟨209, by decide, by decide, by decide⟩
  · subst r; exact ⟨210, by decide, by decide, by decide⟩
  · subst r; exact ⟨211, by decide, by decide, by decide⟩
  · subst r; exact ⟨212, by decide, by decide, by decide⟩
  · subst r; exact ⟨213, by decide, by decide, by decide⟩
  · subst r; exact ⟨134, by decide, by decide, by decide⟩
  · subst r; exact ⟨215, by decide, by decide, by decide⟩
  · subst r; exact ⟨19, by decide, by decide, by decide⟩
  · subst r; exact ⟨217, by decide, by decide, by decide⟩
  · subst r; exact ⟨46, by decide, by decide, by decide⟩
  · subst r; exact ⟨219, by decide, by decide, by decide⟩
  · subst r; exact ⟨105, by decide, by decide, by decide⟩
  · subst r; exact ⟨221, by decide, by decide, by decide⟩
  · subst r; exact ⟨222, by decide, by decide, by decide⟩
  · subst r; exact ⟨223, by decide, by decide, by decide⟩
  · subst r; exact ⟨224, by decide, by decide, by decide⟩
  · subst r; exact ⟨225, by decide, by decide, by decide⟩
  · subst r; exact ⟨226, by decide, by decide, by decide⟩
  · subst r; exact ⟨227, by decide, by decide, by decide⟩
  · subst r; exact ⟨228, by decide, by decide, by decide⟩
  · subst r; exact ⟨229, by decide, by decide, by decide⟩
  · subst r; exact ⟨230, by decide, by decide, by decide⟩
  · subst r; exact ⟨231, by decide, by decide, by decide⟩
  · subst r; exact ⟨232, by decide, by decide, by decide⟩
  · subst r; exact ⟨233, by decide, by decide, by decide⟩
  · subst r; exact ⟨234, by decide, by decide, by decide⟩
  · subst r; exact ⟨178, by decide, by decide, by decide⟩
  · subst r; exact ⟨236, by decide, by decide, by decide⟩
  · subst r; exact ⟨25, by decide, by decide, by decide⟩
  · subst r; exact ⟨238, by decide, by decide, by decide⟩
  · subst r; exact ⟨111, by decide, by decide, by decide⟩
  · subst r; exact ⟨240, by decide, by decide, by decide⟩
  · subst r; exact ⟨40, by decide, by decide, by decide⟩
  · subst r; exact ⟨242, by decide, by decide, by decide⟩
  · subst r; exact ⟨191, by decide, by decide, by decide⟩
  · subst r; exact ⟨244, by decide, by decide, by decide⟩
  · subst r; exact ⟨245, by decide, by decide, by decide⟩
  · subst r; exact ⟨246, by decide, by decide, by decide⟩
  · subst r; exact ⟨247, by decide, by decide, by decide⟩
  · subst r; exact ⟨248, by decide, by decide, by decide⟩
  · subst r; exact ⟨249, by decide, by decide, by decide⟩

theorem slice_5 (r : Nat) (lo : 250 ≤ r) (hi : r ≤ 299) : covered r := by
  have h : r = 250 ∨ r = 251 ∨ r = 252 ∨ r = 253 ∨ r = 254 ∨ r = 255 ∨ r = 256 ∨ r = 257 ∨ r = 258 ∨ r = 259 ∨ r = 260 ∨ r = 261 ∨ r = 262 ∨ r = 263 ∨ r = 264 ∨ r = 265 ∨ r = 266 ∨ r = 267 ∨ r = 268 ∨ r = 269 ∨ r = 270 ∨ r = 271 ∨ r = 272 ∨ r = 273 ∨ r = 274 ∨ r = 275 ∨ r = 276 ∨ r = 277 ∨ r = 278 ∨ r = 279 ∨ r = 280 ∨ r = 281 ∨ r = 282 ∨ r = 283 ∨ r = 284 ∨ r = 285 ∨ r = 286 ∨ r = 287 ∨ r = 288 ∨ r = 289 ∨ r = 290 ∨ r = 291 ∨ r = 292 ∨ r = 293 ∨ r = 294 ∨ r = 295 ∨ r = 296 ∨ r = 297 ∨ r = 298 ∨ r = 299 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨250, by decide, by decide, by decide⟩
  · subst r; exact ⟨251, by decide, by decide, by decide⟩
  · subst r; exact ⟨252, by decide, by decide, by decide⟩
  · subst r; exact ⟨253, by decide, by decide, by decide⟩
  · subst r; exact ⟨254, by decide, by decide, by decide⟩
  · subst r; exact ⟨255, by decide, by decide, by decide⟩
  · subst r; exact ⟨222, by decide, by decide, by decide⟩
  · subst r; exact ⟨257, by decide, by decide, by decide⟩
  · subst r; exact ⟨69, by decide, by decide, by decide⟩
  · subst r; exact ⟨259, by decide, by decide, by decide⟩
  · subst r; exact ⟨84, by decide, by decide, by decide⟩
  · subst r; exact ⟨261, by decide, by decide, by decide⟩
  · subst r; exact ⟨25, by decide, by decide, by decide⟩
  · subst r; exact ⟨263, by decide, by decide, by decide⟩
  · subst r; exact ⟨126, by decide, by decide, by decide⟩
  · subst r; exact ⟨265, by decide, by decide, by decide⟩
  · subst r; exact ⟨266, by decide, by decide, by decide⟩
  · subst r; exact ⟨267, by decide, by decide, by decide⟩
  · subst r; exact ⟨268, by decide, by decide, by decide⟩
  · subst r; exact ⟨269, by decide, by decide, by decide⟩
  · subst r; exact ⟨270, by decide, by decide, by decide⟩
  · subst r; exact ⟨271, by decide, by decide, by decide⟩
  · subst r; exact ⟨272, by decide, by decide, by decide⟩
  · subst r; exact ⟨273, by decide, by decide, by decide⟩
  · subst r; exact ⟨274, by decide, by decide, by decide⟩
  · subst r; exact ⟨275, by decide, by decide, by decide⟩
  · subst r; exact ⟨276, by decide, by decide, by decide⟩
  · subst r; exact ⟨266, by decide, by decide, by decide⟩
  · subst r; exact ⟨278, by decide, by decide, by decide⟩
  · subst r; exact ⟨113, by decide, by decide, by decide⟩
  · subst r; exact ⟨280, by decide, by decide, by decide⟩
  · subst r; exact ⟨40, by decide, by decide, by decide⟩
  · subst r; exact ⟨282, by decide, by decide, by decide⟩
  · subst r; exact ⟨90, by decide, by decide, by decide⟩
  · subst r; exact ⟨284, by decide, by decide, by decide⟩
  · subst r; exact ⟨61, by decide, by decide, by decide⟩
  · subst r; exact ⟨286, by decide, by decide, by decide⟩
  · subst r; exact ⟨212, by decide, by decide, by decide⟩
  · subst r; exact ⟨288, by decide, by decide, by decide⟩
  · subst r; exact ⟨289, by decide, by decide, by decide⟩
  · subst r; exact ⟨290, by decide, by decide, by decide⟩
  · subst r; exact ⟨291, by decide, by decide, by decide⟩
  · subst r; exact ⟨292, by decide, by decide, by decide⟩
  · subst r; exact ⟨293, by decide, by decide, by decide⟩
  · subst r; exact ⟨294, by decide, by decide, by decide⟩
  · subst r; exact ⟨295, by decide, by decide, by decide⟩
  · subst r; exact ⟨296, by decide, by decide, by decide⟩
  · subst r; exact ⟨297, by decide, by decide, by decide⟩
  · subst r; exact ⟨298, by decide, by decide, by decide⟩
  · subst r; exact ⟨299, by decide, by decide, by decide⟩

theorem slice_6 (r : Nat) (lo : 300 ≤ r) (hi : r ≤ 349) : covered r := by
  have h : r = 300 ∨ r = 301 ∨ r = 302 ∨ r = 303 ∨ r = 304 ∨ r = 305 ∨ r = 306 ∨ r = 307 ∨ r = 308 ∨ r = 309 ∨ r = 310 ∨ r = 311 ∨ r = 312 ∨ r = 313 ∨ r = 314 ∨ r = 315 ∨ r = 316 ∨ r = 317 ∨ r = 318 ∨ r = 319 ∨ r = 320 ∨ r = 321 ∨ r = 322 ∨ r = 323 ∨ r = 324 ∨ r = 325 ∨ r = 326 ∨ r = 327 ∨ r = 328 ∨ r = 329 ∨ r = 330 ∨ r = 331 ∨ r = 332 ∨ r = 333 ∨ r = 334 ∨ r = 335 ∨ r = 336 ∨ r = 337 ∨ r = 338 ∨ r = 339 ∨ r = 340 ∨ r = 341 ∨ r = 342 ∨ r = 343 ∨ r = 344 ∨ r = 345 ∨ r = 346 ∨ r = 347 ∨ r = 348 ∨ r = 349 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨157, by decide, by decide, by decide⟩
  · subst r; exact ⟨301, by decide, by decide, by decide⟩
  · subst r; exact ⟨4, by decide, by decide, by decide⟩
  · subst r; exact ⟨303, by decide, by decide, by decide⟩
  · subst r; exact ⟨149, by decide, by decide, by decide⟩
  · subst r; exact ⟨305, by decide, by decide, by decide⟩
  · subst r; exact ⟨4, by decide, by decide, by decide⟩
  · subst r; exact ⟨307, by decide, by decide, by decide⟩
  · subst r; exact ⟨147, by decide, by decide, by decide⟩
  · subst r; exact ⟨309, by decide, by decide, by decide⟩
  · subst r; exact ⟨298, by decide, by decide, by decide⟩
  · subst r; exact ⟨311, by decide, by decide, by decide⟩
  · subst r; exact ⟨312, by decide, by decide, by decide⟩
  · subst r; exact ⟨313, by decide, by decide, by decide⟩
  · subst r; exact ⟨314, by decide, by decide, by decide⟩
  · subst r; exact ⟨315, by decide, by decide, by decide⟩
  · subst r; exact ⟨316, by decide, by decide, by decide⟩
  · subst r; exact ⟨317, by decide, by decide, by decide⟩
  · subst r; exact ⟨318, by decide, by decide, by decide⟩
  · subst r; exact ⟨319, by decide, by decide, by decide⟩
  · subst r; exact ⟨320, by decide, by decide, by decide⟩
  · subst r; exact ⟨201, by decide, by decide, by decide⟩
  · subst r; exact ⟨322, by decide, by decide, by decide⟩
  · subst r; exact ⟨48, by decide, by decide, by decide⟩
  · subst r; exact ⟨324, by decide, by decide, by decide⟩
  · subst r; exact ⟨105, by decide, by decide, by decide⟩
  · subst r; exact ⟨326, by decide, by decide, by decide⟩
  · subst r; exact ⟨69, by decide, by decide, by decide⟩
  · subst r; exact ⟨328, by decide, by decide, by decide⟩
  · subst r; exact ⟨82, by decide, by decide, by decide⟩
  · subst r; exact ⟨330, by decide, by decide, by decide⟩
  · subst r; exact ⟨233, by decide, by decide, by decide⟩
  · subst r; exact ⟨332, by decide, by decide, by decide⟩
  · subst r; exact ⟨333, by decide, by decide, by decide⟩
  · subst r; exact ⟨334, by decide, by decide, by decide⟩
  · subst r; exact ⟨335, by decide, by decide, by decide⟩
  · subst r; exact ⟨336, by decide, by decide, by decide⟩
  · subst r; exact ⟨337, by decide, by decide, by decide⟩
  · subst r; exact ⟨338, by decide, by decide, by decide⟩
  · subst r; exact ⟨339, by decide, by decide, by decide⟩
  · subst r; exact ⟨340, by decide, by decide, by decide⟩
  · subst r; exact ⟨341, by decide, by decide, by decide⟩
  · subst r; exact ⟨245, by decide, by decide, by decide⟩
  · subst r; exact ⟨343, by decide, by decide, by decide⟩
  · subst r; exact ⟨92, by decide, by decide, by decide⟩
  · subst r; exact ⟨345, by decide, by decide, by decide⟩
  · subst r; exact ⟨61, by decide, by decide, by decide⟩
  · subst r; exact ⟨347, by decide, by decide, by decide⟩
  · subst r; exact ⟨134, by decide, by decide, by decide⟩
  · subst r; exact ⟨349, by decide, by decide, by decide⟩

theorem slice_7 (r : Nat) (lo : 350 ≤ r) (hi : r ≤ 399) : covered r := by
  have h : r = 350 ∨ r = 351 ∨ r = 352 ∨ r = 353 ∨ r = 354 ∨ r = 355 ∨ r = 356 ∨ r = 357 ∨ r = 358 ∨ r = 359 ∨ r = 360 ∨ r = 361 ∨ r = 362 ∨ r = 363 ∨ r = 364 ∨ r = 365 ∨ r = 366 ∨ r = 367 ∨ r = 368 ∨ r = 369 ∨ r = 370 ∨ r = 371 ∨ r = 372 ∨ r = 373 ∨ r = 374 ∨ r = 375 ∨ r = 376 ∨ r = 377 ∨ r = 378 ∨ r = 379 ∨ r = 380 ∨ r = 381 ∨ r = 382 ∨ r = 383 ∨ r = 384 ∨ r = 385 ∨ r = 386 ∨ r = 387 ∨ r = 388 ∨ r = 389 ∨ r = 390 ∨ r = 391 ∨ r = 392 ∨ r = 393 ∨ r = 394 ∨ r = 395 ∨ r = 396 ∨ r = 397 ∨ r = 398 ∨ r = 399 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨17, by decide, by decide, by decide⟩
  · subst r; exact ⟨351, by decide, by decide, by decide⟩
  · subst r; exact ⟨168, by decide, by decide, by decide⟩
  · subst r; exact ⟨353, by decide, by decide, by decide⟩
  · subst r; exact ⟨319, by decide, by decide, by decide⟩
  · subst r; exact ⟨355, by decide, by decide, by decide⟩
  · subst r; exact ⟨356, by decide, by decide, by decide⟩
  · subst r; exact ⟨357, by decide, by decide, by decide⟩
  · subst r; exact ⟨358, by decide, by decide, by decide⟩
  · subst r; exact ⟨359, by decide, by decide, by decide⟩
  · subst r; exact ⟨360, by decide, by decide, by decide⟩
  · subst r; exact ⟨361, by decide, by decide, by decide⟩
  · subst r; exact ⟨362, by decide, by decide, by decide⟩
  · subst r; exact ⟨289, by decide, by decide, by decide⟩
  · subst r; exact ⟨364, by decide, by decide, by decide⟩
  · subst r; exact ⟨136, by decide, by decide, by decide⟩
  · subst r; exact ⟨366, by decide, by decide, by decide⟩
  · subst r; exact ⟨17, by decide, by decide, by decide⟩
  · subst r; exact ⟨368, by decide, by decide, by decide⟩
  · subst r; exact ⟨170, by decide, by decide, by decide⟩
  · subst r; exact ⟨370, by decide, by decide, by decide⟩
  · subst r; exact ⟨48, by decide, by decide, by decide⟩
  · subst r; exact ⟨372, by decide, by decide, by decide⟩
  · subst r; exact ⟨103, by decide, by decide, by decide⟩
  · subst r; exact ⟨374, by decide, by decide, by decide⟩
  · subst r; exact ⟨254, by decide, by decide, by decide⟩
  · subst r; exact ⟨376, by decide, by decide, by decide⟩
  · subst r; exact ⟨377, by decide, by decide, by decide⟩
  · subst r; exact ⟨378, by decide, by decide, by decide⟩
  · subst r; exact ⟨379, by decide, by decide, by decide⟩
  · subst r; exact ⟨380, by decide, by decide, by decide⟩
  · subst r; exact ⟨381, by decide, by decide, by decide⟩
  · subst r; exact ⟨382, by decide, by decide, by decide⟩
  · subst r; exact ⟨383, by decide, by decide, by decide⟩
  · subst r; exact ⟨333, by decide, by decide, by decide⟩
  · subst r; exact ⟨385, by decide, by decide, by decide⟩
  · subst r; exact ⟨180, by decide, by decide, by decide⟩
  · subst r; exact ⟨387, by decide, by decide, by decide⟩
  · subst r; exact ⟨27, by decide, by decide, by decide⟩
  · subst r; exact ⟨389, by decide, by decide, by decide⟩
  · subst r; exact ⟨126, by decide, by decide, by decide⟩
  · subst r; exact ⟨391, by decide, by decide, by decide⟩
  · subst r; exact ⟨113, by decide, by decide, by decide⟩
  · subst r; exact ⟨393, by decide, by decide, by decide⟩
  · subst r; exact ⟨38, by decide, by decide, by decide⟩
  · subst r; exact ⟨395, by decide, by decide, by decide⟩
  · subst r; exact ⟨189, by decide, by decide, by decide⟩
  · subst r; exact ⟨397, by decide, by decide, by decide⟩
  · subst r; exact ⟨340, by decide, by decide, by decide⟩
  · subst r; exact ⟨399, by decide, by decide, by decide⟩

theorem slice_8 (r : Nat) (lo : 400 ≤ r) (hi : r ≤ 449) : covered r := by
  have h : r = 400 ∨ r = 401 ∨ r = 402 ∨ r = 403 ∨ r = 404 ∨ r = 405 ∨ r = 406 ∨ r = 407 ∨ r = 408 ∨ r = 409 ∨ r = 410 ∨ r = 411 ∨ r = 412 ∨ r = 413 ∨ r = 414 ∨ r = 415 ∨ r = 416 ∨ r = 417 ∨ r = 418 ∨ r = 419 ∨ r = 420 ∨ r = 421 ∨ r = 422 ∨ r = 423 ∨ r = 424 ∨ r = 425 ∨ r = 426 ∨ r = 427 ∨ r = 428 ∨ r = 429 ∨ r = 430 ∨ r = 431 ∨ r = 432 ∨ r = 433 ∨ r = 434 ∨ r = 435 ∨ r = 436 ∨ r = 437 ∨ r = 438 ∨ r = 439 ∨ r = 440 ∨ r = 441 ∨ r = 442 ∨ r = 443 ∨ r = 444 ∨ r = 445 ∨ r = 446 ∨ r = 447 ∨ r = 448 ∨ r = 449 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨400, by decide, by decide, by decide⟩
  · subst r; exact ⟨401, by decide, by decide, by decide⟩
  · subst r; exact ⟨402, by decide, by decide, by decide⟩
  · subst r; exact ⟨403, by decide, by decide, by decide⟩
  · subst r; exact ⟨404, by decide, by decide, by decide⟩
  · subst r; exact ⟨377, by decide, by decide, by decide⟩
  · subst r; exact ⟨406, by decide, by decide, by decide⟩
  · subst r; exact ⟨224, by decide, by decide, by decide⟩
  · subst r; exact ⟨408, by decide, by decide, by decide⟩
  · subst r; exact ⟨71, by decide, by decide, by decide⟩
  · subst r; exact ⟨410, by decide, by decide, by decide⟩
  · subst r; exact ⟨82, by decide, by decide, by decide⟩
  · subst r; exact ⟨412, by decide, by decide, by decide⟩
  · subst r; exact ⟨178, by decide, by decide, by decide⟩
  · subst r; exact ⟨414, by decide, by decide, by decide⟩
  · subst r; exact ⟨27, by decide, by decide, by decide⟩
  · subst r; exact ⟨416, by decide, by decide, by decide⟩
  · subst r; exact ⟨124, by decide, by decide, by decide⟩
  · subst r; exact ⟨418, by decide, by decide, by decide⟩
  · subst r; exact ⟨275, by decide, by decide, by decide⟩
  · subst r; exact ⟨420, by decide, by decide, by decide⟩
  · subst r; exact ⟨421, by decide, by decide, by decide⟩
  · subst r; exact ⟨422, by decide, by decide, by decide⟩
  · subst r; exact ⟨423, by decide, by decide, by decide⟩
  · subst r; exact ⟨424, by decide, by decide, by decide⟩
  · subst r; exact ⟨425, by decide, by decide, by decide⟩
  · subst r; exact ⟨421, by decide, by decide, by decide⟩
  · subst r; exact ⟨427, by decide, by decide, by decide⟩
  · subst r; exact ⟨268, by decide, by decide, by decide⟩
  · subst r; exact ⟨429, by decide, by decide, by decide⟩
  · subst r; exact ⟨115, by decide, by decide, by decide⟩
  · subst r; exact ⟨431, by decide, by decide, by decide⟩
  · subst r; exact ⟨38, by decide, by decide, by decide⟩
  · subst r; exact ⟨433, by decide, by decide, by decide⟩
  · subst r; exact ⟨191, by decide, by decide, by decide⟩
  · subst r; exact ⟨435, by decide, by decide, by decide⟩
  · subst r; exact ⟨92, by decide, by decide, by decide⟩
  · subst r; exact ⟨437, by decide, by decide, by decide⟩
  · subst r; exact ⟨59, by decide, by decide, by decide⟩
  · subst r; exact ⟨439, by decide, by decide, by decide⟩
  · subst r; exact ⟨210, by decide, by decide, by decide⟩
  · subst r; exact ⟨441, by decide, by decide, by decide⟩
  · subst r; exact ⟨361, by decide, by decide, by decide⟩
  · subst r; exact ⟨443, by decide, by decide, by decide⟩
  · subst r; exact ⟨444, by decide, by decide, by decide⟩
  · subst r; exact ⟨445, by decide, by decide, by decide⟩
  · subst r; exact ⟨446, by decide, by decide, by decide⟩
  · subst r; exact ⟨447, by decide, by decide, by decide⟩
  · subst r; exact ⟨448, by decide, by decide, by decide⟩
  · subst r; exact ⟨312, by decide, by decide, by decide⟩

theorem slice_9 (r : Nat) (lo : 450 ≤ r) (hi : r ≤ 499) : covered r := by
  have h : r = 450 ∨ r = 451 ∨ r = 452 ∨ r = 453 ∨ r = 454 ∨ r = 455 ∨ r = 456 ∨ r = 457 ∨ r = 458 ∨ r = 459 ∨ r = 460 ∨ r = 461 ∨ r = 462 ∨ r = 463 ∨ r = 464 ∨ r = 465 ∨ r = 466 ∨ r = 467 ∨ r = 468 ∨ r = 469 ∨ r = 470 ∨ r = 471 ∨ r = 472 ∨ r = 473 ∨ r = 474 ∨ r = 475 ∨ r = 476 ∨ r = 477 ∨ r = 478 ∨ r = 479 ∨ r = 480 ∨ r = 481 ∨ r = 482 ∨ r = 483 ∨ r = 484 ∨ r = 485 ∨ r = 486 ∨ r = 487 ∨ r = 488 ∨ r = 489 ∨ r = 490 ∨ r = 491 ∨ r = 492 ∨ r = 493 ∨ r = 494 ∨ r = 495 ∨ r = 496 ∨ r = 497 ∨ r = 498 ∨ r = 499 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨450, by decide, by decide, by decide⟩
  · subst r; exact ⟨159, by decide, by decide, by decide⟩
  · subst r; exact ⟨452, by decide, by decide, by decide⟩
  · subst r; exact ⟨6, by decide, by decide, by decide⟩
  · subst r; exact ⟨454, by decide, by decide, by decide⟩
  · subst r; exact ⟨147, by decide, by decide, by decide⟩
  · subst r; exact ⟨456, by decide, by decide, by decide⟩
  · subst r; exact ⟨157, by decide, by decide, by decide⟩
  · subst r; exact ⟨458, by decide, by decide, by decide⟩
  · subst r; exact ⟨6, by decide, by decide, by decide⟩
  · subst r; exact ⟨460, by decide, by decide, by decide⟩
  · subst r; exact ⟨145, by decide, by decide, by decide⟩
  · subst r; exact ⟨462, by decide, by decide, by decide⟩
  · subst r; exact ⟨296, by decide, by decide, by decide⟩
  · subst r; exact ⟨464, by decide, by decide, by decide⟩
  · subst r; exact ⟨447, by decide, by decide, by decide⟩
  · subst r; exact ⟨466, by decide, by decide, by decide⟩
  · subst r; exact ⟨467, by decide, by decide, by decide⟩
  · subst r; exact ⟨468, by decide, by decide, by decide⟩
  · subst r; exact ⟨469, by decide, by decide, by decide⟩
  · subst r; exact ⟨356, by decide, by decide, by decide⟩
  · subst r; exact ⟨471, by decide, by decide, by decide⟩
  · subst r; exact ⟨203, by decide, by decide, by decide⟩
  · subst r; exact ⟨473, by decide, by decide, by decide⟩
  · subst r; exact ⟨50, by decide, by decide, by decide⟩
  · subst r; exact ⟨475, by decide, by decide, by decide⟩
  · subst r; exact ⟨103, by decide, by decide, by decide⟩
  · subst r; exact ⟨477, by decide, by decide, by decide⟩
  · subst r; exact ⟨222, by decide, by decide, by decide⟩
  · subst r; exact ⟨479, by decide, by decide, by decide⟩
  · subst r; exact ⟨71, by decide, by decide, by decide⟩
  · subst r; exact ⟨481, by decide, by decide, by decide⟩
  · subst r; exact ⟨80, by decide, by decide, by decide⟩
  · subst r; exact ⟨483, by decide, by decide, by decide⟩
  · subst r; exact ⟨231, by decide, by decide, by decide⟩
  · subst r; exact ⟨485, by decide, by decide, by decide⟩
  · subst r; exact ⟨382, by decide, by decide, by decide⟩
  · subst r; exact ⟨487, by decide, by decide, by decide⟩
  · subst r; exact ⟨488, by decide, by decide, by decide⟩
  · subst r; exact ⟨489, by decide, by decide, by decide⟩
  · subst r; exact ⟨490, by decide, by decide, by decide⟩
  · subst r; exact ⟨400, by decide, by decide, by decide⟩
  · subst r; exact ⟨492, by decide, by decide, by decide⟩
  · subst r; exact ⟨247, by decide, by decide, by decide⟩
  · subst r; exact ⟨494, by decide, by decide, by decide⟩
  · subst r; exact ⟨94, by decide, by decide, by decide⟩
  · subst r; exact ⟨496, by decide, by decide, by decide⟩
  · subst r; exact ⟨59, by decide, by decide, by decide⟩
  · subst r; exact ⟨498, by decide, by decide, by decide⟩
  · subst r; exact ⟨212, by decide, by decide, by decide⟩

theorem slice_10 (r : Nat) (lo : 500 ≤ r) (hi : r ≤ 549) : covered r := by
  have h : r = 500 ∨ r = 501 ∨ r = 502 ∨ r = 503 ∨ r = 504 ∨ r = 505 ∨ r = 506 ∨ r = 507 ∨ r = 508 ∨ r = 509 ∨ r = 510 ∨ r = 511 ∨ r = 512 ∨ r = 513 ∨ r = 514 ∨ r = 515 ∨ r = 516 ∨ r = 517 ∨ r = 518 ∨ r = 519 ∨ r = 520 ∨ r = 521 ∨ r = 522 ∨ r = 523 ∨ r = 524 ∨ r = 525 ∨ r = 526 ∨ r = 527 ∨ r = 528 ∨ r = 529 ∨ r = 530 ∨ r = 531 ∨ r = 532 ∨ r = 533 ∨ r = 534 ∨ r = 535 ∨ r = 536 ∨ r = 537 ∨ r = 538 ∨ r = 539 ∨ r = 540 ∨ r = 541 ∨ r = 542 ∨ r = 543 ∨ r = 544 ∨ r = 545 ∨ r = 546 ∨ r = 547 ∨ r = 548 ∨ r = 549 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨500, by decide, by decide, by decide⟩
  · subst r; exact ⟨136, by decide, by decide, by decide⟩
  · subst r; exact ⟨502, by decide, by decide, by decide⟩
  · subst r; exact ⟨15, by decide, by decide, by decide⟩
  · subst r; exact ⟨504, by decide, by decide, by decide⟩
  · subst r; exact ⟨166, by decide, by decide, by decide⟩
  · subst r; exact ⟨506, by decide, by decide, by decide⟩
  · subst r; exact ⟨317, by decide, by decide, by decide⟩
  · subst r; exact ⟨508, by decide, by decide, by decide⟩
  · subst r; exact ⟨468, by decide, by decide, by decide⟩
  · subst r; exact ⟨510, by decide, by decide, by decide⟩
  · subst r; exact ⟨511, by decide, by decide, by decide⟩
  · subst r; exact ⟨444, by decide, by decide, by decide⟩
  · subst r; exact ⟨513, by decide, by decide, by decide⟩
  · subst r; exact ⟨291, by decide, by decide, by decide⟩
  · subst r; exact ⟨515, by decide, by decide, by decide⟩
  · subst r; exact ⟨138, by decide, by decide, by decide⟩
  · subst r; exact ⟨517, by decide, by decide, by decide⟩
  · subst r; exact ⟨15, by decide, by decide, by decide⟩
  · subst r; exact ⟨519, by decide, by decide, by decide⟩
  · subst r; exact ⟨168, by decide, by decide, by decide⟩
  · subst r; exact ⟨521, by decide, by decide, by decide⟩
  · subst r; exact ⟨201, by decide, by decide, by decide⟩
  · subst r; exact ⟨523, by decide, by decide, by decide⟩
  · subst r; exact ⟨50, by decide, by decide, by decide⟩
  · subst r; exact ⟨525, by decide, by decide, by decide⟩
  · subst r; exact ⟨101, by decide, by decide, by decide⟩
  · subst r; exact ⟨527, by decide, by decide, by decide⟩
  · subst r; exact ⟨252, by decide, by decide, by decide⟩
  · subst r; exact ⟨529, by decide, by decide, by decide⟩
  · subst r; exact ⟨403, by decide, by decide, by decide⟩
  · subst r; exact ⟨531, by decide, by decide, by decide⟩
  · subst r; exact ⟨532, by decide, by decide, by decide⟩
  · subst r; exact ⟨488, by decide, by decide, by decide⟩
  · subst r; exact ⟨534, by decide, by decide, by decide⟩
  · subst r; exact ⟨335, by decide, by decide, by decide⟩
  · subst r; exact ⟨536, by decide, by decide, by decide⟩
  · subst r; exact ⟨182, by decide, by decide, by decide⟩
  · subst r; exact ⟨538, by decide, by decide, by decide⟩
  · subst r; exact ⟨29, by decide, by decide, by decide⟩
  · subst r; exact ⟨540, by decide, by decide, by decide⟩
  · subst r; exact ⟨124, by decide, by decide, by decide⟩
  · subst r; exact ⟨542, by decide, by decide, by decide⟩
  · subst r; exact ⟨266, by decide, by decide, by decide⟩
  · subst r; exact ⟨544, by decide, by decide, by decide⟩
  · subst r; exact ⟨115, by decide, by decide, by decide⟩
  · subst r; exact ⟨546, by decide, by decide, by decide⟩
  · subst r; exact ⟨36, by decide, by decide, by decide⟩
  · subst r; exact ⟨548, by decide, by decide, by decide⟩
  · subst r; exact ⟨187, by decide, by decide, by decide⟩

theorem slice_11 (r : Nat) (lo : 550 ≤ r) (hi : r ≤ 599) : covered r := by
  have h : r = 550 ∨ r = 551 ∨ r = 552 ∨ r = 553 ∨ r = 554 ∨ r = 555 ∨ r = 556 ∨ r = 557 ∨ r = 558 ∨ r = 559 ∨ r = 560 ∨ r = 561 ∨ r = 562 ∨ r = 563 ∨ r = 564 ∨ r = 565 ∨ r = 566 ∨ r = 567 ∨ r = 568 ∨ r = 569 ∨ r = 570 ∨ r = 571 ∨ r = 572 ∨ r = 573 ∨ r = 574 ∨ r = 575 ∨ r = 576 ∨ r = 577 ∨ r = 578 ∨ r = 579 ∨ r = 580 ∨ r = 581 ∨ r = 582 ∨ r = 583 ∨ r = 584 ∨ r = 585 ∨ r = 586 ∨ r = 587 ∨ r = 588 ∨ r = 589 ∨ r = 590 ∨ r = 591 ∨ r = 592 ∨ r = 593 ∨ r = 594 ∨ r = 595 ∨ r = 596 ∨ r = 597 ∨ r = 598 ∨ r = 599 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨550, by decide, by decide, by decide⟩
  · subst r; exact ⟨338, by decide, by decide, by decide⟩
  · subst r; exact ⟨552, by decide, by decide, by decide⟩
  · subst r; exact ⟨489, by decide, by decide, by decide⟩
  · subst r; exact ⟨532, by decide, by decide, by decide⟩
  · subst r; exact ⟨555, by decide, by decide, by decide⟩
  · subst r; exact ⟨379, by decide, by decide, by decide⟩
  · subst r; exact ⟨557, by decide, by decide, by decide⟩
  · subst r; exact ⟨226, by decide, by decide, by decide⟩
  · subst r; exact ⟨559, by decide, by decide, by decide⟩
  · subst r; exact ⟨73, by decide, by decide, by decide⟩
  · subst r; exact ⟨561, by decide, by decide, by decide⟩
  · subst r; exact ⟨80, by decide, by decide, by decide⟩
  · subst r; exact ⟨563, by decide, by decide, by decide⟩
  · subst r; exact ⟨233, by decide, by decide, by decide⟩
  · subst r; exact ⟨565, by decide, by decide, by decide⟩
  · subst r; exact ⟨180, by decide, by decide, by decide⟩
  · subst r; exact ⟨567, by decide, by decide, by decide⟩
  · subst r; exact ⟨29, by decide, by decide, by decide⟩
  · subst r; exact ⟨569, by decide, by decide, by decide⟩
  · subst r; exact ⟨122, by decide, by decide, by decide⟩
  · subst r; exact ⟨571, by decide, by decide, by decide⟩
  · subst r; exact ⟨273, by decide, by decide, by decide⟩
  · subst r; exact ⟨573, by decide, by decide, by decide⟩
  · subst r; exact ⟨424, by decide, by decide, by decide⟩
  · subst r; exact ⟨575, by decide, by decide, by decide⟩
  · subst r; exact ⟨575, by decide, by decide, by decide⟩
  · subst r; exact ⟨423, by decide, by decide, by decide⟩
  · subst r; exact ⟨578, by decide, by decide, by decide⟩
  · subst r; exact ⟨270, by decide, by decide, by decide⟩
  · subst r; exact ⟨580, by decide, by decide, by decide⟩
  · subst r; exact ⟨117, by decide, by decide, by decide⟩
  · subst r; exact ⟨582, by decide, by decide, by decide⟩
  · subst r; exact ⟨36, by decide, by decide, by decide⟩
  · subst r; exact ⟨584, by decide, by decide, by decide⟩
  · subst r; exact ⟨189, by decide, by decide, by decide⟩
  · subst r; exact ⟨586, by decide, by decide, by decide⟩
  · subst r; exact ⟨245, by decide, by decide, by decide⟩
  · subst r; exact ⟨588, by decide, by decide, by decide⟩
  · subst r; exact ⟨94, by decide, by decide, by decide⟩
  · subst r; exact ⟨590, by decide, by decide, by decide⟩
  · subst r; exact ⟨57, by decide, by decide, by decide⟩
  · subst r; exact ⟨592, by decide, by decide, by decide⟩
  · subst r; exact ⟨208, by decide, by decide, by decide⟩
  · subst r; exact ⟨594, by decide, by decide, by decide⟩
  · subst r; exact ⟨359, by decide, by decide, by decide⟩
  · subst r; exact ⟨596, by decide, by decide, by decide⟩
  · subst r; exact ⟨510, by decide, by decide, by decide⟩
  · subst r; exact ⟨467, by decide, by decide, by decide⟩
  · subst r; exact ⟨599, by decide, by decide, by decide⟩

theorem slice_12 (r : Nat) (lo : 600 ≤ r) (hi : r ≤ 649) : covered r := by
  have h : r = 600 ∨ r = 601 ∨ r = 602 ∨ r = 603 ∨ r = 604 ∨ r = 605 ∨ r = 606 ∨ r = 607 ∨ r = 608 ∨ r = 609 ∨ r = 610 ∨ r = 611 ∨ r = 612 ∨ r = 613 ∨ r = 614 ∨ r = 615 ∨ r = 616 ∨ r = 617 ∨ r = 618 ∨ r = 619 ∨ r = 620 ∨ r = 621 ∨ r = 622 ∨ r = 623 ∨ r = 624 ∨ r = 625 ∨ r = 626 ∨ r = 627 ∨ r = 628 ∨ r = 629 ∨ r = 630 ∨ r = 631 ∨ r = 632 ∨ r = 633 ∨ r = 634 ∨ r = 635 ∨ r = 636 ∨ r = 637 ∨ r = 638 ∨ r = 639 ∨ r = 640 ∨ r = 641 ∨ r = 642 ∨ r = 643 ∨ r = 644 ∨ r = 645 ∨ r = 646 ∨ r = 647 ∨ r = 648 ∨ r = 649 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨314, by decide, by decide, by decide⟩
  · subst r; exact ⟨601, by decide, by decide, by decide⟩
  · subst r; exact ⟨161, by decide, by decide, by decide⟩
  · subst r; exact ⟨603, by decide, by decide, by decide⟩
  · subst r; exact ⟨8, by decide, by decide, by decide⟩
  · subst r; exact ⟨605, by decide, by decide, by decide⟩
  · subst r; exact ⟨145, by decide, by decide, by decide⟩
  · subst r; exact ⟨607, by decide, by decide, by decide⟩
  · subst r; exact ⟨298, by decide, by decide, by decide⟩
  · subst r; exact ⟨609, by decide, by decide, by decide⟩
  · subst r; exact ⟨159, by decide, by decide, by decide⟩
  · subst r; exact ⟨611, by decide, by decide, by decide⟩
  · subst r; exact ⟨8, by decide, by decide, by decide⟩
  · subst r; exact ⟨613, by decide, by decide, by decide⟩
  · subst r; exact ⟨143, by decide, by decide, by decide⟩
  · subst r; exact ⟨615, by decide, by decide, by decide⟩
  · subst r; exact ⟨294, by decide, by decide, by decide⟩
  · subst r; exact ⟨617, by decide, by decide, by decide⟩
  · subst r; exact ⟨445, by decide, by decide, by decide⟩
  · subst r; exact ⟨511, by decide, by decide, by decide⟩
  · subst r; exact ⟨596, by decide, by decide, by decide⟩
  · subst r; exact ⟨358, by decide, by decide, by decide⟩
  · subst r; exact ⟨622, by decide, by decide, by decide⟩
  · subst r; exact ⟨205, by decide, by decide, by decide⟩
  · subst r; exact ⟨624, by decide, by decide, by decide⟩
  · subst r; exact ⟨52, by decide, by decide, by decide⟩
  · subst r; exact ⟨626, by decide, by decide, by decide⟩
  · subst r; exact ⟨101, by decide, by decide, by decide⟩
  · subst r; exact ⟨628, by decide, by decide, by decide⟩
  · subst r; exact ⟨254, by decide, by decide, by decide⟩
  · subst r; exact ⟨630, by decide, by decide, by decide⟩
  · subst r; exact ⟨224, by decide, by decide, by decide⟩
  · subst r; exact ⟨632, by decide, by decide, by decide⟩
  · subst r; exact ⟨73, by decide, by decide, by decide⟩
  · subst r; exact ⟨634, by decide, by decide, by decide⟩
  · subst r; exact ⟨78, by decide, by decide, by decide⟩
  · subst r; exact ⟨636, by decide, by decide, by decide⟩
  · subst r; exact ⟨229, by decide, by decide, by decide⟩
  · subst r; exact ⟨638, by decide, by decide, by decide⟩
  · subst r; exact ⟨380, by decide, by decide, by decide⟩
  · subst r; exact ⟨555, by decide, by decide, by decide⟩
  · subst r; exact ⟨531, by decide, by decide, by decide⟩
  · subst r; exact ⟨402, by decide, by decide, by decide⟩
  · subst r; exact ⟨643, by decide, by decide, by decide⟩
  · subst r; exact ⟨249, by decide, by decide, by decide⟩
  · subst r; exact ⟨645, by decide, by decide, by decide⟩
  · subst r; exact ⟨96, by decide, by decide, by decide⟩
  · subst r; exact ⟨647, by decide, by decide, by decide⟩
  · subst r; exact ⟨57, by decide, by decide, by decide⟩
  · subst r; exact ⟨649, by decide, by decide, by decide⟩

theorem slice_13 (r : Nat) (lo : 650 ≤ r) (hi : r ≤ 699) : covered r := by
  have h : r = 650 ∨ r = 651 ∨ r = 652 ∨ r = 653 ∨ r = 654 ∨ r = 655 ∨ r = 656 ∨ r = 657 ∨ r = 658 ∨ r = 659 ∨ r = 660 ∨ r = 661 ∨ r = 662 ∨ r = 663 ∨ r = 664 ∨ r = 665 ∨ r = 666 ∨ r = 667 ∨ r = 668 ∨ r = 669 ∨ r = 670 ∨ r = 671 ∨ r = 672 ∨ r = 673 ∨ r = 674 ∨ r = 675 ∨ r = 676 ∨ r = 677 ∨ r = 678 ∨ r = 679 ∨ r = 680 ∨ r = 681 ∨ r = 682 ∨ r = 683 ∨ r = 684 ∨ r = 685 ∨ r = 686 ∨ r = 687 ∨ r = 688 ∨ r = 689 ∨ r = 690 ∨ r = 691 ∨ r = 692 ∨ r = 693 ∨ r = 694 ∨ r = 695 ∨ r = 696 ∨ r = 697 ∨ r = 698 ∨ r = 699 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨210, by decide, by decide, by decide⟩
  · subst r; exact ⟨651, by decide, by decide, by decide⟩
  · subst r; exact ⟨289, by decide, by decide, by decide⟩
  · subst r; exact ⟨653, by decide, by decide, by decide⟩
  · subst r; exact ⟨138, by decide, by decide, by decide⟩
  · subst r; exact ⟨655, by decide, by decide, by decide⟩
  · subst r; exact ⟨13, by decide, by decide, by decide⟩
  · subst r; exact ⟨657, by decide, by decide, by decide⟩
  · subst r; exact ⟨164, by decide, by decide, by decide⟩
  · subst r; exact ⟨659, by decide, by decide, by decide⟩
  · subst r; exact ⟨315, by decide, by decide, by decide⟩
  · subst r; exact ⟨599, by decide, by decide, by decide⟩
  · subst r; exact ⟨466, by decide, by decide, by decide⟩
  · subst r; exact ⟨446, by decide, by decide, by decide⟩
  · subst r; exact ⟨617, by decide, by decide, by decide⟩
  · subst r; exact ⟨293, by decide, by decide, by decide⟩
  · subst r; exact ⟨666, by decide, by decide, by decide⟩
  · subst r; exact ⟨140, by decide, by decide, by decide⟩
  · subst r; exact ⟨668, by decide, by decide, by decide⟩
  · subst r; exact ⟨13, by decide, by decide, by decide⟩
  · subst r; exact ⟨670, by decide, by decide, by decide⟩
  · subst r; exact ⟨166, by decide, by decide, by decide⟩
  · subst r; exact ⟨672, by decide, by decide, by decide⟩
  · subst r; exact ⟨319, by decide, by decide, by decide⟩
  · subst r; exact ⟨674, by decide, by decide, by decide⟩
  · subst r; exact ⟨203, by decide, by decide, by decide⟩
  · subst r; exact ⟨676, by decide, by decide, by decide⟩
  · subst r; exact ⟨52, by decide, by decide, by decide⟩
  · subst r; exact ⟨678, by decide, by decide, by decide⟩
  · subst r; exact ⟨99, by decide, by decide, by decide⟩
  · subst r; exact ⟨680, by decide, by decide, by decide⟩
  · subst r; exact ⟨250, by decide, by decide, by decide⟩
  · subst r; exact ⟨643, by decide, by decide, by decide⟩
  · subst r; exact ⟨401, by decide, by decide, by decide⟩
  · subst r; exact ⟨490, by decide, by decide, by decide⟩
  · subst r; exact ⟨552, by decide, by decide, by decide⟩
  · subst r; exact ⟨337, by decide, by decide, by decide⟩
  · subst r; exact ⟨687, by decide, by decide, by decide⟩
  · subst r; exact ⟨184, by decide, by decide, by decide⟩
  · subst r; exact ⟨689, by decide, by decide, by decide⟩
  · subst r; exact ⟨31, by decide, by decide, by decide⟩
  · subst r; exact ⟨691, by decide, by decide, by decide⟩
  · subst r; exact ⟨122, by decide, by decide, by decide⟩
  · subst r; exact ⟨693, by decide, by decide, by decide⟩
  · subst r; exact ⟨275, by decide, by decide, by decide⟩
  · subst r; exact ⟨695, by decide, by decide, by decide⟩
  · subst r; exact ⟨268, by decide, by decide, by decide⟩
  · subst r; exact ⟨697, by decide, by decide, by decide⟩
  · subst r; exact ⟨117, by decide, by decide, by decide⟩
  · subst r; exact ⟨699, by decide, by decide, by decide⟩

theorem slice_14 (r : Nat) (lo : 700 ≤ r) (hi : r ≤ 749) : covered r := by
  have h : r = 700 ∨ r = 701 ∨ r = 702 ∨ r = 703 ∨ r = 704 ∨ r = 705 ∨ r = 706 ∨ r = 707 ∨ r = 708 ∨ r = 709 ∨ r = 710 ∨ r = 711 ∨ r = 712 ∨ r = 713 ∨ r = 714 ∨ r = 715 ∨ r = 716 ∨ r = 717 ∨ r = 718 ∨ r = 719 ∨ r = 720 ∨ r = 721 ∨ r = 722 ∨ r = 723 ∨ r = 724 ∨ r = 725 ∨ r = 726 ∨ r = 727 ∨ r = 728 ∨ r = 729 ∨ r = 730 ∨ r = 731 ∨ r = 732 ∨ r = 733 ∨ r = 734 ∨ r = 735 ∨ r = 736 ∨ r = 737 ∨ r = 738 ∨ r = 739 ∨ r = 740 ∨ r = 741 ∨ r = 742 ∨ r = 743 ∨ r = 744 ∨ r = 745 ∨ r = 746 ∨ r = 747 ∨ r = 748 ∨ r = 749 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨34, by decide, by decide, by decide⟩
  · subst r; exact ⟨701, by decide, by decide, by decide⟩
  · subst r; exact ⟨185, by decide, by decide, by decide⟩
  · subst r; exact ⟨687, by decide, by decide, by decide⟩
  · subst r; exact ⟨336, by decide, by decide, by decide⟩
  · subst r; exact ⟨534, by decide, by decide, by decide⟩
  · subst r; exact ⟨487, by decide, by decide, by decide⟩
  · subst r; exact ⟨381, by decide, by decide, by decide⟩
  · subst r; exact ⟨638, by decide, by decide, by decide⟩
  · subst r; exact ⟨228, by decide, by decide, by decide⟩
  · subst r; exact ⟨710, by decide, by decide, by decide⟩
  · subst r; exact ⟨75, by decide, by decide, by decide⟩
  · subst r; exact ⟨712, by decide, by decide, by decide⟩
  · subst r; exact ⟨78, by decide, by decide, by decide⟩
  · subst r; exact ⟨714, by decide, by decide, by decide⟩
  · subst r; exact ⟨231, by decide, by decide, by decide⟩
  · subst r; exact ⟨716, by decide, by decide, by decide⟩
  · subst r; exact ⟨333, by decide, by decide, by decide⟩
  · subst r; exact ⟨718, by decide, by decide, by decide⟩
  · subst r; exact ⟨182, by decide, by decide, by decide⟩
  · subst r; exact ⟨720, by decide, by decide, by decide⟩
  · subst r; exact ⟨31, by decide, by decide, by decide⟩
  · subst r; exact ⟨722, by decide, by decide, by decide⟩
  · subst r; exact ⟨120, by decide, by decide, by decide⟩
  · subst r; exact ⟨724, by decide, by decide, by decide⟩
  · subst r; exact ⟨271, by decide, by decide, by decide⟩
  · subst r; exact ⟨578, by decide, by decide, by decide⟩
  · subst r; exact ⟨422, by decide, by decide, by decide⟩
  · subst r; exact ⟨425, by decide, by decide, by decide⟩
  · subst r; exact ⟨573, by decide, by decide, by decide⟩
  · subst r; exact ⟨272, by decide, by decide, by decide⟩
  · subst r; exact ⟨724, by decide, by decide, by decide⟩
  · subst r; exact ⟨119, by decide, by decide, by decide⟩
  · subst r; exact ⟨733, by decide, by decide, by decide⟩
  · subst r; exact ⟨34, by decide, by decide, by decide⟩
  · subst r; exact ⟨735, by decide, by decide, by decide⟩
  · subst r; exact ⟨187, by decide, by decide, by decide⟩
  · subst r; exact ⟨737, by decide, by decide, by decide⟩
  · subst r; exact ⟨340, by decide, by decide, by decide⟩
  · subst r; exact ⟨739, by decide, by decide, by decide⟩
  · subst r; exact ⟨247, by decide, by decide, by decide⟩
  · subst r; exact ⟨741, by decide, by decide, by decide⟩
  · subst r; exact ⟨96, by decide, by decide, by decide⟩
  · subst r; exact ⟨743, by decide, by decide, by decide⟩
  · subst r; exact ⟨55, by decide, by decide, by decide⟩
  · subst r; exact ⟨745, by decide, by decide, by decide⟩
  · subst r; exact ⟨206, by decide, by decide, by decide⟩
  · subst r; exact ⟨622, by decide, by decide, by decide⟩
  · subst r; exact ⟨357, by decide, by decide, by decide⟩
  · subst r; exact ⟨469, by decide, by decide, by decide⟩

theorem slice_15 (r : Nat) (lo : 750 ≤ r) (hi : r ≤ 799) : covered r := by
  have h : r = 750 ∨ r = 751 ∨ r = 752 ∨ r = 753 ∨ r = 754 ∨ r = 755 ∨ r = 756 ∨ r = 757 ∨ r = 758 ∨ r = 759 ∨ r = 760 ∨ r = 761 ∨ r = 762 ∨ r = 763 ∨ r = 764 ∨ r = 765 ∨ r = 766 ∨ r = 767 ∨ r = 768 ∨ r = 769 ∨ r = 770 ∨ r = 771 ∨ r = 772 ∨ r = 773 ∨ r = 774 ∨ r = 775 ∨ r = 776 ∨ r = 777 ∨ r = 778 ∨ r = 779 ∨ r = 780 ∨ r = 781 ∨ r = 782 ∨ r = 783 ∨ r = 784 ∨ r = 785 ∨ r = 786 ∨ r = 787 ∨ r = 788 ∨ r = 789 ∨ r = 790 ∨ r = 791 ∨ r = 792 ∨ r = 793 ∨ r = 794 ∨ r = 795 ∨ r = 796 ∨ r = 797 ∨ r = 798 ∨ r = 799 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨508, by decide, by decide, by decide⟩
  · subst r; exact ⟨316, by decide, by decide, by decide⟩
  · subst r; exact ⟨659, by decide, by decide, by decide⟩
  · subst r; exact ⟨163, by decide, by decide, by decide⟩
  · subst r; exact ⟨754, by decide, by decide, by decide⟩
  · subst r; exact ⟨10, by decide, by decide, by decide⟩
  · subst r; exact ⟨756, by decide, by decide, by decide⟩
  · subst r; exact ⟨143, by decide, by decide, by decide⟩
  · subst r; exact ⟨758, by decide, by decide, by decide⟩
  · subst r; exact ⟨296, by decide, by decide, by decide⟩
  · subst r; exact ⟨760, by decide, by decide, by decide⟩
  · subst r; exact ⟨312, by decide, by decide, by decide⟩
  · subst r; exact ⟨762, by decide, by decide, by decide⟩
  · subst r; exact ⟨161, by decide, by decide, by decide⟩
  · subst r; exact ⟨764, by decide, by decide, by decide⟩
  · subst r; exact ⟨10, by decide, by decide, by decide⟩
  · subst r; exact ⟨766, by decide, by decide, by decide⟩
  · subst r; exact ⟨141, by decide, by decide, by decide⟩
  · subst r; exact ⟨666, by decide, by decide, by decide⟩
  · subst r; exact ⟨292, by decide, by decide, by decide⟩
  · subst r; exact ⟨513, by decide, by decide, by decide⟩
  · subst r; exact ⟨443, by decide, by decide, by decide⟩
  · subst r; exact ⟨360, by decide, by decide, by decide⟩
  · subst r; exact ⟨594, by decide, by decide, by decide⟩
  · subst r; exact ⟨207, by decide, by decide, by decide⟩
  · subst r; exact ⟨745, by decide, by decide, by decide⟩
  · subst r; exact ⟨54, by decide, by decide, by decide⟩
  · subst r; exact ⟨777, by decide, by decide, by decide⟩
  · subst r; exact ⟨99, by decide, by decide, by decide⟩
  · subst r; exact ⟨779, by decide, by decide, by decide⟩
  · subst r; exact ⟨252, by decide, by decide, by decide⟩
  · subst r; exact ⟨781, by decide, by decide, by decide⟩
  · subst r; exact ⟨377, by decide, by decide, by decide⟩
  · subst r; exact ⟨783, by decide, by decide, by decide⟩
  · subst r; exact ⟨226, by decide, by decide, by decide⟩
  · subst r; exact ⟨785, by decide, by decide, by decide⟩
  · subst r; exact ⟨75, by decide, by decide, by decide⟩
  · subst r; exact ⟨787, by decide, by decide, by decide⟩
  · subst r; exact ⟨76, by decide, by decide, by decide⟩
  · subst r; exact ⟨710, by decide, by decide, by decide⟩
  · subst r; exact ⟨227, by decide, by decide, by decide⟩
  · subst r; exact ⟨557, by decide, by decide, by decide⟩
  · subst r; exact ⟨378, by decide, by decide, by decide⟩
  · subst r; exact ⟨404, by decide, by decide, by decide⟩
  · subst r; exact ⟨529, by decide, by decide, by decide⟩
  · subst r; exact ⟨251, by decide, by decide, by decide⟩
  · subst r; exact ⟨680, by decide, by decide, by decide⟩
  · subst r; exact ⟨98, by decide, by decide, by decide⟩
  · subst r; exact ⟨798, by decide, by decide, by decide⟩
  · subst r; exact ⟨55, by decide, by decide, by decide⟩

theorem slice_16 (r : Nat) (lo : 800 ≤ r) (hi : r ≤ 849) : covered r := by
  have h : r = 800 ∨ r = 801 ∨ r = 802 ∨ r = 803 ∨ r = 804 ∨ r = 805 ∨ r = 806 ∨ r = 807 ∨ r = 808 ∨ r = 809 ∨ r = 810 ∨ r = 811 ∨ r = 812 ∨ r = 813 ∨ r = 814 ∨ r = 815 ∨ r = 816 ∨ r = 817 ∨ r = 818 ∨ r = 819 ∨ r = 820 ∨ r = 821 ∨ r = 822 ∨ r = 823 ∨ r = 824 ∨ r = 825 ∨ r = 826 ∨ r = 827 ∨ r = 828 ∨ r = 829 ∨ r = 830 ∨ r = 831 ∨ r = 832 ∨ r = 833 ∨ r = 834 ∨ r = 835 ∨ r = 836 ∨ r = 837 ∨ r = 838 ∨ r = 839 ∨ r = 840 ∨ r = 841 ∨ r = 842 ∨ r = 843 ∨ r = 844 ∨ r = 845 ∨ r = 846 ∨ r = 847 ∨ r = 848 ∨ r = 849 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨800, by decide, by decide, by decide⟩
  · subst r; exact ⟨208, by decide, by decide, by decide⟩
  · subst r; exact ⟨802, by decide, by decide, by decide⟩
  · subst r; exact ⟨361, by decide, by decide, by decide⟩
  · subst r; exact ⟨804, by decide, by decide, by decide⟩
  · subst r; exact ⟨291, by decide, by decide, by decide⟩
  · subst r; exact ⟨806, by decide, by decide, by decide⟩
  · subst r; exact ⟨140, by decide, by decide, by decide⟩
  · subst r; exact ⟨808, by decide, by decide, by decide⟩
  · subst r; exact ⟨11, by decide, by decide, by decide⟩
  · subst r; exact ⟨754, by decide, by decide, by decide⟩
  · subst r; exact ⟨162, by decide, by decide, by decide⟩
  · subst r; exact ⟨601, by decide, by decide, by decide⟩
  · subst r; exact ⟨313, by decide, by decide, by decide⟩
  · subst r; exact ⟨448, by decide, by decide, by decide⟩
  · subst r; exact ⟨464, by decide, by decide, by decide⟩
  · subst r; exact ⟨295, by decide, by decide, by decide⟩
  · subst r; exact ⟨615, by decide, by decide, by decide⟩
  · subst r; exact ⟨142, by decide, by decide, by decide⟩
  · subst r; exact ⟨766, by decide, by decide, by decide⟩
  · subst r; exact ⟨11, by decide, by decide, by decide⟩
  · subst r; exact ⟨821, by decide, by decide, by decide⟩
  · subst r; exact ⟨164, by decide, by decide, by decide⟩
  · subst r; exact ⟨823, by decide, by decide, by decide⟩
  · subst r; exact ⟨317, by decide, by decide, by decide⟩
  · subst r; exact ⟨825, by decide, by decide, by decide⟩
  · subst r; exact ⟨356, by decide, by decide, by decide⟩
  · subst r; exact ⟨827, by decide, by decide, by decide⟩
  · subst r; exact ⟨205, by decide, by decide, by decide⟩
  · subst r; exact ⟨829, by decide, by decide, by decide⟩
  · subst r; exact ⟨54, by decide, by decide, by decide⟩
  · subst r; exact ⟨798, by decide, by decide, by decide⟩
  · subst r; exact ⟨97, by decide, by decide, by decide⟩
  · subst r; exact ⟨645, by decide, by decide, by decide⟩
  · subst r; exact ⟨248, by decide, by decide, by decide⟩
  · subst r; exact ⟨492, by decide, by decide, by decide⟩
  · subst r; exact ⟨399, by decide, by decide, by decide⟩
  · subst r; exact ⟨339, by decide, by decide, by decide⟩
  · subst r; exact ⟨550, by decide, by decide, by decide⟩
  · subst r; exact ⟨186, by decide, by decide, by decide⟩
  · subst r; exact ⟨701, by decide, by decide, by decide⟩
  · subst r; exact ⟨33, by decide, by decide, by decide⟩
  · subst r; exact ⟨842, by decide, by decide, by decide⟩
  · subst r; exact ⟨120, by decide, by decide, by decide⟩
  · subst r; exact ⟨844, by decide, by decide, by decide⟩
  · subst r; exact ⟨273, by decide, by decide, by decide⟩
  · subst r; exact ⟨846, by decide, by decide, by decide⟩
  · subst r; exact ⟨421, by decide, by decide, by decide⟩
  · subst r; exact ⟨848, by decide, by decide, by decide⟩
  · subst r; exact ⟨270, by decide, by decide, by decide⟩

theorem slice_17 (r : Nat) (lo : 850 ≤ r) (hi : r ≤ 899) : covered r := by
  have h : r = 850 ∨ r = 851 ∨ r = 852 ∨ r = 853 ∨ r = 854 ∨ r = 855 ∨ r = 856 ∨ r = 857 ∨ r = 858 ∨ r = 859 ∨ r = 860 ∨ r = 861 ∨ r = 862 ∨ r = 863 ∨ r = 864 ∨ r = 865 ∨ r = 866 ∨ r = 867 ∨ r = 868 ∨ r = 869 ∨ r = 870 ∨ r = 871 ∨ r = 872 ∨ r = 873 ∨ r = 874 ∨ r = 875 ∨ r = 876 ∨ r = 877 ∨ r = 878 ∨ r = 879 ∨ r = 880 ∨ r = 881 ∨ r = 882 ∨ r = 883 ∨ r = 884 ∨ r = 885 ∨ r = 886 ∨ r = 887 ∨ r = 888 ∨ r = 889 ∨ r = 890 ∨ r = 891 ∨ r = 892 ∨ r = 893 ∨ r = 894 ∨ r = 895 ∨ r = 896 ∨ r = 897 ∨ r = 898 ∨ r = 899 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨850, by decide, by decide, by decide⟩
  · subst r; exact ⟨119, by decide, by decide, by decide⟩
  · subst r; exact ⟨842, by decide, by decide, by decide⟩
  · subst r; exact ⟨32, by decide, by decide, by decide⟩
  · subst r; exact ⟨689, by decide, by decide, by decide⟩
  · subst r; exact ⟨183, by decide, by decide, by decide⟩
  · subst r; exact ⟨536, by decide, by decide, by decide⟩
  · subst r; exact ⟨334, by decide, by decide, by decide⟩
  · subst r; exact ⟨383, by decide, by decide, by decide⟩
  · subst r; exact ⟨485, by decide, by decide, by decide⟩
  · subst r; exact ⟨230, by decide, by decide, by decide⟩
  · subst r; exact ⟨636, by decide, by decide, by decide⟩
  · subst r; exact ⟨77, by decide, by decide, by decide⟩
  · subst r; exact ⟨787, by decide, by decide, by decide⟩
  · subst r; exact ⟨76, by decide, by decide, by decide⟩
  · subst r; exact ⟨865, by decide, by decide, by decide⟩
  · subst r; exact ⟨229, by decide, by decide, by decide⟩
  · subst r; exact ⟨867, by decide, by decide, by decide⟩
  · subst r; exact ⟨382, by decide, by decide, by decide⟩
  · subst r; exact ⟨869, by decide, by decide, by decide⟩
  · subst r; exact ⟨335, by decide, by decide, by decide⟩
  · subst r; exact ⟨871, by decide, by decide, by decide⟩
  · subst r; exact ⟨184, by decide, by decide, by decide⟩
  · subst r; exact ⟨873, by decide, by decide, by decide⟩
  · subst r; exact ⟨33, by decide, by decide, by decide⟩
  · subst r; exact ⟨733, by decide, by decide, by decide⟩
  · subst r; exact ⟨118, by decide, by decide, by decide⟩
  · subst r; exact ⟨580, by decide, by decide, by decide⟩
  · subst r; exact ⟨269, by decide, by decide, by decide⟩
  · subst r; exact ⟨427, by decide, by decide, by decide⟩
  · subst r; exact ⟨420, by decide, by decide, by decide⟩
  · subst r; exact ⟨274, by decide, by decide, by decide⟩
  · subst r; exact ⟨571, by decide, by decide, by decide⟩
  · subst r; exact ⟨121, by decide, by decide, by decide⟩
  · subst r; exact ⟨722, by decide, by decide, by decide⟩
  · subst r; exact ⟨32, by decide, by decide, by decide⟩
  · subst r; exact ⟨873, by decide, by decide, by decide⟩
  · subst r; exact ⟨185, by decide, by decide, by decide⟩
  · subst r; exact ⟨888, by decide, by decide, by decide⟩
  · subst r; exact ⟨338, by decide, by decide, by decide⟩
  · subst r; exact ⟨890, by decide, by decide, by decide⟩
  · subst r; exact ⟨400, by decide, by decide, by decide⟩
  · subst r; exact ⟨892, by decide, by decide, by decide⟩
  · subst r; exact ⟨249, by decide, by decide, by decide⟩
  · subst r; exact ⟨894, by decide, by decide, by decide⟩
  · subst r; exact ⟨98, by decide, by decide, by decide⟩
  · subst r; exact ⟨777, by decide, by decide, by decide⟩
  · subst r; exact ⟨53, by decide, by decide, by decide⟩
  · subst r; exact ⟨624, by decide, by decide, by decide⟩
  · subst r; exact ⟨204, by decide, by decide, by decide⟩

theorem slice_18 (r : Nat) (lo : 900 ≤ r) (hi : r ≤ 949) : covered r := by
  have h : r = 900 ∨ r = 901 ∨ r = 902 ∨ r = 903 ∨ r = 904 ∨ r = 905 ∨ r = 906 ∨ r = 907 ∨ r = 908 ∨ r = 909 ∨ r = 910 ∨ r = 911 ∨ r = 912 ∨ r = 913 ∨ r = 914 ∨ r = 915 ∨ r = 916 ∨ r = 917 ∨ r = 918 ∨ r = 919 ∨ r = 920 ∨ r = 921 ∨ r = 922 ∨ r = 923 ∨ r = 924 ∨ r = 925 ∨ r = 926 ∨ r = 927 ∨ r = 928 ∨ r = 929 ∨ r = 930 ∨ r = 931 ∨ r = 932 ∨ r = 933 ∨ r = 934 ∨ r = 935 ∨ r = 936 ∨ r = 937 ∨ r = 938 ∨ r = 939 ∨ r = 940 ∨ r = 941 ∨ r = 942 ∨ r = 943 ∨ r = 944 ∨ r = 945 ∨ r = 946 ∨ r = 947 ∨ r = 948 ∨ r = 949 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨471, by decide, by decide, by decide⟩
  · subst r; exact ⟨355, by decide, by decide, by decide⟩
  · subst r; exact ⟨318, by decide, by decide, by decide⟩
  · subst r; exact ⟨506, by decide, by decide, by decide⟩
  · subst r; exact ⟨165, by decide, by decide, by decide⟩
  · subst r; exact ⟨657, by decide, by decide, by decide⟩
  · subst r; exact ⟨12, by decide, by decide, by decide⟩
  · subst r; exact ⟨808, by decide, by decide, by decide⟩
  · subst r; exact ⟨141, by decide, by decide, by decide⟩
  · subst r; exact ⟨909, by decide, by decide, by decide⟩
  · subst r; exact ⟨294, by decide, by decide, by decide⟩
  · subst r; exact ⟨911, by decide, by decide, by decide⟩
  · subst r; exact ⟨447, by decide, by decide, by decide⟩
  · subst r; exact ⟨913, by decide, by decide, by decide⟩
  · subst r; exact ⟨314, by decide, by decide, by decide⟩
  · subst r; exact ⟨915, by decide, by decide, by decide⟩
  · subst r; exact ⟨163, by decide, by decide, by decide⟩
  · subst r; exact ⟨821, by decide, by decide, by decide⟩
  · subst r; exact ⟨12, by decide, by decide, by decide⟩
  · subst r; exact ⟨668, by decide, by decide, by decide⟩
  · subst r; exact ⟨139, by decide, by decide, by decide⟩
  · subst r; exact ⟨515, by decide, by decide, by decide⟩
  · subst r; exact ⟨290, by decide, by decide, by decide⟩
  · subst r; exact ⟨362, by decide, by decide, by decide⟩
  · subst r; exact ⟨441, by decide, by decide, by decide⟩
  · subst r; exact ⟨209, by decide, by decide, by decide⟩
  · subst r; exact ⟨592, by decide, by decide, by decide⟩
  · subst r; exact ⟨56, by decide, by decide, by decide⟩
  · subst r; exact ⟨743, by decide, by decide, by decide⟩
  · subst r; exact ⟨97, by decide, by decide, by decide⟩
  · subst r; exact ⟨894, by decide, by decide, by decide⟩
  · subst r; exact ⟨250, by decide, by decide, by decide⟩
  · subst r; exact ⟨932, by decide, by decide, by decide⟩
  · subst r; exact ⟨403, by decide, by decide, by decide⟩
  · subst r; exact ⟨934, by decide, by decide, by decide⟩
  · subst r; exact ⟨379, by decide, by decide, by decide⟩
  · subst r; exact ⟨936, by decide, by decide, by decide⟩
  · subst r; exact ⟨228, by decide, by decide, by decide⟩
  · subst r; exact ⟨865, by decide, by decide, by decide⟩
  · subst r; exact ⟨77, by decide, by decide, by decide⟩
  · subst r; exact ⟨712, by decide, by decide, by decide⟩
  · subst r; exact ⟨74, by decide, by decide, by decide⟩
  · subst r; exact ⟨559, by decide, by decide, by decide⟩
  · subst r; exact ⟨225, by decide, by decide, by decide⟩
  · subst r; exact ⟨406, by decide, by decide, by decide⟩
  · subst r; exact ⟨376, by decide, by decide, by decide⟩
  · subst r; exact ⟨253, by decide, by decide, by decide⟩
  · subst r; exact ⟨527, by decide, by decide, by decide⟩
  · subst r; exact ⟨100, by decide, by decide, by decide⟩
  · subst r; exact ⟨678, by decide, by decide, by decide⟩

theorem slice_19 (r : Nat) (lo : 950 ≤ r) (hi : r ≤ 999) : covered r := by
  have h : r = 950 ∨ r = 951 ∨ r = 952 ∨ r = 953 ∨ r = 954 ∨ r = 955 ∨ r = 956 ∨ r = 957 ∨ r = 958 ∨ r = 959 ∨ r = 960 ∨ r = 961 ∨ r = 962 ∨ r = 963 ∨ r = 964 ∨ r = 965 ∨ r = 966 ∨ r = 967 ∨ r = 968 ∨ r = 969 ∨ r = 970 ∨ r = 971 ∨ r = 972 ∨ r = 973 ∨ r = 974 ∨ r = 975 ∨ r = 976 ∨ r = 977 ∨ r = 978 ∨ r = 979 ∨ r = 980 ∨ r = 981 ∨ r = 982 ∨ r = 983 ∨ r = 984 ∨ r = 985 ∨ r = 986 ∨ r = 987 ∨ r = 988 ∨ r = 989 ∨ r = 990 ∨ r = 991 ∨ r = 992 ∨ r = 993 ∨ r = 994 ∨ r = 995 ∨ r = 996 ∨ r = 997 ∨ r = 998 ∨ r = 999 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨53, by decide, by decide, by decide⟩
  · subst r; exact ⟨829, by decide, by decide, by decide⟩
  · subst r; exact ⟨206, by decide, by decide, by decide⟩
  · subst r; exact ⟨953, by decide, by decide, by decide⟩
  · subst r; exact ⟨359, by decide, by decide, by decide⟩
  · subst r; exact ⟨955, by decide, by decide, by decide⟩
  · subst r; exact ⟨444, by decide, by decide, by decide⟩
  · subst r; exact ⟨957, by decide, by decide, by decide⟩
  · subst r; exact ⟨293, by decide, by decide, by decide⟩
  · subst r; exact ⟨909, by decide, by decide, by decide⟩
  · subst r; exact ⟨142, by decide, by decide, by decide⟩
  · subst r; exact ⟨756, by decide, by decide, by decide⟩
  · subst r; exact ⟨9, by decide, by decide, by decide⟩
  · subst r; exact ⟨603, by decide, by decide, by decide⟩
  · subst r; exact ⟨160, by decide, by decide, by decide⟩
  · subst r; exact ⟨450, by decide, by decide, by decide⟩
  · subst r; exact ⟨311, by decide, by decide, by decide⟩
  · subst r; exact ⟨297, by decide, by decide, by decide⟩
  · subst r; exact ⟨462, by decide, by decide, by decide⟩
  · subst r; exact ⟨144, by decide, by decide, by decide⟩
  · subst r; exact ⟨613, by decide, by decide, by decide⟩
  · subst r; exact ⟨9, by decide, by decide, by decide⟩
  · subst r; exact ⟨764, by decide, by decide, by decide⟩
  · subst r; exact ⟨162, by decide, by decide, by decide⟩
  · subst r; exact ⟨915, by decide, by decide, by decide⟩
  · subst r; exact ⟨315, by decide, by decide, by decide⟩
  · subst r; exact ⟨976, by decide, by decide, by decide⟩
  · subst r; exact ⟨468, by decide, by decide, by decide⟩
  · subst r; exact ⟨978, by decide, by decide, by decide⟩
  · subst r; exact ⟨358, by decide, by decide, by decide⟩
  · subst r; exact ⟨953, by decide, by decide, by decide⟩
  · subst r; exact ⟨207, by decide, by decide, by decide⟩
  · subst r; exact ⟨800, by decide, by decide, by decide⟩
  · subst r; exact ⟨56, by decide, by decide, by decide⟩
  · subst r; exact ⟨647, by decide, by decide, by decide⟩
  · subst r; exact ⟨95, by decide, by decide, by decide⟩
  · subst r; exact ⟨494, by decide, by decide, by decide⟩
  · subst r; exact ⟨246, by decide, by decide, by decide⟩
  · subst r; exact ⟨341, by decide, by decide, by decide⟩
  · subst r; exact ⟨397, by decide, by decide, by decide⟩
  · subst r; exact ⟨188, by decide, by decide, by decide⟩
  · subst r; exact ⟨548, by decide, by decide, by decide⟩
  · subst r; exact ⟨35, by decide, by decide, by decide⟩
  · subst r; exact ⟨699, by decide, by decide, by decide⟩
  · subst r; exact ⟨118, by decide, by decide, by decide⟩
  · subst r; exact ⟨850, by decide, by decide, by decide⟩
  · subst r; exact ⟨271, by decide, by decide, by decide⟩
  · subst r; exact ⟨997, by decide, by decide, by decide⟩
  · subst r; exact ⟨424, by decide, by decide, by decide⟩
  · subst r; exact ⟨999, by decide, by decide, by decide⟩

theorem slice_20 (r : Nat) (lo : 1000 ≤ r) (hi : r ≤ 1049) : covered r := by
  have h : r = 1000 ∨ r = 1001 ∨ r = 1002 ∨ r = 1003 ∨ r = 1004 ∨ r = 1005 ∨ r = 1006 ∨ r = 1007 ∨ r = 1008 ∨ r = 1009 ∨ r = 1010 ∨ r = 1011 ∨ r = 1012 ∨ r = 1013 ∨ r = 1014 ∨ r = 1015 ∨ r = 1016 ∨ r = 1017 ∨ r = 1018 ∨ r = 1019 ∨ r = 1020 ∨ r = 1021 ∨ r = 1022 ∨ r = 1023 ∨ r = 1024 ∨ r = 1025 ∨ r = 1026 ∨ r = 1027 ∨ r = 1028 ∨ r = 1029 ∨ r = 1030 ∨ r = 1031 ∨ r = 1032 ∨ r = 1033 ∨ r = 1034 ∨ r = 1035 ∨ r = 1036 ∨ r = 1037 ∨ r = 1038 ∨ r = 1039 ∨ r = 1040 ∨ r = 1041 ∨ r = 1042 ∨ r = 1043 ∨ r = 1044 ∨ r = 1045 ∨ r = 1046 ∨ r = 1047 ∨ r = 1048 ∨ r = 1049 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨423, by decide, by decide, by decide⟩
  · subst r; exact ⟨997, by decide, by decide, by decide⟩
  · subst r; exact ⟨272, by decide, by decide, by decide⟩
  · subst r; exact ⟨844, by decide, by decide, by decide⟩
  · subst r; exact ⟨121, by decide, by decide, by decide⟩
  · subst r; exact ⟨691, by decide, by decide, by decide⟩
  · subst r; exact ⟨30, by decide, by decide, by decide⟩
  · subst r; exact ⟨538, by decide, by decide, by decide⟩
  · subst r; exact ⟨181, by decide, by decide, by decide⟩
  · subst r; exact ⟨385, by decide, by decide, by decide⟩
  · subst r; exact ⟨332, by decide, by decide, by decide⟩
  · subst r; exact ⟨232, by decide, by decide, by decide⟩
  · subst r; exact ⟨483, by decide, by decide, by decide⟩
  · subst r; exact ⟨79, by decide, by decide, by decide⟩
  · subst r; exact ⟨634, by decide, by decide, by decide⟩
  · subst r; exact ⟨74, by decide, by decide, by decide⟩
  · subst r; exact ⟨785, by decide, by decide, by decide⟩
  · subst r; exact ⟨227, by decide, by decide, by decide⟩
  · subst r; exact ⟨936, by decide, by decide, by decide⟩
  · subst r; exact ⟨380, by decide, by decide, by decide⟩
  · subst r; exact ⟨1020, by decide, by decide, by decide⟩
  · subst r; exact ⟨488, by decide, by decide, by decide⟩
  · subst r; exact ⟨1022, by decide, by decide, by decide⟩
  · subst r; exact ⟨337, by decide, by decide, by decide⟩
  · subst r; exact ⟨888, by decide, by decide, by decide⟩
  · subst r; exact ⟨186, by decide, by decide, by decide⟩
  · subst r; exact ⟨735, by decide, by decide, by decide⟩
  · subst r; exact ⟨35, by decide, by decide, by decide⟩
  · subst r; exact ⟨582, by decide, by decide, by decide⟩
  · subst r; exact ⟨116, by decide, by decide, by decide⟩
  · subst r; exact ⟨429, by decide, by decide, by decide⟩
  · subst r; exact ⟨267, by decide, by decide, by decide⟩
  · subst r; exact ⟨276, by decide, by decide, by decide⟩
  · subst r; exact ⟨418, by decide, by decide, by decide⟩
  · subst r; exact ⟨123, by decide, by decide, by decide⟩
  · subst r; exact ⟨569, by decide, by decide, by decide⟩
  · subst r; exact ⟨30, by decide, by decide, by decide⟩
  · subst r; exact ⟨720, by decide, by decide, by decide⟩
  · subst r; exact ⟨183, by decide, by decide, by decide⟩
  · subst r; exact ⟨871, by decide, by decide, by decide⟩
  · subst r; exact ⟨336, by decide, by decide, by decide⟩
  · subst r; exact ⟨1022, by decide, by decide, by decide⟩
  · subst r; exact ⟨489, by decide, by decide, by decide⟩
  · subst r; exact ⟨1043, by decide, by decide, by decide⟩
  · subst r; exact ⟨402, by decide, by decide, by decide⟩
  · subst r; exact ⟨932, by decide, by decide, by decide⟩
  · subst r; exact ⟨251, by decide, by decide, by decide⟩
  · subst r; exact ⟨779, by decide, by decide, by decide⟩
  · subst r; exact ⟨100, by decide, by decide, by decide⟩
  · subst r; exact ⟨626, by decide, by decide, by decide⟩

theorem slice_21 (r : Nat) (lo : 1050 ≤ r) (hi : r ≤ 1099) : covered r := by
  have h : r = 1050 ∨ r = 1051 ∨ r = 1052 ∨ r = 1053 ∨ r = 1054 ∨ r = 1055 ∨ r = 1056 ∨ r = 1057 ∨ r = 1058 ∨ r = 1059 ∨ r = 1060 ∨ r = 1061 ∨ r = 1062 ∨ r = 1063 ∨ r = 1064 ∨ r = 1065 ∨ r = 1066 ∨ r = 1067 ∨ r = 1068 ∨ r = 1069 ∨ r = 1070 ∨ r = 1071 ∨ r = 1072 ∨ r = 1073 ∨ r = 1074 ∨ r = 1075 ∨ r = 1076 ∨ r = 1077 ∨ r = 1078 ∨ r = 1079 ∨ r = 1080 ∨ r = 1081 ∨ r = 1082 ∨ r = 1083 ∨ r = 1084 ∨ r = 1085 ∨ r = 1086 ∨ r = 1087 ∨ r = 1088 ∨ r = 1089 ∨ r = 1090 ∨ r = 1091 ∨ r = 1092 ∨ r = 1093 ∨ r = 1094 ∨ r = 1095 ∨ r = 1096 ∨ r = 1097 ∨ r = 1098 ∨ r = 1099 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨51, by decide, by decide, by decide⟩
  · subst r; exact ⟨473, by decide, by decide, by decide⟩
  · subst r; exact ⟨202, by decide, by decide, by decide⟩
  · subst r; exact ⟨320, by decide, by decide, by decide⟩
  · subst r; exact ⟨353, by decide, by decide, by decide⟩
  · subst r; exact ⟨167, by decide, by decide, by decide⟩
  · subst r; exact ⟨504, by decide, by decide, by decide⟩
  · subst r; exact ⟨14, by decide, by decide, by decide⟩
  · subst r; exact ⟨655, by decide, by decide, by decide⟩
  · subst r; exact ⟨139, by decide, by decide, by decide⟩
  · subst r; exact ⟨806, by decide, by decide, by decide⟩
  · subst r; exact ⟨292, by decide, by decide, by decide⟩
  · subst r; exact ⟨957, by decide, by decide, by decide⟩
  · subst r; exact ⟨445, by decide, by decide, by decide⟩
  · subst r; exact ⟨1064, by decide, by decide, by decide⟩
  · subst r; exact ⟨467, by decide, by decide, by decide⟩
  · subst r; exact ⟨976, by decide, by decide, by decide⟩
  · subst r; exact ⟨316, by decide, by decide, by decide⟩
  · subst r; exact ⟨823, by decide, by decide, by decide⟩
  · subst r; exact ⟨165, by decide, by decide, by decide⟩
  · subst r; exact ⟨670, by decide, by decide, by decide⟩
  · subst r; exact ⟨14, by decide, by decide, by decide⟩
  · subst r; exact ⟨517, by decide, by decide, by decide⟩
  · subst r; exact ⟨137, by decide, by decide, by decide⟩
  · subst r; exact ⟨364, by decide, by decide, by decide⟩
  · subst r; exact ⟨288, by decide, by decide, by decide⟩
  · subst r; exact ⟨211, by decide, by decide, by decide⟩
  · subst r; exact ⟨439, by decide, by decide, by decide⟩
  · subst r; exact ⟨58, by decide, by decide, by decide⟩
  · subst r; exact ⟨590, by decide, by decide, by decide⟩
  · subst r; exact ⟨95, by decide, by decide, by decide⟩
  · subst r; exact ⟨741, by decide, by decide, by decide⟩
  · subst r; exact ⟨248, by decide, by decide, by decide⟩
  · subst r; exact ⟨892, by decide, by decide, by decide⟩
  · subst r; exact ⟨401, by decide, by decide, by decide⟩
  · subst r; exact ⟨1043, by decide, by decide, by decide⟩
  · subst r; exact ⟨532, by decide, by decide, by decide⟩
  · subst r; exact ⟨1020, by decide, by decide, by decide⟩
  · subst r; exact ⟨381, by decide, by decide, by decide⟩
  · subst r; exact ⟨867, by decide, by decide, by decide⟩
  · subst r; exact ⟨230, by decide, by decide, by decide⟩
  · subst r; exact ⟨714, by decide, by decide, by decide⟩
  · subst r; exact ⟨79, by decide, by decide, by decide⟩
  · subst r; exact ⟨561, by decide, by decide, by decide⟩
  · subst r; exact ⟨72, by decide, by decide, by decide⟩
  · subst r; exact ⟨408, by decide, by decide, by decide⟩
  · subst r; exact ⟨223, by decide, by decide, by decide⟩
  · subst r; exact ⟨255, by decide, by decide, by decide⟩
  · subst r; exact ⟨374, by decide, by decide, by decide⟩
  · subst r; exact ⟨102, by decide, by decide, by decide⟩

theorem slice_22 (r : Nat) (lo : 1100 ≤ r) (hi : r ≤ 1149) : covered r := by
  have h : r = 1100 ∨ r = 1101 ∨ r = 1102 ∨ r = 1103 ∨ r = 1104 ∨ r = 1105 ∨ r = 1106 ∨ r = 1107 ∨ r = 1108 ∨ r = 1109 ∨ r = 1110 ∨ r = 1111 ∨ r = 1112 ∨ r = 1113 ∨ r = 1114 ∨ r = 1115 ∨ r = 1116 ∨ r = 1117 ∨ r = 1118 ∨ r = 1119 ∨ r = 1120 ∨ r = 1121 ∨ r = 1122 ∨ r = 1123 ∨ r = 1124 ∨ r = 1125 ∨ r = 1126 ∨ r = 1127 ∨ r = 1128 ∨ r = 1129 ∨ r = 1130 ∨ r = 1131 ∨ r = 1132 ∨ r = 1133 ∨ r = 1134 ∨ r = 1135 ∨ r = 1136 ∨ r = 1137 ∨ r = 1138 ∨ r = 1139 ∨ r = 1140 ∨ r = 1141 ∨ r = 1142 ∨ r = 1143 ∨ r = 1144 ∨ r = 1145 ∨ r = 1146 ∨ r = 1147 ∨ r = 1148 ∨ r = 1149 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨525, by decide, by decide, by decide⟩
  · subst r; exact ⟨51, by decide, by decide, by decide⟩
  · subst r; exact ⟨676, by decide, by decide, by decide⟩
  · subst r; exact ⟨204, by decide, by decide, by decide⟩
  · subst r; exact ⟨827, by decide, by decide, by decide⟩
  · subst r; exact ⟨357, by decide, by decide, by decide⟩
  · subst r; exact ⟨978, by decide, by decide, by decide⟩
  · subst r; exact ⟨510, by decide, by decide, by decide⟩
  · subst r; exact ⟨1064, by decide, by decide, by decide⟩
  · subst r; exact ⟨446, by decide, by decide, by decide⟩
  · subst r; exact ⟨911, by decide, by decide, by decide⟩
  · subst r; exact ⟨295, by decide, by decide, by decide⟩
  · subst r; exact ⟨758, by decide, by decide, by decide⟩
  · subst r; exact ⟨144, by decide, by decide, by decide⟩
  · subst r; exact ⟨605, by decide, by decide, by decide⟩
  · subst r; exact ⟨7, by decide, by decide, by decide⟩
  · subst r; exact ⟨452, by decide, by decide, by decide⟩
  · subst r; exact ⟨158, by decide, by decide, by decide⟩
  · subst r; exact ⟨299, by decide, by decide, by decide⟩
  · subst r; exact ⟨309, by decide, by decide, by decide⟩
  · subst r; exact ⟨146, by decide, by decide, by decide⟩
  · subst r; exact ⟨460, by decide, by decide, by decide⟩
  · subst r; exact ⟨7, by decide, by decide, by decide⟩
  · subst r; exact ⟨611, by decide, by decide, by decide⟩
  · subst r; exact ⟨160, by decide, by decide, by decide⟩
  · subst r; exact ⟨762, by decide, by decide, by decide⟩
  · subst r; exact ⟨313, by decide, by decide, by decide⟩
  · subst r; exact ⟨913, by decide, by decide, by decide⟩
  · subst r; exact ⟨466, by decide, by decide, by decide⟩
  · subst r; exact ⟨1064, by decide, by decide, by decide⟩
  · subst r; exact ⟨511, by decide, by decide, by decide⟩
  · subst r; exact ⟨955, by decide, by decide, by decide⟩
  · subst r; exact ⟨360, by decide, by decide, by decide⟩
  · subst r; exact ⟨802, by decide, by decide, by decide⟩
  · subst r; exact ⟨209, by decide, by decide, by decide⟩
  · subst r; exact ⟨649, by decide, by decide, by decide⟩
  · subst r; exact ⟨58, by decide, by decide, by decide⟩
  · subst r; exact ⟨496, by decide, by decide, by decide⟩
  · subst r; exact ⟨93, by decide, by decide, by decide⟩
  · subst r; exact ⟨343, by decide, by decide, by decide⟩
  · subst r; exact ⟨244, by decide, by decide, by decide⟩
  · subst r; exact ⟨190, by decide, by decide, by decide⟩
  · subst r; exact ⟨395, by decide, by decide, by decide⟩
  · subst r; exact ⟨37, by decide, by decide, by decide⟩
  · subst r; exact ⟨546, by decide, by decide, by decide⟩
  · subst r; exact ⟨116, by decide, by decide, by decide⟩
  · subst r; exact ⟨697, by decide, by decide, by decide⟩
  · subst r; exact ⟨269, by decide, by decide, by decide⟩
  · subst r; exact ⟨848, by decide, by decide, by decide⟩
  · subst r; exact ⟨422, by decide, by decide, by decide⟩

theorem slice_23 (r : Nat) (lo : 1150 ≤ r) (hi : r ≤ 1199) : covered r := by
  have h : r = 1150 ∨ r = 1151 ∨ r = 1152 ∨ r = 1153 ∨ r = 1154 ∨ r = 1155 ∨ r = 1156 ∨ r = 1157 ∨ r = 1158 ∨ r = 1159 ∨ r = 1160 ∨ r = 1161 ∨ r = 1162 ∨ r = 1163 ∨ r = 1164 ∨ r = 1165 ∨ r = 1166 ∨ r = 1167 ∨ r = 1168 ∨ r = 1169 ∨ r = 1170 ∨ r = 1171 ∨ r = 1172 ∨ r = 1173 ∨ r = 1174 ∨ r = 1175 ∨ r = 1176 ∨ r = 1177 ∨ r = 1178 ∨ r = 1179 ∨ r = 1180 ∨ r = 1181 ∨ r = 1182 ∨ r = 1183 ∨ r = 1184 ∨ r = 1185 ∨ r = 1186 ∨ r = 1187 ∨ r = 1188 ∨ r = 1189 ∨ r = 1190 ∨ r = 1191 ∨ r = 1192 ∨ r = 1193 ∨ r = 1194 ∨ r = 1195 ∨ r = 1196 ∨ r = 1197 ∨ r = 1198 ∨ r = 1199 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨999, by decide, by decide, by decide⟩
  · subst r; exact ⟨575, by decide, by decide, by decide⟩
  · subst r; exact ⟨999, by decide, by decide, by decide⟩
  · subst r; exact ⟨425, by decide, by decide, by decide⟩
  · subst r; exact ⟨846, by decide, by decide, by decide⟩
  · subst r; exact ⟨274, by decide, by decide, by decide⟩
  · subst r; exact ⟨693, by decide, by decide, by decide⟩
  · subst r; exact ⟨123, by decide, by decide, by decide⟩
  · subst r; exact ⟨540, by decide, by decide, by decide⟩
  · subst r; exact ⟨28, by decide, by decide, by decide⟩
  · subst r; exact ⟨387, by decide, by decide, by decide⟩
  · subst r; exact ⟨179, by decide, by decide, by decide⟩
  · subst r; exact ⟨234, by decide, by decide, by decide⟩
  · subst r; exact ⟨330, by decide, by decide, by decide⟩
  · subst r; exact ⟨81, by decide, by decide, by decide⟩
  · subst r; exact ⟨481, by decide, by decide, by decide⟩
  · subst r; exact ⟨72, by decide, by decide, by decide⟩
  · subst r; exact ⟨632, by decide, by decide, by decide⟩
  · subst r; exact ⟨225, by decide, by decide, by decide⟩
  · subst r; exact ⟨783, by decide, by decide, by decide⟩
  · subst r; exact ⟨378, by decide, by decide, by decide⟩
  · subst r; exact ⟨934, by decide, by decide, by decide⟩
  · subst r; exact ⟨531, by decide, by decide, by decide⟩
  · subst r; exact ⟨1043, by decide, by decide, by decide⟩
  · subst r; exact ⟨490, by decide, by decide, by decide⟩
  · subst r; exact ⟨890, by decide, by decide, by decide⟩
  · subst r; exact ⟨339, by decide, by decide, by decide⟩
  · subst r; exact ⟨737, by decide, by decide, by decide⟩
  · subst r; exact ⟨188, by decide, by decide, by decide⟩
  · subst r; exact ⟨584, by decide, by decide, by decide⟩
  · subst r; exact ⟨37, by decide, by decide, by decide⟩
  · subst r; exact ⟨431, by decide, by decide, by decide⟩
  · subst r; exact ⟨114, by decide, by decide, by decide⟩
  · subst r; exact ⟨278, by decide, by decide, by decide⟩
  · subst r; exact ⟨265, by decide, by decide, by decide⟩
  · subst r; exact ⟨125, by decide, by decide, by decide⟩
  · subst r; exact ⟨416, by decide, by decide, by decide⟩
  · subst r; exact ⟨28, by decide, by decide, by decide⟩
  · subst r; exact ⟨567, by decide, by decide, by decide⟩
  · subst r; exact ⟨181, by decide, by decide, by decide⟩
  · subst r; exact ⟨718, by decide, by decide, by decide⟩
  · subst r; exact ⟨334, by decide, by decide, by decide⟩
  · subst r; exact ⟨869, by decide, by decide, by decide⟩
  · subst r; exact ⟨487, by decide, by decide, by decide⟩
  · subst r; exact ⟨1020, by decide, by decide, by decide⟩
  · subst r; exact ⟨555, by decide, by decide, by decide⟩
  · subst r; exact ⟨934, by decide, by decide, by decide⟩
  · subst r; exact ⟨404, by decide, by decide, by decide⟩
  · subst r; exact ⟨781, by decide, by decide, by decide⟩
  · subst r; exact ⟨253, by decide, by decide, by decide⟩

theorem slice_24 (r : Nat) (lo : 1200 ≤ r) (hi : r ≤ 1249) : covered r := by
  have h : r = 1200 ∨ r = 1201 ∨ r = 1202 ∨ r = 1203 ∨ r = 1204 ∨ r = 1205 ∨ r = 1206 ∨ r = 1207 ∨ r = 1208 ∨ r = 1209 ∨ r = 1210 ∨ r = 1211 ∨ r = 1212 ∨ r = 1213 ∨ r = 1214 ∨ r = 1215 ∨ r = 1216 ∨ r = 1217 ∨ r = 1218 ∨ r = 1219 ∨ r = 1220 ∨ r = 1221 ∨ r = 1222 ∨ r = 1223 ∨ r = 1224 ∨ r = 1225 ∨ r = 1226 ∨ r = 1227 ∨ r = 1228 ∨ r = 1229 ∨ r = 1230 ∨ r = 1231 ∨ r = 1232 ∨ r = 1233 ∨ r = 1234 ∨ r = 1235 ∨ r = 1236 ∨ r = 1237 ∨ r = 1238 ∨ r = 1239 ∨ r = 1240 ∨ r = 1241 ∨ r = 1242 ∨ r = 1243 ∨ r = 1244 ∨ r = 1245 ∨ r = 1246 ∨ r = 1247 ∨ r = 1248 ∨ r = 1249 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨628, by decide, by decide, by decide⟩
  · subst r; exact ⟨102, by decide, by decide, by decide⟩
  · subst r; exact ⟨475, by decide, by decide, by decide⟩
  · subst r; exact ⟨49, by decide, by decide, by decide⟩
  · subst r; exact ⟨322, by decide, by decide, by decide⟩
  · subst r; exact ⟨200, by decide, by decide, by decide⟩
  · subst r; exact ⟨169, by decide, by decide, by decide⟩
  · subst r; exact ⟨351, by decide, by decide, by decide⟩
  · subst r; exact ⟨16, by decide, by decide, by decide⟩
  · subst r; exact ⟨502, by decide, by decide, by decide⟩
  · subst r; exact ⟨137, by decide, by decide, by decide⟩
  · subst r; exact ⟨653, by decide, by decide, by decide⟩
  · subst r; exact ⟨290, by decide, by decide, by decide⟩
  · subst r; exact ⟨804, by decide, by decide, by decide⟩
  · subst r; exact ⟨443, by decide, by decide, by decide⟩
  · subst r; exact ⟨955, by decide, by decide, by decide⟩
  · subst r; exact ⟨596, by decide, by decide, by decide⟩
  · subst r; exact ⟨978, by decide, by decide, by decide⟩
  · subst r; exact ⟨469, by decide, by decide, by decide⟩
  · subst r; exact ⟨825, by decide, by decide, by decide⟩
  · subst r; exact ⟨318, by decide, by decide, by decide⟩
  · subst r; exact ⟨672, by decide, by decide, by decide⟩
  · subst r; exact ⟨167, by decide, by decide, by decide⟩
  · subst r; exact ⟨519, by decide, by decide, by decide⟩
  · subst r; exact ⟨16, by decide, by decide, by decide⟩
  · subst r; exact ⟨366, by decide, by decide, by decide⟩
  · subst r; exact ⟨135, by decide, by decide, by decide⟩
  · subst r; exact ⟨213, by decide, by decide, by decide⟩
  · subst r; exact ⟨286, by decide, by decide, by decide⟩
  · subst r; exact ⟨60, by decide, by decide, by decide⟩
  · subst r; exact ⟨437, by decide, by decide, by decide⟩
  · subst r; exact ⟨93, by decide, by decide, by decide⟩
  · subst r; exact ⟨588, by decide, by decide, by decide⟩
  · subst r; exact ⟨246, by decide, by decide, by decide⟩
  · subst r; exact ⟨739, by decide, by decide, by decide⟩
  · subst r; exact ⟨399, by decide, by decide, by decide⟩
  · subst r; exact ⟨890, by decide, by decide, by decide⟩
  · subst r; exact ⟨552, by decide, by decide, by decide⟩
  · subst r; exact ⟨1022, by decide, by decide, by decide⟩
  · subst r; exact ⟨534, by decide, by decide, by decide⟩
  · subst r; exact ⟨869, by decide, by decide, by decide⟩
  · subst r; exact ⟨383, by decide, by decide, by decide⟩
  · subst r; exact ⟨716, by decide, by decide, by decide⟩
  · subst r; exact ⟨232, by decide, by decide, by decide⟩
  · subst r; exact ⟨563, by decide, by decide, by decide⟩
  · subst r; exact ⟨81, by decide, by decide, by decide⟩
  · subst r; exact ⟨410, by decide, by decide, by decide⟩
  · subst r; exact ⟨70, by decide, by decide, by decide⟩
  · subst r; exact ⟨257, by decide, by decide, by decide⟩
  · subst r; exact ⟨221, by decide, by decide, by decide⟩

theorem slice_25 (r : Nat) (lo : 1250 ≤ r) (hi : r ≤ 1299) : covered r := by
  have h : r = 1250 ∨ r = 1251 ∨ r = 1252 ∨ r = 1253 ∨ r = 1254 ∨ r = 1255 ∨ r = 1256 ∨ r = 1257 ∨ r = 1258 ∨ r = 1259 ∨ r = 1260 ∨ r = 1261 ∨ r = 1262 ∨ r = 1263 ∨ r = 1264 ∨ r = 1265 ∨ r = 1266 ∨ r = 1267 ∨ r = 1268 ∨ r = 1269 ∨ r = 1270 ∨ r = 1271 ∨ r = 1272 ∨ r = 1273 ∨ r = 1274 ∨ r = 1275 ∨ r = 1276 ∨ r = 1277 ∨ r = 1278 ∨ r = 1279 ∨ r = 1280 ∨ r = 1281 ∨ r = 1282 ∨ r = 1283 ∨ r = 1284 ∨ r = 1285 ∨ r = 1286 ∨ r = 1287 ∨ r = 1288 ∨ r = 1289 ∨ r = 1290 ∨ r = 1291 ∨ r = 1292 ∨ r = 1293 ∨ r = 1294 ∨ r = 1295 ∨ r = 1296 ∨ r = 1297 ∨ r = 1298 ∨ r = 1299 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨104, by decide, by decide, by decide⟩
  · subst r; exact ⟨372, by decide, by decide, by decide⟩
  · subst r; exact ⟨49, by decide, by decide, by decide⟩
  · subst r; exact ⟨523, by decide, by decide, by decide⟩
  · subst r; exact ⟨202, by decide, by decide, by decide⟩
  · subst r; exact ⟨674, by decide, by decide, by decide⟩
  · subst r; exact ⟨355, by decide, by decide, by decide⟩
  · subst r; exact ⟨825, by decide, by decide, by decide⟩
  · subst r; exact ⟨508, by decide, by decide, by decide⟩
  · subst r; exact ⟨976, by decide, by decide, by decide⟩
  · subst r; exact ⟨599, by decide, by decide, by decide⟩
  · subst r; exact ⟨913, by decide, by decide, by decide⟩
  · subst r; exact ⟨448, by decide, by decide, by decide⟩
  · subst r; exact ⟨760, by decide, by decide, by decide⟩
  · subst r; exact ⟨297, by decide, by decide, by decide⟩
  · subst r; exact ⟨607, by decide, by decide, by decide⟩
  · subst r; exact ⟨146, by decide, by decide, by decide⟩
  · subst r; exact ⟨454, by decide, by decide, by decide⟩
  · subst r; exact ⟨5, by decide, by decide, by decide⟩
  · subst r; exact ⟨301, by decide, by decide, by decide⟩
  · subst r; exact ⟨156, by decide, by decide, by decide⟩
  · subst r; exact ⟨148, by decide, by decide, by decide⟩
  · subst r; exact ⟨307, by decide, by decide, by decide⟩
  · subst r; exact ⟨5, by decide, by decide, by decide⟩
  · subst r; exact ⟨458, by decide, by decide, by decide⟩
  · subst r; exact ⟨158, by decide, by decide, by decide⟩
  · subst r; exact ⟨609, by decide, by decide, by decide⟩
  · subst r; exact ⟨311, by decide, by decide, by decide⟩
  · subst r; exact ⟨760, by decide, by decide, by decide⟩
  · subst r; exact ⟨464, by decide, by decide, by decide⟩
  · subst r; exact ⟨911, by decide, by decide, by decide⟩
  · subst r; exact ⟨617, by decide, by decide, by decide⟩
  · subst r; exact ⟨957, by decide, by decide, by decide⟩
  · subst r; exact ⟨513, by decide, by decide, by decide⟩
  · subst r; exact ⟨804, by decide, by decide, by decide⟩
  · subst r; exact ⟨362, by decide, by decide, by decide⟩
  · subst r; exact ⟨651, by decide, by decide, by decide⟩
  · subst r; exact ⟨211, by decide, by decide, by decide⟩
  · subst r; exact ⟨498, by decide, by decide, by decide⟩
  · subst r; exact ⟨60, by decide, by decide, by decide⟩
  · subst r; exact ⟨345, by decide, by decide, by decide⟩
  · subst r; exact ⟨91, by decide, by decide, by decide⟩
  · subst r; exact ⟨192, by decide, by decide, by decide⟩
  · subst r; exact ⟨242, by decide, by decide, by decide⟩
  · subst r; exact ⟨39, by decide, by decide, by decide⟩
  · subst r; exact ⟨393, by decide, by decide, by decide⟩
  · subst r; exact ⟨114, by decide, by decide, by decide⟩
  · subst r; exact ⟨544, by decide, by decide, by decide⟩
  · subst r; exact ⟨267, by decide, by decide, by decide⟩
  · subst r; exact ⟨695, by decide, by decide, by decide⟩

theorem slice_26 (r : Nat) (lo : 1300 ≤ r) (hi : r ≤ 1349) : covered r := by
  have h : r = 1300 ∨ r = 1301 ∨ r = 1302 ∨ r = 1303 ∨ r = 1304 ∨ r = 1305 ∨ r = 1306 ∨ r = 1307 ∨ r = 1308 ∨ r = 1309 ∨ r = 1310 ∨ r = 1311 ∨ r = 1312 ∨ r = 1313 ∨ r = 1314 ∨ r = 1315 ∨ r = 1316 ∨ r = 1317 ∨ r = 1318 ∨ r = 1319 ∨ r = 1320 ∨ r = 1321 ∨ r = 1322 ∨ r = 1323 ∨ r = 1324 ∨ r = 1325 ∨ r = 1326 ∨ r = 1327 ∨ r = 1328 ∨ r = 1329 ∨ r = 1330 ∨ r = 1331 ∨ r = 1332 ∨ r = 1333 ∨ r = 1334 ∨ r = 1335 ∨ r = 1336 ∨ r = 1337 ∨ r = 1338 ∨ r = 1339 ∨ r = 1340 ∨ r = 1341 ∨ r = 1342 ∨ r = 1343 ∨ r = 1344 ∨ r = 1345 ∨ r = 1346 ∨ r = 1347 ∨ r = 1348 ∨ r = 1349 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨420, by decide, by decide, by decide⟩
  · subst r; exact ⟨846, by decide, by decide, by decide⟩
  · subst r; exact ⟨573, by decide, by decide, by decide⟩
  · subst r; exact ⟨997, by decide, by decide, by decide⟩
  · subst r; exact ⟨578, by decide, by decide, by decide⟩
  · subst r; exact ⟨848, by decide, by decide, by decide⟩
  · subst r; exact ⟨427, by decide, by decide, by decide⟩
  · subst r; exact ⟨695, by decide, by decide, by decide⟩
  · subst r; exact ⟨276, by decide, by decide, by decide⟩
  · subst r; exact ⟨542, by decide, by decide, by decide⟩
  · subst r; exact ⟨125, by decide, by decide, by decide⟩
  · subst r; exact ⟨389, by decide, by decide, by decide⟩
  · subst r; exact ⟨26, by decide, by decide, by decide⟩
  · subst r; exact ⟨236, by decide, by decide, by decide⟩
  · subst r; exact ⟨177, by decide, by decide, by decide⟩
  · subst r; exact ⟨83, by decide, by decide, by decide⟩
  · subst r; exact ⟨328, by decide, by decide, by decide⟩
  · subst r; exact ⟨70, by decide, by decide, by decide⟩
  · subst r; exact ⟨479, by decide, by decide, by decide⟩
  · subst r; exact ⟨223, by decide, by decide, by decide⟩
  · subst r; exact ⟨630, by decide, by decide, by decide⟩
  · subst r; exact ⟨376, by decide, by decide, by decide⟩
  · subst r; exact ⟨781, by decide, by decide, by decide⟩
  · subst r; exact ⟨529, by decide, by decide, by decide⟩
  · subst r; exact ⟨932, by decide, by decide, by decide⟩
  · subst r; exact ⟨643, by decide, by decide, by decide⟩
  · subst r; exact ⟨892, by decide, by decide, by decide⟩
  · subst r; exact ⟨492, by decide, by decide, by decide⟩
  · subst r; exact ⟨739, by decide, by decide, by decide⟩
  · subst r; exact ⟨341, by decide, by decide, by decide⟩
  · subst r; exact ⟨586, by decide, by decide, by decide⟩
  · subst r; exact ⟨190, by decide, by decide, by decide⟩
  · subst r; exact ⟨433, by decide, by decide, by decide⟩
  · subst r; exact ⟨39, by decide, by decide, by decide⟩
  · subst r; exact ⟨280, by decide, by decide, by decide⟩
  · subst r; exact ⟨112, by decide, by decide, by decide⟩
  · subst r; exact ⟨127, by decide, by decide, by decide⟩
  · subst r; exact ⟨263, by decide, by decide, by decide⟩
  · subst r; exact ⟨26, by decide, by decide, by decide⟩
  · subst r; exact ⟨414, by decide, by decide, by decide⟩
  · subst r; exact ⟨179, by decide, by decide, by decide⟩
  · subst r; exact ⟨565, by decide, by decide, by decide⟩
  · subst r; exact ⟨332, by decide, by decide, by decide⟩
  · subst r; exact ⟨716, by decide, by decide, by decide⟩
  · subst r; exact ⟨485, by decide, by decide, by decide⟩
  · subst r; exact ⟨867, by decide, by decide, by decide⟩
  · subst r; exact ⟨638, by decide, by decide, by decide⟩
  · subst r; exact ⟨936, by decide, by decide, by decide⟩
  · subst r; exact ⟨557, by decide, by decide, by decide⟩
  · subst r; exact ⟨783, by decide, by decide, by decide⟩

theorem slice_27 (r : Nat) (lo : 1350 ≤ r) (hi : r ≤ 1399) : covered r := by
  have h : r = 1350 ∨ r = 1351 ∨ r = 1352 ∨ r = 1353 ∨ r = 1354 ∨ r = 1355 ∨ r = 1356 ∨ r = 1357 ∨ r = 1358 ∨ r = 1359 ∨ r = 1360 ∨ r = 1361 ∨ r = 1362 ∨ r = 1363 ∨ r = 1364 ∨ r = 1365 ∨ r = 1366 ∨ r = 1367 ∨ r = 1368 ∨ r = 1369 ∨ r = 1370 ∨ r = 1371 ∨ r = 1372 ∨ r = 1373 ∨ r = 1374 ∨ r = 1375 ∨ r = 1376 ∨ r = 1377 ∨ r = 1378 ∨ r = 1379 ∨ r = 1380 ∨ r = 1381 ∨ r = 1382 ∨ r = 1383 ∨ r = 1384 ∨ r = 1385 ∨ r = 1386 ∨ r = 1387 ∨ r = 1388 ∨ r = 1389 ∨ r = 1390 ∨ r = 1391 ∨ r = 1392 ∨ r = 1393 ∨ r = 1394 ∨ r = 1395 ∨ r = 1396 ∨ r = 1397 ∨ r = 1398 ∨ r = 1399 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨406, by decide, by decide, by decide⟩
  · subst r; exact ⟨630, by decide, by decide, by decide⟩
  · subst r; exact ⟨255, by decide, by decide, by decide⟩
  · subst r; exact ⟨477, by decide, by decide, by decide⟩
  · subst r; exact ⟨104, by decide, by decide, by decide⟩
  · subst r; exact ⟨324, by decide, by decide, by decide⟩
  · subst r; exact ⟨47, by decide, by decide, by decide⟩
  · subst r; exact ⟨171, by decide, by decide, by decide⟩
  · subst r; exact ⟨198, by decide, by decide, by decide⟩
  · subst r; exact ⟨18, by decide, by decide, by decide⟩
  · subst r; exact ⟨349, by decide, by decide, by decide⟩
  · subst r; exact ⟨135, by decide, by decide, by decide⟩
  · subst r; exact ⟨500, by decide, by decide, by decide⟩
  · subst r; exact ⟨288, by decide, by decide, by decide⟩
  · subst r; exact ⟨651, by decide, by decide, by decide⟩
  · subst r; exact ⟨441, by decide, by decide, by decide⟩
  · subst r; exact ⟨802, by decide, by decide, by decide⟩
  · subst r; exact ⟨594, by decide, by decide, by decide⟩
  · subst r; exact ⟨953, by decide, by decide, by decide⟩
  · subst r; exact ⟨622, by decide, by decide, by decide⟩
  · subst r; exact ⟨827, by decide, by decide, by decide⟩
  · subst r; exact ⟨471, by decide, by decide, by decide⟩
  · subst r; exact ⟨674, by decide, by decide, by decide⟩
  · subst r; exact ⟨320, by decide, by decide, by decide⟩
  · subst r; exact ⟨521, by decide, by decide, by decide⟩
  · subst r; exact ⟨169, by decide, by decide, by decide⟩
  · subst r; exact ⟨368, by decide, by decide, by decide⟩
  · subst r; exact ⟨18, by decide, by decide, by decide⟩
  · subst r; exact ⟨215, by decide, by decide, by decide⟩
  · subst r; exact ⟨133, by decide, by decide, by decide⟩
  · subst r; exact ⟨62, by decide, by decide, by decide⟩
  · subst r; exact ⟨284, by decide, by decide, by decide⟩
  · subst r; exact ⟨91, by decide, by decide, by decide⟩
  · subst r; exact ⟨435, by decide, by decide, by decide⟩
  · subst r; exact ⟨244, by decide, by decide, by decide⟩
  · subst r; exact ⟨586, by decide, by decide, by decide⟩
  · subst r; exact ⟨397, by decide, by decide, by decide⟩
  · subst r; exact ⟨737, by decide, by decide, by decide⟩
  · subst r; exact ⟨550, by decide, by decide, by decide⟩
  · subst r; exact ⟨888, by decide, by decide, by decide⟩
  · subst r; exact ⟨687, by decide, by decide, by decide⟩
  · subst r; exact ⟨871, by decide, by decide, by decide⟩
  · subst r; exact ⟨536, by decide, by decide, by decide⟩
  · subst r; exact ⟨718, by decide, by decide, by decide⟩
  · subst r; exact ⟨385, by decide, by decide, by decide⟩
  · subst r; exact ⟨565, by decide, by decide, by decide⟩
  · subst r; exact ⟨234, by decide, by decide, by decide⟩
  · subst r; exact ⟨412, by decide, by decide, by decide⟩
  · subst r; exact ⟨83, by decide, by decide, by decide⟩
  · subst r; exact ⟨259, by decide, by decide, by decide⟩

theorem slice_28 (r : Nat) (lo : 1400 ≤ r) (hi : r ≤ 1449) : covered r := by
  have h : r = 1400 ∨ r = 1401 ∨ r = 1402 ∨ r = 1403 ∨ r = 1404 ∨ r = 1405 ∨ r = 1406 ∨ r = 1407 ∨ r = 1408 ∨ r = 1409 ∨ r = 1410 ∨ r = 1411 ∨ r = 1412 ∨ r = 1413 ∨ r = 1414 ∨ r = 1415 ∨ r = 1416 ∨ r = 1417 ∨ r = 1418 ∨ r = 1419 ∨ r = 1420 ∨ r = 1421 ∨ r = 1422 ∨ r = 1423 ∨ r = 1424 ∨ r = 1425 ∨ r = 1426 ∨ r = 1427 ∨ r = 1428 ∨ r = 1429 ∨ r = 1430 ∨ r = 1431 ∨ r = 1432 ∨ r = 1433 ∨ r = 1434 ∨ r = 1435 ∨ r = 1436 ∨ r = 1437 ∨ r = 1438 ∨ r = 1439 ∨ r = 1440 ∨ r = 1441 ∨ r = 1442 ∨ r = 1443 ∨ r = 1444 ∨ r = 1445 ∨ r = 1446 ∨ r = 1447 ∨ r = 1448 ∨ r = 1449 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨68, by decide, by decide, by decide⟩
  · subst r; exact ⟨106, by decide, by decide, by decide⟩
  · subst r; exact ⟨219, by decide, by decide, by decide⟩
  · subst r; exact ⟨47, by decide, by decide, by decide⟩
  · subst r; exact ⟨370, by decide, by decide, by decide⟩
  · subst r; exact ⟨200, by decide, by decide, by decide⟩
  · subst r; exact ⟨521, by decide, by decide, by decide⟩
  · subst r; exact ⟨353, by decide, by decide, by decide⟩
  · subst r; exact ⟨672, by decide, by decide, by decide⟩
  · subst r; exact ⟨506, by decide, by decide, by decide⟩
  · subst r; exact ⟨823, by decide, by decide, by decide⟩
  · subst r; exact ⟨659, by decide, by decide, by decide⟩
  · subst r; exact ⟨915, by decide, by decide, by decide⟩
  · subst r; exact ⟨601, by decide, by decide, by decide⟩
  · subst r; exact ⟨762, by decide, by decide, by decide⟩
  · subst r; exact ⟨450, by decide, by decide, by decide⟩
  · subst r; exact ⟨609, by decide, by decide, by decide⟩
  · subst r; exact ⟨299, by decide, by decide, by decide⟩
  · subst r; exact ⟨456, by decide, by decide, by decide⟩
  · subst r; exact ⟨148, by decide, by decide, by decide⟩
  · subst r; exact ⟨303, by decide, by decide, by decide⟩
  · subst r; exact ⟨3, by decide, by decide, by decide⟩
  · subst r; exact ⟨150, by decide, by decide, by decide⟩
  · subst r; exact ⟨154, by decide, by decide, by decide⟩
  · subst r; exact ⟨3, by decide, by decide, by decide⟩
  · subst r; exact ⟨305, by decide, by decide, by decide⟩
  · subst r; exact ⟨156, by decide, by decide, by decide⟩
  · subst r; exact ⟨456, by decide, by decide, by decide⟩
  · subst r; exact ⟨309, by decide, by decide, by decide⟩
  · subst r; exact ⟨607, by decide, by decide, by decide⟩
  · subst r; exact ⟨462, by decide, by decide, by decide⟩
  · subst r; exact ⟨758, by decide, by decide, by decide⟩
  · subst r; exact ⟨615, by decide, by decide, by decide⟩
  · subst r; exact ⟨909, by decide, by decide, by decide⟩
  · subst r; exact ⟨666, by decide, by decide, by decide⟩
  · subst r; exact ⟨806, by decide, by decide, by decide⟩
  · subst r; exact ⟨515, by decide, by decide, by decide⟩
  · subst r; exact ⟨653, by decide, by decide, by decide⟩
  · subst r; exact ⟨364, by decide, by decide, by decide⟩
  · subst r; exact ⟨500, by decide, by decide, by decide⟩
  · subst r; exact ⟨213, by decide, by decide, by decide⟩
  · subst r; exact ⟨347, by decide, by decide, by decide⟩
  · subst r; exact ⟨62, by decide, by decide, by decide⟩
  · subst r; exact ⟨194, by decide, by decide, by decide⟩
  · subst r; exact ⟨89, by decide, by decide, by decide⟩
  · subst r; exact ⟨41, by decide, by decide, by decide⟩
  · subst r; exact ⟨240, by decide, by decide, by decide⟩
  · subst r; exact ⟨112, by decide, by decide, by decide⟩
  · subst r; exact ⟨391, by decide, by decide, by decide⟩
  · subst r; exact ⟨265, by decide, by decide, by decide⟩

theorem slice_29 (r : Nat) (lo : 1450 ≤ r) (hi : r ≤ 1499) : covered r := by
  have h : r = 1450 ∨ r = 1451 ∨ r = 1452 ∨ r = 1453 ∨ r = 1454 ∨ r = 1455 ∨ r = 1456 ∨ r = 1457 ∨ r = 1458 ∨ r = 1459 ∨ r = 1460 ∨ r = 1461 ∨ r = 1462 ∨ r = 1463 ∨ r = 1464 ∨ r = 1465 ∨ r = 1466 ∨ r = 1467 ∨ r = 1468 ∨ r = 1469 ∨ r = 1470 ∨ r = 1471 ∨ r = 1472 ∨ r = 1473 ∨ r = 1474 ∨ r = 1475 ∨ r = 1476 ∨ r = 1477 ∨ r = 1478 ∨ r = 1479 ∨ r = 1480 ∨ r = 1481 ∨ r = 1482 ∨ r = 1483 ∨ r = 1484 ∨ r = 1485 ∨ r = 1486 ∨ r = 1487 ∨ r = 1488 ∨ r = 1489 ∨ r = 1490 ∨ r = 1491 ∨ r = 1492 ∨ r = 1493 ∨ r = 1494 ∨ r = 1495 ∨ r = 1496 ∨ r = 1497 ∨ r = 1498 ∨ r = 1499 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨542, by decide, by decide, by decide⟩
  · subst r; exact ⟨418, by decide, by decide, by decide⟩
  · subst r; exact ⟨693, by decide, by decide, by decide⟩
  · subst r; exact ⟨571, by decide, by decide, by decide⟩
  · subst r; exact ⟨844, by decide, by decide, by decide⟩
  · subst r; exact ⟨724, by decide, by decide, by decide⟩
  · subst r; exact ⟨850, by decide, by decide, by decide⟩
  · subst r; exact ⟨580, by decide, by decide, by decide⟩
  · subst r; exact ⟨697, by decide, by decide, by decide⟩
  · subst r; exact ⟨429, by decide, by decide, by decide⟩
  · subst r; exact ⟨544, by decide, by decide, by decide⟩
  · subst r; exact ⟨278, by decide, by decide, by decide⟩
  · subst r; exact ⟨391, by decide, by decide, by decide⟩
  · subst r; exact ⟨127, by decide, by decide, by decide⟩
  · subst r; exact ⟨238, by decide, by decide, by decide⟩
  · subst r; exact ⟨24, by decide, by decide, by decide⟩
  · subst r; exact ⟨85, by decide, by decide, by decide⟩
  · subst r; exact ⟨175, by decide, by decide, by decide⟩
  · subst r; exact ⟨68, by decide, by decide, by decide⟩
  · subst r; exact ⟨326, by decide, by decide, by decide⟩
  · subst r; exact ⟨221, by decide, by decide, by decide⟩
  · subst r; exact ⟨477, by decide, by decide, by decide⟩
  · subst r; exact ⟨374, by decide, by decide, by decide⟩
  · subst r; exact ⟨628, by decide, by decide, by decide⟩
  · subst r; exact ⟨527, by decide, by decide, by decide⟩
  · subst r; exact ⟨779, by decide, by decide, by decide⟩
  · subst r; exact ⟨680, by decide, by decide, by decide⟩
  · subst r; exact ⟨894, by decide, by decide, by decide⟩
  · subst r; exact ⟨645, by decide, by decide, by decide⟩
  · subst r; exact ⟨741, by decide, by decide, by decide⟩
  · subst r; exact ⟨494, by decide, by decide, by decide⟩
  · subst r; exact ⟨588, by decide, by decide, by decide⟩
  · subst r; exact ⟨343, by decide, by decide, by decide⟩
  · subst r; exact ⟨435, by decide, by decide, by decide⟩
  · subst r; exact ⟨192, by decide, by decide, by decide⟩
  · subst r; exact ⟨282, by decide, by decide, by decide⟩
  · subst r; exact ⟨41, by decide, by decide, by decide⟩
  · subst r; exact ⟨129, by decide, by decide, by decide⟩
  · subst r; exact ⟨110, by decide, by decide, by decide⟩
  · subst r; exact ⟨24, by decide, by decide, by decide⟩
  · subst r; exact ⟨261, by decide, by decide, by decide⟩
  · subst r; exact ⟨177, by decide, by decide, by decide⟩
  · subst r; exact ⟨412, by decide, by decide, by decide⟩
  · subst r; exact ⟨330, by decide, by decide, by decide⟩
  · subst r; exact ⟨563, by decide, by decide, by decide⟩
  · subst r; exact ⟨483, by decide, by decide, by decide⟩
  · subst r; exact ⟨714, by decide, by decide, by decide⟩
  · subst r; exact ⟨636, by decide, by decide, by decide⟩
  · subst r; exact ⟨865, by decide, by decide, by decide⟩
  · subst r; exact ⟨710, by decide, by decide, by decide⟩

theorem slice_30 (r : Nat) (lo : 1500 ≤ r) (hi : r ≤ 1549) : covered r := by
  have h : r = 1500 ∨ r = 1501 ∨ r = 1502 ∨ r = 1503 ∨ r = 1504 ∨ r = 1505 ∨ r = 1506 ∨ r = 1507 ∨ r = 1508 ∨ r = 1509 ∨ r = 1510 ∨ r = 1511 ∨ r = 1512 ∨ r = 1513 ∨ r = 1514 ∨ r = 1515 ∨ r = 1516 ∨ r = 1517 ∨ r = 1518 ∨ r = 1519 ∨ r = 1520 ∨ r = 1521 ∨ r = 1522 ∨ r = 1523 ∨ r = 1524 ∨ r = 1525 ∨ r = 1526 ∨ r = 1527 ∨ r = 1528 ∨ r = 1529 ∨ r = 1530 ∨ r = 1531 ∨ r = 1532 ∨ r = 1533 ∨ r = 1534 ∨ r = 1535 ∨ r = 1536 ∨ r = 1537 ∨ r = 1538 ∨ r = 1539 ∨ r = 1540 ∨ r = 1541 ∨ r = 1542 ∨ r = 1543 ∨ r = 1544 ∨ r = 1545 ∨ r = 1546 ∨ r = 1547 ∨ r = 1548 ∨ r = 1549 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨785, by decide, by decide, by decide⟩
  · subst r; exact ⟨559, by decide, by decide, by decide⟩
  · subst r; exact ⟨632, by decide, by decide, by decide⟩
  · subst r; exact ⟨408, by decide, by decide, by decide⟩
  · subst r; exact ⟨479, by decide, by decide, by decide⟩
  · subst r; exact ⟨257, by decide, by decide, by decide⟩
  · subst r; exact ⟨326, by decide, by decide, by decide⟩
  · subst r; exact ⟨106, by decide, by decide, by decide⟩
  · subst r; exact ⟨173, by decide, by decide, by decide⟩
  · subst r; exact ⟨45, by decide, by decide, by decide⟩
  · subst r; exact ⟨20, by decide, by decide, by decide⟩
  · subst r; exact ⟨196, by decide, by decide, by decide⟩
  · subst r; exact ⟨133, by decide, by decide, by decide⟩
  · subst r; exact ⟨347, by decide, by decide, by decide⟩
  · subst r; exact ⟨286, by decide, by decide, by decide⟩
  · subst r; exact ⟨498, by decide, by decide, by decide⟩
  · subst r; exact ⟨439, by decide, by decide, by decide⟩
  · subst r; exact ⟨649, by decide, by decide, by decide⟩
  · subst r; exact ⟨592, by decide, by decide, by decide⟩
  · subst r; exact ⟨800, by decide, by decide, by decide⟩
  · subst r; exact ⟨745, by decide, by decide, by decide⟩
  · subst r; exact ⟨829, by decide, by decide, by decide⟩
  · subst r; exact ⟨624, by decide, by decide, by decide⟩
  · subst r; exact ⟨676, by decide, by decide, by decide⟩
  · subst r; exact ⟨473, by decide, by decide, by decide⟩
  · subst r; exact ⟨523, by decide, by decide, by decide⟩
  · subst r; exact ⟨322, by decide, by decide, by decide⟩
  · subst r; exact ⟨370, by decide, by decide, by decide⟩
  · subst r; exact ⟨171, by decide, by decide, by decide⟩
  · subst r; exact ⟨217, by decide, by decide, by decide⟩
  · subst r; exact ⟨20, by decide, by decide, by decide⟩
  · subst r; exact ⟨64, by decide, by decide, by decide⟩
  · subst r; exact ⟨131, by decide, by decide, by decide⟩
  · subst r; exact ⟨89, by decide, by decide, by decide⟩
  · subst r; exact ⟨282, by decide, by decide, by decide⟩
  · subst r; exact ⟨242, by decide, by decide, by decide⟩
  · subst r; exact ⟨433, by decide, by decide, by decide⟩
  · subst r; exact ⟨395, by decide, by decide, by decide⟩
  · subst r; exact ⟨584, by decide, by decide, by decide⟩
  · subst r; exact ⟨548, by decide, by decide, by decide⟩
  · subst r; exact ⟨735, by decide, by decide, by decide⟩
  · subst r; exact ⟨701, by decide, by decide, by decide⟩
  · subst r; exact ⟨873, by decide, by decide, by decide⟩
  · subst r; exact ⟨689, by decide, by decide, by decide⟩
  · subst r; exact ⟨720, by decide, by decide, by decide⟩
  · subst r; exact ⟨538, by decide, by decide, by decide⟩
  · subst r; exact ⟨567, by decide, by decide, by decide⟩
  · subst r; exact ⟨387, by decide, by decide, by decide⟩
  · subst r; exact ⟨414, by decide, by decide, by decide⟩
  · subst r; exact ⟨236, by decide, by decide, by decide⟩

theorem slice_31 (r : Nat) (lo : 1550 ≤ r) (hi : r ≤ 1599) : covered r := by
  have h : r = 1550 ∨ r = 1551 ∨ r = 1552 ∨ r = 1553 ∨ r = 1554 ∨ r = 1555 ∨ r = 1556 ∨ r = 1557 ∨ r = 1558 ∨ r = 1559 ∨ r = 1560 ∨ r = 1561 ∨ r = 1562 ∨ r = 1563 ∨ r = 1564 ∨ r = 1565 ∨ r = 1566 ∨ r = 1567 ∨ r = 1568 ∨ r = 1569 ∨ r = 1570 ∨ r = 1571 ∨ r = 1572 ∨ r = 1573 ∨ r = 1574 ∨ r = 1575 ∨ r = 1576 ∨ r = 1577 ∨ r = 1578 ∨ r = 1579 ∨ r = 1580 ∨ r = 1581 ∨ r = 1582 ∨ r = 1583 ∨ r = 1584 ∨ r = 1585 ∨ r = 1586 ∨ r = 1587 ∨ r = 1588 ∨ r = 1589 ∨ r = 1590 ∨ r = 1591 ∨ r = 1592 ∨ r = 1593 ∨ r = 1594 ∨ r = 1595 ∨ r = 1596 ∨ r = 1597 ∨ r = 1598 ∨ r = 1599 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨261, by decide, by decide, by decide⟩
  · subst r; exact ⟨85, by decide, by decide, by decide⟩
  · subst r; exact ⟨108, by decide, by decide, by decide⟩
  · subst r; exact ⟨66, by decide, by decide, by decide⟩
  · subst r; exact ⟨45, by decide, by decide, by decide⟩
  · subst r; exact ⟨217, by decide, by decide, by decide⟩
  · subst r; exact ⟨198, by decide, by decide, by decide⟩
  · subst r; exact ⟨368, by decide, by decide, by decide⟩
  · subst r; exact ⟨351, by decide, by decide, by decide⟩
  · subst r; exact ⟨519, by decide, by decide, by decide⟩
  · subst r; exact ⟨504, by decide, by decide, by decide⟩
  · subst r; exact ⟨670, by decide, by decide, by decide⟩
  · subst r; exact ⟨657, by decide, by decide, by decide⟩
  · subst r; exact ⟨821, by decide, by decide, by decide⟩
  · subst r; exact ⟨754, by decide, by decide, by decide⟩
  · subst r; exact ⟨764, by decide, by decide, by decide⟩
  · subst r; exact ⟨603, by decide, by decide, by decide⟩
  · subst r; exact ⟨611, by decide, by decide, by decide⟩
  · subst r; exact ⟨452, by decide, by decide, by decide⟩
  · subst r; exact ⟨458, by decide, by decide, by decide⟩
  · subst r; exact ⟨301, by decide, by decide, by decide⟩
  · subst r; exact ⟨305, by decide, by decide, by decide⟩
  · subst r; exact ⟨150, by decide, by decide, by decide⟩
  · subst r; exact ⟨152, by decide, by decide, by decide⟩
  · subst r; exact ⟨1, by decide, by decide, by decide⟩
  · subst r; exact ⟨1, by decide, by decide, by decide⟩
  · subst r; exact ⟨152, by decide, by decide, by decide⟩
  · subst r; exact ⟨154, by decide, by decide, by decide⟩
  · subst r; exact ⟨303, by decide, by decide, by decide⟩
  · subst r; exact ⟨307, by decide, by decide, by decide⟩
  · subst r; exact ⟨454, by decide, by decide, by decide⟩
  · subst r; exact ⟨460, by decide, by decide, by decide⟩
  · subst r; exact ⟨605, by decide, by decide, by decide⟩
  · subst r; exact ⟨613, by decide, by decide, by decide⟩
  · subst r; exact ⟨756, by decide, by decide, by decide⟩
  · subst r; exact ⟨766, by decide, by decide, by decide⟩
  · subst r; exact ⟨808, by decide, by decide, by decide⟩
  · subst r; exact ⟨668, by decide, by decide, by decide⟩
  · subst r; exact ⟨655, by decide, by decide, by decide⟩
  · subst r; exact ⟨517, by decide, by decide, by decide⟩
  · subst r; exact ⟨502, by decide, by decide, by decide⟩
  · subst r; exact ⟨366, by decide, by decide, by decide⟩
  · subst r; exact ⟨349, by decide, by decide, by decide⟩
  · subst r; exact ⟨215, by decide, by decide, by decide⟩
  · subst r; exact ⟨196, by decide, by decide, by decide⟩
  · subst r; exact ⟨64, by decide, by decide, by decide⟩
  · subst r; exact ⟨43, by decide, by decide, by decide⟩
  · subst r; exact ⟨87, by decide, by decide, by decide⟩
  · subst r; exact ⟨110, by decide, by decide, by decide⟩
  · subst r; exact ⟨238, by decide, by decide, by decide⟩

theorem slice_32 (r : Nat) (lo : 1600 ≤ r) (hi : r ≤ 1649) : covered r := by
  have h : r = 1600 ∨ r = 1601 ∨ r = 1602 ∨ r = 1603 ∨ r = 1604 ∨ r = 1605 ∨ r = 1606 ∨ r = 1607 ∨ r = 1608 ∨ r = 1609 ∨ r = 1610 ∨ r = 1611 ∨ r = 1612 ∨ r = 1613 ∨ r = 1614 ∨ r = 1615 ∨ r = 1616 ∨ r = 1617 ∨ r = 1618 ∨ r = 1619 ∨ r = 1620 ∨ r = 1621 ∨ r = 1622 ∨ r = 1623 ∨ r = 1624 ∨ r = 1625 ∨ r = 1626 ∨ r = 1627 ∨ r = 1628 ∨ r = 1629 ∨ r = 1630 ∨ r = 1631 ∨ r = 1632 ∨ r = 1633 ∨ r = 1634 ∨ r = 1635 ∨ r = 1636 ∨ r = 1637 ∨ r = 1638 ∨ r = 1639 ∨ r = 1640 ∨ r = 1641 ∨ r = 1642 ∨ r = 1643 ∨ r = 1644 ∨ r = 1645 ∨ r = 1646 ∨ r = 1647 ∨ r = 1648 ∨ r = 1649 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨263, by decide, by decide, by decide⟩
  · subst r; exact ⟨389, by decide, by decide, by decide⟩
  · subst r; exact ⟨416, by decide, by decide, by decide⟩
  · subst r; exact ⟨540, by decide, by decide, by decide⟩
  · subst r; exact ⟨569, by decide, by decide, by decide⟩
  · subst r; exact ⟨691, by decide, by decide, by decide⟩
  · subst r; exact ⟨722, by decide, by decide, by decide⟩
  · subst r; exact ⟨842, by decide, by decide, by decide⟩
  · subst r; exact ⟨733, by decide, by decide, by decide⟩
  · subst r; exact ⟨699, by decide, by decide, by decide⟩
  · subst r; exact ⟨582, by decide, by decide, by decide⟩
  · subst r; exact ⟨546, by decide, by decide, by decide⟩
  · subst r; exact ⟨431, by decide, by decide, by decide⟩
  · subst r; exact ⟨393, by decide, by decide, by decide⟩
  · subst r; exact ⟨280, by decide, by decide, by decide⟩
  · subst r; exact ⟨240, by decide, by decide, by decide⟩
  · subst r; exact ⟨129, by decide, by decide, by decide⟩
  · subst r; exact ⟨87, by decide, by decide, by decide⟩
  · subst r; exact ⟨22, by decide, by decide, by decide⟩
  · subst r; exact ⟨66, by decide, by decide, by decide⟩
  · subst r; exact ⟨173, by decide, by decide, by decide⟩
  · subst r; exact ⟨219, by decide, by decide, by decide⟩
  · subst r; exact ⟨324, by decide, by decide, by decide⟩
  · subst r; exact ⟨372, by decide, by decide, by decide⟩
  · subst r; exact ⟨475, by decide, by decide, by decide⟩
  · subst r; exact ⟨525, by decide, by decide, by decide⟩
  · subst r; exact ⟨626, by decide, by decide, by decide⟩
  · subst r; exact ⟨678, by decide, by decide, by decide⟩
  · subst r; exact ⟨777, by decide, by decide, by decide⟩
  · subst r; exact ⟨798, by decide, by decide, by decide⟩
  · subst r; exact ⟨743, by decide, by decide, by decide⟩
  · subst r; exact ⟨647, by decide, by decide, by decide⟩
  · subst r; exact ⟨590, by decide, by decide, by decide⟩
  · subst r; exact ⟨496, by decide, by decide, by decide⟩
  · subst r; exact ⟨437, by decide, by decide, by decide⟩
  · subst r; exact ⟨345, by decide, by decide, by decide⟩
  · subst r; exact ⟨284, by decide, by decide, by decide⟩
  · subst r; exact ⟨194, by decide, by decide, by decide⟩
  · subst r; exact ⟨131, by decide, by decide, by decide⟩
  · subst r; exact ⟨43, by decide, by decide, by decide⟩
  · subst r; exact ⟨22, by decide, by decide, by decide⟩
  · subst r; exact ⟨108, by decide, by decide, by decide⟩
  · subst r; exact ⟨175, by decide, by decide, by decide⟩
  · subst r; exact ⟨259, by decide, by decide, by decide⟩
  · subst r; exact ⟨328, by decide, by decide, by decide⟩
  · subst r; exact ⟨410, by decide, by decide, by decide⟩
  · subst r; exact ⟨481, by decide, by decide, by decide⟩
  · subst r; exact ⟨561, by decide, by decide, by decide⟩
  · subst r; exact ⟨634, by decide, by decide, by decide⟩
  · subst r; exact ⟨712, by decide, by decide, by decide⟩

theorem slice_33 (r : Nat) (lo : 1650 ≤ r) (hi : r ≤ 1699) : covered r := by
  have h : r = 1650 ∨ r = 1651 ∨ r = 1652 ∨ r = 1653 ∨ r = 1654 ∨ r = 1655 ∨ r = 1656 ∨ r = 1657 ∨ r = 1658 ∨ r = 1659 ∨ r = 1660 ∨ r = 1661 ∨ r = 1662 ∨ r = 1663 ∨ r = 1664 ∨ r = 1665 ∨ r = 1666 ∨ r = 1667 ∨ r = 1668 ∨ r = 1669 ∨ r = 1670 ∨ r = 1671 ∨ r = 1672 ∨ r = 1673 ∨ r = 1674 ∨ r = 1675 ∨ r = 1676 ∨ r = 1677 ∨ r = 1678 ∨ r = 1679 ∨ r = 1680 ∨ r = 1681 ∨ r = 1682 ∨ r = 1683 ∨ r = 1684 ∨ r = 1685 ∨ r = 1686 ∨ r = 1687 ∨ r = 1688 ∨ r = 1689 ∨ r = 1690 ∨ r = 1691 ∨ r = 1692 ∨ r = 1693 ∨ r = 1694 ∨ r = 1695 ∨ r = 1696 ∨ r = 1697 ∨ r = 1698 ∨ r = 1699 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨787, by decide, by decide, by decide⟩
  · subst r; exact ⟨787, by decide, by decide, by decide⟩
  · subst r; exact ⟨712, by decide, by decide, by decide⟩
  · subst r; exact ⟨634, by decide, by decide, by decide⟩
  · subst r; exact ⟨561, by decide, by decide, by decide⟩
  · subst r; exact ⟨481, by decide, by decide, by decide⟩
  · subst r; exact ⟨410, by decide, by decide, by decide⟩
  · subst r; exact ⟨328, by decide, by decide, by decide⟩
  · subst r; exact ⟨259, by decide, by decide, by decide⟩
  · subst r; exact ⟨175, by decide, by decide, by decide⟩
  · subst r; exact ⟨108, by decide, by decide, by decide⟩
  · subst r; exact ⟨22, by decide, by decide, by decide⟩
  · subst r; exact ⟨43, by decide, by decide, by decide⟩
  · subst r; exact ⟨131, by decide, by decide, by decide⟩
  · subst r; exact ⟨194, by decide, by decide, by decide⟩
  · subst r; exact ⟨284, by decide, by decide, by decide⟩
  · subst r; exact ⟨345, by decide, by decide, by decide⟩
  · subst r; exact ⟨437, by decide, by decide, by decide⟩
  · subst r; exact ⟨496, by decide, by decide, by decide⟩
  · subst r; exact ⟨590, by decide, by decide, by decide⟩
  · subst r; exact ⟨647, by decide, by decide, by decide⟩
  · subst r; exact ⟨743, by decide, by decide, by decide⟩
  · subst r; exact ⟨798, by decide, by decide, by decide⟩
  · subst r; exact ⟨777, by decide, by decide, by decide⟩
  · subst r; exact ⟨678, by decide, by decide, by decide⟩
  · subst r; exact ⟨626, by decide, by decide, by decide⟩
  · subst r; exact ⟨525, by decide, by decide, by decide⟩
  · subst r; exact ⟨475, by decide, by decide, by decide⟩
  · subst r; exact ⟨372, by decide, by decide, by decide⟩
  · subst r; exact ⟨324, by decide, by decide, by decide⟩
  · subst r; exact ⟨219, by decide, by decide, by decide⟩
  · subst r; exact ⟨173, by decide, by decide, by decide⟩
  · subst r; exact ⟨66, by decide, by decide, by decide⟩
  · subst r; exact ⟨22, by decide, by decide, by decide⟩
  · subst r; exact ⟨87, by decide, by decide, by decide⟩
  · subst r; exact ⟨129, by decide, by decide, by decide⟩
  · subst r; exact ⟨240, by decide, by decide, by decide⟩
  · subst r; exact ⟨280, by decide, by decide, by decide⟩
  · subst r; exact ⟨393, by decide, by decide, by decide⟩
  · subst r; exact ⟨431, by decide, by decide, by decide⟩
  · subst r; exact ⟨546, by decide, by decide, by decide⟩
  · subst r; exact ⟨582, by decide, by decide, by decide⟩
  · subst r; exact ⟨699, by decide, by decide, by decide⟩
  · subst r; exact ⟨733, by decide, by decide, by decide⟩
  · subst r; exact ⟨842, by decide, by decide, by decide⟩
  · subst r; exact ⟨722, by decide, by decide, by decide⟩
  · subst r; exact ⟨691, by decide, by decide, by decide⟩
  · subst r; exact ⟨569, by decide, by decide, by decide⟩
  · subst r; exact ⟨540, by decide, by decide, by decide⟩
  · subst r; exact ⟨416, by decide, by decide, by decide⟩

theorem slice_34 (r : Nat) (lo : 1700 ≤ r) (hi : r ≤ 1749) : covered r := by
  have h : r = 1700 ∨ r = 1701 ∨ r = 1702 ∨ r = 1703 ∨ r = 1704 ∨ r = 1705 ∨ r = 1706 ∨ r = 1707 ∨ r = 1708 ∨ r = 1709 ∨ r = 1710 ∨ r = 1711 ∨ r = 1712 ∨ r = 1713 ∨ r = 1714 ∨ r = 1715 ∨ r = 1716 ∨ r = 1717 ∨ r = 1718 ∨ r = 1719 ∨ r = 1720 ∨ r = 1721 ∨ r = 1722 ∨ r = 1723 ∨ r = 1724 ∨ r = 1725 ∨ r = 1726 ∨ r = 1727 ∨ r = 1728 ∨ r = 1729 ∨ r = 1730 ∨ r = 1731 ∨ r = 1732 ∨ r = 1733 ∨ r = 1734 ∨ r = 1735 ∨ r = 1736 ∨ r = 1737 ∨ r = 1738 ∨ r = 1739 ∨ r = 1740 ∨ r = 1741 ∨ r = 1742 ∨ r = 1743 ∨ r = 1744 ∨ r = 1745 ∨ r = 1746 ∨ r = 1747 ∨ r = 1748 ∨ r = 1749 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨389, by decide, by decide, by decide⟩
  · subst r; exact ⟨263, by decide, by decide, by decide⟩
  · subst r; exact ⟨238, by decide, by decide, by decide⟩
  · subst r; exact ⟨110, by decide, by decide, by decide⟩
  · subst r; exact ⟨87, by decide, by decide, by decide⟩
  · subst r; exact ⟨43, by decide, by decide, by decide⟩
  · subst r; exact ⟨64, by decide, by decide, by decide⟩
  · subst r; exact ⟨196, by decide, by decide, by decide⟩
  · subst r; exact ⟨215, by decide, by decide, by decide⟩
  · subst r; exact ⟨349, by decide, by decide, by decide⟩
  · subst r; exact ⟨366, by decide, by decide, by decide⟩
  · subst r; exact ⟨502, by decide, by decide, by decide⟩
  · subst r; exact ⟨517, by decide, by decide, by decide⟩
  · subst r; exact ⟨655, by decide, by decide, by decide⟩
  · subst r; exact ⟨668, by decide, by decide, by decide⟩
  · subst r; exact ⟨808, by decide, by decide, by decide⟩
  · subst r; exact ⟨766, by decide, by decide, by decide⟩
  · subst r; exact ⟨756, by decide, by decide, by decide⟩
  · subst r; exact ⟨613, by decide, by decide, by decide⟩
  · subst r; exact ⟨605, by decide, by decide, by decide⟩
  · subst r; exact ⟨460, by decide, by decide, by decide⟩
  · subst r; exact ⟨454, by decide, by decide, by decide⟩
  · subst r; exact ⟨307, by decide, by decide, by decide⟩
  · subst r; exact ⟨303, by decide, by decide, by decide⟩
  · subst r; exact ⟨154, by decide, by decide, by decide⟩
  · subst r; exact ⟨152, by decide, by decide, by decide⟩
  · subst r; exact ⟨1, by decide, by decide, by decide⟩
  · subst r; exact ⟨1, by decide, by decide, by decide⟩
  · subst r; exact ⟨152, by decide, by decide, by decide⟩
  · subst r; exact ⟨150, by decide, by decide, by decide⟩
  · subst r; exact ⟨305, by decide, by decide, by decide⟩
  · subst r; exact ⟨301, by decide, by decide, by decide⟩
  · subst r; exact ⟨458, by decide, by decide, by decide⟩
  · subst r; exact ⟨452, by decide, by decide, by decide⟩
  · subst r; exact ⟨611, by decide, by decide, by decide⟩
  · subst r; exact ⟨603, by decide, by decide, by decide⟩
  · subst r; exact ⟨764, by decide, by decide, by decide⟩
  · subst r; exact ⟨754, by decide, by decide, by decide⟩
  · subst r; exact ⟨821, by decide, by decide, by decide⟩
  · subst r; exact ⟨657, by decide, by decide, by decide⟩
  · subst r; exact ⟨670, by decide, by decide, by decide⟩
  · subst r; exact ⟨504, by decide, by decide, by decide⟩
  · subst r; exact ⟨519, by decide, by decide, by decide⟩
  · subst r; exact ⟨351, by decide, by decide, by decide⟩
  · subst r; exact ⟨368, by decide, by decide, by decide⟩
  · subst r; exact ⟨198, by decide, by decide, by decide⟩
  · subst r; exact ⟨217, by decide, by decide, by decide⟩
  · subst r; exact ⟨45, by decide, by decide, by decide⟩
  · subst r; exact ⟨66, by decide, by decide, by decide⟩
  · subst r; exact ⟨108, by decide, by decide, by decide⟩

theorem slice_35 (r : Nat) (lo : 1750 ≤ r) (hi : r ≤ 1799) : covered r := by
  have h : r = 1750 ∨ r = 1751 ∨ r = 1752 ∨ r = 1753 ∨ r = 1754 ∨ r = 1755 ∨ r = 1756 ∨ r = 1757 ∨ r = 1758 ∨ r = 1759 ∨ r = 1760 ∨ r = 1761 ∨ r = 1762 ∨ r = 1763 ∨ r = 1764 ∨ r = 1765 ∨ r = 1766 ∨ r = 1767 ∨ r = 1768 ∨ r = 1769 ∨ r = 1770 ∨ r = 1771 ∨ r = 1772 ∨ r = 1773 ∨ r = 1774 ∨ r = 1775 ∨ r = 1776 ∨ r = 1777 ∨ r = 1778 ∨ r = 1779 ∨ r = 1780 ∨ r = 1781 ∨ r = 1782 ∨ r = 1783 ∨ r = 1784 ∨ r = 1785 ∨ r = 1786 ∨ r = 1787 ∨ r = 1788 ∨ r = 1789 ∨ r = 1790 ∨ r = 1791 ∨ r = 1792 ∨ r = 1793 ∨ r = 1794 ∨ r = 1795 ∨ r = 1796 ∨ r = 1797 ∨ r = 1798 ∨ r = 1799 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨85, by decide, by decide, by decide⟩
  · subst r; exact ⟨261, by decide, by decide, by decide⟩
  · subst r; exact ⟨236, by decide, by decide, by decide⟩
  · subst r; exact ⟨414, by decide, by decide, by decide⟩
  · subst r; exact ⟨387, by decide, by decide, by decide⟩
  · subst r; exact ⟨567, by decide, by decide, by decide⟩
  · subst r; exact ⟨538, by decide, by decide, by decide⟩
  · subst r; exact ⟨720, by decide, by decide, by decide⟩
  · subst r; exact ⟨689, by decide, by decide, by decide⟩
  · subst r; exact ⟨873, by decide, by decide, by decide⟩
  · subst r; exact ⟨701, by decide, by decide, by decide⟩
  · subst r; exact ⟨735, by decide, by decide, by decide⟩
  · subst r; exact ⟨548, by decide, by decide, by decide⟩
  · subst r; exact ⟨584, by decide, by decide, by decide⟩
  · subst r; exact ⟨395, by decide, by decide, by decide⟩
  · subst r; exact ⟨433, by decide, by decide, by decide⟩
  · subst r; exact ⟨242, by decide, by decide, by decide⟩
  · subst r; exact ⟨282, by decide, by decide, by decide⟩
  · subst r; exact ⟨89, by decide, by decide, by decide⟩
  · subst r; exact ⟨131, by decide, by decide, by decide⟩
  · subst r; exact ⟨64, by decide, by decide, by decide⟩
  · subst r; exact ⟨20, by decide, by decide, by decide⟩
  · subst r; exact ⟨217, by decide, by decide, by decide⟩
  · subst r; exact ⟨171, by decide, by decide, by decide⟩
  · subst r; exact ⟨370, by decide, by decide, by decide⟩
  · subst r; exact ⟨322, by decide, by decide, by decide⟩
  · subst r; exact ⟨523, by decide, by decide, by decide⟩
  · subst r; exact ⟨473, by decide, by decide, by decide⟩
  · subst r; exact ⟨676, by decide, by decide, by decide⟩
  · subst r; exact ⟨624, by decide, by decide, by decide⟩
  · subst r; exact ⟨829, by decide, by decide, by decide⟩
  · subst r; exact ⟨745, by decide, by decide, by decide⟩
  · subst r; exact ⟨800, by decide, by decide, by decide⟩
  · subst r; exact ⟨592, by decide, by decide, by decide⟩
  · subst r; exact ⟨649, by decide, by decide, by decide⟩
  · subst r; exact ⟨439, by decide, by decide, by decide⟩
  · subst r; exact ⟨498, by decide, by decide, by decide⟩
  · subst r; exact ⟨286, by decide, by decide, by decide⟩
  · subst r; exact ⟨347, by decide, by decide, by decide⟩
  · subst r; exact ⟨133, by decide, by decide, by decide⟩
  · subst r; exact ⟨196, by decide, by decide, by decide⟩
  · subst r; exact ⟨20, by decide, by decide, by decide⟩
  · subst r; exact ⟨45, by decide, by decide, by decide⟩
  · subst r; exact ⟨173, by decide, by decide, by decide⟩
  · subst r; exact ⟨106, by decide, by decide, by decide⟩
  · subst r; exact ⟨326, by decide, by decide, by decide⟩
  · subst r; exact ⟨257, by decide, by decide, by decide⟩
  · subst r; exact ⟨479, by decide, by decide, by decide⟩
  · subst r; exact ⟨408, by decide, by decide, by decide⟩
  · subst r; exact ⟨632, by decide, by decide, by decide⟩

theorem slice_36 (r : Nat) (lo : 1800 ≤ r) (hi : r ≤ 1849) : covered r := by
  have h : r = 1800 ∨ r = 1801 ∨ r = 1802 ∨ r = 1803 ∨ r = 1804 ∨ r = 1805 ∨ r = 1806 ∨ r = 1807 ∨ r = 1808 ∨ r = 1809 ∨ r = 1810 ∨ r = 1811 ∨ r = 1812 ∨ r = 1813 ∨ r = 1814 ∨ r = 1815 ∨ r = 1816 ∨ r = 1817 ∨ r = 1818 ∨ r = 1819 ∨ r = 1820 ∨ r = 1821 ∨ r = 1822 ∨ r = 1823 ∨ r = 1824 ∨ r = 1825 ∨ r = 1826 ∨ r = 1827 ∨ r = 1828 ∨ r = 1829 ∨ r = 1830 ∨ r = 1831 ∨ r = 1832 ∨ r = 1833 ∨ r = 1834 ∨ r = 1835 ∨ r = 1836 ∨ r = 1837 ∨ r = 1838 ∨ r = 1839 ∨ r = 1840 ∨ r = 1841 ∨ r = 1842 ∨ r = 1843 ∨ r = 1844 ∨ r = 1845 ∨ r = 1846 ∨ r = 1847 ∨ r = 1848 ∨ r = 1849 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨559, by decide, by decide, by decide⟩
  · subst r; exact ⟨785, by decide, by decide, by decide⟩
  · subst r; exact ⟨710, by decide, by decide, by decide⟩
  · subst r; exact ⟨865, by decide, by decide, by decide⟩
  · subst r; exact ⟨636, by decide, by decide, by decide⟩
  · subst r; exact ⟨714, by decide, by decide, by decide⟩
  · subst r; exact ⟨483, by decide, by decide, by decide⟩
  · subst r; exact ⟨563, by decide, by decide, by decide⟩
  · subst r; exact ⟨330, by decide, by decide, by decide⟩
  · subst r; exact ⟨412, by decide, by decide, by decide⟩
  · subst r; exact ⟨177, by decide, by decide, by decide⟩
  · subst r; exact ⟨261, by decide, by decide, by decide⟩
  · subst r; exact ⟨24, by decide, by decide, by decide⟩
  · subst r; exact ⟨110, by decide, by decide, by decide⟩
  · subst r; exact ⟨129, by decide, by decide, by decide⟩
  · subst r; exact ⟨41, by decide, by decide, by decide⟩
  · subst r; exact ⟨282, by decide, by decide, by decide⟩
  · subst r; exact ⟨192, by decide, by decide, by decide⟩
  · subst r; exact ⟨435, by decide, by decide, by decide⟩
  · subst r; exact ⟨343, by decide, by decide, by decide⟩
  · subst r; exact ⟨588, by decide, by decide, by decide⟩
  · subst r; exact ⟨494, by decide, by decide, by decide⟩
  · subst r; exact ⟨741, by decide, by decide, by decide⟩
  · subst r; exact ⟨645, by decide, by decide, by decide⟩
  · subst r; exact ⟨894, by decide, by decide, by decide⟩
  · subst r; exact ⟨680, by decide, by decide, by decide⟩
  · subst r; exact ⟨779, by decide, by decide, by decide⟩
  · subst r; exact ⟨527, by decide, by decide, by decide⟩
  · subst r; exact ⟨628, by decide, by decide, by decide⟩
  · subst r; exact ⟨374, by decide, by decide, by decide⟩
  · subst r; exact ⟨477, by decide, by decide, by decide⟩
  · subst r; exact ⟨221, by decide, by decide, by decide⟩
  · subst r; exact ⟨326, by decide, by decide, by decide⟩
  · subst r; exact ⟨68, by decide, by decide, by decide⟩
  · subst r; exact ⟨175, by decide, by decide, by decide⟩
  · subst r; exact ⟨85, by decide, by decide, by decide⟩
  · subst r; exact ⟨24, by decide, by decide, by decide⟩
  · subst r; exact ⟨238, by decide, by decide, by decide⟩
  · subst r; exact ⟨127, by decide, by decide, by decide⟩
  · subst r; exact ⟨391, by decide, by decide, by decide⟩
  · subst r; exact ⟨278, by decide, by decide, by decide⟩
  · subst r; exact ⟨544, by decide, by decide, by decide⟩
  · subst r; exact ⟨429, by decide, by decide, by decide⟩
  · subst r; exact ⟨697, by decide, by decide, by decide⟩
  · subst r; exact ⟨580, by decide, by decide, by decide⟩
  · subst r; exact ⟨850, by decide, by decide, by decide⟩
  · subst r; exact ⟨724, by decide, by decide, by decide⟩
  · subst r; exact ⟨844, by decide, by decide, by decide⟩
  · subst r; exact ⟨571, by decide, by decide, by decide⟩
  · subst r; exact ⟨693, by decide, by decide, by decide⟩

theorem slice_37 (r : Nat) (lo : 1850 ≤ r) (hi : r ≤ 1899) : covered r := by
  have h : r = 1850 ∨ r = 1851 ∨ r = 1852 ∨ r = 1853 ∨ r = 1854 ∨ r = 1855 ∨ r = 1856 ∨ r = 1857 ∨ r = 1858 ∨ r = 1859 ∨ r = 1860 ∨ r = 1861 ∨ r = 1862 ∨ r = 1863 ∨ r = 1864 ∨ r = 1865 ∨ r = 1866 ∨ r = 1867 ∨ r = 1868 ∨ r = 1869 ∨ r = 1870 ∨ r = 1871 ∨ r = 1872 ∨ r = 1873 ∨ r = 1874 ∨ r = 1875 ∨ r = 1876 ∨ r = 1877 ∨ r = 1878 ∨ r = 1879 ∨ r = 1880 ∨ r = 1881 ∨ r = 1882 ∨ r = 1883 ∨ r = 1884 ∨ r = 1885 ∨ r = 1886 ∨ r = 1887 ∨ r = 1888 ∨ r = 1889 ∨ r = 1890 ∨ r = 1891 ∨ r = 1892 ∨ r = 1893 ∨ r = 1894 ∨ r = 1895 ∨ r = 1896 ∨ r = 1897 ∨ r = 1898 ∨ r = 1899 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨418, by decide, by decide, by decide⟩
  · subst r; exact ⟨542, by decide, by decide, by decide⟩
  · subst r; exact ⟨265, by decide, by decide, by decide⟩
  · subst r; exact ⟨391, by decide, by decide, by decide⟩
  · subst r; exact ⟨112, by decide, by decide, by decide⟩
  · subst r; exact ⟨240, by decide, by decide, by decide⟩
  · subst r; exact ⟨41, by decide, by decide, by decide⟩
  · subst r; exact ⟨89, by decide, by decide, by decide⟩
  · subst r; exact ⟨194, by decide, by decide, by decide⟩
  · subst r; exact ⟨62, by decide, by decide, by decide⟩
  · subst r; exact ⟨347, by decide, by decide, by decide⟩
  · subst r; exact ⟨213, by decide, by decide, by decide⟩
  · subst r; exact ⟨500, by decide, by decide, by decide⟩
  · subst r; exact ⟨364, by decide, by decide, by decide⟩
  · subst r; exact ⟨653, by decide, by decide, by decide⟩
  · subst r; exact ⟨515, by decide, by decide, by decide⟩
  · subst r; exact ⟨806, by decide, by decide, by decide⟩
  · subst r; exact ⟨666, by decide, by decide, by decide⟩
  · subst r; exact ⟨909, by decide, by decide, by decide⟩
  · subst r; exact ⟨615, by decide, by decide, by decide⟩
  · subst r; exact ⟨758, by decide, by decide, by decide⟩
  · subst r; exact ⟨462, by decide, by decide, by decide⟩
  · subst r; exact ⟨607, by decide, by decide, by decide⟩
  · subst r; exact ⟨309, by decide, by decide, by decide⟩
  · subst r; exact ⟨456, by decide, by decide, by decide⟩
  · subst r; exact ⟨156, by decide, by decide, by decide⟩
  · subst r; exact ⟨305, by decide, by decide, by decide⟩
  · subst r; exact ⟨3, by decide, by decide, by decide⟩
  · subst r; exact ⟨154, by decide, by decide, by decide⟩
  · subst r; exact ⟨150, by decide, by decide, by decide⟩
  · subst r; exact ⟨3, by decide, by decide, by decide⟩
  · subst r; exact ⟨303, by decide, by decide, by decide⟩
  · subst r; exact ⟨148, by decide, by decide, by decide⟩
  · subst r; exact ⟨456, by decide, by decide, by decide⟩
  · subst r; exact ⟨299, by decide, by decide, by decide⟩
  · subst r; exact ⟨609, by decide, by decide, by decide⟩
  · subst r; exact ⟨450, by decide, by decide, by decide⟩
  · subst r; exact ⟨762, by decide, by decide, by decide⟩
  · subst r; exact ⟨601, by decide, by decide, by decide⟩
  · subst r; exact ⟨915, by decide, by decide, by decide⟩
  · subst r; exact ⟨659, by decide, by decide, by decide⟩
  · subst r; exact ⟨823, by decide, by decide, by decide⟩
  · subst r; exact ⟨506, by decide, by decide, by decide⟩
  · subst r; exact ⟨672, by decide, by decide, by decide⟩
  · subst r; exact ⟨353, by decide, by decide, by decide⟩
  · subst r; exact ⟨521, by decide, by decide, by decide⟩
  · subst r; exact ⟨200, by decide, by decide, by decide⟩
  · subst r; exact ⟨370, by decide, by decide, by decide⟩
  · subst r; exact ⟨47, by decide, by decide, by decide⟩
  · subst r; exact ⟨219, by decide, by decide, by decide⟩

theorem slice_38 (r : Nat) (lo : 1900 ≤ r) (hi : r ≤ 1949) : covered r := by
  have h : r = 1900 ∨ r = 1901 ∨ r = 1902 ∨ r = 1903 ∨ r = 1904 ∨ r = 1905 ∨ r = 1906 ∨ r = 1907 ∨ r = 1908 ∨ r = 1909 ∨ r = 1910 ∨ r = 1911 ∨ r = 1912 ∨ r = 1913 ∨ r = 1914 ∨ r = 1915 ∨ r = 1916 ∨ r = 1917 ∨ r = 1918 ∨ r = 1919 ∨ r = 1920 ∨ r = 1921 ∨ r = 1922 ∨ r = 1923 ∨ r = 1924 ∨ r = 1925 ∨ r = 1926 ∨ r = 1927 ∨ r = 1928 ∨ r = 1929 ∨ r = 1930 ∨ r = 1931 ∨ r = 1932 ∨ r = 1933 ∨ r = 1934 ∨ r = 1935 ∨ r = 1936 ∨ r = 1937 ∨ r = 1938 ∨ r = 1939 ∨ r = 1940 ∨ r = 1941 ∨ r = 1942 ∨ r = 1943 ∨ r = 1944 ∨ r = 1945 ∨ r = 1946 ∨ r = 1947 ∨ r = 1948 ∨ r = 1949 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨106, by decide, by decide, by decide⟩
  · subst r; exact ⟨68, by decide, by decide, by decide⟩
  · subst r; exact ⟨259, by decide, by decide, by decide⟩
  · subst r; exact ⟨83, by decide, by decide, by decide⟩
  · subst r; exact ⟨412, by decide, by decide, by decide⟩
  · subst r; exact ⟨234, by decide, by decide, by decide⟩
  · subst r; exact ⟨565, by decide, by decide, by decide⟩
  · subst r; exact ⟨385, by decide, by decide, by decide⟩
  · subst r; exact ⟨718, by decide, by decide, by decide⟩
  · subst r; exact ⟨536, by decide, by decide, by decide⟩
  · subst r; exact ⟨871, by decide, by decide, by decide⟩
  · subst r; exact ⟨687, by decide, by decide, by decide⟩
  · subst r; exact ⟨888, by decide, by decide, by decide⟩
  · subst r; exact ⟨550, by decide, by decide, by decide⟩
  · subst r; exact ⟨737, by decide, by decide, by decide⟩
  · subst r; exact ⟨397, by decide, by decide, by decide⟩
  · subst r; exact ⟨586, by decide, by decide, by decide⟩
  · subst r; exact ⟨244, by decide, by decide, by decide⟩
  · subst r; exact ⟨435, by decide, by decide, by decide⟩
  · subst r; exact ⟨91, by decide, by decide, by decide⟩
  · subst r; exact ⟨284, by decide, by decide, by decide⟩
  · subst r; exact ⟨62, by decide, by decide, by decide⟩
  · subst r; exact ⟨133, by decide, by decide, by decide⟩
  · subst r; exact ⟨215, by decide, by decide, by decide⟩
  · subst r; exact ⟨18, by decide, by decide, by decide⟩
  · subst r; exact ⟨368, by decide, by decide, by decide⟩
  · subst r; exact ⟨169, by decide, by decide, by decide⟩
  · subst r; exact ⟨521, by decide, by decide, by decide⟩
  · subst r; exact ⟨320, by decide, by decide, by decide⟩
  · subst r; exact ⟨674, by decide, by decide, by decide⟩
  · subst r; exact ⟨471, by decide, by decide, by decide⟩
  · subst r; exact ⟨827, by decide, by decide, by decide⟩
  · subst r; exact ⟨622, by decide, by decide, by decide⟩
  · subst r; exact ⟨953, by decide, by decide, by decide⟩
  · subst r; exact ⟨594, by decide, by decide, by decide⟩
  · subst r; exact ⟨802, by decide, by decide, by decide⟩
  · subst r; exact ⟨441, by decide, by decide, by decide⟩
  · subst r; exact ⟨651, by decide, by decide, by decide⟩
  · subst r; exact ⟨288, by decide, by decide, by decide⟩
  · subst r; exact ⟨500, by decide, by decide, by decide⟩
  · subst r; exact ⟨135, by decide, by decide, by decide⟩
  · subst r; exact ⟨349, by decide, by decide, by decide⟩
  · subst r; exact ⟨18, by decide, by decide, by decide⟩
  · subst r; exact ⟨198, by decide, by decide, by decide⟩
  · subst r; exact ⟨171, by decide, by decide, by decide⟩
  · subst r; exact ⟨47, by decide, by decide, by decide⟩
  · subst r; exact ⟨324, by decide, by decide, by decide⟩
  · subst r; exact ⟨104, by decide, by decide, by decide⟩
  · subst r; exact ⟨477, by decide, by decide, by decide⟩
  · subst r; exact ⟨255, by decide, by decide, by decide⟩

theorem slice_39 (r : Nat) (lo : 1950 ≤ r) (hi : r ≤ 1999) : covered r := by
  have h : r = 1950 ∨ r = 1951 ∨ r = 1952 ∨ r = 1953 ∨ r = 1954 ∨ r = 1955 ∨ r = 1956 ∨ r = 1957 ∨ r = 1958 ∨ r = 1959 ∨ r = 1960 ∨ r = 1961 ∨ r = 1962 ∨ r = 1963 ∨ r = 1964 ∨ r = 1965 ∨ r = 1966 ∨ r = 1967 ∨ r = 1968 ∨ r = 1969 ∨ r = 1970 ∨ r = 1971 ∨ r = 1972 ∨ r = 1973 ∨ r = 1974 ∨ r = 1975 ∨ r = 1976 ∨ r = 1977 ∨ r = 1978 ∨ r = 1979 ∨ r = 1980 ∨ r = 1981 ∨ r = 1982 ∨ r = 1983 ∨ r = 1984 ∨ r = 1985 ∨ r = 1986 ∨ r = 1987 ∨ r = 1988 ∨ r = 1989 ∨ r = 1990 ∨ r = 1991 ∨ r = 1992 ∨ r = 1993 ∨ r = 1994 ∨ r = 1995 ∨ r = 1996 ∨ r = 1997 ∨ r = 1998 ∨ r = 1999 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨630, by decide, by decide, by decide⟩
  · subst r; exact ⟨406, by decide, by decide, by decide⟩
  · subst r; exact ⟨783, by decide, by decide, by decide⟩
  · subst r; exact ⟨557, by decide, by decide, by decide⟩
  · subst r; exact ⟨936, by decide, by decide, by decide⟩
  · subst r; exact ⟨638, by decide, by decide, by decide⟩
  · subst r; exact ⟨867, by decide, by decide, by decide⟩
  · subst r; exact ⟨485, by decide, by decide, by decide⟩
  · subst r; exact ⟨716, by decide, by decide, by decide⟩
  · subst r; exact ⟨332, by decide, by decide, by decide⟩
  · subst r; exact ⟨565, by decide, by decide, by decide⟩
  · subst r; exact ⟨179, by decide, by decide, by decide⟩
  · subst r; exact ⟨414, by decide, by decide, by decide⟩
  · subst r; exact ⟨26, by decide, by decide, by decide⟩
  · subst r; exact ⟨263, by decide, by decide, by decide⟩
  · subst r; exact ⟨127, by decide, by decide, by decide⟩
  · subst r; exact ⟨112, by decide, by decide, by decide⟩
  · subst r; exact ⟨280, by decide, by decide, by decide⟩
  · subst r; exact ⟨39, by decide, by decide, by decide⟩
  · subst r; exact ⟨433, by decide, by decide, by decide⟩
  · subst r; exact ⟨190, by decide, by decide, by decide⟩
  · subst r; exact ⟨586, by decide, by decide, by decide⟩
  · subst r; exact ⟨341, by decide, by decide, by decide⟩
  · subst r; exact ⟨739, by decide, by decide, by decide⟩
  · subst r; exact ⟨492, by decide, by decide, by decide⟩
  · subst r; exact ⟨892, by decide, by decide, by decide⟩
  · subst r; exact ⟨643, by decide, by decide, by decide⟩
  · subst r; exact ⟨932, by decide, by decide, by decide⟩
  · subst r; exact ⟨529, by decide, by decide, by decide⟩
  · subst r; exact ⟨781, by decide, by decide, by decide⟩
  · subst r; exact ⟨376, by decide, by decide, by decide⟩
  · subst r; exact ⟨630, by decide, by decide, by decide⟩
  · subst r; exact ⟨223, by decide, by decide, by decide⟩
  · subst r; exact ⟨479, by decide, by decide, by decide⟩
  · subst r; exact ⟨70, by decide, by decide, by decide⟩
  · subst r; exact ⟨328, by decide, by decide, by decide⟩
  · subst r; exact ⟨83, by decide, by decide, by decide⟩
  · subst r; exact ⟨177, by decide, by decide, by decide⟩
  · subst r; exact ⟨236, by decide, by decide, by decide⟩
  · subst r; exact ⟨26, by decide, by decide, by decide⟩
  · subst r; exact ⟨389, by decide, by decide, by decide⟩
  · subst r; exact ⟨125, by decide, by decide, by decide⟩
  · subst r; exact ⟨542, by decide, by decide, by decide⟩
  · subst r; exact ⟨276, by decide, by decide, by decide⟩
  · subst r; exact ⟨695, by decide, by decide, by decide⟩
  · subst r; exact ⟨427, by decide, by decide, by decide⟩
  · subst r; exact ⟨848, by decide, by decide, by decide⟩
  · subst r; exact ⟨578, by decide, by decide, by decide⟩
  · subst r; exact ⟨997, by decide, by decide, by decide⟩
  · subst r; exact ⟨573, by decide, by decide, by decide⟩

theorem slice_40 (r : Nat) (lo : 2000 ≤ r) (hi : r ≤ 2049) : covered r := by
  have h : r = 2000 ∨ r = 2001 ∨ r = 2002 ∨ r = 2003 ∨ r = 2004 ∨ r = 2005 ∨ r = 2006 ∨ r = 2007 ∨ r = 2008 ∨ r = 2009 ∨ r = 2010 ∨ r = 2011 ∨ r = 2012 ∨ r = 2013 ∨ r = 2014 ∨ r = 2015 ∨ r = 2016 ∨ r = 2017 ∨ r = 2018 ∨ r = 2019 ∨ r = 2020 ∨ r = 2021 ∨ r = 2022 ∨ r = 2023 ∨ r = 2024 ∨ r = 2025 ∨ r = 2026 ∨ r = 2027 ∨ r = 2028 ∨ r = 2029 ∨ r = 2030 ∨ r = 2031 ∨ r = 2032 ∨ r = 2033 ∨ r = 2034 ∨ r = 2035 ∨ r = 2036 ∨ r = 2037 ∨ r = 2038 ∨ r = 2039 ∨ r = 2040 ∨ r = 2041 ∨ r = 2042 ∨ r = 2043 ∨ r = 2044 ∨ r = 2045 ∨ r = 2046 ∨ r = 2047 ∨ r = 2048 ∨ r = 2049 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨846, by decide, by decide, by decide⟩
  · subst r; exact ⟨420, by decide, by decide, by decide⟩
  · subst r; exact ⟨695, by decide, by decide, by decide⟩
  · subst r; exact ⟨267, by decide, by decide, by decide⟩
  · subst r; exact ⟨544, by decide, by decide, by decide⟩
  · subst r; exact ⟨114, by decide, by decide, by decide⟩
  · subst r; exact ⟨393, by decide, by decide, by decide⟩
  · subst r; exact ⟨39, by decide, by decide, by decide⟩
  · subst r; exact ⟨242, by decide, by decide, by decide⟩
  · subst r; exact ⟨192, by decide, by decide, by decide⟩
  · subst r; exact ⟨91, by decide, by decide, by decide⟩
  · subst r; exact ⟨345, by decide, by decide, by decide⟩
  · subst r; exact ⟨60, by decide, by decide, by decide⟩
  · subst r; exact ⟨498, by decide, by decide, by decide⟩
  · subst r; exact ⟨211, by decide, by decide, by decide⟩
  · subst r; exact ⟨651, by decide, by decide, by decide⟩
  · subst r; exact ⟨362, by decide, by decide, by decide⟩
  · subst r; exact ⟨804, by decide, by decide, by decide⟩
  · subst r; exact ⟨513, by decide, by decide, by decide⟩
  · subst r; exact ⟨957, by decide, by decide, by decide⟩
  · subst r; exact ⟨617, by decide, by decide, by decide⟩
  · subst r; exact ⟨911, by decide, by decide, by decide⟩
  · subst r; exact ⟨464, by decide, by decide, by decide⟩
  · subst r; exact ⟨760, by decide, by decide, by decide⟩
  · subst r; exact ⟨311, by decide, by decide, by decide⟩
  · subst r; exact ⟨609, by decide, by decide, by decide⟩
  · subst r; exact ⟨158, by decide, by decide, by decide⟩
  · subst r; exact ⟨458, by decide, by decide, by decide⟩
  · subst r; exact ⟨5, by decide, by decide, by decide⟩
  · subst r; exact ⟨307, by decide, by decide, by decide⟩
  · subst r; exact ⟨148, by decide, by decide, by decide⟩
  · subst r; exact ⟨156, by decide, by decide, by decide⟩
  · subst r; exact ⟨301, by decide, by decide, by decide⟩
  · subst r; exact ⟨5, by decide, by decide, by decide⟩
  · subst r; exact ⟨454, by decide, by decide, by decide⟩
  · subst r; exact ⟨146, by decide, by decide, by decide⟩
  · subst r; exact ⟨607, by decide, by decide, by decide⟩
  · subst r; exact ⟨297, by decide, by decide, by decide⟩
  · subst r; exact ⟨760, by decide, by decide, by decide⟩
  · subst r; exact ⟨448, by decide, by decide, by decide⟩
  · subst r; exact ⟨913, by decide, by decide, by decide⟩
  · subst r; exact ⟨599, by decide, by decide, by decide⟩
  · subst r; exact ⟨976, by decide, by decide, by decide⟩
  · subst r; exact ⟨508, by decide, by decide, by decide⟩
  · subst r; exact ⟨825, by decide, by decide, by decide⟩
  · subst r; exact ⟨355, by decide, by decide, by decide⟩
  · subst r; exact ⟨674, by decide, by decide, by decide⟩
  · subst r; exact ⟨202, by decide, by decide, by decide⟩
  · subst r; exact ⟨523, by decide, by decide, by decide⟩
  · subst r; exact ⟨49, by decide, by decide, by decide⟩

theorem slice_41 (r : Nat) (lo : 2050 ≤ r) (hi : r ≤ 2099) : covered r := by
  have h : r = 2050 ∨ r = 2051 ∨ r = 2052 ∨ r = 2053 ∨ r = 2054 ∨ r = 2055 ∨ r = 2056 ∨ r = 2057 ∨ r = 2058 ∨ r = 2059 ∨ r = 2060 ∨ r = 2061 ∨ r = 2062 ∨ r = 2063 ∨ r = 2064 ∨ r = 2065 ∨ r = 2066 ∨ r = 2067 ∨ r = 2068 ∨ r = 2069 ∨ r = 2070 ∨ r = 2071 ∨ r = 2072 ∨ r = 2073 ∨ r = 2074 ∨ r = 2075 ∨ r = 2076 ∨ r = 2077 ∨ r = 2078 ∨ r = 2079 ∨ r = 2080 ∨ r = 2081 ∨ r = 2082 ∨ r = 2083 ∨ r = 2084 ∨ r = 2085 ∨ r = 2086 ∨ r = 2087 ∨ r = 2088 ∨ r = 2089 ∨ r = 2090 ∨ r = 2091 ∨ r = 2092 ∨ r = 2093 ∨ r = 2094 ∨ r = 2095 ∨ r = 2096 ∨ r = 2097 ∨ r = 2098 ∨ r = 2099 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨372, by decide, by decide, by decide⟩
  · subst r; exact ⟨104, by decide, by decide, by decide⟩
  · subst r; exact ⟨221, by decide, by decide, by decide⟩
  · subst r; exact ⟨257, by decide, by decide, by decide⟩
  · subst r; exact ⟨70, by decide, by decide, by decide⟩
  · subst r; exact ⟨410, by decide, by decide, by decide⟩
  · subst r; exact ⟨81, by decide, by decide, by decide⟩
  · subst r; exact ⟨563, by decide, by decide, by decide⟩
  · subst r; exact ⟨232, by decide, by decide, by decide⟩
  · subst r; exact ⟨716, by decide, by decide, by decide⟩
  · subst r; exact ⟨383, by decide, by decide, by decide⟩
  · subst r; exact ⟨869, by decide, by decide, by decide⟩
  · subst r; exact ⟨534, by decide, by decide, by decide⟩
  · subst r; exact ⟨1022, by decide, by decide, by decide⟩
  · subst r; exact ⟨552, by decide, by decide, by decide⟩
  · subst r; exact ⟨890, by decide, by decide, by decide⟩
  · subst r; exact ⟨399, by decide, by decide, by decide⟩
  · subst r; exact ⟨739, by decide, by decide, by decide⟩
  · subst r; exact ⟨246, by decide, by decide, by decide⟩
  · subst r; exact ⟨588, by decide, by decide, by decide⟩
  · subst r; exact ⟨93, by decide, by decide, by decide⟩
  · subst r; exact ⟨437, by decide, by decide, by decide⟩
  · subst r; exact ⟨60, by decide, by decide, by decide⟩
  · subst r; exact ⟨286, by decide, by decide, by decide⟩
  · subst r; exact ⟨213, by decide, by decide, by decide⟩
  · subst r; exact ⟨135, by decide, by decide, by decide⟩
  · subst r; exact ⟨366, by decide, by decide, by decide⟩
  · subst r; exact ⟨16, by decide, by decide, by decide⟩
  · subst r; exact ⟨519, by decide, by decide, by decide⟩
  · subst r; exact ⟨167, by decide, by decide, by decide⟩
  · subst r; exact ⟨672, by decide, by decide, by decide⟩
  · subst r; exact ⟨318, by decide, by decide, by decide⟩
  · subst r; exact ⟨825, by decide, by decide, by decide⟩
  · subst r; exact ⟨469, by decide, by decide, by decide⟩
  · subst r; exact ⟨978, by decide, by decide, by decide⟩
  · subst r; exact ⟨596, by decide, by decide, by decide⟩
  · subst r; exact ⟨955, by decide, by decide, by decide⟩
  · subst r; exact ⟨443, by decide, by decide, by decide⟩
  · subst r; exact ⟨804, by decide, by decide, by decide⟩
  · subst r; exact ⟨290, by decide, by decide, by decide⟩
  · subst r; exact ⟨653, by decide, by decide, by decide⟩
  · subst r; exact ⟨137, by decide, by decide, by decide⟩
  · subst r; exact ⟨502, by decide, by decide, by decide⟩
  · subst r; exact ⟨16, by decide, by decide, by decide⟩
  · subst r; exact ⟨351, by decide, by decide, by decide⟩
  · subst r; exact ⟨169, by decide, by decide, by decide⟩
  · subst r; exact ⟨200, by decide, by decide, by decide⟩
  · subst r; exact ⟨322, by decide, by decide, by decide⟩
  · subst r; exact ⟨49, by decide, by decide, by decide⟩
  · subst r; exact ⟨475, by decide, by decide, by decide⟩

theorem slice_42 (r : Nat) (lo : 2100 ≤ r) (hi : r ≤ 2149) : covered r := by
  have h : r = 2100 ∨ r = 2101 ∨ r = 2102 ∨ r = 2103 ∨ r = 2104 ∨ r = 2105 ∨ r = 2106 ∨ r = 2107 ∨ r = 2108 ∨ r = 2109 ∨ r = 2110 ∨ r = 2111 ∨ r = 2112 ∨ r = 2113 ∨ r = 2114 ∨ r = 2115 ∨ r = 2116 ∨ r = 2117 ∨ r = 2118 ∨ r = 2119 ∨ r = 2120 ∨ r = 2121 ∨ r = 2122 ∨ r = 2123 ∨ r = 2124 ∨ r = 2125 ∨ r = 2126 ∨ r = 2127 ∨ r = 2128 ∨ r = 2129 ∨ r = 2130 ∨ r = 2131 ∨ r = 2132 ∨ r = 2133 ∨ r = 2134 ∨ r = 2135 ∨ r = 2136 ∨ r = 2137 ∨ r = 2138 ∨ r = 2139 ∨ r = 2140 ∨ r = 2141 ∨ r = 2142 ∨ r = 2143 ∨ r = 2144 ∨ r = 2145 ∨ r = 2146 ∨ r = 2147 ∨ r = 2148 ∨ r = 2149 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨102, by decide, by decide, by decide⟩
  · subst r; exact ⟨628, by decide, by decide, by decide⟩
  · subst r; exact ⟨253, by decide, by decide, by decide⟩
  · subst r; exact ⟨781, by decide, by decide, by decide⟩
  · subst r; exact ⟨404, by decide, by decide, by decide⟩
  · subst r; exact ⟨934, by decide, by decide, by decide⟩
  · subst r; exact ⟨555, by decide, by decide, by decide⟩
  · subst r; exact ⟨1020, by decide, by decide, by decide⟩
  · subst r; exact ⟨487, by decide, by decide, by decide⟩
  · subst r; exact ⟨869, by decide, by decide, by decide⟩
  · subst r; exact ⟨334, by decide, by decide, by decide⟩
  · subst r; exact ⟨718, by decide, by decide, by decide⟩
  · subst r; exact ⟨181, by decide, by decide, by decide⟩
  · subst r; exact ⟨567, by decide, by decide, by decide⟩
  · subst r; exact ⟨28, by decide, by decide, by decide⟩
  · subst r; exact ⟨416, by decide, by decide, by decide⟩
  · subst r; exact ⟨125, by decide, by decide, by decide⟩
  · subst r; exact ⟨265, by decide, by decide, by decide⟩
  · subst r; exact ⟨278, by decide, by decide, by decide⟩
  · subst r; exact ⟨114, by decide, by decide, by decide⟩
  · subst r; exact ⟨431, by decide, by decide, by decide⟩
  · subst r; exact ⟨37, by decide, by decide, by decide⟩
  · subst r; exact ⟨584, by decide, by decide, by decide⟩
  · subst r; exact ⟨188, by decide, by decide, by decide⟩
  · subst r; exact ⟨737, by decide, by decide, by decide⟩
  · subst r; exact ⟨339, by decide, by decide, by decide⟩
  · subst r; exact ⟨890, by decide, by decide, by decide⟩
  · subst r; exact ⟨490, by decide, by decide, by decide⟩
  · subst r; exact ⟨1043, by decide, by decide, by decide⟩
  · subst r; exact ⟨531, by decide, by decide, by decide⟩
  · subst r; exact ⟨934, by decide, by decide, by decide⟩
  · subst r; exact ⟨378, by decide, by decide, by decide⟩
  · subst r; exact ⟨783, by decide, by decide, by decide⟩
  · subst r; exact ⟨225, by decide, by decide, by decide⟩
  · subst r; exact ⟨632, by decide, by decide, by decide⟩
  · subst r; exact ⟨72, by decide, by decide, by decide⟩
  · subst r; exact ⟨481, by decide, by decide, by decide⟩
  · subst r; exact ⟨81, by decide, by decide, by decide⟩
  · subst r; exact ⟨330, by decide, by decide, by decide⟩
  · subst r; exact ⟨234, by decide, by decide, by decide⟩
  · subst r; exact ⟨179, by decide, by decide, by decide⟩
  · subst r; exact ⟨387, by decide, by decide, by decide⟩
  · subst r; exact ⟨28, by decide, by decide, by decide⟩
  · subst r; exact ⟨540, by decide, by decide, by decide⟩
  · subst r; exact ⟨123, by decide, by decide, by decide⟩
  · subst r; exact ⟨693, by decide, by decide, by decide⟩
  · subst r; exact ⟨274, by decide, by decide, by decide⟩
  · subst r; exact ⟨846, by decide, by decide, by decide⟩
  · subst r; exact ⟨425, by decide, by decide, by decide⟩
  · subst r; exact ⟨999, by decide, by decide, by decide⟩

theorem slice_43 (r : Nat) (lo : 2150 ≤ r) (hi : r ≤ 2199) : covered r := by
  have h : r = 2150 ∨ r = 2151 ∨ r = 2152 ∨ r = 2153 ∨ r = 2154 ∨ r = 2155 ∨ r = 2156 ∨ r = 2157 ∨ r = 2158 ∨ r = 2159 ∨ r = 2160 ∨ r = 2161 ∨ r = 2162 ∨ r = 2163 ∨ r = 2164 ∨ r = 2165 ∨ r = 2166 ∨ r = 2167 ∨ r = 2168 ∨ r = 2169 ∨ r = 2170 ∨ r = 2171 ∨ r = 2172 ∨ r = 2173 ∨ r = 2174 ∨ r = 2175 ∨ r = 2176 ∨ r = 2177 ∨ r = 2178 ∨ r = 2179 ∨ r = 2180 ∨ r = 2181 ∨ r = 2182 ∨ r = 2183 ∨ r = 2184 ∨ r = 2185 ∨ r = 2186 ∨ r = 2187 ∨ r = 2188 ∨ r = 2189 ∨ r = 2190 ∨ r = 2191 ∨ r = 2192 ∨ r = 2193 ∨ r = 2194 ∨ r = 2195 ∨ r = 2196 ∨ r = 2197 ∨ r = 2198 ∨ r = 2199 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨575, by decide, by decide, by decide⟩
  · subst r; exact ⟨999, by decide, by decide, by decide⟩
  · subst r; exact ⟨422, by decide, by decide, by decide⟩
  · subst r; exact ⟨848, by decide, by decide, by decide⟩
  · subst r; exact ⟨269, by decide, by decide, by decide⟩
  · subst r; exact ⟨697, by decide, by decide, by decide⟩
  · subst r; exact ⟨116, by decide, by decide, by decide⟩
  · subst r; exact ⟨546, by decide, by decide, by decide⟩
  · subst r; exact ⟨37, by decide, by decide, by decide⟩
  · subst r; exact ⟨395, by decide, by decide, by decide⟩
  · subst r; exact ⟨190, by decide, by decide, by decide⟩
  · subst r; exact ⟨244, by decide, by decide, by decide⟩
  · subst r; exact ⟨343, by decide, by decide, by decide⟩
  · subst r; exact ⟨93, by decide, by decide, by decide⟩
  · subst r; exact ⟨496, by decide, by decide, by decide⟩
  · subst r; exact ⟨58, by decide, by decide, by decide⟩
  · subst r; exact ⟨649, by decide, by decide, by decide⟩
  · subst r; exact ⟨209, by decide, by decide, by decide⟩
  · subst r; exact ⟨802, by decide, by decide, by decide⟩
  · subst r; exact ⟨360, by decide, by decide, by decide⟩
  · subst r; exact ⟨955, by decide, by decide, by decide⟩
  · subst r; exact ⟨511, by decide, by decide, by decide⟩
  · subst r; exact ⟨1064, by decide, by decide, by decide⟩
  · subst r; exact ⟨466, by decide, by decide, by decide⟩
  · subst r; exact ⟨913, by decide, by decide, by decide⟩
  · subst r; exact ⟨313, by decide, by decide, by decide⟩
  · subst r; exact ⟨762, by decide, by decide, by decide⟩
  · subst r; exact ⟨160, by decide, by decide, by decide⟩
  · subst r; exact ⟨611, by decide, by decide, by decide⟩
  · subst r; exact ⟨7, by decide, by decide, by decide⟩
  · subst r; exact ⟨460, by decide, by decide, by decide⟩
  · subst r; exact ⟨146, by decide, by decide, by decide⟩
  · subst r; exact ⟨309, by decide, by decide, by decide⟩
  · subst r; exact ⟨299, by decide, by decide, by decide⟩
  · subst r; exact ⟨158, by decide, by decide, by decide⟩
  · subst r; exact ⟨452, by decide, by decide, by decide⟩
  · subst r; exact ⟨7, by decide, by decide, by decide⟩
  · subst r; exact ⟨605, by decide, by decide, by decide⟩
  · subst r; exact ⟨144, by decide, by decide, by decide⟩
  · subst r; exact ⟨758, by decide, by decide, by decide⟩
  · subst r; exact ⟨295, by decide, by decide, by decide⟩
  · subst r; exact ⟨911, by decide, by decide, by decide⟩
  · subst r; exact ⟨446, by decide, by decide, by decide⟩
  · subst r; exact ⟨1064, by decide, by decide, by decide⟩
  · subst r; exact ⟨510, by decide, by decide, by decide⟩
  · subst r; exact ⟨978, by decide, by decide, by decide⟩
  · subst r; exact ⟨357, by decide, by decide, by decide⟩
  · subst r; exact ⟨827, by decide, by decide, by decide⟩
  · subst r; exact ⟨204, by decide, by decide, by decide⟩
  · subst r; exact ⟨676, by decide, by decide, by decide⟩

theorem slice_44 (r : Nat) (lo : 2200 ≤ r) (hi : r ≤ 2249) : covered r := by
  have h : r = 2200 ∨ r = 2201 ∨ r = 2202 ∨ r = 2203 ∨ r = 2204 ∨ r = 2205 ∨ r = 2206 ∨ r = 2207 ∨ r = 2208 ∨ r = 2209 ∨ r = 2210 ∨ r = 2211 ∨ r = 2212 ∨ r = 2213 ∨ r = 2214 ∨ r = 2215 ∨ r = 2216 ∨ r = 2217 ∨ r = 2218 ∨ r = 2219 ∨ r = 2220 ∨ r = 2221 ∨ r = 2222 ∨ r = 2223 ∨ r = 2224 ∨ r = 2225 ∨ r = 2226 ∨ r = 2227 ∨ r = 2228 ∨ r = 2229 ∨ r = 2230 ∨ r = 2231 ∨ r = 2232 ∨ r = 2233 ∨ r = 2234 ∨ r = 2235 ∨ r = 2236 ∨ r = 2237 ∨ r = 2238 ∨ r = 2239 ∨ r = 2240 ∨ r = 2241 ∨ r = 2242 ∨ r = 2243 ∨ r = 2244 ∨ r = 2245 ∨ r = 2246 ∨ r = 2247 ∨ r = 2248 ∨ r = 2249 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨51, by decide, by decide, by decide⟩
  · subst r; exact ⟨525, by decide, by decide, by decide⟩
  · subst r; exact ⟨102, by decide, by decide, by decide⟩
  · subst r; exact ⟨374, by decide, by decide, by decide⟩
  · subst r; exact ⟨255, by decide, by decide, by decide⟩
  · subst r; exact ⟨223, by decide, by decide, by decide⟩
  · subst r; exact ⟨408, by decide, by decide, by decide⟩
  · subst r; exact ⟨72, by decide, by decide, by decide⟩
  · subst r; exact ⟨561, by decide, by decide, by decide⟩
  · subst r; exact ⟨79, by decide, by decide, by decide⟩
  · subst r; exact ⟨714, by decide, by decide, by decide⟩
  · subst r; exact ⟨230, by decide, by decide, by decide⟩
  · subst r; exact ⟨867, by decide, by decide, by decide⟩
  · subst r; exact ⟨381, by decide, by decide, by decide⟩
  · subst r; exact ⟨1020, by decide, by decide, by decide⟩
  · subst r; exact ⟨532, by decide, by decide, by decide⟩
  · subst r; exact ⟨1043, by decide, by decide, by decide⟩
  · subst r; exact ⟨401, by decide, by decide, by decide⟩
  · subst r; exact ⟨892, by decide, by decide, by decide⟩
  · subst r; exact ⟨248, by decide, by decide, by decide⟩
  · subst r; exact ⟨741, by decide, by decide, by decide⟩
  · subst r; exact ⟨95, by decide, by decide, by decide⟩
  · subst r; exact ⟨590, by decide, by decide, by decide⟩
  · subst r; exact ⟨58, by decide, by decide, by decide⟩
  · subst r; exact ⟨439, by decide, by decide, by decide⟩
  · subst r; exact ⟨211, by decide, by decide, by decide⟩
  · subst r; exact ⟨288, by decide, by decide, by decide⟩
  · subst r; exact ⟨364, by decide, by decide, by decide⟩
  · subst r; exact ⟨137, by decide, by decide, by decide⟩
  · subst r; exact ⟨517, by decide, by decide, by decide⟩
  · subst r; exact ⟨14, by decide, by decide, by decide⟩
  · subst r; exact ⟨670, by decide, by decide, by decide⟩
  · subst r; exact ⟨165, by decide, by decide, by decide⟩
  · subst r; exact ⟨823, by decide, by decide, by decide⟩
  · subst r; exact ⟨316, by decide, by decide, by decide⟩
  · subst r; exact ⟨976, by decide, by decide, by decide⟩
  · subst r; exact ⟨467, by decide, by decide, by decide⟩
  · subst r; exact ⟨1064, by decide, by decide, by decide⟩
  · subst r; exact ⟨445, by decide, by decide, by decide⟩
  · subst r; exact ⟨957, by decide, by decide, by decide⟩
  · subst r; exact ⟨292, by decide, by decide, by decide⟩
  · subst r; exact ⟨806, by decide, by decide, by decide⟩
  · subst r; exact ⟨139, by decide, by decide, by decide⟩
  · subst r; exact ⟨655, by decide, by decide, by decide⟩
  · subst r; exact ⟨14, by decide, by decide, by decide⟩
  · subst r; exact ⟨504, by decide, by decide, by decide⟩
  · subst r; exact ⟨167, by decide, by decide, by decide⟩
  · subst r; exact ⟨353, by decide, by decide, by decide⟩
  · subst r; exact ⟨320, by decide, by decide, by decide⟩
  · subst r; exact ⟨202, by decide, by decide, by decide⟩

theorem slice_45 (r : Nat) (lo : 2250 ≤ r) (hi : r ≤ 2299) : covered r := by
  have h : r = 2250 ∨ r = 2251 ∨ r = 2252 ∨ r = 2253 ∨ r = 2254 ∨ r = 2255 ∨ r = 2256 ∨ r = 2257 ∨ r = 2258 ∨ r = 2259 ∨ r = 2260 ∨ r = 2261 ∨ r = 2262 ∨ r = 2263 ∨ r = 2264 ∨ r = 2265 ∨ r = 2266 ∨ r = 2267 ∨ r = 2268 ∨ r = 2269 ∨ r = 2270 ∨ r = 2271 ∨ r = 2272 ∨ r = 2273 ∨ r = 2274 ∨ r = 2275 ∨ r = 2276 ∨ r = 2277 ∨ r = 2278 ∨ r = 2279 ∨ r = 2280 ∨ r = 2281 ∨ r = 2282 ∨ r = 2283 ∨ r = 2284 ∨ r = 2285 ∨ r = 2286 ∨ r = 2287 ∨ r = 2288 ∨ r = 2289 ∨ r = 2290 ∨ r = 2291 ∨ r = 2292 ∨ r = 2293 ∨ r = 2294 ∨ r = 2295 ∨ r = 2296 ∨ r = 2297 ∨ r = 2298 ∨ r = 2299 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨473, by decide, by decide, by decide⟩
  · subst r; exact ⟨51, by decide, by decide, by decide⟩
  · subst r; exact ⟨626, by decide, by decide, by decide⟩
  · subst r; exact ⟨100, by decide, by decide, by decide⟩
  · subst r; exact ⟨779, by decide, by decide, by decide⟩
  · subst r; exact ⟨251, by decide, by decide, by decide⟩
  · subst r; exact ⟨932, by decide, by decide, by decide⟩
  · subst r; exact ⟨402, by decide, by decide, by decide⟩
  · subst r; exact ⟨1043, by decide, by decide, by decide⟩
  · subst r; exact ⟨489, by decide, by decide, by decide⟩
  · subst r; exact ⟨1022, by decide, by decide, by decide⟩
  · subst r; exact ⟨336, by decide, by decide, by decide⟩
  · subst r; exact ⟨871, by decide, by decide, by decide⟩
  · subst r; exact ⟨183, by decide, by decide, by decide⟩
  · subst r; exact ⟨720, by decide, by decide, by decide⟩
  · subst r; exact ⟨30, by decide, by decide, by decide⟩
  · subst r; exact ⟨569, by decide, by decide, by decide⟩
  · subst r; exact ⟨123, by decide, by decide, by decide⟩
  · subst r; exact ⟨418, by decide, by decide, by decide⟩
  · subst r; exact ⟨276, by decide, by decide, by decide⟩
  · subst r; exact ⟨267, by decide, by decide, by decide⟩
  · subst r; exact ⟨429, by decide, by decide, by decide⟩
  · subst r; exact ⟨116, by decide, by decide, by decide⟩
  · subst r; exact ⟨582, by decide, by decide, by decide⟩
  · subst r; exact ⟨35, by decide, by decide, by decide⟩
  · subst r; exact ⟨735, by decide, by decide, by decide⟩
  · subst r; exact ⟨186, by decide, by decide, by decide⟩
  · subst r; exact ⟨888, by decide, by decide, by decide⟩
  · subst r; exact ⟨337, by decide, by decide, by decide⟩
  · subst r; exact ⟨1022, by decide, by decide, by decide⟩
  · subst r; exact ⟨488, by decide, by decide, by decide⟩
  · subst r; exact ⟨1020, by decide, by decide, by decide⟩
  · subst r; exact ⟨380, by decide, by decide, by decide⟩
  · subst r; exact ⟨936, by decide, by decide, by decide⟩
  · subst r; exact ⟨227, by decide, by decide, by decide⟩
  · subst r; exact ⟨785, by decide, by decide, by decide⟩
  · subst r; exact ⟨74, by decide, by decide, by decide⟩
  · subst r; exact ⟨634, by decide, by decide, by decide⟩
  · subst r; exact ⟨79, by decide, by decide, by decide⟩
  · subst r; exact ⟨483, by decide, by decide, by decide⟩
  · subst r; exact ⟨232, by decide, by decide, by decide⟩
  · subst r; exact ⟨332, by decide, by decide, by decide⟩
  · subst r; exact ⟨385, by decide, by decide, by decide⟩
  · subst r; exact ⟨181, by decide, by decide, by decide⟩
  · subst r; exact ⟨538, by decide, by decide, by decide⟩
  · subst r; exact ⟨30, by decide, by decide, by decide⟩
  · subst r; exact ⟨691, by decide, by decide, by decide⟩
  · subst r; exact ⟨121, by decide, by decide, by decide⟩
  · subst r; exact ⟨844, by decide, by decide, by decide⟩
  · subst r; exact ⟨272, by decide, by decide, by decide⟩

theorem slice_46 (r : Nat) (lo : 2300 ≤ r) (hi : r ≤ 2349) : covered r := by
  have h : r = 2300 ∨ r = 2301 ∨ r = 2302 ∨ r = 2303 ∨ r = 2304 ∨ r = 2305 ∨ r = 2306 ∨ r = 2307 ∨ r = 2308 ∨ r = 2309 ∨ r = 2310 ∨ r = 2311 ∨ r = 2312 ∨ r = 2313 ∨ r = 2314 ∨ r = 2315 ∨ r = 2316 ∨ r = 2317 ∨ r = 2318 ∨ r = 2319 ∨ r = 2320 ∨ r = 2321 ∨ r = 2322 ∨ r = 2323 ∨ r = 2324 ∨ r = 2325 ∨ r = 2326 ∨ r = 2327 ∨ r = 2328 ∨ r = 2329 ∨ r = 2330 ∨ r = 2331 ∨ r = 2332 ∨ r = 2333 ∨ r = 2334 ∨ r = 2335 ∨ r = 2336 ∨ r = 2337 ∨ r = 2338 ∨ r = 2339 ∨ r = 2340 ∨ r = 2341 ∨ r = 2342 ∨ r = 2343 ∨ r = 2344 ∨ r = 2345 ∨ r = 2346 ∨ r = 2347 ∨ r = 2348 ∨ r = 2349 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨997, by decide, by decide, by decide⟩
  · subst r; exact ⟨423, by decide, by decide, by decide⟩
  · subst r; exact ⟨999, by decide, by decide, by decide⟩
  · subst r; exact ⟨424, by decide, by decide, by decide⟩
  · subst r; exact ⟨997, by decide, by decide, by decide⟩
  · subst r; exact ⟨271, by decide, by decide, by decide⟩
  · subst r; exact ⟨850, by decide, by decide, by decide⟩
  · subst r; exact ⟨118, by decide, by decide, by decide⟩
  · subst r; exact ⟨699, by decide, by decide, by decide⟩
  · subst r; exact ⟨35, by decide, by decide, by decide⟩
  · subst r; exact ⟨548, by decide, by decide, by decide⟩
  · subst r; exact ⟨188, by decide, by decide, by decide⟩
  · subst r; exact ⟨397, by decide, by decide, by decide⟩
  · subst r; exact ⟨341, by decide, by decide, by decide⟩
  · subst r; exact ⟨246, by decide, by decide, by decide⟩
  · subst r; exact ⟨494, by decide, by decide, by decide⟩
  · subst r; exact ⟨95, by decide, by decide, by decide⟩
  · subst r; exact ⟨647, by decide, by decide, by decide⟩
  · subst r; exact ⟨56, by decide, by decide, by decide⟩
  · subst r; exact ⟨800, by decide, by decide, by decide⟩
  · subst r; exact ⟨207, by decide, by decide, by decide⟩
  · subst r; exact ⟨953, by decide, by decide, by decide⟩
  · subst r; exact ⟨358, by decide, by decide, by decide⟩
  · subst r; exact ⟨978, by decide, by decide, by decide⟩
  · subst r; exact ⟨468, by decide, by decide, by decide⟩
  · subst r; exact ⟨976, by decide, by decide, by decide⟩
  · subst r; exact ⟨315, by decide, by decide, by decide⟩
  · subst r; exact ⟨915, by decide, by decide, by decide⟩
  · subst r; exact ⟨162, by decide, by decide, by decide⟩
  · subst r; exact ⟨764, by decide, by decide, by decide⟩
  · subst r; exact ⟨9, by decide, by decide, by decide⟩
  · subst r; exact ⟨613, by decide, by decide, by decide⟩
  · subst r; exact ⟨144, by decide, by decide, by decide⟩
  · subst r; exact ⟨462, by decide, by decide, by decide⟩
  · subst r; exact ⟨297, by decide, by decide, by decide⟩
  · subst r; exact ⟨311, by decide, by decide, by decide⟩
  · subst r; exact ⟨450, by decide, by decide, by decide⟩
  · subst r; exact ⟨160, by decide, by decide, by decide⟩
  · subst r; exact ⟨603, by decide, by decide, by decide⟩
  · subst r; exact ⟨9, by decide, by decide, by decide⟩
  · subst r; exact ⟨756, by decide, by decide, by decide⟩
  · subst r; exact ⟨142, by decide, by decide, by decide⟩
  · subst r; exact ⟨909, by decide, by decide, by decide⟩
  · subst r; exact ⟨293, by decide, by decide, by decide⟩
  · subst r; exact ⟨957, by decide, by decide, by decide⟩
  · subst r; exact ⟨444, by decide, by decide, by decide⟩
  · subst r; exact ⟨955, by decide, by decide, by decide⟩
  · subst r; exact ⟨359, by decide, by decide, by decide⟩
  · subst r; exact ⟨953, by decide, by decide, by decide⟩
  · subst r; exact ⟨206, by decide, by decide, by decide⟩

theorem slice_47 (r : Nat) (lo : 2350 ≤ r) (hi : r ≤ 2399) : covered r := by
  have h : r = 2350 ∨ r = 2351 ∨ r = 2352 ∨ r = 2353 ∨ r = 2354 ∨ r = 2355 ∨ r = 2356 ∨ r = 2357 ∨ r = 2358 ∨ r = 2359 ∨ r = 2360 ∨ r = 2361 ∨ r = 2362 ∨ r = 2363 ∨ r = 2364 ∨ r = 2365 ∨ r = 2366 ∨ r = 2367 ∨ r = 2368 ∨ r = 2369 ∨ r = 2370 ∨ r = 2371 ∨ r = 2372 ∨ r = 2373 ∨ r = 2374 ∨ r = 2375 ∨ r = 2376 ∨ r = 2377 ∨ r = 2378 ∨ r = 2379 ∨ r = 2380 ∨ r = 2381 ∨ r = 2382 ∨ r = 2383 ∨ r = 2384 ∨ r = 2385 ∨ r = 2386 ∨ r = 2387 ∨ r = 2388 ∨ r = 2389 ∨ r = 2390 ∨ r = 2391 ∨ r = 2392 ∨ r = 2393 ∨ r = 2394 ∨ r = 2395 ∨ r = 2396 ∨ r = 2397 ∨ r = 2398 ∨ r = 2399 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨829, by decide, by decide, by decide⟩
  · subst r; exact ⟨53, by decide, by decide, by decide⟩
  · subst r; exact ⟨678, by decide, by decide, by decide⟩
  · subst r; exact ⟨100, by decide, by decide, by decide⟩
  · subst r; exact ⟨527, by decide, by decide, by decide⟩
  · subst r; exact ⟨253, by decide, by decide, by decide⟩
  · subst r; exact ⟨376, by decide, by decide, by decide⟩
  · subst r; exact ⟨406, by decide, by decide, by decide⟩
  · subst r; exact ⟨225, by decide, by decide, by decide⟩
  · subst r; exact ⟨559, by decide, by decide, by decide⟩
  · subst r; exact ⟨74, by decide, by decide, by decide⟩
  · subst r; exact ⟨712, by decide, by decide, by decide⟩
  · subst r; exact ⟨77, by decide, by decide, by decide⟩
  · subst r; exact ⟨865, by decide, by decide, by decide⟩
  · subst r; exact ⟨228, by decide, by decide, by decide⟩
  · subst r; exact ⟨936, by decide, by decide, by decide⟩
  · subst r; exact ⟨379, by decide, by decide, by decide⟩
  · subst r; exact ⟨934, by decide, by decide, by decide⟩
  · subst r; exact ⟨403, by decide, by decide, by decide⟩
  · subst r; exact ⟨932, by decide, by decide, by decide⟩
  · subst r; exact ⟨250, by decide, by decide, by decide⟩
  · subst r; exact ⟨894, by decide, by decide, by decide⟩
  · subst r; exact ⟨97, by decide, by decide, by decide⟩
  · subst r; exact ⟨743, by decide, by decide, by decide⟩
  · subst r; exact ⟨56, by decide, by decide, by decide⟩
  · subst r; exact ⟨592, by decide, by decide, by decide⟩
  · subst r; exact ⟨209, by decide, by decide, by decide⟩
  · subst r; exact ⟨441, by decide, by decide, by decide⟩
  · subst r; exact ⟨362, by decide, by decide, by decide⟩
  · subst r; exact ⟨290, by decide, by decide, by decide⟩
  · subst r; exact ⟨515, by decide, by decide, by decide⟩
  · subst r; exact ⟨139, by decide, by decide, by decide⟩
  · subst r; exact ⟨668, by decide, by decide, by decide⟩
  · subst r; exact ⟨12, by decide, by decide, by decide⟩
  · subst r; exact ⟨821, by decide, by decide, by decide⟩
  · subst r; exact ⟨163, by decide, by decide, by decide⟩
  · subst r; exact ⟨915, by decide, by decide, by decide⟩
  · subst r; exact ⟨314, by decide, by decide, by decide⟩
  · subst r; exact ⟨913, by decide, by decide, by decide⟩
  · subst r; exact ⟨447, by decide, by decide, by decide⟩
  · subst r; exact ⟨911, by decide, by decide, by decide⟩
  · subst r; exact ⟨294, by decide, by decide, by decide⟩
  · subst r; exact ⟨909, by decide, by decide, by decide⟩
  · subst r; exact ⟨141, by decide, by decide, by decide⟩
  · subst r; exact ⟨808, by decide, by decide, by decide⟩
  · subst r; exact ⟨12, by decide, by decide, by decide⟩
  · subst r; exact ⟨657, by decide, by decide, by decide⟩
  · subst r; exact ⟨165, by decide, by decide, by decide⟩
  · subst r; exact ⟨506, by decide, by decide, by decide⟩
  · subst r; exact ⟨318, by decide, by decide, by decide⟩

theorem slice_48 (r : Nat) (lo : 2400 ≤ r) (hi : r ≤ 2449) : covered r := by
  have h : r = 2400 ∨ r = 2401 ∨ r = 2402 ∨ r = 2403 ∨ r = 2404 ∨ r = 2405 ∨ r = 2406 ∨ r = 2407 ∨ r = 2408 ∨ r = 2409 ∨ r = 2410 ∨ r = 2411 ∨ r = 2412 ∨ r = 2413 ∨ r = 2414 ∨ r = 2415 ∨ r = 2416 ∨ r = 2417 ∨ r = 2418 ∨ r = 2419 ∨ r = 2420 ∨ r = 2421 ∨ r = 2422 ∨ r = 2423 ∨ r = 2424 ∨ r = 2425 ∨ r = 2426 ∨ r = 2427 ∨ r = 2428 ∨ r = 2429 ∨ r = 2430 ∨ r = 2431 ∨ r = 2432 ∨ r = 2433 ∨ r = 2434 ∨ r = 2435 ∨ r = 2436 ∨ r = 2437 ∨ r = 2438 ∨ r = 2439 ∨ r = 2440 ∨ r = 2441 ∨ r = 2442 ∨ r = 2443 ∨ r = 2444 ∨ r = 2445 ∨ r = 2446 ∨ r = 2447 ∨ r = 2448 ∨ r = 2449 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨355, by decide, by decide, by decide⟩
  · subst r; exact ⟨471, by decide, by decide, by decide⟩
  · subst r; exact ⟨204, by decide, by decide, by decide⟩
  · subst r; exact ⟨624, by decide, by decide, by decide⟩
  · subst r; exact ⟨53, by decide, by decide, by decide⟩
  · subst r; exact ⟨777, by decide, by decide, by decide⟩
  · subst r; exact ⟨98, by decide, by decide, by decide⟩
  · subst r; exact ⟨894, by decide, by decide, by decide⟩
  · subst r; exact ⟨249, by decide, by decide, by decide⟩
  · subst r; exact ⟨892, by decide, by decide, by decide⟩
  · subst r; exact ⟨400, by decide, by decide, by decide⟩
  · subst r; exact ⟨890, by decide, by decide, by decide⟩
  · subst r; exact ⟨338, by decide, by decide, by decide⟩
  · subst r; exact ⟨888, by decide, by decide, by decide⟩
  · subst r; exact ⟨185, by decide, by decide, by decide⟩
  · subst r; exact ⟨873, by decide, by decide, by decide⟩
  · subst r; exact ⟨32, by decide, by decide, by decide⟩
  · subst r; exact ⟨722, by decide, by decide, by decide⟩
  · subst r; exact ⟨121, by decide, by decide, by decide⟩
  · subst r; exact ⟨571, by decide, by decide, by decide⟩
  · subst r; exact ⟨274, by decide, by decide, by decide⟩
  · subst r; exact ⟨420, by decide, by decide, by decide⟩
  · subst r; exact ⟨427, by decide, by decide, by decide⟩
  · subst r; exact ⟨269, by decide, by decide, by decide⟩
  · subst r; exact ⟨580, by decide, by decide, by decide⟩
  · subst r; exact ⟨118, by decide, by decide, by decide⟩
  · subst r; exact ⟨733, by decide, by decide, by decide⟩
  · subst r; exact ⟨33, by decide, by decide, by decide⟩
  · subst r; exact ⟨873, by decide, by decide, by decide⟩
  · subst r; exact ⟨184, by decide, by decide, by decide⟩
  · subst r; exact ⟨871, by decide, by decide, by decide⟩
  · subst r; exact ⟨335, by decide, by decide, by decide⟩
  · subst r; exact ⟨869, by decide, by decide, by decide⟩
  · subst r; exact ⟨382, by decide, by decide, by decide⟩
  · subst r; exact ⟨867, by decide, by decide, by decide⟩
  · subst r; exact ⟨229, by decide, by decide, by decide⟩
  · subst r; exact ⟨865, by decide, by decide, by decide⟩
  · subst r; exact ⟨76, by decide, by decide, by decide⟩
  · subst r; exact ⟨787, by decide, by decide, by decide⟩
  · subst r; exact ⟨77, by decide, by decide, by decide⟩
  · subst r; exact ⟨636, by decide, by decide, by decide⟩
  · subst r; exact ⟨230, by decide, by decide, by decide⟩
  · subst r; exact ⟨485, by decide, by decide, by decide⟩
  · subst r; exact ⟨383, by decide, by decide, by decide⟩
  · subst r; exact ⟨334, by decide, by decide, by decide⟩
  · subst r; exact ⟨536, by decide, by decide, by decide⟩
  · subst r; exact ⟨183, by decide, by decide, by decide⟩
  · subst r; exact ⟨689, by decide, by decide, by decide⟩
  · subst r; exact ⟨32, by decide, by decide, by decide⟩
  · subst r; exact ⟨842, by decide, by decide, by decide⟩

theorem slice_49 (r : Nat) (lo : 2450 ≤ r) (hi : r ≤ 2499) : covered r := by
  have h : r = 2450 ∨ r = 2451 ∨ r = 2452 ∨ r = 2453 ∨ r = 2454 ∨ r = 2455 ∨ r = 2456 ∨ r = 2457 ∨ r = 2458 ∨ r = 2459 ∨ r = 2460 ∨ r = 2461 ∨ r = 2462 ∨ r = 2463 ∨ r = 2464 ∨ r = 2465 ∨ r = 2466 ∨ r = 2467 ∨ r = 2468 ∨ r = 2469 ∨ r = 2470 ∨ r = 2471 ∨ r = 2472 ∨ r = 2473 ∨ r = 2474 ∨ r = 2475 ∨ r = 2476 ∨ r = 2477 ∨ r = 2478 ∨ r = 2479 ∨ r = 2480 ∨ r = 2481 ∨ r = 2482 ∨ r = 2483 ∨ r = 2484 ∨ r = 2485 ∨ r = 2486 ∨ r = 2487 ∨ r = 2488 ∨ r = 2489 ∨ r = 2490 ∨ r = 2491 ∨ r = 2492 ∨ r = 2493 ∨ r = 2494 ∨ r = 2495 ∨ r = 2496 ∨ r = 2497 ∨ r = 2498 ∨ r = 2499 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨119, by decide, by decide, by decide⟩
  · subst r; exact ⟨850, by decide, by decide, by decide⟩
  · subst r; exact ⟨270, by decide, by decide, by decide⟩
  · subst r; exact ⟨848, by decide, by decide, by decide⟩
  · subst r; exact ⟨421, by decide, by decide, by decide⟩
  · subst r; exact ⟨846, by decide, by decide, by decide⟩
  · subst r; exact ⟨273, by decide, by decide, by decide⟩
  · subst r; exact ⟨844, by decide, by decide, by decide⟩
  · subst r; exact ⟨120, by decide, by decide, by decide⟩
  · subst r; exact ⟨842, by decide, by decide, by decide⟩
  · subst r; exact ⟨33, by decide, by decide, by decide⟩
  · subst r; exact ⟨701, by decide, by decide, by decide⟩
  · subst r; exact ⟨186, by decide, by decide, by decide⟩
  · subst r; exact ⟨550, by decide, by decide, by decide⟩
  · subst r; exact ⟨339, by decide, by decide, by decide⟩
  · subst r; exact ⟨399, by decide, by decide, by decide⟩
  · subst r; exact ⟨492, by decide, by decide, by decide⟩
  · subst r; exact ⟨248, by decide, by decide, by decide⟩
  · subst r; exact ⟨645, by decide, by decide, by decide⟩
  · subst r; exact ⟨97, by decide, by decide, by decide⟩
  · subst r; exact ⟨798, by decide, by decide, by decide⟩
  · subst r; exact ⟨54, by decide, by decide, by decide⟩
  · subst r; exact ⟨829, by decide, by decide, by decide⟩
  · subst r; exact ⟨205, by decide, by decide, by decide⟩
  · subst r; exact ⟨827, by decide, by decide, by decide⟩
  · subst r; exact ⟨356, by decide, by decide, by decide⟩
  · subst r; exact ⟨825, by decide, by decide, by decide⟩
  · subst r; exact ⟨317, by decide, by decide, by decide⟩
  · subst r; exact ⟨823, by decide, by decide, by decide⟩
  · subst r; exact ⟨164, by decide, by decide, by decide⟩
  · subst r; exact ⟨821, by decide, by decide, by decide⟩
  · subst r; exact ⟨11, by decide, by decide, by decide⟩
  · subst r; exact ⟨766, by decide, by decide, by decide⟩
  · subst r; exact ⟨142, by decide, by decide, by decide⟩
  · subst r; exact ⟨615, by decide, by decide, by decide⟩
  · subst r; exact ⟨295, by decide, by decide, by decide⟩
  · subst r; exact ⟨464, by decide, by decide, by decide⟩
  · subst r; exact ⟨448, by decide, by decide, by decide⟩
  · subst r; exact ⟨313, by decide, by decide, by decide⟩
  · subst r; exact ⟨601, by decide, by decide, by decide⟩
  · subst r; exact ⟨162, by decide, by decide, by decide⟩
  · subst r; exact ⟨754, by decide, by decide, by decide⟩
  · subst r; exact ⟨11, by decide, by decide, by decide⟩
  · subst r; exact ⟨808, by decide, by decide, by decide⟩
  · subst r; exact ⟨140, by decide, by decide, by decide⟩
  · subst r; exact ⟨806, by decide, by decide, by decide⟩
  · subst r; exact ⟨291, by decide, by decide, by decide⟩
  · subst r; exact ⟨804, by decide, by decide, by decide⟩
  · subst r; exact ⟨361, by decide, by decide, by decide⟩
  · subst r; exact ⟨802, by decide, by decide, by decide⟩

theorem slice_50 (r : Nat) (lo : 2500 ≤ r) (hi : r ≤ 2549) : covered r := by
  have h : r = 2500 ∨ r = 2501 ∨ r = 2502 ∨ r = 2503 ∨ r = 2504 ∨ r = 2505 ∨ r = 2506 ∨ r = 2507 ∨ r = 2508 ∨ r = 2509 ∨ r = 2510 ∨ r = 2511 ∨ r = 2512 ∨ r = 2513 ∨ r = 2514 ∨ r = 2515 ∨ r = 2516 ∨ r = 2517 ∨ r = 2518 ∨ r = 2519 ∨ r = 2520 ∨ r = 2521 ∨ r = 2522 ∨ r = 2523 ∨ r = 2524 ∨ r = 2525 ∨ r = 2526 ∨ r = 2527 ∨ r = 2528 ∨ r = 2529 ∨ r = 2530 ∨ r = 2531 ∨ r = 2532 ∨ r = 2533 ∨ r = 2534 ∨ r = 2535 ∨ r = 2536 ∨ r = 2537 ∨ r = 2538 ∨ r = 2539 ∨ r = 2540 ∨ r = 2541 ∨ r = 2542 ∨ r = 2543 ∨ r = 2544 ∨ r = 2545 ∨ r = 2546 ∨ r = 2547 ∨ r = 2548 ∨ r = 2549 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨208, by decide, by decide, by decide⟩
  · subst r; exact ⟨800, by decide, by decide, by decide⟩
  · subst r; exact ⟨55, by decide, by decide, by decide⟩
  · subst r; exact ⟨798, by decide, by decide, by decide⟩
  · subst r; exact ⟨98, by decide, by decide, by decide⟩
  · subst r; exact ⟨680, by decide, by decide, by decide⟩
  · subst r; exact ⟨251, by decide, by decide, by decide⟩
  · subst r; exact ⟨529, by decide, by decide, by decide⟩
  · subst r; exact ⟨404, by decide, by decide, by decide⟩
  · subst r; exact ⟨378, by decide, by decide, by decide⟩
  · subst r; exact ⟨557, by decide, by decide, by decide⟩
  · subst r; exact ⟨227, by decide, by decide, by decide⟩
  · subst r; exact ⟨710, by decide, by decide, by decide⟩
  · subst r; exact ⟨76, by decide, by decide, by decide⟩
  · subst r; exact ⟨787, by decide, by decide, by decide⟩
  · subst r; exact ⟨75, by decide, by decide, by decide⟩
  · subst r; exact ⟨785, by decide, by decide, by decide⟩
  · subst r; exact ⟨226, by decide, by decide, by decide⟩
  · subst r; exact ⟨783, by decide, by decide, by decide⟩
  · subst r; exact ⟨377, by decide, by decide, by decide⟩
  · subst r; exact ⟨781, by decide, by decide, by decide⟩
  · subst r; exact ⟨252, by decide, by decide, by decide⟩
  · subst r; exact ⟨779, by decide, by decide, by decide⟩
  · subst r; exact ⟨99, by decide, by decide, by decide⟩
  · subst r; exact ⟨777, by decide, by decide, by decide⟩
  · subst r; exact ⟨54, by decide, by decide, by decide⟩
  · subst r; exact ⟨745, by decide, by decide, by decide⟩
  · subst r; exact ⟨207, by decide, by decide, by decide⟩
  · subst r; exact ⟨594, by decide, by decide, by decide⟩
  · subst r; exact ⟨360, by decide, by decide, by decide⟩
  · subst r; exact ⟨443, by decide, by decide, by decide⟩
  · subst r; exact ⟨513, by decide, by decide, by decide⟩
  · subst r; exact ⟨292, by decide, by decide, by decide⟩
  · subst r; exact ⟨666, by decide, by decide, by decide⟩
  · subst r; exact ⟨141, by decide, by decide, by decide⟩
  · subst r; exact ⟨766, by decide, by decide, by decide⟩
  · subst r; exact ⟨10, by decide, by decide, by decide⟩
  · subst r; exact ⟨764, by decide, by decide, by decide⟩
  · subst r; exact ⟨161, by decide, by decide, by decide⟩
  · subst r; exact ⟨762, by decide, by decide, by decide⟩
  · subst r; exact ⟨312, by decide, by decide, by decide⟩
  · subst r; exact ⟨760, by decide, by decide, by decide⟩
  · subst r; exact ⟨296, by decide, by decide, by decide⟩
  · subst r; exact ⟨758, by decide, by decide, by decide⟩
  · subst r; exact ⟨143, by decide, by decide, by decide⟩
  · subst r; exact ⟨756, by decide, by decide, by decide⟩
  · subst r; exact ⟨10, by decide, by decide, by decide⟩
  · subst r; exact ⟨754, by decide, by decide, by decide⟩
  · subst r; exact ⟨163, by decide, by decide, by decide⟩
  · subst r; exact ⟨659, by decide, by decide, by decide⟩

theorem slice_51 (r : Nat) (lo : 2550 ≤ r) (hi : r ≤ 2599) : covered r := by
  have h : r = 2550 ∨ r = 2551 ∨ r = 2552 ∨ r = 2553 ∨ r = 2554 ∨ r = 2555 ∨ r = 2556 ∨ r = 2557 ∨ r = 2558 ∨ r = 2559 ∨ r = 2560 ∨ r = 2561 ∨ r = 2562 ∨ r = 2563 ∨ r = 2564 ∨ r = 2565 ∨ r = 2566 ∨ r = 2567 ∨ r = 2568 ∨ r = 2569 ∨ r = 2570 ∨ r = 2571 ∨ r = 2572 ∨ r = 2573 ∨ r = 2574 ∨ r = 2575 ∨ r = 2576 ∨ r = 2577 ∨ r = 2578 ∨ r = 2579 ∨ r = 2580 ∨ r = 2581 ∨ r = 2582 ∨ r = 2583 ∨ r = 2584 ∨ r = 2585 ∨ r = 2586 ∨ r = 2587 ∨ r = 2588 ∨ r = 2589 ∨ r = 2590 ∨ r = 2591 ∨ r = 2592 ∨ r = 2593 ∨ r = 2594 ∨ r = 2595 ∨ r = 2596 ∨ r = 2597 ∨ r = 2598 ∨ r = 2599 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨316, by decide, by decide, by decide⟩
  · subst r; exact ⟨508, by decide, by decide, by decide⟩
  · subst r; exact ⟨469, by decide, by decide, by decide⟩
  · subst r; exact ⟨357, by decide, by decide, by decide⟩
  · subst r; exact ⟨622, by decide, by decide, by decide⟩
  · subst r; exact ⟨206, by decide, by decide, by decide⟩
  · subst r; exact ⟨745, by decide, by decide, by decide⟩
  · subst r; exact ⟨55, by decide, by decide, by decide⟩
  · subst r; exact ⟨743, by decide, by decide, by decide⟩
  · subst r; exact ⟨96, by decide, by decide, by decide⟩
  · subst r; exact ⟨741, by decide, by decide, by decide⟩
  · subst r; exact ⟨247, by decide, by decide, by decide⟩
  · subst r; exact ⟨739, by decide, by decide, by decide⟩
  · subst r; exact ⟨340, by decide, by decide, by decide⟩
  · subst r; exact ⟨737, by decide, by decide, by decide⟩
  · subst r; exact ⟨187, by decide, by decide, by decide⟩
  · subst r; exact ⟨735, by decide, by decide, by decide⟩
  · subst r; exact ⟨34, by decide, by decide, by decide⟩
  · subst r; exact ⟨733, by decide, by decide, by decide⟩
  · subst r; exact ⟨119, by decide, by decide, by decide⟩
  · subst r; exact ⟨724, by decide, by decide, by decide⟩
  · subst r; exact ⟨272, by decide, by decide, by decide⟩
  · subst r; exact ⟨573, by decide, by decide, by decide⟩
  · subst r; exact ⟨425, by decide, by decide, by decide⟩
  · subst r; exact ⟨422, by decide, by decide, by decide⟩
  · subst r; exact ⟨578, by decide, by decide, by decide⟩
  · subst r; exact ⟨271, by decide, by decide, by decide⟩
  · subst r; exact ⟨724, by decide, by decide, by decide⟩
  · subst r; exact ⟨120, by decide, by decide, by decide⟩
  · subst r; exact ⟨722, by decide, by decide, by decide⟩
  · subst r; exact ⟨31, by decide, by decide, by decide⟩
  · subst r; exact ⟨720, by decide, by decide, by decide⟩
  · subst r; exact ⟨182, by decide, by decide, by decide⟩
  · subst r; exact ⟨718, by decide, by decide, by decide⟩
  · subst r; exact ⟨333, by decide, by decide, by decide⟩
  · subst r; exact ⟨716, by decide, by decide, by decide⟩
  · subst r; exact ⟨231, by decide, by decide, by decide⟩
  · subst r; exact ⟨714, by decide, by decide, by decide⟩
  · subst r; exact ⟨78, by decide, by decide, by decide⟩
  · subst r; exact ⟨712, by decide, by decide, by decide⟩
  · subst r; exact ⟨75, by decide, by decide, by decide⟩
  · subst r; exact ⟨710, by decide, by decide, by decide⟩
  · subst r; exact ⟨228, by decide, by decide, by decide⟩
  · subst r; exact ⟨638, by decide, by decide, by decide⟩
  · subst r; exact ⟨381, by decide, by decide, by decide⟩
  · subst r; exact ⟨487, by decide, by decide, by decide⟩
  · subst r; exact ⟨534, by decide, by decide, by decide⟩
  · subst r; exact ⟨336, by decide, by decide, by decide⟩
  · subst r; exact ⟨687, by decide, by decide, by decide⟩
  · subst r; exact ⟨185, by decide, by decide, by decide⟩

theorem slice_52 (r : Nat) (lo : 2600 ≤ r) (hi : r ≤ 2649) : covered r := by
  have h : r = 2600 ∨ r = 2601 ∨ r = 2602 ∨ r = 2603 ∨ r = 2604 ∨ r = 2605 ∨ r = 2606 ∨ r = 2607 ∨ r = 2608 ∨ r = 2609 ∨ r = 2610 ∨ r = 2611 ∨ r = 2612 ∨ r = 2613 ∨ r = 2614 ∨ r = 2615 ∨ r = 2616 ∨ r = 2617 ∨ r = 2618 ∨ r = 2619 ∨ r = 2620 ∨ r = 2621 ∨ r = 2622 ∨ r = 2623 ∨ r = 2624 ∨ r = 2625 ∨ r = 2626 ∨ r = 2627 ∨ r = 2628 ∨ r = 2629 ∨ r = 2630 ∨ r = 2631 ∨ r = 2632 ∨ r = 2633 ∨ r = 2634 ∨ r = 2635 ∨ r = 2636 ∨ r = 2637 ∨ r = 2638 ∨ r = 2639 ∨ r = 2640 ∨ r = 2641 ∨ r = 2642 ∨ r = 2643 ∨ r = 2644 ∨ r = 2645 ∨ r = 2646 ∨ r = 2647 ∨ r = 2648 ∨ r = 2649 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨701, by decide, by decide, by decide⟩
  · subst r; exact ⟨34, by decide, by decide, by decide⟩
  · subst r; exact ⟨699, by decide, by decide, by decide⟩
  · subst r; exact ⟨117, by decide, by decide, by decide⟩
  · subst r; exact ⟨697, by decide, by decide, by decide⟩
  · subst r; exact ⟨268, by decide, by decide, by decide⟩
  · subst r; exact ⟨695, by decide, by decide, by decide⟩
  · subst r; exact ⟨275, by decide, by decide, by decide⟩
  · subst r; exact ⟨693, by decide, by decide, by decide⟩
  · subst r; exact ⟨122, by decide, by decide, by decide⟩
  · subst r; exact ⟨691, by decide, by decide, by decide⟩
  · subst r; exact ⟨31, by decide, by decide, by decide⟩
  · subst r; exact ⟨689, by decide, by decide, by decide⟩
  · subst r; exact ⟨184, by decide, by decide, by decide⟩
  · subst r; exact ⟨687, by decide, by decide, by decide⟩
  · subst r; exact ⟨337, by decide, by decide, by decide⟩
  · subst r; exact ⟨552, by decide, by decide, by decide⟩
  · subst r; exact ⟨490, by decide, by decide, by decide⟩
  · subst r; exact ⟨401, by decide, by decide, by decide⟩
  · subst r; exact ⟨643, by decide, by decide, by decide⟩
  · subst r; exact ⟨250, by decide, by decide, by decide⟩
  · subst r; exact ⟨680, by decide, by decide, by decide⟩
  · subst r; exact ⟨99, by decide, by decide, by decide⟩
  · subst r; exact ⟨678, by decide, by decide, by decide⟩
  · subst r; exact ⟨52, by decide, by decide, by decide⟩
  · subst r; exact ⟨676, by decide, by decide, by decide⟩
  · subst r; exact ⟨203, by decide, by decide, by decide⟩
  · subst r; exact ⟨674, by decide, by decide, by decide⟩
  · subst r; exact ⟨319, by decide, by decide, by decide⟩
  · subst r; exact ⟨672, by decide, by decide, by decide⟩
  · subst r; exact ⟨166, by decide, by decide, by decide⟩
  · subst r; exact ⟨670, by decide, by decide, by decide⟩
  · subst r; exact ⟨13, by decide, by decide, by decide⟩
  · subst r; exact ⟨668, by decide, by decide, by decide⟩
  · subst r; exact ⟨140, by decide, by decide, by decide⟩
  · subst r; exact ⟨666, by decide, by decide, by decide⟩
  · subst r; exact ⟨293, by decide, by decide, by decide⟩
  · subst r; exact ⟨617, by decide, by decide, by decide⟩
  · subst r; exact ⟨446, by decide, by decide, by decide⟩
  · subst r; exact ⟨466, by decide, by decide, by decide⟩
  · subst r; exact ⟨599, by decide, by decide, by decide⟩
  · subst r; exact ⟨315, by decide, by decide, by decide⟩
  · subst r; exact ⟨659, by decide, by decide, by decide⟩
  · subst r; exact ⟨164, by decide, by decide, by decide⟩
  · subst r; exact ⟨657, by decide, by decide, by decide⟩
  · subst r; exact ⟨13, by decide, by decide, by decide⟩
  · subst r; exact ⟨655, by decide, by decide, by decide⟩
  · subst r; exact ⟨138, by decide, by decide, by decide⟩
  · subst r; exact ⟨653, by decide, by decide, by decide⟩
  · subst r; exact ⟨289, by decide, by decide, by decide⟩

theorem slice_53 (r : Nat) (lo : 2650 ≤ r) (hi : r ≤ 2699) : covered r := by
  have h : r = 2650 ∨ r = 2651 ∨ r = 2652 ∨ r = 2653 ∨ r = 2654 ∨ r = 2655 ∨ r = 2656 ∨ r = 2657 ∨ r = 2658 ∨ r = 2659 ∨ r = 2660 ∨ r = 2661 ∨ r = 2662 ∨ r = 2663 ∨ r = 2664 ∨ r = 2665 ∨ r = 2666 ∨ r = 2667 ∨ r = 2668 ∨ r = 2669 ∨ r = 2670 ∨ r = 2671 ∨ r = 2672 ∨ r = 2673 ∨ r = 2674 ∨ r = 2675 ∨ r = 2676 ∨ r = 2677 ∨ r = 2678 ∨ r = 2679 ∨ r = 2680 ∨ r = 2681 ∨ r = 2682 ∨ r = 2683 ∨ r = 2684 ∨ r = 2685 ∨ r = 2686 ∨ r = 2687 ∨ r = 2688 ∨ r = 2689 ∨ r = 2690 ∨ r = 2691 ∨ r = 2692 ∨ r = 2693 ∨ r = 2694 ∨ r = 2695 ∨ r = 2696 ∨ r = 2697 ∨ r = 2698 ∨ r = 2699 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨651, by decide, by decide, by decide⟩
  · subst r; exact ⟨210, by decide, by decide, by decide⟩
  · subst r; exact ⟨649, by decide, by decide, by decide⟩
  · subst r; exact ⟨57, by decide, by decide, by decide⟩
  · subst r; exact ⟨647, by decide, by decide, by decide⟩
  · subst r; exact ⟨96, by decide, by decide, by decide⟩
  · subst r; exact ⟨645, by decide, by decide, by decide⟩
  · subst r; exact ⟨249, by decide, by decide, by decide⟩
  · subst r; exact ⟨643, by decide, by decide, by decide⟩
  · subst r; exact ⟨402, by decide, by decide, by decide⟩
  · subst r; exact ⟨531, by decide, by decide, by decide⟩
  · subst r; exact ⟨555, by decide, by decide, by decide⟩
  · subst r; exact ⟨380, by decide, by decide, by decide⟩
  · subst r; exact ⟨638, by decide, by decide, by decide⟩
  · subst r; exact ⟨229, by decide, by decide, by decide⟩
  · subst r; exact ⟨636, by decide, by decide, by decide⟩
  · subst r; exact ⟨78, by decide, by decide, by decide⟩
  · subst r; exact ⟨634, by decide, by decide, by decide⟩
  · subst r; exact ⟨73, by decide, by decide, by decide⟩
  · subst r; exact ⟨632, by decide, by decide, by decide⟩
  · subst r; exact ⟨224, by decide, by decide, by decide⟩
  · subst r; exact ⟨630, by decide, by decide, by decide⟩
  · subst r; exact ⟨254, by decide, by decide, by decide⟩
  · subst r; exact ⟨628, by decide, by decide, by decide⟩
  · subst r; exact ⟨101, by decide, by decide, by decide⟩
  · subst r; exact ⟨626, by decide, by decide, by decide⟩
  · subst r; exact ⟨52, by decide, by decide, by decide⟩
  · subst r; exact ⟨624, by decide, by decide, by decide⟩
  · subst r; exact ⟨205, by decide, by decide, by decide⟩
  · subst r; exact ⟨622, by decide, by decide, by decide⟩
  · subst r; exact ⟨358, by decide, by decide, by decide⟩
  · subst r; exact ⟨596, by decide, by decide, by decide⟩
  · subst r; exact ⟨511, by decide, by decide, by decide⟩
  · subst r; exact ⟨445, by decide, by decide, by decide⟩
  · subst r; exact ⟨617, by decide, by decide, by decide⟩
  · subst r; exact ⟨294, by decide, by decide, by decide⟩
  · subst r; exact ⟨615, by decide, by decide, by decide⟩
  · subst r; exact ⟨143, by decide, by decide, by decide⟩
  · subst r; exact ⟨613, by decide, by decide, by decide⟩
  · subst r; exact ⟨8, by decide, by decide, by decide⟩
  · subst r; exact ⟨611, by decide, by decide, by decide⟩
  · subst r; exact ⟨159, by decide, by decide, by decide⟩
  · subst r; exact ⟨609, by decide, by decide, by decide⟩
  · subst r; exact ⟨298, by decide, by decide, by decide⟩
  · subst r; exact ⟨607, by decide, by decide, by decide⟩
  · subst r; exact ⟨145, by decide, by decide, by decide⟩
  · subst r; exact ⟨605, by decide, by decide, by decide⟩
  · subst r; exact ⟨8, by decide, by decide, by decide⟩
  · subst r; exact ⟨603, by decide, by decide, by decide⟩
  · subst r; exact ⟨161, by decide, by decide, by decide⟩

theorem slice_54 (r : Nat) (lo : 2700 ≤ r) (hi : r ≤ 2749) : covered r := by
  have h : r = 2700 ∨ r = 2701 ∨ r = 2702 ∨ r = 2703 ∨ r = 2704 ∨ r = 2705 ∨ r = 2706 ∨ r = 2707 ∨ r = 2708 ∨ r = 2709 ∨ r = 2710 ∨ r = 2711 ∨ r = 2712 ∨ r = 2713 ∨ r = 2714 ∨ r = 2715 ∨ r = 2716 ∨ r = 2717 ∨ r = 2718 ∨ r = 2719 ∨ r = 2720 ∨ r = 2721 ∨ r = 2722 ∨ r = 2723 ∨ r = 2724 ∨ r = 2725 ∨ r = 2726 ∨ r = 2727 ∨ r = 2728 ∨ r = 2729 ∨ r = 2730 ∨ r = 2731 ∨ r = 2732 ∨ r = 2733 ∨ r = 2734 ∨ r = 2735 ∨ r = 2736 ∨ r = 2737 ∨ r = 2738 ∨ r = 2739 ∨ r = 2740 ∨ r = 2741 ∨ r = 2742 ∨ r = 2743 ∨ r = 2744 ∨ r = 2745 ∨ r = 2746 ∨ r = 2747 ∨ r = 2748 ∨ r = 2749 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨601, by decide, by decide, by decide⟩
  · subst r; exact ⟨314, by decide, by decide, by decide⟩
  · subst r; exact ⟨599, by decide, by decide, by decide⟩
  · subst r; exact ⟨467, by decide, by decide, by decide⟩
  · subst r; exact ⟨510, by decide, by decide, by decide⟩
  · subst r; exact ⟨596, by decide, by decide, by decide⟩
  · subst r; exact ⟨359, by decide, by decide, by decide⟩
  · subst r; exact ⟨594, by decide, by decide, by decide⟩
  · subst r; exact ⟨208, by decide, by decide, by decide⟩
  · subst r; exact ⟨592, by decide, by decide, by decide⟩
  · subst r; exact ⟨57, by decide, by decide, by decide⟩
  · subst r; exact ⟨590, by decide, by decide, by decide⟩
  · subst r; exact ⟨94, by decide, by decide, by decide⟩
  · subst r; exact ⟨588, by decide, by decide, by decide⟩
  · subst r; exact ⟨245, by decide, by decide, by decide⟩
  · subst r; exact ⟨586, by decide, by decide, by decide⟩
  · subst r; exact ⟨189, by decide, by decide, by decide⟩
  · subst r; exact ⟨584, by decide, by decide, by decide⟩
  · subst r; exact ⟨36, by decide, by decide, by decide⟩
  · subst r; exact ⟨582, by decide, by decide, by decide⟩
  · subst r; exact ⟨117, by decide, by decide, by decide⟩
  · subst r; exact ⟨580, by decide, by decide, by decide⟩
  · subst r; exact ⟨270, by decide, by decide, by decide⟩
  · subst r; exact ⟨578, by decide, by decide, by decide⟩
  · subst r; exact ⟨423, by decide, by decide, by decide⟩
  · subst r; exact ⟨575, by decide, by decide, by decide⟩
  · subst r; exact ⟨575, by decide, by decide, by decide⟩
  · subst r; exact ⟨424, by decide, by decide, by decide⟩
  · subst r; exact ⟨573, by decide, by decide, by decide⟩
  · subst r; exact ⟨273, by decide, by decide, by decide⟩
  · subst r; exact ⟨571, by decide, by decide, by decide⟩
  · subst r; exact ⟨122, by decide, by decide, by decide⟩
  · subst r; exact ⟨569, by decide, by decide, by decide⟩
  · subst r; exact ⟨29, by decide, by decide, by decide⟩
  · subst r; exact ⟨567, by decide, by decide, by decide⟩
  · subst r; exact ⟨180, by decide, by decide, by decide⟩
  · subst r; exact ⟨565, by decide, by decide, by decide⟩
  · subst r; exact ⟨233, by decide, by decide, by decide⟩
  · subst r; exact ⟨563, by decide, by decide, by decide⟩
  · subst r; exact ⟨80, by decide, by decide, by decide⟩
  · subst r; exact ⟨561, by decide, by decide, by decide⟩
  · subst r; exact ⟨73, by decide, by decide, by decide⟩
  · subst r; exact ⟨559, by decide, by decide, by decide⟩
  · subst r; exact ⟨226, by decide, by decide, by decide⟩
  · subst r; exact ⟨557, by decide, by decide, by decide⟩
  · subst r; exact ⟨379, by decide, by decide, by decide⟩
  · subst r; exact ⟨555, by decide, by decide, by decide⟩
  · subst r; exact ⟨532, by decide, by decide, by decide⟩
  · subst r; exact ⟨489, by decide, by decide, by decide⟩
  · subst r; exact ⟨552, by decide, by decide, by decide⟩

theorem slice_55 (r : Nat) (lo : 2750 ≤ r) (hi : r ≤ 2799) : covered r := by
  have h : r = 2750 ∨ r = 2751 ∨ r = 2752 ∨ r = 2753 ∨ r = 2754 ∨ r = 2755 ∨ r = 2756 ∨ r = 2757 ∨ r = 2758 ∨ r = 2759 ∨ r = 2760 ∨ r = 2761 ∨ r = 2762 ∨ r = 2763 ∨ r = 2764 ∨ r = 2765 ∨ r = 2766 ∨ r = 2767 ∨ r = 2768 ∨ r = 2769 ∨ r = 2770 ∨ r = 2771 ∨ r = 2772 ∨ r = 2773 ∨ r = 2774 ∨ r = 2775 ∨ r = 2776 ∨ r = 2777 ∨ r = 2778 ∨ r = 2779 ∨ r = 2780 ∨ r = 2781 ∨ r = 2782 ∨ r = 2783 ∨ r = 2784 ∨ r = 2785 ∨ r = 2786 ∨ r = 2787 ∨ r = 2788 ∨ r = 2789 ∨ r = 2790 ∨ r = 2791 ∨ r = 2792 ∨ r = 2793 ∨ r = 2794 ∨ r = 2795 ∨ r = 2796 ∨ r = 2797 ∨ r = 2798 ∨ r = 2799 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨338, by decide, by decide, by decide⟩
  · subst r; exact ⟨550, by decide, by decide, by decide⟩
  · subst r; exact ⟨187, by decide, by decide, by decide⟩
  · subst r; exact ⟨548, by decide, by decide, by decide⟩
  · subst r; exact ⟨36, by decide, by decide, by decide⟩
  · subst r; exact ⟨546, by decide, by decide, by decide⟩
  · subst r; exact ⟨115, by decide, by decide, by decide⟩
  · subst r; exact ⟨544, by decide, by decide, by decide⟩
  · subst r; exact ⟨266, by decide, by decide, by decide⟩
  · subst r; exact ⟨542, by decide, by decide, by decide⟩
  · subst r; exact ⟨124, by decide, by decide, by decide⟩
  · subst r; exact ⟨540, by decide, by decide, by decide⟩
  · subst r; exact ⟨29, by decide, by decide, by decide⟩
  · subst r; exact ⟨538, by decide, by decide, by decide⟩
  · subst r; exact ⟨182, by decide, by decide, by decide⟩
  · subst r; exact ⟨536, by decide, by decide, by decide⟩
  · subst r; exact ⟨335, by decide, by decide, by decide⟩
  · subst r; exact ⟨534, by decide, by decide, by decide⟩
  · subst r; exact ⟨488, by decide, by decide, by decide⟩
  · subst r; exact ⟨532, by decide, by decide, by decide⟩
  · subst r; exact ⟨531, by decide, by decide, by decide⟩
  · subst r; exact ⟨403, by decide, by decide, by decide⟩
  · subst r; exact ⟨529, by decide, by decide, by decide⟩
  · subst r; exact ⟨252, by decide, by decide, by decide⟩
  · subst r; exact ⟨527, by decide, by decide, by decide⟩
  · subst r; exact ⟨101, by decide, by decide, by decide⟩
  · subst r; exact ⟨525, by decide, by decide, by decide⟩
  · subst r; exact ⟨50, by decide, by decide, by decide⟩
  · subst r; exact ⟨523, by decide, by decide, by decide⟩
  · subst r; exact ⟨201, by decide, by decide, by decide⟩
  · subst r; exact ⟨521, by decide, by decide, by decide⟩
  · subst r; exact ⟨168, by decide, by decide, by decide⟩
  · subst r; exact ⟨519, by decide, by decide, by decide⟩
  · subst r; exact ⟨15, by decide, by decide, by decide⟩
  · subst r; exact ⟨517, by decide, by decide, by decide⟩
  · subst r; exact ⟨138, by decide, by decide, by decide⟩
  · subst r; exact ⟨515, by decide, by decide, by decide⟩
  · subst r; exact ⟨291, by decide, by decide, by decide⟩
  · subst r; exact ⟨513, by decide, by decide, by decide⟩
  · subst r; exact ⟨444, by decide, by decide, by decide⟩
  · subst r; exact ⟨511, by decide, by decide, by decide⟩
  · subst r; exact ⟨510, by decide, by decide, by decide⟩
  · subst r; exact ⟨468, by decide, by decide, by decide⟩
  · subst r; exact ⟨508, by decide, by decide, by decide⟩
  · subst r; exact ⟨317, by decide, by decide, by decide⟩
  · subst r; exact ⟨506, by decide, by decide, by decide⟩
  · subst r; exact ⟨166, by decide, by decide, by decide⟩
  · subst r; exact ⟨504, by decide, by decide, by decide⟩
  · subst r; exact ⟨15, by decide, by decide, by decide⟩
  · subst r; exact ⟨502, by decide, by decide, by decide⟩

theorem slice_56 (r : Nat) (lo : 2800 ≤ r) (hi : r ≤ 2849) : covered r := by
  have h : r = 2800 ∨ r = 2801 ∨ r = 2802 ∨ r = 2803 ∨ r = 2804 ∨ r = 2805 ∨ r = 2806 ∨ r = 2807 ∨ r = 2808 ∨ r = 2809 ∨ r = 2810 ∨ r = 2811 ∨ r = 2812 ∨ r = 2813 ∨ r = 2814 ∨ r = 2815 ∨ r = 2816 ∨ r = 2817 ∨ r = 2818 ∨ r = 2819 ∨ r = 2820 ∨ r = 2821 ∨ r = 2822 ∨ r = 2823 ∨ r = 2824 ∨ r = 2825 ∨ r = 2826 ∨ r = 2827 ∨ r = 2828 ∨ r = 2829 ∨ r = 2830 ∨ r = 2831 ∨ r = 2832 ∨ r = 2833 ∨ r = 2834 ∨ r = 2835 ∨ r = 2836 ∨ r = 2837 ∨ r = 2838 ∨ r = 2839 ∨ r = 2840 ∨ r = 2841 ∨ r = 2842 ∨ r = 2843 ∨ r = 2844 ∨ r = 2845 ∨ r = 2846 ∨ r = 2847 ∨ r = 2848 ∨ r = 2849 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨136, by decide, by decide, by decide⟩
  · subst r; exact ⟨500, by decide, by decide, by decide⟩
  · subst r; exact ⟨212, by decide, by decide, by decide⟩
  · subst r; exact ⟨498, by decide, by decide, by decide⟩
  · subst r; exact ⟨59, by decide, by decide, by decide⟩
  · subst r; exact ⟨496, by decide, by decide, by decide⟩
  · subst r; exact ⟨94, by decide, by decide, by decide⟩
  · subst r; exact ⟨494, by decide, by decide, by decide⟩
  · subst r; exact ⟨247, by decide, by decide, by decide⟩
  · subst r; exact ⟨492, by decide, by decide, by decide⟩
  · subst r; exact ⟨400, by decide, by decide, by decide⟩
  · subst r; exact ⟨490, by decide, by decide, by decide⟩
  · subst r; exact ⟨489, by decide, by decide, by decide⟩
  · subst r; exact ⟨488, by decide, by decide, by decide⟩
  · subst r; exact ⟨487, by decide, by decide, by decide⟩
  · subst r; exact ⟨382, by decide, by decide, by decide⟩
  · subst r; exact ⟨485, by decide, by decide, by decide⟩
  · subst r; exact ⟨231, by decide, by decide, by decide⟩
  · subst r; exact ⟨483, by decide, by decide, by decide⟩
  · subst r; exact ⟨80, by decide, by decide, by decide⟩
  · subst r; exact ⟨481, by decide, by decide, by decide⟩
  · subst r; exact ⟨71, by decide, by decide, by decide⟩
  · subst r; exact ⟨479, by decide, by decide, by decide⟩
  · subst r; exact ⟨222, by decide, by decide, by decide⟩
  · subst r; exact ⟨477, by decide, by decide, by decide⟩
  · subst r; exact ⟨103, by decide, by decide, by decide⟩
  · subst r; exact ⟨475, by decide, by decide, by decide⟩
  · subst r; exact ⟨50, by decide, by decide, by decide⟩
  · subst r; exact ⟨473, by decide, by decide, by decide⟩
  · subst r; exact ⟨203, by decide, by decide, by decide⟩
  · subst r; exact ⟨471, by decide, by decide, by decide⟩
  · subst r; exact ⟨356, by decide, by decide, by decide⟩
  · subst r; exact ⟨469, by decide, by decide, by decide⟩
  · subst r; exact ⟨468, by decide, by decide, by decide⟩
  · subst r; exact ⟨467, by decide, by decide, by decide⟩
  · subst r; exact ⟨466, by decide, by decide, by decide⟩
  · subst r; exact ⟨447, by decide, by decide, by decide⟩
  · subst r; exact ⟨464, by decide, by decide, by decide⟩
  · subst r; exact ⟨296, by decide, by decide, by decide⟩
  · subst r; exact ⟨462, by decide, by decide, by decide⟩
  · subst r; exact ⟨145, by decide, by decide, by decide⟩
  · subst r; exact ⟨460, by decide, by decide, by decide⟩
  · subst r; exact ⟨6, by decide, by decide, by decide⟩
  · subst r; exact ⟨458, by decide, by decide, by decide⟩
  · subst r; exact ⟨157, by decide, by decide, by decide⟩
  · subst r; exact ⟨456, by decide, by decide, by decide⟩
  · subst r; exact ⟨147, by decide, by decide, by decide⟩
  · subst r; exact ⟨454, by decide, by decide, by decide⟩
  · subst r; exact ⟨6, by decide, by decide, by decide⟩
  · subst r; exact ⟨452, by decide, by decide, by decide⟩

theorem slice_57 (r : Nat) (lo : 2850 ≤ r) (hi : r ≤ 2899) : covered r := by
  have h : r = 2850 ∨ r = 2851 ∨ r = 2852 ∨ r = 2853 ∨ r = 2854 ∨ r = 2855 ∨ r = 2856 ∨ r = 2857 ∨ r = 2858 ∨ r = 2859 ∨ r = 2860 ∨ r = 2861 ∨ r = 2862 ∨ r = 2863 ∨ r = 2864 ∨ r = 2865 ∨ r = 2866 ∨ r = 2867 ∨ r = 2868 ∨ r = 2869 ∨ r = 2870 ∨ r = 2871 ∨ r = 2872 ∨ r = 2873 ∨ r = 2874 ∨ r = 2875 ∨ r = 2876 ∨ r = 2877 ∨ r = 2878 ∨ r = 2879 ∨ r = 2880 ∨ r = 2881 ∨ r = 2882 ∨ r = 2883 ∨ r = 2884 ∨ r = 2885 ∨ r = 2886 ∨ r = 2887 ∨ r = 2888 ∨ r = 2889 ∨ r = 2890 ∨ r = 2891 ∨ r = 2892 ∨ r = 2893 ∨ r = 2894 ∨ r = 2895 ∨ r = 2896 ∨ r = 2897 ∨ r = 2898 ∨ r = 2899 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨159, by decide, by decide, by decide⟩
  · subst r; exact ⟨450, by decide, by decide, by decide⟩
  · subst r; exact ⟨312, by decide, by decide, by decide⟩
  · subst r; exact ⟨448, by decide, by decide, by decide⟩
  · subst r; exact ⟨447, by decide, by decide, by decide⟩
  · subst r; exact ⟨446, by decide, by decide, by decide⟩
  · subst r; exact ⟨445, by decide, by decide, by decide⟩
  · subst r; exact ⟨444, by decide, by decide, by decide⟩
  · subst r; exact ⟨443, by decide, by decide, by decide⟩
  · subst r; exact ⟨361, by decide, by decide, by decide⟩
  · subst r; exact ⟨441, by decide, by decide, by decide⟩
  · subst r; exact ⟨210, by decide, by decide, by decide⟩
  · subst r; exact ⟨439, by decide, by decide, by decide⟩
  · subst r; exact ⟨59, by decide, by decide, by decide⟩
  · subst r; exact ⟨437, by decide, by decide, by decide⟩
  · subst r; exact ⟨92, by decide, by decide, by decide⟩
  · subst r; exact ⟨435, by decide, by decide, by decide⟩
  · subst r; exact ⟨191, by decide, by decide, by decide⟩
  · subst r; exact ⟨433, by decide, by decide, by decide⟩
  · subst r; exact ⟨38, by decide, by decide, by decide⟩
  · subst r; exact ⟨431, by decide, by decide, by decide⟩
  · subst r; exact ⟨115, by decide, by decide, by decide⟩
  · subst r; exact ⟨429, by decide, by decide, by decide⟩
  · subst r; exact ⟨268, by decide, by decide, by decide⟩
  · subst r; exact ⟨427, by decide, by decide, by decide⟩
  · subst r; exact ⟨421, by decide, by decide, by decide⟩
  · subst r; exact ⟨425, by decide, by decide, by decide⟩
  · subst r; exact ⟨424, by decide, by decide, by decide⟩
  · subst r; exact ⟨423, by decide, by decide, by decide⟩
  · subst r; exact ⟨422, by decide, by decide, by decide⟩
  · subst r; exact ⟨421, by decide, by decide, by decide⟩
  · subst r; exact ⟨420, by decide, by decide, by decide⟩
  · subst r; exact ⟨275, by decide, by decide, by decide⟩
  · subst r; exact ⟨418, by decide, by decide, by decide⟩
  · subst r; exact ⟨124, by decide, by decide, by decide⟩
  · subst r; exact ⟨416, by decide, by decide, by decide⟩
  · subst r; exact ⟨27, by decide, by decide, by decide⟩
  · subst r; exact ⟨414, by decide, by decide, by decide⟩
  · subst r; exact ⟨178, by decide, by decide, by decide⟩
  · subst r; exact ⟨412, by decide, by decide, by decide⟩
  · subst r; exact ⟨82, by decide, by decide, by decide⟩
  · subst r; exact ⟨410, by decide, by decide, by decide⟩
  · subst r; exact ⟨71, by decide, by decide, by decide⟩
  · subst r; exact ⟨408, by decide, by decide, by decide⟩
  · subst r; exact ⟨224, by decide, by decide, by decide⟩
  · subst r; exact ⟨406, by decide, by decide, by decide⟩
  · subst r; exact ⟨377, by decide, by decide, by decide⟩
  · subst r; exact ⟨404, by decide, by decide, by decide⟩
  · subst r; exact ⟨403, by decide, by decide, by decide⟩
  · subst r; exact ⟨402, by decide, by decide, by decide⟩

theorem slice_58 (r : Nat) (lo : 2900 ≤ r) (hi : r ≤ 2949) : covered r := by
  have h : r = 2900 ∨ r = 2901 ∨ r = 2902 ∨ r = 2903 ∨ r = 2904 ∨ r = 2905 ∨ r = 2906 ∨ r = 2907 ∨ r = 2908 ∨ r = 2909 ∨ r = 2910 ∨ r = 2911 ∨ r = 2912 ∨ r = 2913 ∨ r = 2914 ∨ r = 2915 ∨ r = 2916 ∨ r = 2917 ∨ r = 2918 ∨ r = 2919 ∨ r = 2920 ∨ r = 2921 ∨ r = 2922 ∨ r = 2923 ∨ r = 2924 ∨ r = 2925 ∨ r = 2926 ∨ r = 2927 ∨ r = 2928 ∨ r = 2929 ∨ r = 2930 ∨ r = 2931 ∨ r = 2932 ∨ r = 2933 ∨ r = 2934 ∨ r = 2935 ∨ r = 2936 ∨ r = 2937 ∨ r = 2938 ∨ r = 2939 ∨ r = 2940 ∨ r = 2941 ∨ r = 2942 ∨ r = 2943 ∨ r = 2944 ∨ r = 2945 ∨ r = 2946 ∨ r = 2947 ∨ r = 2948 ∨ r = 2949 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨401, by decide, by decide, by decide⟩
  · subst r; exact ⟨400, by decide, by decide, by decide⟩
  · subst r; exact ⟨399, by decide, by decide, by decide⟩
  · subst r; exact ⟨340, by decide, by decide, by decide⟩
  · subst r; exact ⟨397, by decide, by decide, by decide⟩
  · subst r; exact ⟨189, by decide, by decide, by decide⟩
  · subst r; exact ⟨395, by decide, by decide, by decide⟩
  · subst r; exact ⟨38, by decide, by decide, by decide⟩
  · subst r; exact ⟨393, by decide, by decide, by decide⟩
  · subst r; exact ⟨113, by decide, by decide, by decide⟩
  · subst r; exact ⟨391, by decide, by decide, by decide⟩
  · subst r; exact ⟨126, by decide, by decide, by decide⟩
  · subst r; exact ⟨389, by decide, by decide, by decide⟩
  · subst r; exact ⟨27, by decide, by decide, by decide⟩
  · subst r; exact ⟨387, by decide, by decide, by decide⟩
  · subst r; exact ⟨180, by decide, by decide, by decide⟩
  · subst r; exact ⟨385, by decide, by decide, by decide⟩
  · subst r; exact ⟨333, by decide, by decide, by decide⟩
  · subst r; exact ⟨383, by decide, by decide, by decide⟩
  · subst r; exact ⟨382, by decide, by decide, by decide⟩
  · subst r; exact ⟨381, by decide, by decide, by decide⟩
  · subst r; exact ⟨380, by decide, by decide, by decide⟩
  · subst r; exact ⟨379, by decide, by decide, by decide⟩
  · subst r; exact ⟨378, by decide, by decide, by decide⟩
  · subst r; exact ⟨377, by decide, by decide, by decide⟩
  · subst r; exact ⟨376, by decide, by decide, by decide⟩
  · subst r; exact ⟨254, by decide, by decide, by decide⟩
  · subst r; exact ⟨374, by decide, by decide, by decide⟩
  · subst r; exact ⟨103, by decide, by decide, by decide⟩
  · subst r; exact ⟨372, by decide, by decide, by decide⟩
  · subst r; exact ⟨48, by decide, by decide, by decide⟩
  · subst r; exact ⟨370, by decide, by decide, by decide⟩
  · subst r; exact ⟨170, by decide, by decide, by decide⟩
  · subst r; exact ⟨368, by decide, by decide, by decide⟩
  · subst r; exact ⟨17, by decide, by decide, by decide⟩
  · subst r; exact ⟨366, by decide, by decide, by decide⟩
  · subst r; exact ⟨136, by decide, by decide, by decide⟩
  · subst r; exact ⟨364, by decide, by decide, by decide⟩
  · subst r; exact ⟨289, by decide, by decide, by decide⟩
  · subst r; exact ⟨362, by decide, by decide, by decide⟩
  · subst r; exact ⟨361, by decide, by decide, by decide⟩
  · subst r; exact ⟨360, by decide, by decide, by decide⟩
  · subst r; exact ⟨359, by decide, by decide, by decide⟩
  · subst r; exact ⟨358, by decide, by decide, by decide⟩
  · subst r; exact ⟨357, by decide, by decide, by decide⟩
  · subst r; exact ⟨356, by decide, by decide, by decide⟩
  · subst r; exact ⟨355, by decide, by decide, by decide⟩
  · subst r; exact ⟨319, by decide, by decide, by decide⟩
  · subst r; exact ⟨353, by decide, by decide, by decide⟩
  · subst r; exact ⟨168, by decide, by decide, by decide⟩

theorem slice_59 (r : Nat) (lo : 2950 ≤ r) (hi : r ≤ 2999) : covered r := by
  have h : r = 2950 ∨ r = 2951 ∨ r = 2952 ∨ r = 2953 ∨ r = 2954 ∨ r = 2955 ∨ r = 2956 ∨ r = 2957 ∨ r = 2958 ∨ r = 2959 ∨ r = 2960 ∨ r = 2961 ∨ r = 2962 ∨ r = 2963 ∨ r = 2964 ∨ r = 2965 ∨ r = 2966 ∨ r = 2967 ∨ r = 2968 ∨ r = 2969 ∨ r = 2970 ∨ r = 2971 ∨ r = 2972 ∨ r = 2973 ∨ r = 2974 ∨ r = 2975 ∨ r = 2976 ∨ r = 2977 ∨ r = 2978 ∨ r = 2979 ∨ r = 2980 ∨ r = 2981 ∨ r = 2982 ∨ r = 2983 ∨ r = 2984 ∨ r = 2985 ∨ r = 2986 ∨ r = 2987 ∨ r = 2988 ∨ r = 2989 ∨ r = 2990 ∨ r = 2991 ∨ r = 2992 ∨ r = 2993 ∨ r = 2994 ∨ r = 2995 ∨ r = 2996 ∨ r = 2997 ∨ r = 2998 ∨ r = 2999 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨351, by decide, by decide, by decide⟩
  · subst r; exact ⟨17, by decide, by decide, by decide⟩
  · subst r; exact ⟨349, by decide, by decide, by decide⟩
  · subst r; exact ⟨134, by decide, by decide, by decide⟩
  · subst r; exact ⟨347, by decide, by decide, by decide⟩
  · subst r; exact ⟨61, by decide, by decide, by decide⟩
  · subst r; exact ⟨345, by decide, by decide, by decide⟩
  · subst r; exact ⟨92, by decide, by decide, by decide⟩
  · subst r; exact ⟨343, by decide, by decide, by decide⟩
  · subst r; exact ⟨245, by decide, by decide, by decide⟩
  · subst r; exact ⟨341, by decide, by decide, by decide⟩
  · subst r; exact ⟨340, by decide, by decide, by decide⟩
  · subst r; exact ⟨339, by decide, by decide, by decide⟩
  · subst r; exact ⟨338, by decide, by decide, by decide⟩
  · subst r; exact ⟨337, by decide, by decide, by decide⟩
  · subst r; exact ⟨336, by decide, by decide, by decide⟩
  · subst r; exact ⟨335, by decide, by decide, by decide⟩
  · subst r; exact ⟨334, by decide, by decide, by decide⟩
  · subst r; exact ⟨333, by decide, by decide, by decide⟩
  · subst r; exact ⟨332, by decide, by decide, by decide⟩
  · subst r; exact ⟨233, by decide, by decide, by decide⟩
  · subst r; exact ⟨330, by decide, by decide, by decide⟩
  · subst r; exact ⟨82, by decide, by decide, by decide⟩
  · subst r; exact ⟨328, by decide, by decide, by decide⟩
  · subst r; exact ⟨69, by decide, by decide, by decide⟩
  · subst r; exact ⟨326, by decide, by decide, by decide⟩
  · subst r; exact ⟨105, by decide, by decide, by decide⟩
  · subst r; exact ⟨324, by decide, by decide, by decide⟩
  · subst r; exact ⟨48, by decide, by decide, by decide⟩
  · subst r; exact ⟨322, by decide, by decide, by decide⟩
  · subst r; exact ⟨201, by decide, by decide, by decide⟩
  · subst r; exact ⟨320, by decide, by decide, by decide⟩
  · subst r; exact ⟨319, by decide, by decide, by decide⟩
  · subst r; exact ⟨318, by decide, by decide, by decide⟩
  · subst r; exact ⟨317, by decide, by decide, by decide⟩
  · subst r; exact ⟨316, by decide, by decide, by decide⟩
  · subst r; exact ⟨315, by decide, by decide, by decide⟩
  · subst r; exact ⟨314, by decide, by decide, by decide⟩
  · subst r; exact ⟨313, by decide, by decide, by decide⟩
  · subst r; exact ⟨312, by decide, by decide, by decide⟩
  · subst r; exact ⟨311, by decide, by decide, by decide⟩
  · subst r; exact ⟨298, by decide, by decide, by decide⟩
  · subst r; exact ⟨309, by decide, by decide, by decide⟩
  · subst r; exact ⟨147, by decide, by decide, by decide⟩
  · subst r; exact ⟨307, by decide, by decide, by decide⟩
  · subst r; exact ⟨4, by decide, by decide, by decide⟩
  · subst r; exact ⟨305, by decide, by decide, by decide⟩
  · subst r; exact ⟨149, by decide, by decide, by decide⟩
  · subst r; exact ⟨303, by decide, by decide, by decide⟩
  · subst r; exact ⟨4, by decide, by decide, by decide⟩

theorem slice_60 (r : Nat) (lo : 3000 ≤ r) (hi : r ≤ 3049) : covered r := by
  have h : r = 3000 ∨ r = 3001 ∨ r = 3002 ∨ r = 3003 ∨ r = 3004 ∨ r = 3005 ∨ r = 3006 ∨ r = 3007 ∨ r = 3008 ∨ r = 3009 ∨ r = 3010 ∨ r = 3011 ∨ r = 3012 ∨ r = 3013 ∨ r = 3014 ∨ r = 3015 ∨ r = 3016 ∨ r = 3017 ∨ r = 3018 ∨ r = 3019 ∨ r = 3020 ∨ r = 3021 ∨ r = 3022 ∨ r = 3023 ∨ r = 3024 ∨ r = 3025 ∨ r = 3026 ∨ r = 3027 ∨ r = 3028 ∨ r = 3029 ∨ r = 3030 ∨ r = 3031 ∨ r = 3032 ∨ r = 3033 ∨ r = 3034 ∨ r = 3035 ∨ r = 3036 ∨ r = 3037 ∨ r = 3038 ∨ r = 3039 ∨ r = 3040 ∨ r = 3041 ∨ r = 3042 ∨ r = 3043 ∨ r = 3044 ∨ r = 3045 ∨ r = 3046 ∨ r = 3047 ∨ r = 3048 ∨ r = 3049 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨301, by decide, by decide, by decide⟩
  · subst r; exact ⟨157, by decide, by decide, by decide⟩
  · subst r; exact ⟨299, by decide, by decide, by decide⟩
  · subst r; exact ⟨298, by decide, by decide, by decide⟩
  · subst r; exact ⟨297, by decide, by decide, by decide⟩
  · subst r; exact ⟨296, by decide, by decide, by decide⟩
  · subst r; exact ⟨295, by decide, by decide, by decide⟩
  · subst r; exact ⟨294, by decide, by decide, by decide⟩
  · subst r; exact ⟨293, by decide, by decide, by decide⟩
  · subst r; exact ⟨292, by decide, by decide, by decide⟩
  · subst r; exact ⟨291, by decide, by decide, by decide⟩
  · subst r; exact ⟨290, by decide, by decide, by decide⟩
  · subst r; exact ⟨289, by decide, by decide, by decide⟩
  · subst r; exact ⟨288, by decide, by decide, by decide⟩
  · subst r; exact ⟨212, by decide, by decide, by decide⟩
  · subst r; exact ⟨286, by decide, by decide, by decide⟩
  · subst r; exact ⟨61, by decide, by decide, by decide⟩
  · subst r; exact ⟨284, by decide, by decide, by decide⟩
  · subst r; exact ⟨90, by decide, by decide, by decide⟩
  · subst r; exact ⟨282, by decide, by decide, by decide⟩
  · subst r; exact ⟨40, by decide, by decide, by decide⟩
  · subst r; exact ⟨280, by decide, by decide, by decide⟩
  · subst r; exact ⟨113, by decide, by decide, by decide⟩
  · subst r; exact ⟨278, by decide, by decide, by decide⟩
  · subst r; exact ⟨266, by decide, by decide, by decide⟩
  · subst r; exact ⟨276, by decide, by decide, by decide⟩
  · subst r; exact ⟨275, by decide, by decide, by decide⟩
  · subst r; exact ⟨274, by decide, by decide, by decide⟩
  · subst r; exact ⟨273, by decide, by decide, by decide⟩
  · subst r; exact ⟨272, by decide, by decide, by decide⟩
  · subst r; exact ⟨271, by decide, by decide, by decide⟩
  · subst r; exact ⟨270, by decide, by decide, by decide⟩
  · subst r; exact ⟨269, by decide, by decide, by decide⟩
  · subst r; exact ⟨268, by decide, by decide, by decide⟩
  · subst r; exact ⟨267, by decide, by decide, by decide⟩
  · subst r; exact ⟨266, by decide, by decide, by decide⟩
  · subst r; exact ⟨265, by decide, by decide, by decide⟩
  · subst r; exact ⟨126, by decide, by decide, by decide⟩
  · subst r; exact ⟨263, by decide, by decide, by decide⟩
  · subst r; exact ⟨25, by decide, by decide, by decide⟩
  · subst r; exact ⟨261, by decide, by decide, by decide⟩
  · subst r; exact ⟨84, by decide, by decide, by decide⟩
  · subst r; exact ⟨259, by decide, by decide, by decide⟩
  · subst r; exact ⟨69, by decide, by decide, by decide⟩
  · subst r; exact ⟨257, by decide, by decide, by decide⟩
  · subst r; exact ⟨222, by decide, by decide, by decide⟩
  · subst r; exact ⟨255, by decide, by decide, by decide⟩
  · subst r; exact ⟨254, by decide, by decide, by decide⟩
  · subst r; exact ⟨253, by decide, by decide, by decide⟩
  · subst r; exact ⟨252, by decide, by decide, by decide⟩

theorem slice_61 (r : Nat) (lo : 3050 ≤ r) (hi : r ≤ 3099) : covered r := by
  have h : r = 3050 ∨ r = 3051 ∨ r = 3052 ∨ r = 3053 ∨ r = 3054 ∨ r = 3055 ∨ r = 3056 ∨ r = 3057 ∨ r = 3058 ∨ r = 3059 ∨ r = 3060 ∨ r = 3061 ∨ r = 3062 ∨ r = 3063 ∨ r = 3064 ∨ r = 3065 ∨ r = 3066 ∨ r = 3067 ∨ r = 3068 ∨ r = 3069 ∨ r = 3070 ∨ r = 3071 ∨ r = 3072 ∨ r = 3073 ∨ r = 3074 ∨ r = 3075 ∨ r = 3076 ∨ r = 3077 ∨ r = 3078 ∨ r = 3079 ∨ r = 3080 ∨ r = 3081 ∨ r = 3082 ∨ r = 3083 ∨ r = 3084 ∨ r = 3085 ∨ r = 3086 ∨ r = 3087 ∨ r = 3088 ∨ r = 3089 ∨ r = 3090 ∨ r = 3091 ∨ r = 3092 ∨ r = 3093 ∨ r = 3094 ∨ r = 3095 ∨ r = 3096 ∨ r = 3097 ∨ r = 3098 ∨ r = 3099 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨251, by decide, by decide, by decide⟩
  · subst r; exact ⟨250, by decide, by decide, by decide⟩
  · subst r; exact ⟨249, by decide, by decide, by decide⟩
  · subst r; exact ⟨248, by decide, by decide, by decide⟩
  · subst r; exact ⟨247, by decide, by decide, by decide⟩
  · subst r; exact ⟨246, by decide, by decide, by decide⟩
  · subst r; exact ⟨245, by decide, by decide, by decide⟩
  · subst r; exact ⟨244, by decide, by decide, by decide⟩
  · subst r; exact ⟨191, by decide, by decide, by decide⟩
  · subst r; exact ⟨242, by decide, by decide, by decide⟩
  · subst r; exact ⟨40, by decide, by decide, by decide⟩
  · subst r; exact ⟨240, by decide, by decide, by decide⟩
  · subst r; exact ⟨111, by decide, by decide, by decide⟩
  · subst r; exact ⟨238, by decide, by decide, by decide⟩
  · subst r; exact ⟨25, by decide, by decide, by decide⟩
  · subst r; exact ⟨236, by decide, by decide, by decide⟩
  · subst r; exact ⟨178, by decide, by decide, by decide⟩
  · subst r; exact ⟨234, by decide, by decide, by decide⟩
  · subst r; exact ⟨233, by decide, by decide, by decide⟩
  · subst r; exact ⟨232, by decide, by decide, by decide⟩
  · subst r; exact ⟨231, by decide, by decide, by decide⟩
  · subst r; exact ⟨230, by decide, by decide, by decide⟩
  · subst r; exact ⟨229, by decide, by decide, by decide⟩
  · subst r; exact ⟨228, by decide, by decide, by decide⟩
  · subst r; exact ⟨227, by decide, by decide, by decide⟩
  · subst r; exact ⟨226, by decide, by decide, by decide⟩
  · subst r; exact ⟨225, by decide, by decide, by decide⟩
  · subst r; exact ⟨224, by decide, by decide, by decide⟩
  · subst r; exact ⟨223, by decide, by decide, by decide⟩
  · subst r; exact ⟨222, by decide, by decide, by decide⟩
  · subst r; exact ⟨221, by decide, by decide, by decide⟩
  · subst r; exact ⟨105, by decide, by decide, by decide⟩
  · subst r; exact ⟨219, by decide, by decide, by decide⟩
  · subst r; exact ⟨46, by decide, by decide, by decide⟩
  · subst r; exact ⟨217, by decide, by decide, by decide⟩
  · subst r; exact ⟨19, by decide, by decide, by decide⟩
  · subst r; exact ⟨215, by decide, by decide, by decide⟩
  · subst r; exact ⟨134, by decide, by decide, by decide⟩
  · subst r; exact ⟨213, by decide, by decide, by decide⟩
  · subst r; exact ⟨212, by decide, by decide, by decide⟩
  · subst r; exact ⟨211, by decide, by decide, by decide⟩
  · subst r; exact ⟨210, by decide, by decide, by decide⟩
  · subst r; exact ⟨209, by decide, by decide, by decide⟩
  · subst r; exact ⟨208, by decide, by decide, by decide⟩
  · subst r; exact ⟨207, by decide, by decide, by decide⟩
  · subst r; exact ⟨206, by decide, by decide, by decide⟩
  · subst r; exact ⟨205, by decide, by decide, by decide⟩
  · subst r; exact ⟨204, by decide, by decide, by decide⟩
  · subst r; exact ⟨203, by decide, by decide, by decide⟩
  · subst r; exact ⟨202, by decide, by decide, by decide⟩

theorem slice_62 (r : Nat) (lo : 3100 ≤ r) (hi : r ≤ 3149) : covered r := by
  have h : r = 3100 ∨ r = 3101 ∨ r = 3102 ∨ r = 3103 ∨ r = 3104 ∨ r = 3105 ∨ r = 3106 ∨ r = 3107 ∨ r = 3108 ∨ r = 3109 ∨ r = 3110 ∨ r = 3111 ∨ r = 3112 ∨ r = 3113 ∨ r = 3114 ∨ r = 3115 ∨ r = 3116 ∨ r = 3117 ∨ r = 3118 ∨ r = 3119 ∨ r = 3120 ∨ r = 3121 ∨ r = 3122 ∨ r = 3123 ∨ r = 3124 ∨ r = 3125 ∨ r = 3126 ∨ r = 3127 ∨ r = 3128 ∨ r = 3129 ∨ r = 3130 ∨ r = 3131 ∨ r = 3132 ∨ r = 3133 ∨ r = 3134 ∨ r = 3135 ∨ r = 3136 ∨ r = 3137 ∨ r = 3138 ∨ r = 3139 ∨ r = 3140 ∨ r = 3141 ∨ r = 3142 ∨ r = 3143 ∨ r = 3144 ∨ r = 3145 ∨ r = 3146 ∨ r = 3147 ∨ r = 3148 ∨ r = 3149 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨201, by decide, by decide, by decide⟩
  · subst r; exact ⟨200, by decide, by decide, by decide⟩
  · subst r; exact ⟨170, by decide, by decide, by decide⟩
  · subst r; exact ⟨198, by decide, by decide, by decide⟩
  · subst r; exact ⟨19, by decide, by decide, by decide⟩
  · subst r; exact ⟨196, by decide, by decide, by decide⟩
  · subst r; exact ⟨63, by decide, by decide, by decide⟩
  · subst r; exact ⟨194, by decide, by decide, by decide⟩
  · subst r; exact ⟨90, by decide, by decide, by decide⟩
  · subst r; exact ⟨192, by decide, by decide, by decide⟩
  · subst r; exact ⟨191, by decide, by decide, by decide⟩
  · subst r; exact ⟨190, by decide, by decide, by decide⟩
  · subst r; exact ⟨189, by decide, by decide, by decide⟩
  · subst r; exact ⟨188, by decide, by decide, by decide⟩
  · subst r; exact ⟨187, by decide, by decide, by decide⟩
  · subst r; exact ⟨186, by decide, by decide, by decide⟩
  · subst r; exact ⟨185, by decide, by decide, by decide⟩
  · subst r; exact ⟨184, by decide, by decide, by decide⟩
  · subst r; exact ⟨183, by decide, by decide, by decide⟩
  · subst r; exact ⟨182, by decide, by decide, by decide⟩
  · subst r; exact ⟨181, by decide, by decide, by decide⟩
  · subst r; exact ⟨180, by decide, by decide, by decide⟩
  · subst r; exact ⟨179, by decide, by decide, by decide⟩
  · subst r; exact ⟨178, by decide, by decide, by decide⟩
  · subst r; exact ⟨177, by decide, by decide, by decide⟩
  · subst r; exact ⟨84, by decide, by decide, by decide⟩
  · subst r; exact ⟨175, by decide, by decide, by decide⟩
  · subst r; exact ⟨67, by decide, by decide, by decide⟩
  · subst r; exact ⟨173, by decide, by decide, by decide⟩
  · subst r; exact ⟨46, by decide, by decide, by decide⟩
  · subst r; exact ⟨171, by decide, by decide, by decide⟩
  · subst r; exact ⟨170, by decide, by decide, by decide⟩
  · subst r; exact ⟨169, by decide, by decide, by decide⟩
  · subst r; exact ⟨168, by decide, by decide, by decide⟩
  · subst r; exact ⟨167, by decide, by decide, by decide⟩
  · subst r; exact ⟨166, by decide, by decide, by decide⟩
  · subst r; exact ⟨165, by decide, by decide, by decide⟩
  · subst r; exact ⟨164, by decide, by decide, by decide⟩
  · subst r; exact ⟨163, by decide, by decide, by decide⟩
  · subst r; exact ⟨162, by decide, by decide, by decide⟩
  · subst r; exact ⟨161, by decide, by decide, by decide⟩
  · subst r; exact ⟨160, by decide, by decide, by decide⟩
  · subst r; exact ⟨159, by decide, by decide, by decide⟩
  · subst r; exact ⟨158, by decide, by decide, by decide⟩
  · subst r; exact ⟨157, by decide, by decide, by decide⟩
  · subst r; exact ⟨156, by decide, by decide, by decide⟩
  · subst r; exact ⟨149, by decide, by decide, by decide⟩
  · subst r; exact ⟨154, by decide, by decide, by decide⟩
  · subst r; exact ⟨2, by decide, by decide, by decide⟩
  · subst r; exact ⟨152, by decide, by decide, by decide⟩

theorem slice_63 (r : Nat) (lo : 3150 ≤ r) (hi : r ≤ 3199) : covered r := by
  have h : r = 3150 ∨ r = 3151 ∨ r = 3152 ∨ r = 3153 ∨ r = 3154 ∨ r = 3155 ∨ r = 3156 ∨ r = 3157 ∨ r = 3158 ∨ r = 3159 ∨ r = 3160 ∨ r = 3161 ∨ r = 3162 ∨ r = 3163 ∨ r = 3164 ∨ r = 3165 ∨ r = 3166 ∨ r = 3167 ∨ r = 3168 ∨ r = 3169 ∨ r = 3170 ∨ r = 3171 ∨ r = 3172 ∨ r = 3173 ∨ r = 3174 ∨ r = 3175 ∨ r = 3176 ∨ r = 3177 ∨ r = 3178 ∨ r = 3179 ∨ r = 3180 ∨ r = 3181 ∨ r = 3182 ∨ r = 3183 ∨ r = 3184 ∨ r = 3185 ∨ r = 3186 ∨ r = 3187 ∨ r = 3188 ∨ r = 3189 ∨ r = 3190 ∨ r = 3191 ∨ r = 3192 ∨ r = 3193 ∨ r = 3194 ∨ r = 3195 ∨ r = 3196 ∨ r = 3197 ∨ r = 3198 ∨ r = 3199 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨2, by decide, by decide, by decide⟩
  · subst r; exact ⟨150, by decide, by decide, by decide⟩
  · subst r; exact ⟨149, by decide, by decide, by decide⟩
  · subst r; exact ⟨148, by decide, by decide, by decide⟩
  · subst r; exact ⟨147, by decide, by decide, by decide⟩
  · subst r; exact ⟨146, by decide, by decide, by decide⟩
  · subst r; exact ⟨145, by decide, by decide, by decide⟩
  · subst r; exact ⟨144, by decide, by decide, by decide⟩
  · subst r; exact ⟨143, by decide, by decide, by decide⟩
  · subst r; exact ⟨142, by decide, by decide, by decide⟩
  · subst r; exact ⟨141, by decide, by decide, by decide⟩
  · subst r; exact ⟨140, by decide, by decide, by decide⟩
  · subst r; exact ⟨139, by decide, by decide, by decide⟩
  · subst r; exact ⟨138, by decide, by decide, by decide⟩
  · subst r; exact ⟨137, by decide, by decide, by decide⟩
  · subst r; exact ⟨136, by decide, by decide, by decide⟩
  · subst r; exact ⟨135, by decide, by decide, by decide⟩
  · subst r; exact ⟨134, by decide, by decide, by decide⟩
  · subst r; exact ⟨133, by decide, by decide, by decide⟩
  · subst r; exact ⟨63, by decide, by decide, by decide⟩
  · subst r; exact ⟨131, by decide, by decide, by decide⟩
  · subst r; exact ⟨42, by decide, by decide, by decide⟩
  · subst r; exact ⟨129, by decide, by decide, by decide⟩
  · subst r; exact ⟨111, by decide, by decide, by decide⟩
  · subst r; exact ⟨127, by decide, by decide, by decide⟩
  · subst r; exact ⟨126, by decide, by decide, by decide⟩
  · subst r; exact ⟨125, by decide, by decide, by decide⟩
  · subst r; exact ⟨124, by decide, by decide, by decide⟩
  · subst r; exact ⟨123, by decide, by decide, by decide⟩
  · subst r; exact ⟨122, by decide, by decide, by decide⟩
  · subst r; exact ⟨121, by decide, by decide, by decide⟩
  · subst r; exact ⟨120, by decide, by decide, by decide⟩
  · subst r; exact ⟨119, by decide, by decide, by decide⟩
  · subst r; exact ⟨118, by decide, by decide, by decide⟩
  · subst r; exact ⟨117, by decide, by decide, by decide⟩
  · subst r; exact ⟨116, by decide, by decide, by decide⟩
  · subst r; exact ⟨115, by decide, by decide, by decide⟩
  · subst r; exact ⟨114, by decide, by decide, by decide⟩
  · subst r; exact ⟨113, by decide, by decide, by decide⟩
  · subst r; exact ⟨112, by decide, by decide, by decide⟩
  · subst r; exact ⟨111, by decide, by decide, by decide⟩
  · subst r; exact ⟨110, by decide, by decide, by decide⟩
  · subst r; exact ⟨23, by decide, by decide, by decide⟩
  · subst r; exact ⟨108, by decide, by decide, by decide⟩
  · subst r; exact ⟨67, by decide, by decide, by decide⟩
  · subst r; exact ⟨106, by decide, by decide, by decide⟩
  · subst r; exact ⟨105, by decide, by decide, by decide⟩
  · subst r; exact ⟨104, by decide, by decide, by decide⟩
  · subst r; exact ⟨103, by decide, by decide, by decide⟩
  · subst r; exact ⟨102, by decide, by decide, by decide⟩

theorem slice_64 (r : Nat) (lo : 3200 ≤ r) (hi : r ≤ 3249) : covered r := by
  have h : r = 3200 ∨ r = 3201 ∨ r = 3202 ∨ r = 3203 ∨ r = 3204 ∨ r = 3205 ∨ r = 3206 ∨ r = 3207 ∨ r = 3208 ∨ r = 3209 ∨ r = 3210 ∨ r = 3211 ∨ r = 3212 ∨ r = 3213 ∨ r = 3214 ∨ r = 3215 ∨ r = 3216 ∨ r = 3217 ∨ r = 3218 ∨ r = 3219 ∨ r = 3220 ∨ r = 3221 ∨ r = 3222 ∨ r = 3223 ∨ r = 3224 ∨ r = 3225 ∨ r = 3226 ∨ r = 3227 ∨ r = 3228 ∨ r = 3229 ∨ r = 3230 ∨ r = 3231 ∨ r = 3232 ∨ r = 3233 ∨ r = 3234 ∨ r = 3235 ∨ r = 3236 ∨ r = 3237 ∨ r = 3238 ∨ r = 3239 ∨ r = 3240 ∨ r = 3241 ∨ r = 3242 ∨ r = 3243 ∨ r = 3244 ∨ r = 3245 ∨ r = 3246 ∨ r = 3247 ∨ r = 3248 ∨ r = 3249 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨101, by decide, by decide, by decide⟩
  · subst r; exact ⟨100, by decide, by decide, by decide⟩
  · subst r; exact ⟨99, by decide, by decide, by decide⟩
  · subst r; exact ⟨98, by decide, by decide, by decide⟩
  · subst r; exact ⟨97, by decide, by decide, by decide⟩
  · subst r; exact ⟨96, by decide, by decide, by decide⟩
  · subst r; exact ⟨95, by decide, by decide, by decide⟩
  · subst r; exact ⟨94, by decide, by decide, by decide⟩
  · subst r; exact ⟨93, by decide, by decide, by decide⟩
  · subst r; exact ⟨92, by decide, by decide, by decide⟩
  · subst r; exact ⟨91, by decide, by decide, by decide⟩
  · subst r; exact ⟨90, by decide, by decide, by decide⟩
  · subst r; exact ⟨89, by decide, by decide, by decide⟩
  · subst r; exact ⟨42, by decide, by decide, by decide⟩
  · subst r; exact ⟨87, by decide, by decide, by decide⟩
  · subst r; exact ⟨23, by decide, by decide, by decide⟩
  · subst r; exact ⟨85, by decide, by decide, by decide⟩
  · subst r; exact ⟨84, by decide, by decide, by decide⟩
  · subst r; exact ⟨83, by decide, by decide, by decide⟩
  · subst r; exact ⟨82, by decide, by decide, by decide⟩
  · subst r; exact ⟨81, by decide, by decide, by decide⟩
  · subst r; exact ⟨80, by decide, by decide, by decide⟩
  · subst r; exact ⟨79, by decide, by decide, by decide⟩
  · subst r; exact ⟨78, by decide, by decide, by decide⟩
  · subst r; exact ⟨77, by decide, by decide, by decide⟩
  · subst r; exact ⟨76, by decide, by decide, by decide⟩
  · subst r; exact ⟨75, by decide, by decide, by decide⟩
  · subst r; exact ⟨74, by decide, by decide, by decide⟩
  · subst r; exact ⟨73, by decide, by decide, by decide⟩
  · subst r; exact ⟨72, by decide, by decide, by decide⟩
  · subst r; exact ⟨71, by decide, by decide, by decide⟩
  · subst r; exact ⟨70, by decide, by decide, by decide⟩
  · subst r; exact ⟨69, by decide, by decide, by decide⟩
  · subst r; exact ⟨68, by decide, by decide, by decide⟩
  · subst r; exact ⟨67, by decide, by decide, by decide⟩
  · subst r; exact ⟨66, by decide, by decide, by decide⟩
  · subst r; exact ⟨21, by decide, by decide, by decide⟩
  · subst r; exact ⟨64, by decide, by decide, by decide⟩
  · subst r; exact ⟨63, by decide, by decide, by decide⟩
  · subst r; exact ⟨62, by decide, by decide, by decide⟩
  · subst r; exact ⟨61, by decide, by decide, by decide⟩
  · subst r; exact ⟨60, by decide, by decide, by decide⟩
  · subst r; exact ⟨59, by decide, by decide, by decide⟩
  · subst r; exact ⟨58, by decide, by decide, by decide⟩
  · subst r; exact ⟨57, by decide, by decide, by decide⟩
  · subst r; exact ⟨56, by decide, by decide, by decide⟩
  · subst r; exact ⟨55, by decide, by decide, by decide⟩
  · subst r; exact ⟨54, by decide, by decide, by decide⟩
  · subst r; exact ⟨53, by decide, by decide, by decide⟩
  · subst r; exact ⟨52, by decide, by decide, by decide⟩

theorem slice_65 (r : Nat) (lo : 3250 ≤ r) (hi : r ≤ 3299) : covered r := by
  have h : r = 3250 ∨ r = 3251 ∨ r = 3252 ∨ r = 3253 ∨ r = 3254 ∨ r = 3255 ∨ r = 3256 ∨ r = 3257 ∨ r = 3258 ∨ r = 3259 ∨ r = 3260 ∨ r = 3261 ∨ r = 3262 ∨ r = 3263 ∨ r = 3264 ∨ r = 3265 ∨ r = 3266 ∨ r = 3267 ∨ r = 3268 ∨ r = 3269 ∨ r = 3270 ∨ r = 3271 ∨ r = 3272 ∨ r = 3273 ∨ r = 3274 ∨ r = 3275 ∨ r = 3276 ∨ r = 3277 ∨ r = 3278 ∨ r = 3279 ∨ r = 3280 ∨ r = 3281 ∨ r = 3282 ∨ r = 3283 ∨ r = 3284 ∨ r = 3285 ∨ r = 3286 ∨ r = 3287 ∨ r = 3288 ∨ r = 3289 ∨ r = 3290 ∨ r = 3291 ∨ r = 3292 ∨ r = 3293 ∨ r = 3294 ∨ r = 3295 ∨ r = 3296 ∨ r = 3297 ∨ r = 3298 ∨ r = 3299 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨51, by decide, by decide, by decide⟩
  · subst r; exact ⟨50, by decide, by decide, by decide⟩
  · subst r; exact ⟨49, by decide, by decide, by decide⟩
  · subst r; exact ⟨48, by decide, by decide, by decide⟩
  · subst r; exact ⟨47, by decide, by decide, by decide⟩
  · subst r; exact ⟨46, by decide, by decide, by decide⟩
  · subst r; exact ⟨45, by decide, by decide, by decide⟩
  · subst r; exact ⟨21, by decide, by decide, by decide⟩
  · subst r; exact ⟨43, by decide, by decide, by decide⟩
  · subst r; exact ⟨42, by decide, by decide, by decide⟩
  · subst r; exact ⟨41, by decide, by decide, by decide⟩
  · subst r; exact ⟨40, by decide, by decide, by decide⟩
  · subst r; exact ⟨39, by decide, by decide, by decide⟩
  · subst r; exact ⟨38, by decide, by decide, by decide⟩
  · subst r; exact ⟨37, by decide, by decide, by decide⟩
  · subst r; exact ⟨36, by decide, by decide, by decide⟩
  · subst r; exact ⟨35, by decide, by decide, by decide⟩
  · subst r; exact ⟨34, by decide, by decide, by decide⟩
  · subst r; exact ⟨33, by decide, by decide, by decide⟩
  · subst r; exact ⟨32, by decide, by decide, by decide⟩
  · subst r; exact ⟨31, by decide, by decide, by decide⟩
  · subst r; exact ⟨30, by decide, by decide, by decide⟩
  · subst r; exact ⟨29, by decide, by decide, by decide⟩
  · subst r; exact ⟨28, by decide, by decide, by decide⟩
  · subst r; exact ⟨27, by decide, by decide, by decide⟩
  · subst r; exact ⟨26, by decide, by decide, by decide⟩
  · subst r; exact ⟨25, by decide, by decide, by decide⟩
  · subst r; exact ⟨24, by decide, by decide, by decide⟩
  · subst r; exact ⟨23, by decide, by decide, by decide⟩
  · subst r; exact ⟨22, by decide, by decide, by decide⟩
  · subst r; exact ⟨21, by decide, by decide, by decide⟩
  · subst r; exact ⟨20, by decide, by decide, by decide⟩
  · subst r; exact ⟨19, by decide, by decide, by decide⟩
  · subst r; exact ⟨18, by decide, by decide, by decide⟩
  · subst r; exact ⟨17, by decide, by decide, by decide⟩
  · subst r; exact ⟨16, by decide, by decide, by decide⟩
  · subst r; exact ⟨15, by decide, by decide, by decide⟩
  · subst r; exact ⟨14, by decide, by decide, by decide⟩
  · subst r; exact ⟨13, by decide, by decide, by decide⟩
  · subst r; exact ⟨12, by decide, by decide, by decide⟩
  · subst r; exact ⟨11, by decide, by decide, by decide⟩
  · subst r; exact ⟨10, by decide, by decide, by decide⟩
  · subst r; exact ⟨9, by decide, by decide, by decide⟩
  · subst r; exact ⟨8, by decide, by decide, by decide⟩
  · subst r; exact ⟨7, by decide, by decide, by decide⟩
  · subst r; exact ⟨6, by decide, by decide, by decide⟩
  · subst r; exact ⟨5, by decide, by decide, by decide⟩
  · subst r; exact ⟨4, by decide, by decide, by decide⟩
  · subst r; exact ⟨3, by decide, by decide, by decide⟩
  · subst r; exact ⟨2, by decide, by decide, by decide⟩

theorem slice_66 (r : Nat) (lo : 3300 ≤ r) (hi : r ≤ 3300) : covered r := by
  have h : r = 3300 := by omega
  rcases h with h
  · subst r; exact ⟨1, by decide, by decide, by decide⟩

theorem all_residues_covered (r : Nat) (hr : r < 3301) : covered r := by
  by_cases h0 : r ≤ 49
  · exact slice_0 r (by omega) h0
  by_cases h1 : r ≤ 99
  · exact slice_1 r (by omega) h1
  by_cases h2 : r ≤ 149
  · exact slice_2 r (by omega) h2
  by_cases h3 : r ≤ 199
  · exact slice_3 r (by omega) h3
  by_cases h4 : r ≤ 249
  · exact slice_4 r (by omega) h4
  by_cases h5 : r ≤ 299
  · exact slice_5 r (by omega) h5
  by_cases h6 : r ≤ 349
  · exact slice_6 r (by omega) h6
  by_cases h7 : r ≤ 399
  · exact slice_7 r (by omega) h7
  by_cases h8 : r ≤ 449
  · exact slice_8 r (by omega) h8
  by_cases h9 : r ≤ 499
  · exact slice_9 r (by omega) h9
  by_cases h10 : r ≤ 549
  · exact slice_10 r (by omega) h10
  by_cases h11 : r ≤ 599
  · exact slice_11 r (by omega) h11
  by_cases h12 : r ≤ 649
  · exact slice_12 r (by omega) h12
  by_cases h13 : r ≤ 699
  · exact slice_13 r (by omega) h13
  by_cases h14 : r ≤ 749
  · exact slice_14 r (by omega) h14
  by_cases h15 : r ≤ 799
  · exact slice_15 r (by omega) h15
  by_cases h16 : r ≤ 849
  · exact slice_16 r (by omega) h16
  by_cases h17 : r ≤ 899
  · exact slice_17 r (by omega) h17
  by_cases h18 : r ≤ 949
  · exact slice_18 r (by omega) h18
  by_cases h19 : r ≤ 999
  · exact slice_19 r (by omega) h19
  by_cases h20 : r ≤ 1049
  · exact slice_20 r (by omega) h20
  by_cases h21 : r ≤ 1099
  · exact slice_21 r (by omega) h21
  by_cases h22 : r ≤ 1149
  · exact slice_22 r (by omega) h22
  by_cases h23 : r ≤ 1199
  · exact slice_23 r (by omega) h23
  by_cases h24 : r ≤ 1249
  · exact slice_24 r (by omega) h24
  by_cases h25 : r ≤ 1299
  · exact slice_25 r (by omega) h25
  by_cases h26 : r ≤ 1349
  · exact slice_26 r (by omega) h26
  by_cases h27 : r ≤ 1399
  · exact slice_27 r (by omega) h27
  by_cases h28 : r ≤ 1449
  · exact slice_28 r (by omega) h28
  by_cases h29 : r ≤ 1499
  · exact slice_29 r (by omega) h29
  by_cases h30 : r ≤ 1549
  · exact slice_30 r (by omega) h30
  by_cases h31 : r ≤ 1599
  · exact slice_31 r (by omega) h31
  by_cases h32 : r ≤ 1649
  · exact slice_32 r (by omega) h32
  by_cases h33 : r ≤ 1699
  · exact slice_33 r (by omega) h33
  by_cases h34 : r ≤ 1749
  · exact slice_34 r (by omega) h34
  by_cases h35 : r ≤ 1799
  · exact slice_35 r (by omega) h35
  by_cases h36 : r ≤ 1849
  · exact slice_36 r (by omega) h36
  by_cases h37 : r ≤ 1899
  · exact slice_37 r (by omega) h37
  by_cases h38 : r ≤ 1949
  · exact slice_38 r (by omega) h38
  by_cases h39 : r ≤ 1999
  · exact slice_39 r (by omega) h39
  by_cases h40 : r ≤ 2049
  · exact slice_40 r (by omega) h40
  by_cases h41 : r ≤ 2099
  · exact slice_41 r (by omega) h41
  by_cases h42 : r ≤ 2149
  · exact slice_42 r (by omega) h42
  by_cases h43 : r ≤ 2199
  · exact slice_43 r (by omega) h43
  by_cases h44 : r ≤ 2249
  · exact slice_44 r (by omega) h44
  by_cases h45 : r ≤ 2299
  · exact slice_45 r (by omega) h45
  by_cases h46 : r ≤ 2349
  · exact slice_46 r (by omega) h46
  by_cases h47 : r ≤ 2399
  · exact slice_47 r (by omega) h47
  by_cases h48 : r ≤ 2449
  · exact slice_48 r (by omega) h48
  by_cases h49 : r ≤ 2499
  · exact slice_49 r (by omega) h49
  by_cases h50 : r ≤ 2549
  · exact slice_50 r (by omega) h50
  by_cases h51 : r ≤ 2599
  · exact slice_51 r (by omega) h51
  by_cases h52 : r ≤ 2649
  · exact slice_52 r (by omega) h52
  by_cases h53 : r ≤ 2699
  · exact slice_53 r (by omega) h53
  by_cases h54 : r ≤ 2749
  · exact slice_54 r (by omega) h54
  by_cases h55 : r ≤ 2799
  · exact slice_55 r (by omega) h55
  by_cases h56 : r ≤ 2849
  · exact slice_56 r (by omega) h56
  by_cases h57 : r ≤ 2899
  · exact slice_57 r (by omega) h57
  by_cases h58 : r ≤ 2949
  · exact slice_58 r (by omega) h58
  by_cases h59 : r ≤ 2999
  · exact slice_59 r (by omega) h59
  by_cases h60 : r ≤ 3049
  · exact slice_60 r (by omega) h60
  by_cases h61 : r ≤ 3099
  · exact slice_61 r (by omega) h61
  by_cases h62 : r ≤ 3149
  · exact slice_62 r (by omega) h62
  by_cases h63 : r ≤ 3199
  · exact slice_63 r (by omega) h63
  by_cases h64 : r ≤ 3249
  · exact slice_64 r (by omega) h64
  by_cases h65 : r ≤ 3299
  · exact slice_65 r (by omega) h65
  exact slice_66 r (by omega) (by omega)

theorem canonical_mem (m : Nat) (hm : m ≤ 1064)
    (hc : isCanonical m = true) : m ∈ seeds := by
  simp only [seeds, List.mem_filter, List.mem_range]
  exact ⟨by omega, hc⟩

theorem all_residues_covered_by_table (r : Nat) (hr : r < 3301) :
    ∃ m : Nat, (m = 0 ∨ m ∈ seeds) ∧ (
      r = m ∨ r = (3300*m)%3301 ∨ r = (1726*m)%3301 ∨
      r = (1575*m)%3301 ∨ r = (1574*m)%3301 ∨
      r = (1727*m)%3301) := by
  obtain ⟨m, hm, hc, hform⟩ := all_residues_covered r hr
  refine ⟨m, ?_, hform⟩
  rcases hc with hz | hc
  · exact Or.inl hz
  · exact Or.inr (canonical_mem m hm hc)

#print axioms all_residues_covered
#print axioms all_residues_covered_by_table
end SplitPrimeCanonicalCover
