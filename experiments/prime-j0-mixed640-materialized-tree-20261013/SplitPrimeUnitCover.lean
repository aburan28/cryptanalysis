import Lean
set_option maxHeartbeats 0
namespace SplitPrimeUnitCover

-- This explicit finite certificate uses kernel reduction (`decide`), not
-- native evaluation. All 3301 residues are covered by one of six units.
def covered (r : Nat) : Prop :=
  ∃ m : Nat, m ≤ 1064 ∧ (
    r = m ∨ r = (3300*m)%3301 ∨ r = (1726*m)%3301 ∨
    r = (1575*m)%3301 ∨ r = (1574*m)%3301 ∨ r = (1727*m)%3301)

theorem direct_low (r : Nat) (hr : r ≤ 1064) : covered r := by
  exact ⟨r, hr, Or.inl rfl⟩

theorem direct_high (r : Nat) (hlo : 2237 ≤ r) (hhi : r < 3301) : covered r := by
  refine ⟨3301-r, by omega, ?_⟩
  right
  left
  omega

theorem slice_0 (r : Nat) (lo : 1065 ≤ r) (hi : r ≤ 1114) : covered r := by
  have h : r = 1065 ∨ r = 1066 ∨ r = 1067 ∨ r = 1068 ∨ r = 1069 ∨ r = 1070 ∨ r = 1071 ∨ r = 1072 ∨ r = 1073 ∨ r = 1074 ∨ r = 1075 ∨ r = 1076 ∨ r = 1077 ∨ r = 1078 ∨ r = 1079 ∨ r = 1080 ∨ r = 1081 ∨ r = 1082 ∨ r = 1083 ∨ r = 1084 ∨ r = 1085 ∨ r = 1086 ∨ r = 1087 ∨ r = 1088 ∨ r = 1089 ∨ r = 1090 ∨ r = 1091 ∨ r = 1092 ∨ r = 1093 ∨ r = 1094 ∨ r = 1095 ∨ r = 1096 ∨ r = 1097 ∨ r = 1098 ∨ r = 1099 ∨ r = 1100 ∨ r = 1101 ∨ r = 1102 ∨ r = 1103 ∨ r = 1104 ∨ r = 1105 ∨ r = 1106 ∨ r = 1107 ∨ r = 1108 ∨ r = 1109 ∨ r = 1110 ∨ r = 1111 ∨ r = 1112 ∨ r = 1113 ∨ r = 1114 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨467, by decide, by decide⟩
  · subst r; exact ⟨976, by decide, by decide⟩
  · subst r; exact ⟨316, by decide, by decide⟩
  · subst r; exact ⟨823, by decide, by decide⟩
  · subst r; exact ⟨165, by decide, by decide⟩
  · subst r; exact ⟨670, by decide, by decide⟩
  · subst r; exact ⟨14, by decide, by decide⟩
  · subst r; exact ⟨517, by decide, by decide⟩
  · subst r; exact ⟨137, by decide, by decide⟩
  · subst r; exact ⟨364, by decide, by decide⟩
  · subst r; exact ⟨288, by decide, by decide⟩
  · subst r; exact ⟨211, by decide, by decide⟩
  · subst r; exact ⟨439, by decide, by decide⟩
  · subst r; exact ⟨58, by decide, by decide⟩
  · subst r; exact ⟨590, by decide, by decide⟩
  · subst r; exact ⟨95, by decide, by decide⟩
  · subst r; exact ⟨741, by decide, by decide⟩
  · subst r; exact ⟨248, by decide, by decide⟩
  · subst r; exact ⟨892, by decide, by decide⟩
  · subst r; exact ⟨401, by decide, by decide⟩
  · subst r; exact ⟨1043, by decide, by decide⟩
  · subst r; exact ⟨532, by decide, by decide⟩
  · subst r; exact ⟨1020, by decide, by decide⟩
  · subst r; exact ⟨381, by decide, by decide⟩
  · subst r; exact ⟨867, by decide, by decide⟩
  · subst r; exact ⟨230, by decide, by decide⟩
  · subst r; exact ⟨714, by decide, by decide⟩
  · subst r; exact ⟨79, by decide, by decide⟩
  · subst r; exact ⟨561, by decide, by decide⟩
  · subst r; exact ⟨72, by decide, by decide⟩
  · subst r; exact ⟨408, by decide, by decide⟩
  · subst r; exact ⟨223, by decide, by decide⟩
  · subst r; exact ⟨255, by decide, by decide⟩
  · subst r; exact ⟨374, by decide, by decide⟩
  · subst r; exact ⟨102, by decide, by decide⟩
  · subst r; exact ⟨525, by decide, by decide⟩
  · subst r; exact ⟨51, by decide, by decide⟩
  · subst r; exact ⟨676, by decide, by decide⟩
  · subst r; exact ⟨204, by decide, by decide⟩
  · subst r; exact ⟨827, by decide, by decide⟩
  · subst r; exact ⟨357, by decide, by decide⟩
  · subst r; exact ⟨978, by decide, by decide⟩
  · subst r; exact ⟨510, by decide, by decide⟩
  · subst r; exact ⟨1064, by decide, by decide⟩
  · subst r; exact ⟨446, by decide, by decide⟩
  · subst r; exact ⟨911, by decide, by decide⟩
  · subst r; exact ⟨295, by decide, by decide⟩
  · subst r; exact ⟨758, by decide, by decide⟩
  · subst r; exact ⟨144, by decide, by decide⟩
  · subst r; exact ⟨605, by decide, by decide⟩

theorem slice_1 (r : Nat) (lo : 1115 ≤ r) (hi : r ≤ 1164) : covered r := by
  have h : r = 1115 ∨ r = 1116 ∨ r = 1117 ∨ r = 1118 ∨ r = 1119 ∨ r = 1120 ∨ r = 1121 ∨ r = 1122 ∨ r = 1123 ∨ r = 1124 ∨ r = 1125 ∨ r = 1126 ∨ r = 1127 ∨ r = 1128 ∨ r = 1129 ∨ r = 1130 ∨ r = 1131 ∨ r = 1132 ∨ r = 1133 ∨ r = 1134 ∨ r = 1135 ∨ r = 1136 ∨ r = 1137 ∨ r = 1138 ∨ r = 1139 ∨ r = 1140 ∨ r = 1141 ∨ r = 1142 ∨ r = 1143 ∨ r = 1144 ∨ r = 1145 ∨ r = 1146 ∨ r = 1147 ∨ r = 1148 ∨ r = 1149 ∨ r = 1150 ∨ r = 1151 ∨ r = 1152 ∨ r = 1153 ∨ r = 1154 ∨ r = 1155 ∨ r = 1156 ∨ r = 1157 ∨ r = 1158 ∨ r = 1159 ∨ r = 1160 ∨ r = 1161 ∨ r = 1162 ∨ r = 1163 ∨ r = 1164 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨7, by decide, by decide⟩
  · subst r; exact ⟨452, by decide, by decide⟩
  · subst r; exact ⟨158, by decide, by decide⟩
  · subst r; exact ⟨299, by decide, by decide⟩
  · subst r; exact ⟨309, by decide, by decide⟩
  · subst r; exact ⟨146, by decide, by decide⟩
  · subst r; exact ⟨460, by decide, by decide⟩
  · subst r; exact ⟨7, by decide, by decide⟩
  · subst r; exact ⟨611, by decide, by decide⟩
  · subst r; exact ⟨160, by decide, by decide⟩
  · subst r; exact ⟨762, by decide, by decide⟩
  · subst r; exact ⟨313, by decide, by decide⟩
  · subst r; exact ⟨913, by decide, by decide⟩
  · subst r; exact ⟨466, by decide, by decide⟩
  · subst r; exact ⟨1064, by decide, by decide⟩
  · subst r; exact ⟨511, by decide, by decide⟩
  · subst r; exact ⟨955, by decide, by decide⟩
  · subst r; exact ⟨360, by decide, by decide⟩
  · subst r; exact ⟨802, by decide, by decide⟩
  · subst r; exact ⟨209, by decide, by decide⟩
  · subst r; exact ⟨649, by decide, by decide⟩
  · subst r; exact ⟨58, by decide, by decide⟩
  · subst r; exact ⟨496, by decide, by decide⟩
  · subst r; exact ⟨93, by decide, by decide⟩
  · subst r; exact ⟨343, by decide, by decide⟩
  · subst r; exact ⟨244, by decide, by decide⟩
  · subst r; exact ⟨190, by decide, by decide⟩
  · subst r; exact ⟨395, by decide, by decide⟩
  · subst r; exact ⟨37, by decide, by decide⟩
  · subst r; exact ⟨546, by decide, by decide⟩
  · subst r; exact ⟨116, by decide, by decide⟩
  · subst r; exact ⟨697, by decide, by decide⟩
  · subst r; exact ⟨269, by decide, by decide⟩
  · subst r; exact ⟨848, by decide, by decide⟩
  · subst r; exact ⟨422, by decide, by decide⟩
  · subst r; exact ⟨999, by decide, by decide⟩
  · subst r; exact ⟨575, by decide, by decide⟩
  · subst r; exact ⟨999, by decide, by decide⟩
  · subst r; exact ⟨425, by decide, by decide⟩
  · subst r; exact ⟨846, by decide, by decide⟩
  · subst r; exact ⟨274, by decide, by decide⟩
  · subst r; exact ⟨693, by decide, by decide⟩
  · subst r; exact ⟨123, by decide, by decide⟩
  · subst r; exact ⟨540, by decide, by decide⟩
  · subst r; exact ⟨28, by decide, by decide⟩
  · subst r; exact ⟨387, by decide, by decide⟩
  · subst r; exact ⟨179, by decide, by decide⟩
  · subst r; exact ⟨234, by decide, by decide⟩
  · subst r; exact ⟨330, by decide, by decide⟩
  · subst r; exact ⟨81, by decide, by decide⟩

theorem slice_2 (r : Nat) (lo : 1165 ≤ r) (hi : r ≤ 1214) : covered r := by
  have h : r = 1165 ∨ r = 1166 ∨ r = 1167 ∨ r = 1168 ∨ r = 1169 ∨ r = 1170 ∨ r = 1171 ∨ r = 1172 ∨ r = 1173 ∨ r = 1174 ∨ r = 1175 ∨ r = 1176 ∨ r = 1177 ∨ r = 1178 ∨ r = 1179 ∨ r = 1180 ∨ r = 1181 ∨ r = 1182 ∨ r = 1183 ∨ r = 1184 ∨ r = 1185 ∨ r = 1186 ∨ r = 1187 ∨ r = 1188 ∨ r = 1189 ∨ r = 1190 ∨ r = 1191 ∨ r = 1192 ∨ r = 1193 ∨ r = 1194 ∨ r = 1195 ∨ r = 1196 ∨ r = 1197 ∨ r = 1198 ∨ r = 1199 ∨ r = 1200 ∨ r = 1201 ∨ r = 1202 ∨ r = 1203 ∨ r = 1204 ∨ r = 1205 ∨ r = 1206 ∨ r = 1207 ∨ r = 1208 ∨ r = 1209 ∨ r = 1210 ∨ r = 1211 ∨ r = 1212 ∨ r = 1213 ∨ r = 1214 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨481, by decide, by decide⟩
  · subst r; exact ⟨72, by decide, by decide⟩
  · subst r; exact ⟨632, by decide, by decide⟩
  · subst r; exact ⟨225, by decide, by decide⟩
  · subst r; exact ⟨783, by decide, by decide⟩
  · subst r; exact ⟨378, by decide, by decide⟩
  · subst r; exact ⟨934, by decide, by decide⟩
  · subst r; exact ⟨531, by decide, by decide⟩
  · subst r; exact ⟨1043, by decide, by decide⟩
  · subst r; exact ⟨490, by decide, by decide⟩
  · subst r; exact ⟨890, by decide, by decide⟩
  · subst r; exact ⟨339, by decide, by decide⟩
  · subst r; exact ⟨737, by decide, by decide⟩
  · subst r; exact ⟨188, by decide, by decide⟩
  · subst r; exact ⟨584, by decide, by decide⟩
  · subst r; exact ⟨37, by decide, by decide⟩
  · subst r; exact ⟨431, by decide, by decide⟩
  · subst r; exact ⟨114, by decide, by decide⟩
  · subst r; exact ⟨278, by decide, by decide⟩
  · subst r; exact ⟨265, by decide, by decide⟩
  · subst r; exact ⟨125, by decide, by decide⟩
  · subst r; exact ⟨416, by decide, by decide⟩
  · subst r; exact ⟨28, by decide, by decide⟩
  · subst r; exact ⟨567, by decide, by decide⟩
  · subst r; exact ⟨181, by decide, by decide⟩
  · subst r; exact ⟨718, by decide, by decide⟩
  · subst r; exact ⟨334, by decide, by decide⟩
  · subst r; exact ⟨869, by decide, by decide⟩
  · subst r; exact ⟨487, by decide, by decide⟩
  · subst r; exact ⟨1020, by decide, by decide⟩
  · subst r; exact ⟨555, by decide, by decide⟩
  · subst r; exact ⟨934, by decide, by decide⟩
  · subst r; exact ⟨404, by decide, by decide⟩
  · subst r; exact ⟨781, by decide, by decide⟩
  · subst r; exact ⟨253, by decide, by decide⟩
  · subst r; exact ⟨628, by decide, by decide⟩
  · subst r; exact ⟨102, by decide, by decide⟩
  · subst r; exact ⟨475, by decide, by decide⟩
  · subst r; exact ⟨49, by decide, by decide⟩
  · subst r; exact ⟨322, by decide, by decide⟩
  · subst r; exact ⟨200, by decide, by decide⟩
  · subst r; exact ⟨169, by decide, by decide⟩
  · subst r; exact ⟨351, by decide, by decide⟩
  · subst r; exact ⟨16, by decide, by decide⟩
  · subst r; exact ⟨502, by decide, by decide⟩
  · subst r; exact ⟨137, by decide, by decide⟩
  · subst r; exact ⟨653, by decide, by decide⟩
  · subst r; exact ⟨290, by decide, by decide⟩
  · subst r; exact ⟨804, by decide, by decide⟩
  · subst r; exact ⟨443, by decide, by decide⟩

theorem slice_3 (r : Nat) (lo : 1215 ≤ r) (hi : r ≤ 1264) : covered r := by
  have h : r = 1215 ∨ r = 1216 ∨ r = 1217 ∨ r = 1218 ∨ r = 1219 ∨ r = 1220 ∨ r = 1221 ∨ r = 1222 ∨ r = 1223 ∨ r = 1224 ∨ r = 1225 ∨ r = 1226 ∨ r = 1227 ∨ r = 1228 ∨ r = 1229 ∨ r = 1230 ∨ r = 1231 ∨ r = 1232 ∨ r = 1233 ∨ r = 1234 ∨ r = 1235 ∨ r = 1236 ∨ r = 1237 ∨ r = 1238 ∨ r = 1239 ∨ r = 1240 ∨ r = 1241 ∨ r = 1242 ∨ r = 1243 ∨ r = 1244 ∨ r = 1245 ∨ r = 1246 ∨ r = 1247 ∨ r = 1248 ∨ r = 1249 ∨ r = 1250 ∨ r = 1251 ∨ r = 1252 ∨ r = 1253 ∨ r = 1254 ∨ r = 1255 ∨ r = 1256 ∨ r = 1257 ∨ r = 1258 ∨ r = 1259 ∨ r = 1260 ∨ r = 1261 ∨ r = 1262 ∨ r = 1263 ∨ r = 1264 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨955, by decide, by decide⟩
  · subst r; exact ⟨596, by decide, by decide⟩
  · subst r; exact ⟨978, by decide, by decide⟩
  · subst r; exact ⟨469, by decide, by decide⟩
  · subst r; exact ⟨825, by decide, by decide⟩
  · subst r; exact ⟨318, by decide, by decide⟩
  · subst r; exact ⟨672, by decide, by decide⟩
  · subst r; exact ⟨167, by decide, by decide⟩
  · subst r; exact ⟨519, by decide, by decide⟩
  · subst r; exact ⟨16, by decide, by decide⟩
  · subst r; exact ⟨366, by decide, by decide⟩
  · subst r; exact ⟨135, by decide, by decide⟩
  · subst r; exact ⟨213, by decide, by decide⟩
  · subst r; exact ⟨286, by decide, by decide⟩
  · subst r; exact ⟨60, by decide, by decide⟩
  · subst r; exact ⟨437, by decide, by decide⟩
  · subst r; exact ⟨93, by decide, by decide⟩
  · subst r; exact ⟨588, by decide, by decide⟩
  · subst r; exact ⟨246, by decide, by decide⟩
  · subst r; exact ⟨739, by decide, by decide⟩
  · subst r; exact ⟨399, by decide, by decide⟩
  · subst r; exact ⟨890, by decide, by decide⟩
  · subst r; exact ⟨552, by decide, by decide⟩
  · subst r; exact ⟨1022, by decide, by decide⟩
  · subst r; exact ⟨534, by decide, by decide⟩
  · subst r; exact ⟨869, by decide, by decide⟩
  · subst r; exact ⟨383, by decide, by decide⟩
  · subst r; exact ⟨716, by decide, by decide⟩
  · subst r; exact ⟨232, by decide, by decide⟩
  · subst r; exact ⟨563, by decide, by decide⟩
  · subst r; exact ⟨81, by decide, by decide⟩
  · subst r; exact ⟨410, by decide, by decide⟩
  · subst r; exact ⟨70, by decide, by decide⟩
  · subst r; exact ⟨257, by decide, by decide⟩
  · subst r; exact ⟨221, by decide, by decide⟩
  · subst r; exact ⟨104, by decide, by decide⟩
  · subst r; exact ⟨372, by decide, by decide⟩
  · subst r; exact ⟨49, by decide, by decide⟩
  · subst r; exact ⟨523, by decide, by decide⟩
  · subst r; exact ⟨202, by decide, by decide⟩
  · subst r; exact ⟨674, by decide, by decide⟩
  · subst r; exact ⟨355, by decide, by decide⟩
  · subst r; exact ⟨825, by decide, by decide⟩
  · subst r; exact ⟨508, by decide, by decide⟩
  · subst r; exact ⟨976, by decide, by decide⟩
  · subst r; exact ⟨599, by decide, by decide⟩
  · subst r; exact ⟨913, by decide, by decide⟩
  · subst r; exact ⟨448, by decide, by decide⟩
  · subst r; exact ⟨760, by decide, by decide⟩
  · subst r; exact ⟨297, by decide, by decide⟩

theorem slice_4 (r : Nat) (lo : 1265 ≤ r) (hi : r ≤ 1314) : covered r := by
  have h : r = 1265 ∨ r = 1266 ∨ r = 1267 ∨ r = 1268 ∨ r = 1269 ∨ r = 1270 ∨ r = 1271 ∨ r = 1272 ∨ r = 1273 ∨ r = 1274 ∨ r = 1275 ∨ r = 1276 ∨ r = 1277 ∨ r = 1278 ∨ r = 1279 ∨ r = 1280 ∨ r = 1281 ∨ r = 1282 ∨ r = 1283 ∨ r = 1284 ∨ r = 1285 ∨ r = 1286 ∨ r = 1287 ∨ r = 1288 ∨ r = 1289 ∨ r = 1290 ∨ r = 1291 ∨ r = 1292 ∨ r = 1293 ∨ r = 1294 ∨ r = 1295 ∨ r = 1296 ∨ r = 1297 ∨ r = 1298 ∨ r = 1299 ∨ r = 1300 ∨ r = 1301 ∨ r = 1302 ∨ r = 1303 ∨ r = 1304 ∨ r = 1305 ∨ r = 1306 ∨ r = 1307 ∨ r = 1308 ∨ r = 1309 ∨ r = 1310 ∨ r = 1311 ∨ r = 1312 ∨ r = 1313 ∨ r = 1314 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨607, by decide, by decide⟩
  · subst r; exact ⟨146, by decide, by decide⟩
  · subst r; exact ⟨454, by decide, by decide⟩
  · subst r; exact ⟨5, by decide, by decide⟩
  · subst r; exact ⟨301, by decide, by decide⟩
  · subst r; exact ⟨156, by decide, by decide⟩
  · subst r; exact ⟨148, by decide, by decide⟩
  · subst r; exact ⟨307, by decide, by decide⟩
  · subst r; exact ⟨5, by decide, by decide⟩
  · subst r; exact ⟨458, by decide, by decide⟩
  · subst r; exact ⟨158, by decide, by decide⟩
  · subst r; exact ⟨609, by decide, by decide⟩
  · subst r; exact ⟨311, by decide, by decide⟩
  · subst r; exact ⟨760, by decide, by decide⟩
  · subst r; exact ⟨464, by decide, by decide⟩
  · subst r; exact ⟨911, by decide, by decide⟩
  · subst r; exact ⟨617, by decide, by decide⟩
  · subst r; exact ⟨957, by decide, by decide⟩
  · subst r; exact ⟨513, by decide, by decide⟩
  · subst r; exact ⟨804, by decide, by decide⟩
  · subst r; exact ⟨362, by decide, by decide⟩
  · subst r; exact ⟨651, by decide, by decide⟩
  · subst r; exact ⟨211, by decide, by decide⟩
  · subst r; exact ⟨498, by decide, by decide⟩
  · subst r; exact ⟨60, by decide, by decide⟩
  · subst r; exact ⟨345, by decide, by decide⟩
  · subst r; exact ⟨91, by decide, by decide⟩
  · subst r; exact ⟨192, by decide, by decide⟩
  · subst r; exact ⟨242, by decide, by decide⟩
  · subst r; exact ⟨39, by decide, by decide⟩
  · subst r; exact ⟨393, by decide, by decide⟩
  · subst r; exact ⟨114, by decide, by decide⟩
  · subst r; exact ⟨544, by decide, by decide⟩
  · subst r; exact ⟨267, by decide, by decide⟩
  · subst r; exact ⟨695, by decide, by decide⟩
  · subst r; exact ⟨420, by decide, by decide⟩
  · subst r; exact ⟨846, by decide, by decide⟩
  · subst r; exact ⟨573, by decide, by decide⟩
  · subst r; exact ⟨997, by decide, by decide⟩
  · subst r; exact ⟨578, by decide, by decide⟩
  · subst r; exact ⟨848, by decide, by decide⟩
  · subst r; exact ⟨427, by decide, by decide⟩
  · subst r; exact ⟨695, by decide, by decide⟩
  · subst r; exact ⟨276, by decide, by decide⟩
  · subst r; exact ⟨542, by decide, by decide⟩
  · subst r; exact ⟨125, by decide, by decide⟩
  · subst r; exact ⟨389, by decide, by decide⟩
  · subst r; exact ⟨26, by decide, by decide⟩
  · subst r; exact ⟨236, by decide, by decide⟩
  · subst r; exact ⟨177, by decide, by decide⟩

theorem slice_5 (r : Nat) (lo : 1315 ≤ r) (hi : r ≤ 1364) : covered r := by
  have h : r = 1315 ∨ r = 1316 ∨ r = 1317 ∨ r = 1318 ∨ r = 1319 ∨ r = 1320 ∨ r = 1321 ∨ r = 1322 ∨ r = 1323 ∨ r = 1324 ∨ r = 1325 ∨ r = 1326 ∨ r = 1327 ∨ r = 1328 ∨ r = 1329 ∨ r = 1330 ∨ r = 1331 ∨ r = 1332 ∨ r = 1333 ∨ r = 1334 ∨ r = 1335 ∨ r = 1336 ∨ r = 1337 ∨ r = 1338 ∨ r = 1339 ∨ r = 1340 ∨ r = 1341 ∨ r = 1342 ∨ r = 1343 ∨ r = 1344 ∨ r = 1345 ∨ r = 1346 ∨ r = 1347 ∨ r = 1348 ∨ r = 1349 ∨ r = 1350 ∨ r = 1351 ∨ r = 1352 ∨ r = 1353 ∨ r = 1354 ∨ r = 1355 ∨ r = 1356 ∨ r = 1357 ∨ r = 1358 ∨ r = 1359 ∨ r = 1360 ∨ r = 1361 ∨ r = 1362 ∨ r = 1363 ∨ r = 1364 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨83, by decide, by decide⟩
  · subst r; exact ⟨328, by decide, by decide⟩
  · subst r; exact ⟨70, by decide, by decide⟩
  · subst r; exact ⟨479, by decide, by decide⟩
  · subst r; exact ⟨223, by decide, by decide⟩
  · subst r; exact ⟨630, by decide, by decide⟩
  · subst r; exact ⟨376, by decide, by decide⟩
  · subst r; exact ⟨781, by decide, by decide⟩
  · subst r; exact ⟨529, by decide, by decide⟩
  · subst r; exact ⟨932, by decide, by decide⟩
  · subst r; exact ⟨643, by decide, by decide⟩
  · subst r; exact ⟨892, by decide, by decide⟩
  · subst r; exact ⟨492, by decide, by decide⟩
  · subst r; exact ⟨739, by decide, by decide⟩
  · subst r; exact ⟨341, by decide, by decide⟩
  · subst r; exact ⟨586, by decide, by decide⟩
  · subst r; exact ⟨190, by decide, by decide⟩
  · subst r; exact ⟨433, by decide, by decide⟩
  · subst r; exact ⟨39, by decide, by decide⟩
  · subst r; exact ⟨280, by decide, by decide⟩
  · subst r; exact ⟨112, by decide, by decide⟩
  · subst r; exact ⟨127, by decide, by decide⟩
  · subst r; exact ⟨263, by decide, by decide⟩
  · subst r; exact ⟨26, by decide, by decide⟩
  · subst r; exact ⟨414, by decide, by decide⟩
  · subst r; exact ⟨179, by decide, by decide⟩
  · subst r; exact ⟨565, by decide, by decide⟩
  · subst r; exact ⟨332, by decide, by decide⟩
  · subst r; exact ⟨716, by decide, by decide⟩
  · subst r; exact ⟨485, by decide, by decide⟩
  · subst r; exact ⟨867, by decide, by decide⟩
  · subst r; exact ⟨638, by decide, by decide⟩
  · subst r; exact ⟨936, by decide, by decide⟩
  · subst r; exact ⟨557, by decide, by decide⟩
  · subst r; exact ⟨783, by decide, by decide⟩
  · subst r; exact ⟨406, by decide, by decide⟩
  · subst r; exact ⟨630, by decide, by decide⟩
  · subst r; exact ⟨255, by decide, by decide⟩
  · subst r; exact ⟨477, by decide, by decide⟩
  · subst r; exact ⟨104, by decide, by decide⟩
  · subst r; exact ⟨324, by decide, by decide⟩
  · subst r; exact ⟨47, by decide, by decide⟩
  · subst r; exact ⟨171, by decide, by decide⟩
  · subst r; exact ⟨198, by decide, by decide⟩
  · subst r; exact ⟨18, by decide, by decide⟩
  · subst r; exact ⟨349, by decide, by decide⟩
  · subst r; exact ⟨135, by decide, by decide⟩
  · subst r; exact ⟨500, by decide, by decide⟩
  · subst r; exact ⟨288, by decide, by decide⟩
  · subst r; exact ⟨651, by decide, by decide⟩

theorem slice_6 (r : Nat) (lo : 1365 ≤ r) (hi : r ≤ 1414) : covered r := by
  have h : r = 1365 ∨ r = 1366 ∨ r = 1367 ∨ r = 1368 ∨ r = 1369 ∨ r = 1370 ∨ r = 1371 ∨ r = 1372 ∨ r = 1373 ∨ r = 1374 ∨ r = 1375 ∨ r = 1376 ∨ r = 1377 ∨ r = 1378 ∨ r = 1379 ∨ r = 1380 ∨ r = 1381 ∨ r = 1382 ∨ r = 1383 ∨ r = 1384 ∨ r = 1385 ∨ r = 1386 ∨ r = 1387 ∨ r = 1388 ∨ r = 1389 ∨ r = 1390 ∨ r = 1391 ∨ r = 1392 ∨ r = 1393 ∨ r = 1394 ∨ r = 1395 ∨ r = 1396 ∨ r = 1397 ∨ r = 1398 ∨ r = 1399 ∨ r = 1400 ∨ r = 1401 ∨ r = 1402 ∨ r = 1403 ∨ r = 1404 ∨ r = 1405 ∨ r = 1406 ∨ r = 1407 ∨ r = 1408 ∨ r = 1409 ∨ r = 1410 ∨ r = 1411 ∨ r = 1412 ∨ r = 1413 ∨ r = 1414 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨441, by decide, by decide⟩
  · subst r; exact ⟨802, by decide, by decide⟩
  · subst r; exact ⟨594, by decide, by decide⟩
  · subst r; exact ⟨953, by decide, by decide⟩
  · subst r; exact ⟨622, by decide, by decide⟩
  · subst r; exact ⟨827, by decide, by decide⟩
  · subst r; exact ⟨471, by decide, by decide⟩
  · subst r; exact ⟨674, by decide, by decide⟩
  · subst r; exact ⟨320, by decide, by decide⟩
  · subst r; exact ⟨521, by decide, by decide⟩
  · subst r; exact ⟨169, by decide, by decide⟩
  · subst r; exact ⟨368, by decide, by decide⟩
  · subst r; exact ⟨18, by decide, by decide⟩
  · subst r; exact ⟨215, by decide, by decide⟩
  · subst r; exact ⟨133, by decide, by decide⟩
  · subst r; exact ⟨62, by decide, by decide⟩
  · subst r; exact ⟨284, by decide, by decide⟩
  · subst r; exact ⟨91, by decide, by decide⟩
  · subst r; exact ⟨435, by decide, by decide⟩
  · subst r; exact ⟨244, by decide, by decide⟩
  · subst r; exact ⟨586, by decide, by decide⟩
  · subst r; exact ⟨397, by decide, by decide⟩
  · subst r; exact ⟨737, by decide, by decide⟩
  · subst r; exact ⟨550, by decide, by decide⟩
  · subst r; exact ⟨888, by decide, by decide⟩
  · subst r; exact ⟨687, by decide, by decide⟩
  · subst r; exact ⟨871, by decide, by decide⟩
  · subst r; exact ⟨536, by decide, by decide⟩
  · subst r; exact ⟨718, by decide, by decide⟩
  · subst r; exact ⟨385, by decide, by decide⟩
  · subst r; exact ⟨565, by decide, by decide⟩
  · subst r; exact ⟨234, by decide, by decide⟩
  · subst r; exact ⟨412, by decide, by decide⟩
  · subst r; exact ⟨83, by decide, by decide⟩
  · subst r; exact ⟨259, by decide, by decide⟩
  · subst r; exact ⟨68, by decide, by decide⟩
  · subst r; exact ⟨106, by decide, by decide⟩
  · subst r; exact ⟨219, by decide, by decide⟩
  · subst r; exact ⟨47, by decide, by decide⟩
  · subst r; exact ⟨370, by decide, by decide⟩
  · subst r; exact ⟨200, by decide, by decide⟩
  · subst r; exact ⟨521, by decide, by decide⟩
  · subst r; exact ⟨353, by decide, by decide⟩
  · subst r; exact ⟨672, by decide, by decide⟩
  · subst r; exact ⟨506, by decide, by decide⟩
  · subst r; exact ⟨823, by decide, by decide⟩
  · subst r; exact ⟨659, by decide, by decide⟩
  · subst r; exact ⟨915, by decide, by decide⟩
  · subst r; exact ⟨601, by decide, by decide⟩
  · subst r; exact ⟨762, by decide, by decide⟩

theorem slice_7 (r : Nat) (lo : 1415 ≤ r) (hi : r ≤ 1464) : covered r := by
  have h : r = 1415 ∨ r = 1416 ∨ r = 1417 ∨ r = 1418 ∨ r = 1419 ∨ r = 1420 ∨ r = 1421 ∨ r = 1422 ∨ r = 1423 ∨ r = 1424 ∨ r = 1425 ∨ r = 1426 ∨ r = 1427 ∨ r = 1428 ∨ r = 1429 ∨ r = 1430 ∨ r = 1431 ∨ r = 1432 ∨ r = 1433 ∨ r = 1434 ∨ r = 1435 ∨ r = 1436 ∨ r = 1437 ∨ r = 1438 ∨ r = 1439 ∨ r = 1440 ∨ r = 1441 ∨ r = 1442 ∨ r = 1443 ∨ r = 1444 ∨ r = 1445 ∨ r = 1446 ∨ r = 1447 ∨ r = 1448 ∨ r = 1449 ∨ r = 1450 ∨ r = 1451 ∨ r = 1452 ∨ r = 1453 ∨ r = 1454 ∨ r = 1455 ∨ r = 1456 ∨ r = 1457 ∨ r = 1458 ∨ r = 1459 ∨ r = 1460 ∨ r = 1461 ∨ r = 1462 ∨ r = 1463 ∨ r = 1464 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨450, by decide, by decide⟩
  · subst r; exact ⟨609, by decide, by decide⟩
  · subst r; exact ⟨299, by decide, by decide⟩
  · subst r; exact ⟨456, by decide, by decide⟩
  · subst r; exact ⟨148, by decide, by decide⟩
  · subst r; exact ⟨303, by decide, by decide⟩
  · subst r; exact ⟨3, by decide, by decide⟩
  · subst r; exact ⟨150, by decide, by decide⟩
  · subst r; exact ⟨154, by decide, by decide⟩
  · subst r; exact ⟨3, by decide, by decide⟩
  · subst r; exact ⟨305, by decide, by decide⟩
  · subst r; exact ⟨156, by decide, by decide⟩
  · subst r; exact ⟨456, by decide, by decide⟩
  · subst r; exact ⟨309, by decide, by decide⟩
  · subst r; exact ⟨607, by decide, by decide⟩
  · subst r; exact ⟨462, by decide, by decide⟩
  · subst r; exact ⟨758, by decide, by decide⟩
  · subst r; exact ⟨615, by decide, by decide⟩
  · subst r; exact ⟨909, by decide, by decide⟩
  · subst r; exact ⟨666, by decide, by decide⟩
  · subst r; exact ⟨806, by decide, by decide⟩
  · subst r; exact ⟨515, by decide, by decide⟩
  · subst r; exact ⟨653, by decide, by decide⟩
  · subst r; exact ⟨364, by decide, by decide⟩
  · subst r; exact ⟨500, by decide, by decide⟩
  · subst r; exact ⟨213, by decide, by decide⟩
  · subst r; exact ⟨347, by decide, by decide⟩
  · subst r; exact ⟨62, by decide, by decide⟩
  · subst r; exact ⟨194, by decide, by decide⟩
  · subst r; exact ⟨89, by decide, by decide⟩
  · subst r; exact ⟨41, by decide, by decide⟩
  · subst r; exact ⟨240, by decide, by decide⟩
  · subst r; exact ⟨112, by decide, by decide⟩
  · subst r; exact ⟨391, by decide, by decide⟩
  · subst r; exact ⟨265, by decide, by decide⟩
  · subst r; exact ⟨542, by decide, by decide⟩
  · subst r; exact ⟨418, by decide, by decide⟩
  · subst r; exact ⟨693, by decide, by decide⟩
  · subst r; exact ⟨571, by decide, by decide⟩
  · subst r; exact ⟨844, by decide, by decide⟩
  · subst r; exact ⟨724, by decide, by decide⟩
  · subst r; exact ⟨850, by decide, by decide⟩
  · subst r; exact ⟨580, by decide, by decide⟩
  · subst r; exact ⟨697, by decide, by decide⟩
  · subst r; exact ⟨429, by decide, by decide⟩
  · subst r; exact ⟨544, by decide, by decide⟩
  · subst r; exact ⟨278, by decide, by decide⟩
  · subst r; exact ⟨391, by decide, by decide⟩
  · subst r; exact ⟨127, by decide, by decide⟩
  · subst r; exact ⟨238, by decide, by decide⟩

theorem slice_8 (r : Nat) (lo : 1465 ≤ r) (hi : r ≤ 1514) : covered r := by
  have h : r = 1465 ∨ r = 1466 ∨ r = 1467 ∨ r = 1468 ∨ r = 1469 ∨ r = 1470 ∨ r = 1471 ∨ r = 1472 ∨ r = 1473 ∨ r = 1474 ∨ r = 1475 ∨ r = 1476 ∨ r = 1477 ∨ r = 1478 ∨ r = 1479 ∨ r = 1480 ∨ r = 1481 ∨ r = 1482 ∨ r = 1483 ∨ r = 1484 ∨ r = 1485 ∨ r = 1486 ∨ r = 1487 ∨ r = 1488 ∨ r = 1489 ∨ r = 1490 ∨ r = 1491 ∨ r = 1492 ∨ r = 1493 ∨ r = 1494 ∨ r = 1495 ∨ r = 1496 ∨ r = 1497 ∨ r = 1498 ∨ r = 1499 ∨ r = 1500 ∨ r = 1501 ∨ r = 1502 ∨ r = 1503 ∨ r = 1504 ∨ r = 1505 ∨ r = 1506 ∨ r = 1507 ∨ r = 1508 ∨ r = 1509 ∨ r = 1510 ∨ r = 1511 ∨ r = 1512 ∨ r = 1513 ∨ r = 1514 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨24, by decide, by decide⟩
  · subst r; exact ⟨85, by decide, by decide⟩
  · subst r; exact ⟨175, by decide, by decide⟩
  · subst r; exact ⟨68, by decide, by decide⟩
  · subst r; exact ⟨326, by decide, by decide⟩
  · subst r; exact ⟨221, by decide, by decide⟩
  · subst r; exact ⟨477, by decide, by decide⟩
  · subst r; exact ⟨374, by decide, by decide⟩
  · subst r; exact ⟨628, by decide, by decide⟩
  · subst r; exact ⟨527, by decide, by decide⟩
  · subst r; exact ⟨779, by decide, by decide⟩
  · subst r; exact ⟨680, by decide, by decide⟩
  · subst r; exact ⟨894, by decide, by decide⟩
  · subst r; exact ⟨645, by decide, by decide⟩
  · subst r; exact ⟨741, by decide, by decide⟩
  · subst r; exact ⟨494, by decide, by decide⟩
  · subst r; exact ⟨588, by decide, by decide⟩
  · subst r; exact ⟨343, by decide, by decide⟩
  · subst r; exact ⟨435, by decide, by decide⟩
  · subst r; exact ⟨192, by decide, by decide⟩
  · subst r; exact ⟨282, by decide, by decide⟩
  · subst r; exact ⟨41, by decide, by decide⟩
  · subst r; exact ⟨129, by decide, by decide⟩
  · subst r; exact ⟨110, by decide, by decide⟩
  · subst r; exact ⟨24, by decide, by decide⟩
  · subst r; exact ⟨261, by decide, by decide⟩
  · subst r; exact ⟨177, by decide, by decide⟩
  · subst r; exact ⟨412, by decide, by decide⟩
  · subst r; exact ⟨330, by decide, by decide⟩
  · subst r; exact ⟨563, by decide, by decide⟩
  · subst r; exact ⟨483, by decide, by decide⟩
  · subst r; exact ⟨714, by decide, by decide⟩
  · subst r; exact ⟨636, by decide, by decide⟩
  · subst r; exact ⟨865, by decide, by decide⟩
  · subst r; exact ⟨710, by decide, by decide⟩
  · subst r; exact ⟨785, by decide, by decide⟩
  · subst r; exact ⟨559, by decide, by decide⟩
  · subst r; exact ⟨632, by decide, by decide⟩
  · subst r; exact ⟨408, by decide, by decide⟩
  · subst r; exact ⟨479, by decide, by decide⟩
  · subst r; exact ⟨257, by decide, by decide⟩
  · subst r; exact ⟨326, by decide, by decide⟩
  · subst r; exact ⟨106, by decide, by decide⟩
  · subst r; exact ⟨173, by decide, by decide⟩
  · subst r; exact ⟨45, by decide, by decide⟩
  · subst r; exact ⟨20, by decide, by decide⟩
  · subst r; exact ⟨196, by decide, by decide⟩
  · subst r; exact ⟨133, by decide, by decide⟩
  · subst r; exact ⟨347, by decide, by decide⟩
  · subst r; exact ⟨286, by decide, by decide⟩

theorem slice_9 (r : Nat) (lo : 1515 ≤ r) (hi : r ≤ 1564) : covered r := by
  have h : r = 1515 ∨ r = 1516 ∨ r = 1517 ∨ r = 1518 ∨ r = 1519 ∨ r = 1520 ∨ r = 1521 ∨ r = 1522 ∨ r = 1523 ∨ r = 1524 ∨ r = 1525 ∨ r = 1526 ∨ r = 1527 ∨ r = 1528 ∨ r = 1529 ∨ r = 1530 ∨ r = 1531 ∨ r = 1532 ∨ r = 1533 ∨ r = 1534 ∨ r = 1535 ∨ r = 1536 ∨ r = 1537 ∨ r = 1538 ∨ r = 1539 ∨ r = 1540 ∨ r = 1541 ∨ r = 1542 ∨ r = 1543 ∨ r = 1544 ∨ r = 1545 ∨ r = 1546 ∨ r = 1547 ∨ r = 1548 ∨ r = 1549 ∨ r = 1550 ∨ r = 1551 ∨ r = 1552 ∨ r = 1553 ∨ r = 1554 ∨ r = 1555 ∨ r = 1556 ∨ r = 1557 ∨ r = 1558 ∨ r = 1559 ∨ r = 1560 ∨ r = 1561 ∨ r = 1562 ∨ r = 1563 ∨ r = 1564 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨498, by decide, by decide⟩
  · subst r; exact ⟨439, by decide, by decide⟩
  · subst r; exact ⟨649, by decide, by decide⟩
  · subst r; exact ⟨592, by decide, by decide⟩
  · subst r; exact ⟨800, by decide, by decide⟩
  · subst r; exact ⟨745, by decide, by decide⟩
  · subst r; exact ⟨829, by decide, by decide⟩
  · subst r; exact ⟨624, by decide, by decide⟩
  · subst r; exact ⟨676, by decide, by decide⟩
  · subst r; exact ⟨473, by decide, by decide⟩
  · subst r; exact ⟨523, by decide, by decide⟩
  · subst r; exact ⟨322, by decide, by decide⟩
  · subst r; exact ⟨370, by decide, by decide⟩
  · subst r; exact ⟨171, by decide, by decide⟩
  · subst r; exact ⟨217, by decide, by decide⟩
  · subst r; exact ⟨20, by decide, by decide⟩
  · subst r; exact ⟨64, by decide, by decide⟩
  · subst r; exact ⟨131, by decide, by decide⟩
  · subst r; exact ⟨89, by decide, by decide⟩
  · subst r; exact ⟨282, by decide, by decide⟩
  · subst r; exact ⟨242, by decide, by decide⟩
  · subst r; exact ⟨433, by decide, by decide⟩
  · subst r; exact ⟨395, by decide, by decide⟩
  · subst r; exact ⟨584, by decide, by decide⟩
  · subst r; exact ⟨548, by decide, by decide⟩
  · subst r; exact ⟨735, by decide, by decide⟩
  · subst r; exact ⟨701, by decide, by decide⟩
  · subst r; exact ⟨873, by decide, by decide⟩
  · subst r; exact ⟨689, by decide, by decide⟩
  · subst r; exact ⟨720, by decide, by decide⟩
  · subst r; exact ⟨538, by decide, by decide⟩
  · subst r; exact ⟨567, by decide, by decide⟩
  · subst r; exact ⟨387, by decide, by decide⟩
  · subst r; exact ⟨414, by decide, by decide⟩
  · subst r; exact ⟨236, by decide, by decide⟩
  · subst r; exact ⟨261, by decide, by decide⟩
  · subst r; exact ⟨85, by decide, by decide⟩
  · subst r; exact ⟨108, by decide, by decide⟩
  · subst r; exact ⟨66, by decide, by decide⟩
  · subst r; exact ⟨45, by decide, by decide⟩
  · subst r; exact ⟨217, by decide, by decide⟩
  · subst r; exact ⟨198, by decide, by decide⟩
  · subst r; exact ⟨368, by decide, by decide⟩
  · subst r; exact ⟨351, by decide, by decide⟩
  · subst r; exact ⟨519, by decide, by decide⟩
  · subst r; exact ⟨504, by decide, by decide⟩
  · subst r; exact ⟨670, by decide, by decide⟩
  · subst r; exact ⟨657, by decide, by decide⟩
  · subst r; exact ⟨821, by decide, by decide⟩
  · subst r; exact ⟨754, by decide, by decide⟩

theorem slice_10 (r : Nat) (lo : 1565 ≤ r) (hi : r ≤ 1614) : covered r := by
  have h : r = 1565 ∨ r = 1566 ∨ r = 1567 ∨ r = 1568 ∨ r = 1569 ∨ r = 1570 ∨ r = 1571 ∨ r = 1572 ∨ r = 1573 ∨ r = 1574 ∨ r = 1575 ∨ r = 1576 ∨ r = 1577 ∨ r = 1578 ∨ r = 1579 ∨ r = 1580 ∨ r = 1581 ∨ r = 1582 ∨ r = 1583 ∨ r = 1584 ∨ r = 1585 ∨ r = 1586 ∨ r = 1587 ∨ r = 1588 ∨ r = 1589 ∨ r = 1590 ∨ r = 1591 ∨ r = 1592 ∨ r = 1593 ∨ r = 1594 ∨ r = 1595 ∨ r = 1596 ∨ r = 1597 ∨ r = 1598 ∨ r = 1599 ∨ r = 1600 ∨ r = 1601 ∨ r = 1602 ∨ r = 1603 ∨ r = 1604 ∨ r = 1605 ∨ r = 1606 ∨ r = 1607 ∨ r = 1608 ∨ r = 1609 ∨ r = 1610 ∨ r = 1611 ∨ r = 1612 ∨ r = 1613 ∨ r = 1614 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨764, by decide, by decide⟩
  · subst r; exact ⟨603, by decide, by decide⟩
  · subst r; exact ⟨611, by decide, by decide⟩
  · subst r; exact ⟨452, by decide, by decide⟩
  · subst r; exact ⟨458, by decide, by decide⟩
  · subst r; exact ⟨301, by decide, by decide⟩
  · subst r; exact ⟨305, by decide, by decide⟩
  · subst r; exact ⟨150, by decide, by decide⟩
  · subst r; exact ⟨152, by decide, by decide⟩
  · subst r; exact ⟨1, by decide, by decide⟩
  · subst r; exact ⟨1, by decide, by decide⟩
  · subst r; exact ⟨152, by decide, by decide⟩
  · subst r; exact ⟨154, by decide, by decide⟩
  · subst r; exact ⟨303, by decide, by decide⟩
  · subst r; exact ⟨307, by decide, by decide⟩
  · subst r; exact ⟨454, by decide, by decide⟩
  · subst r; exact ⟨460, by decide, by decide⟩
  · subst r; exact ⟨605, by decide, by decide⟩
  · subst r; exact ⟨613, by decide, by decide⟩
  · subst r; exact ⟨756, by decide, by decide⟩
  · subst r; exact ⟨766, by decide, by decide⟩
  · subst r; exact ⟨808, by decide, by decide⟩
  · subst r; exact ⟨668, by decide, by decide⟩
  · subst r; exact ⟨655, by decide, by decide⟩
  · subst r; exact ⟨517, by decide, by decide⟩
  · subst r; exact ⟨502, by decide, by decide⟩
  · subst r; exact ⟨366, by decide, by decide⟩
  · subst r; exact ⟨349, by decide, by decide⟩
  · subst r; exact ⟨215, by decide, by decide⟩
  · subst r; exact ⟨196, by decide, by decide⟩
  · subst r; exact ⟨64, by decide, by decide⟩
  · subst r; exact ⟨43, by decide, by decide⟩
  · subst r; exact ⟨87, by decide, by decide⟩
  · subst r; exact ⟨110, by decide, by decide⟩
  · subst r; exact ⟨238, by decide, by decide⟩
  · subst r; exact ⟨263, by decide, by decide⟩
  · subst r; exact ⟨389, by decide, by decide⟩
  · subst r; exact ⟨416, by decide, by decide⟩
  · subst r; exact ⟨540, by decide, by decide⟩
  · subst r; exact ⟨569, by decide, by decide⟩
  · subst r; exact ⟨691, by decide, by decide⟩
  · subst r; exact ⟨722, by decide, by decide⟩
  · subst r; exact ⟨842, by decide, by decide⟩
  · subst r; exact ⟨733, by decide, by decide⟩
  · subst r; exact ⟨699, by decide, by decide⟩
  · subst r; exact ⟨582, by decide, by decide⟩
  · subst r; exact ⟨546, by decide, by decide⟩
  · subst r; exact ⟨431, by decide, by decide⟩
  · subst r; exact ⟨393, by decide, by decide⟩
  · subst r; exact ⟨280, by decide, by decide⟩

theorem slice_11 (r : Nat) (lo : 1615 ≤ r) (hi : r ≤ 1664) : covered r := by
  have h : r = 1615 ∨ r = 1616 ∨ r = 1617 ∨ r = 1618 ∨ r = 1619 ∨ r = 1620 ∨ r = 1621 ∨ r = 1622 ∨ r = 1623 ∨ r = 1624 ∨ r = 1625 ∨ r = 1626 ∨ r = 1627 ∨ r = 1628 ∨ r = 1629 ∨ r = 1630 ∨ r = 1631 ∨ r = 1632 ∨ r = 1633 ∨ r = 1634 ∨ r = 1635 ∨ r = 1636 ∨ r = 1637 ∨ r = 1638 ∨ r = 1639 ∨ r = 1640 ∨ r = 1641 ∨ r = 1642 ∨ r = 1643 ∨ r = 1644 ∨ r = 1645 ∨ r = 1646 ∨ r = 1647 ∨ r = 1648 ∨ r = 1649 ∨ r = 1650 ∨ r = 1651 ∨ r = 1652 ∨ r = 1653 ∨ r = 1654 ∨ r = 1655 ∨ r = 1656 ∨ r = 1657 ∨ r = 1658 ∨ r = 1659 ∨ r = 1660 ∨ r = 1661 ∨ r = 1662 ∨ r = 1663 ∨ r = 1664 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨240, by decide, by decide⟩
  · subst r; exact ⟨129, by decide, by decide⟩
  · subst r; exact ⟨87, by decide, by decide⟩
  · subst r; exact ⟨22, by decide, by decide⟩
  · subst r; exact ⟨66, by decide, by decide⟩
  · subst r; exact ⟨173, by decide, by decide⟩
  · subst r; exact ⟨219, by decide, by decide⟩
  · subst r; exact ⟨324, by decide, by decide⟩
  · subst r; exact ⟨372, by decide, by decide⟩
  · subst r; exact ⟨475, by decide, by decide⟩
  · subst r; exact ⟨525, by decide, by decide⟩
  · subst r; exact ⟨626, by decide, by decide⟩
  · subst r; exact ⟨678, by decide, by decide⟩
  · subst r; exact ⟨777, by decide, by decide⟩
  · subst r; exact ⟨798, by decide, by decide⟩
  · subst r; exact ⟨743, by decide, by decide⟩
  · subst r; exact ⟨647, by decide, by decide⟩
  · subst r; exact ⟨590, by decide, by decide⟩
  · subst r; exact ⟨496, by decide, by decide⟩
  · subst r; exact ⟨437, by decide, by decide⟩
  · subst r; exact ⟨345, by decide, by decide⟩
  · subst r; exact ⟨284, by decide, by decide⟩
  · subst r; exact ⟨194, by decide, by decide⟩
  · subst r; exact ⟨131, by decide, by decide⟩
  · subst r; exact ⟨43, by decide, by decide⟩
  · subst r; exact ⟨22, by decide, by decide⟩
  · subst r; exact ⟨108, by decide, by decide⟩
  · subst r; exact ⟨175, by decide, by decide⟩
  · subst r; exact ⟨259, by decide, by decide⟩
  · subst r; exact ⟨328, by decide, by decide⟩
  · subst r; exact ⟨410, by decide, by decide⟩
  · subst r; exact ⟨481, by decide, by decide⟩
  · subst r; exact ⟨561, by decide, by decide⟩
  · subst r; exact ⟨634, by decide, by decide⟩
  · subst r; exact ⟨712, by decide, by decide⟩
  · subst r; exact ⟨787, by decide, by decide⟩
  · subst r; exact ⟨787, by decide, by decide⟩
  · subst r; exact ⟨712, by decide, by decide⟩
  · subst r; exact ⟨634, by decide, by decide⟩
  · subst r; exact ⟨561, by decide, by decide⟩
  · subst r; exact ⟨481, by decide, by decide⟩
  · subst r; exact ⟨410, by decide, by decide⟩
  · subst r; exact ⟨328, by decide, by decide⟩
  · subst r; exact ⟨259, by decide, by decide⟩
  · subst r; exact ⟨175, by decide, by decide⟩
  · subst r; exact ⟨108, by decide, by decide⟩
  · subst r; exact ⟨22, by decide, by decide⟩
  · subst r; exact ⟨43, by decide, by decide⟩
  · subst r; exact ⟨131, by decide, by decide⟩
  · subst r; exact ⟨194, by decide, by decide⟩

theorem slice_12 (r : Nat) (lo : 1665 ≤ r) (hi : r ≤ 1714) : covered r := by
  have h : r = 1665 ∨ r = 1666 ∨ r = 1667 ∨ r = 1668 ∨ r = 1669 ∨ r = 1670 ∨ r = 1671 ∨ r = 1672 ∨ r = 1673 ∨ r = 1674 ∨ r = 1675 ∨ r = 1676 ∨ r = 1677 ∨ r = 1678 ∨ r = 1679 ∨ r = 1680 ∨ r = 1681 ∨ r = 1682 ∨ r = 1683 ∨ r = 1684 ∨ r = 1685 ∨ r = 1686 ∨ r = 1687 ∨ r = 1688 ∨ r = 1689 ∨ r = 1690 ∨ r = 1691 ∨ r = 1692 ∨ r = 1693 ∨ r = 1694 ∨ r = 1695 ∨ r = 1696 ∨ r = 1697 ∨ r = 1698 ∨ r = 1699 ∨ r = 1700 ∨ r = 1701 ∨ r = 1702 ∨ r = 1703 ∨ r = 1704 ∨ r = 1705 ∨ r = 1706 ∨ r = 1707 ∨ r = 1708 ∨ r = 1709 ∨ r = 1710 ∨ r = 1711 ∨ r = 1712 ∨ r = 1713 ∨ r = 1714 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨284, by decide, by decide⟩
  · subst r; exact ⟨345, by decide, by decide⟩
  · subst r; exact ⟨437, by decide, by decide⟩
  · subst r; exact ⟨496, by decide, by decide⟩
  · subst r; exact ⟨590, by decide, by decide⟩
  · subst r; exact ⟨647, by decide, by decide⟩
  · subst r; exact ⟨743, by decide, by decide⟩
  · subst r; exact ⟨798, by decide, by decide⟩
  · subst r; exact ⟨777, by decide, by decide⟩
  · subst r; exact ⟨678, by decide, by decide⟩
  · subst r; exact ⟨626, by decide, by decide⟩
  · subst r; exact ⟨525, by decide, by decide⟩
  · subst r; exact ⟨475, by decide, by decide⟩
  · subst r; exact ⟨372, by decide, by decide⟩
  · subst r; exact ⟨324, by decide, by decide⟩
  · subst r; exact ⟨219, by decide, by decide⟩
  · subst r; exact ⟨173, by decide, by decide⟩
  · subst r; exact ⟨66, by decide, by decide⟩
  · subst r; exact ⟨22, by decide, by decide⟩
  · subst r; exact ⟨87, by decide, by decide⟩
  · subst r; exact ⟨129, by decide, by decide⟩
  · subst r; exact ⟨240, by decide, by decide⟩
  · subst r; exact ⟨280, by decide, by decide⟩
  · subst r; exact ⟨393, by decide, by decide⟩
  · subst r; exact ⟨431, by decide, by decide⟩
  · subst r; exact ⟨546, by decide, by decide⟩
  · subst r; exact ⟨582, by decide, by decide⟩
  · subst r; exact ⟨699, by decide, by decide⟩
  · subst r; exact ⟨733, by decide, by decide⟩
  · subst r; exact ⟨842, by decide, by decide⟩
  · subst r; exact ⟨722, by decide, by decide⟩
  · subst r; exact ⟨691, by decide, by decide⟩
  · subst r; exact ⟨569, by decide, by decide⟩
  · subst r; exact ⟨540, by decide, by decide⟩
  · subst r; exact ⟨416, by decide, by decide⟩
  · subst r; exact ⟨389, by decide, by decide⟩
  · subst r; exact ⟨263, by decide, by decide⟩
  · subst r; exact ⟨238, by decide, by decide⟩
  · subst r; exact ⟨110, by decide, by decide⟩
  · subst r; exact ⟨87, by decide, by decide⟩
  · subst r; exact ⟨43, by decide, by decide⟩
  · subst r; exact ⟨64, by decide, by decide⟩
  · subst r; exact ⟨196, by decide, by decide⟩
  · subst r; exact ⟨215, by decide, by decide⟩
  · subst r; exact ⟨349, by decide, by decide⟩
  · subst r; exact ⟨366, by decide, by decide⟩
  · subst r; exact ⟨502, by decide, by decide⟩
  · subst r; exact ⟨517, by decide, by decide⟩
  · subst r; exact ⟨655, by decide, by decide⟩
  · subst r; exact ⟨668, by decide, by decide⟩

theorem slice_13 (r : Nat) (lo : 1715 ≤ r) (hi : r ≤ 1764) : covered r := by
  have h : r = 1715 ∨ r = 1716 ∨ r = 1717 ∨ r = 1718 ∨ r = 1719 ∨ r = 1720 ∨ r = 1721 ∨ r = 1722 ∨ r = 1723 ∨ r = 1724 ∨ r = 1725 ∨ r = 1726 ∨ r = 1727 ∨ r = 1728 ∨ r = 1729 ∨ r = 1730 ∨ r = 1731 ∨ r = 1732 ∨ r = 1733 ∨ r = 1734 ∨ r = 1735 ∨ r = 1736 ∨ r = 1737 ∨ r = 1738 ∨ r = 1739 ∨ r = 1740 ∨ r = 1741 ∨ r = 1742 ∨ r = 1743 ∨ r = 1744 ∨ r = 1745 ∨ r = 1746 ∨ r = 1747 ∨ r = 1748 ∨ r = 1749 ∨ r = 1750 ∨ r = 1751 ∨ r = 1752 ∨ r = 1753 ∨ r = 1754 ∨ r = 1755 ∨ r = 1756 ∨ r = 1757 ∨ r = 1758 ∨ r = 1759 ∨ r = 1760 ∨ r = 1761 ∨ r = 1762 ∨ r = 1763 ∨ r = 1764 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨808, by decide, by decide⟩
  · subst r; exact ⟨766, by decide, by decide⟩
  · subst r; exact ⟨756, by decide, by decide⟩
  · subst r; exact ⟨613, by decide, by decide⟩
  · subst r; exact ⟨605, by decide, by decide⟩
  · subst r; exact ⟨460, by decide, by decide⟩
  · subst r; exact ⟨454, by decide, by decide⟩
  · subst r; exact ⟨307, by decide, by decide⟩
  · subst r; exact ⟨303, by decide, by decide⟩
  · subst r; exact ⟨154, by decide, by decide⟩
  · subst r; exact ⟨152, by decide, by decide⟩
  · subst r; exact ⟨1, by decide, by decide⟩
  · subst r; exact ⟨1, by decide, by decide⟩
  · subst r; exact ⟨152, by decide, by decide⟩
  · subst r; exact ⟨150, by decide, by decide⟩
  · subst r; exact ⟨305, by decide, by decide⟩
  · subst r; exact ⟨301, by decide, by decide⟩
  · subst r; exact ⟨458, by decide, by decide⟩
  · subst r; exact ⟨452, by decide, by decide⟩
  · subst r; exact ⟨611, by decide, by decide⟩
  · subst r; exact ⟨603, by decide, by decide⟩
  · subst r; exact ⟨764, by decide, by decide⟩
  · subst r; exact ⟨754, by decide, by decide⟩
  · subst r; exact ⟨821, by decide, by decide⟩
  · subst r; exact ⟨657, by decide, by decide⟩
  · subst r; exact ⟨670, by decide, by decide⟩
  · subst r; exact ⟨504, by decide, by decide⟩
  · subst r; exact ⟨519, by decide, by decide⟩
  · subst r; exact ⟨351, by decide, by decide⟩
  · subst r; exact ⟨368, by decide, by decide⟩
  · subst r; exact ⟨198, by decide, by decide⟩
  · subst r; exact ⟨217, by decide, by decide⟩
  · subst r; exact ⟨45, by decide, by decide⟩
  · subst r; exact ⟨66, by decide, by decide⟩
  · subst r; exact ⟨108, by decide, by decide⟩
  · subst r; exact ⟨85, by decide, by decide⟩
  · subst r; exact ⟨261, by decide, by decide⟩
  · subst r; exact ⟨236, by decide, by decide⟩
  · subst r; exact ⟨414, by decide, by decide⟩
  · subst r; exact ⟨387, by decide, by decide⟩
  · subst r; exact ⟨567, by decide, by decide⟩
  · subst r; exact ⟨538, by decide, by decide⟩
  · subst r; exact ⟨720, by decide, by decide⟩
  · subst r; exact ⟨689, by decide, by decide⟩
  · subst r; exact ⟨873, by decide, by decide⟩
  · subst r; exact ⟨701, by decide, by decide⟩
  · subst r; exact ⟨735, by decide, by decide⟩
  · subst r; exact ⟨548, by decide, by decide⟩
  · subst r; exact ⟨584, by decide, by decide⟩
  · subst r; exact ⟨395, by decide, by decide⟩

theorem slice_14 (r : Nat) (lo : 1765 ≤ r) (hi : r ≤ 1814) : covered r := by
  have h : r = 1765 ∨ r = 1766 ∨ r = 1767 ∨ r = 1768 ∨ r = 1769 ∨ r = 1770 ∨ r = 1771 ∨ r = 1772 ∨ r = 1773 ∨ r = 1774 ∨ r = 1775 ∨ r = 1776 ∨ r = 1777 ∨ r = 1778 ∨ r = 1779 ∨ r = 1780 ∨ r = 1781 ∨ r = 1782 ∨ r = 1783 ∨ r = 1784 ∨ r = 1785 ∨ r = 1786 ∨ r = 1787 ∨ r = 1788 ∨ r = 1789 ∨ r = 1790 ∨ r = 1791 ∨ r = 1792 ∨ r = 1793 ∨ r = 1794 ∨ r = 1795 ∨ r = 1796 ∨ r = 1797 ∨ r = 1798 ∨ r = 1799 ∨ r = 1800 ∨ r = 1801 ∨ r = 1802 ∨ r = 1803 ∨ r = 1804 ∨ r = 1805 ∨ r = 1806 ∨ r = 1807 ∨ r = 1808 ∨ r = 1809 ∨ r = 1810 ∨ r = 1811 ∨ r = 1812 ∨ r = 1813 ∨ r = 1814 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨433, by decide, by decide⟩
  · subst r; exact ⟨242, by decide, by decide⟩
  · subst r; exact ⟨282, by decide, by decide⟩
  · subst r; exact ⟨89, by decide, by decide⟩
  · subst r; exact ⟨131, by decide, by decide⟩
  · subst r; exact ⟨64, by decide, by decide⟩
  · subst r; exact ⟨20, by decide, by decide⟩
  · subst r; exact ⟨217, by decide, by decide⟩
  · subst r; exact ⟨171, by decide, by decide⟩
  · subst r; exact ⟨370, by decide, by decide⟩
  · subst r; exact ⟨322, by decide, by decide⟩
  · subst r; exact ⟨523, by decide, by decide⟩
  · subst r; exact ⟨473, by decide, by decide⟩
  · subst r; exact ⟨676, by decide, by decide⟩
  · subst r; exact ⟨624, by decide, by decide⟩
  · subst r; exact ⟨829, by decide, by decide⟩
  · subst r; exact ⟨745, by decide, by decide⟩
  · subst r; exact ⟨800, by decide, by decide⟩
  · subst r; exact ⟨592, by decide, by decide⟩
  · subst r; exact ⟨649, by decide, by decide⟩
  · subst r; exact ⟨439, by decide, by decide⟩
  · subst r; exact ⟨498, by decide, by decide⟩
  · subst r; exact ⟨286, by decide, by decide⟩
  · subst r; exact ⟨347, by decide, by decide⟩
  · subst r; exact ⟨133, by decide, by decide⟩
  · subst r; exact ⟨196, by decide, by decide⟩
  · subst r; exact ⟨20, by decide, by decide⟩
  · subst r; exact ⟨45, by decide, by decide⟩
  · subst r; exact ⟨173, by decide, by decide⟩
  · subst r; exact ⟨106, by decide, by decide⟩
  · subst r; exact ⟨326, by decide, by decide⟩
  · subst r; exact ⟨257, by decide, by decide⟩
  · subst r; exact ⟨479, by decide, by decide⟩
  · subst r; exact ⟨408, by decide, by decide⟩
  · subst r; exact ⟨632, by decide, by decide⟩
  · subst r; exact ⟨559, by decide, by decide⟩
  · subst r; exact ⟨785, by decide, by decide⟩
  · subst r; exact ⟨710, by decide, by decide⟩
  · subst r; exact ⟨865, by decide, by decide⟩
  · subst r; exact ⟨636, by decide, by decide⟩
  · subst r; exact ⟨714, by decide, by decide⟩
  · subst r; exact ⟨483, by decide, by decide⟩
  · subst r; exact ⟨563, by decide, by decide⟩
  · subst r; exact ⟨330, by decide, by decide⟩
  · subst r; exact ⟨412, by decide, by decide⟩
  · subst r; exact ⟨177, by decide, by decide⟩
  · subst r; exact ⟨261, by decide, by decide⟩
  · subst r; exact ⟨24, by decide, by decide⟩
  · subst r; exact ⟨110, by decide, by decide⟩
  · subst r; exact ⟨129, by decide, by decide⟩

theorem slice_15 (r : Nat) (lo : 1815 ≤ r) (hi : r ≤ 1864) : covered r := by
  have h : r = 1815 ∨ r = 1816 ∨ r = 1817 ∨ r = 1818 ∨ r = 1819 ∨ r = 1820 ∨ r = 1821 ∨ r = 1822 ∨ r = 1823 ∨ r = 1824 ∨ r = 1825 ∨ r = 1826 ∨ r = 1827 ∨ r = 1828 ∨ r = 1829 ∨ r = 1830 ∨ r = 1831 ∨ r = 1832 ∨ r = 1833 ∨ r = 1834 ∨ r = 1835 ∨ r = 1836 ∨ r = 1837 ∨ r = 1838 ∨ r = 1839 ∨ r = 1840 ∨ r = 1841 ∨ r = 1842 ∨ r = 1843 ∨ r = 1844 ∨ r = 1845 ∨ r = 1846 ∨ r = 1847 ∨ r = 1848 ∨ r = 1849 ∨ r = 1850 ∨ r = 1851 ∨ r = 1852 ∨ r = 1853 ∨ r = 1854 ∨ r = 1855 ∨ r = 1856 ∨ r = 1857 ∨ r = 1858 ∨ r = 1859 ∨ r = 1860 ∨ r = 1861 ∨ r = 1862 ∨ r = 1863 ∨ r = 1864 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨41, by decide, by decide⟩
  · subst r; exact ⟨282, by decide, by decide⟩
  · subst r; exact ⟨192, by decide, by decide⟩
  · subst r; exact ⟨435, by decide, by decide⟩
  · subst r; exact ⟨343, by decide, by decide⟩
  · subst r; exact ⟨588, by decide, by decide⟩
  · subst r; exact ⟨494, by decide, by decide⟩
  · subst r; exact ⟨741, by decide, by decide⟩
  · subst r; exact ⟨645, by decide, by decide⟩
  · subst r; exact ⟨894, by decide, by decide⟩
  · subst r; exact ⟨680, by decide, by decide⟩
  · subst r; exact ⟨779, by decide, by decide⟩
  · subst r; exact ⟨527, by decide, by decide⟩
  · subst r; exact ⟨628, by decide, by decide⟩
  · subst r; exact ⟨374, by decide, by decide⟩
  · subst r; exact ⟨477, by decide, by decide⟩
  · subst r; exact ⟨221, by decide, by decide⟩
  · subst r; exact ⟨326, by decide, by decide⟩
  · subst r; exact ⟨68, by decide, by decide⟩
  · subst r; exact ⟨175, by decide, by decide⟩
  · subst r; exact ⟨85, by decide, by decide⟩
  · subst r; exact ⟨24, by decide, by decide⟩
  · subst r; exact ⟨238, by decide, by decide⟩
  · subst r; exact ⟨127, by decide, by decide⟩
  · subst r; exact ⟨391, by decide, by decide⟩
  · subst r; exact ⟨278, by decide, by decide⟩
  · subst r; exact ⟨544, by decide, by decide⟩
  · subst r; exact ⟨429, by decide, by decide⟩
  · subst r; exact ⟨697, by decide, by decide⟩
  · subst r; exact ⟨580, by decide, by decide⟩
  · subst r; exact ⟨850, by decide, by decide⟩
  · subst r; exact ⟨724, by decide, by decide⟩
  · subst r; exact ⟨844, by decide, by decide⟩
  · subst r; exact ⟨571, by decide, by decide⟩
  · subst r; exact ⟨693, by decide, by decide⟩
  · subst r; exact ⟨418, by decide, by decide⟩
  · subst r; exact ⟨542, by decide, by decide⟩
  · subst r; exact ⟨265, by decide, by decide⟩
  · subst r; exact ⟨391, by decide, by decide⟩
  · subst r; exact ⟨112, by decide, by decide⟩
  · subst r; exact ⟨240, by decide, by decide⟩
  · subst r; exact ⟨41, by decide, by decide⟩
  · subst r; exact ⟨89, by decide, by decide⟩
  · subst r; exact ⟨194, by decide, by decide⟩
  · subst r; exact ⟨62, by decide, by decide⟩
  · subst r; exact ⟨347, by decide, by decide⟩
  · subst r; exact ⟨213, by decide, by decide⟩
  · subst r; exact ⟨500, by decide, by decide⟩
  · subst r; exact ⟨364, by decide, by decide⟩
  · subst r; exact ⟨653, by decide, by decide⟩

theorem slice_16 (r : Nat) (lo : 1865 ≤ r) (hi : r ≤ 1914) : covered r := by
  have h : r = 1865 ∨ r = 1866 ∨ r = 1867 ∨ r = 1868 ∨ r = 1869 ∨ r = 1870 ∨ r = 1871 ∨ r = 1872 ∨ r = 1873 ∨ r = 1874 ∨ r = 1875 ∨ r = 1876 ∨ r = 1877 ∨ r = 1878 ∨ r = 1879 ∨ r = 1880 ∨ r = 1881 ∨ r = 1882 ∨ r = 1883 ∨ r = 1884 ∨ r = 1885 ∨ r = 1886 ∨ r = 1887 ∨ r = 1888 ∨ r = 1889 ∨ r = 1890 ∨ r = 1891 ∨ r = 1892 ∨ r = 1893 ∨ r = 1894 ∨ r = 1895 ∨ r = 1896 ∨ r = 1897 ∨ r = 1898 ∨ r = 1899 ∨ r = 1900 ∨ r = 1901 ∨ r = 1902 ∨ r = 1903 ∨ r = 1904 ∨ r = 1905 ∨ r = 1906 ∨ r = 1907 ∨ r = 1908 ∨ r = 1909 ∨ r = 1910 ∨ r = 1911 ∨ r = 1912 ∨ r = 1913 ∨ r = 1914 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨515, by decide, by decide⟩
  · subst r; exact ⟨806, by decide, by decide⟩
  · subst r; exact ⟨666, by decide, by decide⟩
  · subst r; exact ⟨909, by decide, by decide⟩
  · subst r; exact ⟨615, by decide, by decide⟩
  · subst r; exact ⟨758, by decide, by decide⟩
  · subst r; exact ⟨462, by decide, by decide⟩
  · subst r; exact ⟨607, by decide, by decide⟩
  · subst r; exact ⟨309, by decide, by decide⟩
  · subst r; exact ⟨456, by decide, by decide⟩
  · subst r; exact ⟨156, by decide, by decide⟩
  · subst r; exact ⟨305, by decide, by decide⟩
  · subst r; exact ⟨3, by decide, by decide⟩
  · subst r; exact ⟨154, by decide, by decide⟩
  · subst r; exact ⟨150, by decide, by decide⟩
  · subst r; exact ⟨3, by decide, by decide⟩
  · subst r; exact ⟨303, by decide, by decide⟩
  · subst r; exact ⟨148, by decide, by decide⟩
  · subst r; exact ⟨456, by decide, by decide⟩
  · subst r; exact ⟨299, by decide, by decide⟩
  · subst r; exact ⟨609, by decide, by decide⟩
  · subst r; exact ⟨450, by decide, by decide⟩
  · subst r; exact ⟨762, by decide, by decide⟩
  · subst r; exact ⟨601, by decide, by decide⟩
  · subst r; exact ⟨915, by decide, by decide⟩
  · subst r; exact ⟨659, by decide, by decide⟩
  · subst r; exact ⟨823, by decide, by decide⟩
  · subst r; exact ⟨506, by decide, by decide⟩
  · subst r; exact ⟨672, by decide, by decide⟩
  · subst r; exact ⟨353, by decide, by decide⟩
  · subst r; exact ⟨521, by decide, by decide⟩
  · subst r; exact ⟨200, by decide, by decide⟩
  · subst r; exact ⟨370, by decide, by decide⟩
  · subst r; exact ⟨47, by decide, by decide⟩
  · subst r; exact ⟨219, by decide, by decide⟩
  · subst r; exact ⟨106, by decide, by decide⟩
  · subst r; exact ⟨68, by decide, by decide⟩
  · subst r; exact ⟨259, by decide, by decide⟩
  · subst r; exact ⟨83, by decide, by decide⟩
  · subst r; exact ⟨412, by decide, by decide⟩
  · subst r; exact ⟨234, by decide, by decide⟩
  · subst r; exact ⟨565, by decide, by decide⟩
  · subst r; exact ⟨385, by decide, by decide⟩
  · subst r; exact ⟨718, by decide, by decide⟩
  · subst r; exact ⟨536, by decide, by decide⟩
  · subst r; exact ⟨871, by decide, by decide⟩
  · subst r; exact ⟨687, by decide, by decide⟩
  · subst r; exact ⟨888, by decide, by decide⟩
  · subst r; exact ⟨550, by decide, by decide⟩
  · subst r; exact ⟨737, by decide, by decide⟩

theorem slice_17 (r : Nat) (lo : 1915 ≤ r) (hi : r ≤ 1964) : covered r := by
  have h : r = 1915 ∨ r = 1916 ∨ r = 1917 ∨ r = 1918 ∨ r = 1919 ∨ r = 1920 ∨ r = 1921 ∨ r = 1922 ∨ r = 1923 ∨ r = 1924 ∨ r = 1925 ∨ r = 1926 ∨ r = 1927 ∨ r = 1928 ∨ r = 1929 ∨ r = 1930 ∨ r = 1931 ∨ r = 1932 ∨ r = 1933 ∨ r = 1934 ∨ r = 1935 ∨ r = 1936 ∨ r = 1937 ∨ r = 1938 ∨ r = 1939 ∨ r = 1940 ∨ r = 1941 ∨ r = 1942 ∨ r = 1943 ∨ r = 1944 ∨ r = 1945 ∨ r = 1946 ∨ r = 1947 ∨ r = 1948 ∨ r = 1949 ∨ r = 1950 ∨ r = 1951 ∨ r = 1952 ∨ r = 1953 ∨ r = 1954 ∨ r = 1955 ∨ r = 1956 ∨ r = 1957 ∨ r = 1958 ∨ r = 1959 ∨ r = 1960 ∨ r = 1961 ∨ r = 1962 ∨ r = 1963 ∨ r = 1964 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨397, by decide, by decide⟩
  · subst r; exact ⟨586, by decide, by decide⟩
  · subst r; exact ⟨244, by decide, by decide⟩
  · subst r; exact ⟨435, by decide, by decide⟩
  · subst r; exact ⟨91, by decide, by decide⟩
  · subst r; exact ⟨284, by decide, by decide⟩
  · subst r; exact ⟨62, by decide, by decide⟩
  · subst r; exact ⟨133, by decide, by decide⟩
  · subst r; exact ⟨215, by decide, by decide⟩
  · subst r; exact ⟨18, by decide, by decide⟩
  · subst r; exact ⟨368, by decide, by decide⟩
  · subst r; exact ⟨169, by decide, by decide⟩
  · subst r; exact ⟨521, by decide, by decide⟩
  · subst r; exact ⟨320, by decide, by decide⟩
  · subst r; exact ⟨674, by decide, by decide⟩
  · subst r; exact ⟨471, by decide, by decide⟩
  · subst r; exact ⟨827, by decide, by decide⟩
  · subst r; exact ⟨622, by decide, by decide⟩
  · subst r; exact ⟨953, by decide, by decide⟩
  · subst r; exact ⟨594, by decide, by decide⟩
  · subst r; exact ⟨802, by decide, by decide⟩
  · subst r; exact ⟨441, by decide, by decide⟩
  · subst r; exact ⟨651, by decide, by decide⟩
  · subst r; exact ⟨288, by decide, by decide⟩
  · subst r; exact ⟨500, by decide, by decide⟩
  · subst r; exact ⟨135, by decide, by decide⟩
  · subst r; exact ⟨349, by decide, by decide⟩
  · subst r; exact ⟨18, by decide, by decide⟩
  · subst r; exact ⟨198, by decide, by decide⟩
  · subst r; exact ⟨171, by decide, by decide⟩
  · subst r; exact ⟨47, by decide, by decide⟩
  · subst r; exact ⟨324, by decide, by decide⟩
  · subst r; exact ⟨104, by decide, by decide⟩
  · subst r; exact ⟨477, by decide, by decide⟩
  · subst r; exact ⟨255, by decide, by decide⟩
  · subst r; exact ⟨630, by decide, by decide⟩
  · subst r; exact ⟨406, by decide, by decide⟩
  · subst r; exact ⟨783, by decide, by decide⟩
  · subst r; exact ⟨557, by decide, by decide⟩
  · subst r; exact ⟨936, by decide, by decide⟩
  · subst r; exact ⟨638, by decide, by decide⟩
  · subst r; exact ⟨867, by decide, by decide⟩
  · subst r; exact ⟨485, by decide, by decide⟩
  · subst r; exact ⟨716, by decide, by decide⟩
  · subst r; exact ⟨332, by decide, by decide⟩
  · subst r; exact ⟨565, by decide, by decide⟩
  · subst r; exact ⟨179, by decide, by decide⟩
  · subst r; exact ⟨414, by decide, by decide⟩
  · subst r; exact ⟨26, by decide, by decide⟩
  · subst r; exact ⟨263, by decide, by decide⟩

theorem slice_18 (r : Nat) (lo : 1965 ≤ r) (hi : r ≤ 2014) : covered r := by
  have h : r = 1965 ∨ r = 1966 ∨ r = 1967 ∨ r = 1968 ∨ r = 1969 ∨ r = 1970 ∨ r = 1971 ∨ r = 1972 ∨ r = 1973 ∨ r = 1974 ∨ r = 1975 ∨ r = 1976 ∨ r = 1977 ∨ r = 1978 ∨ r = 1979 ∨ r = 1980 ∨ r = 1981 ∨ r = 1982 ∨ r = 1983 ∨ r = 1984 ∨ r = 1985 ∨ r = 1986 ∨ r = 1987 ∨ r = 1988 ∨ r = 1989 ∨ r = 1990 ∨ r = 1991 ∨ r = 1992 ∨ r = 1993 ∨ r = 1994 ∨ r = 1995 ∨ r = 1996 ∨ r = 1997 ∨ r = 1998 ∨ r = 1999 ∨ r = 2000 ∨ r = 2001 ∨ r = 2002 ∨ r = 2003 ∨ r = 2004 ∨ r = 2005 ∨ r = 2006 ∨ r = 2007 ∨ r = 2008 ∨ r = 2009 ∨ r = 2010 ∨ r = 2011 ∨ r = 2012 ∨ r = 2013 ∨ r = 2014 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨127, by decide, by decide⟩
  · subst r; exact ⟨112, by decide, by decide⟩
  · subst r; exact ⟨280, by decide, by decide⟩
  · subst r; exact ⟨39, by decide, by decide⟩
  · subst r; exact ⟨433, by decide, by decide⟩
  · subst r; exact ⟨190, by decide, by decide⟩
  · subst r; exact ⟨586, by decide, by decide⟩
  · subst r; exact ⟨341, by decide, by decide⟩
  · subst r; exact ⟨739, by decide, by decide⟩
  · subst r; exact ⟨492, by decide, by decide⟩
  · subst r; exact ⟨892, by decide, by decide⟩
  · subst r; exact ⟨643, by decide, by decide⟩
  · subst r; exact ⟨932, by decide, by decide⟩
  · subst r; exact ⟨529, by decide, by decide⟩
  · subst r; exact ⟨781, by decide, by decide⟩
  · subst r; exact ⟨376, by decide, by decide⟩
  · subst r; exact ⟨630, by decide, by decide⟩
  · subst r; exact ⟨223, by decide, by decide⟩
  · subst r; exact ⟨479, by decide, by decide⟩
  · subst r; exact ⟨70, by decide, by decide⟩
  · subst r; exact ⟨328, by decide, by decide⟩
  · subst r; exact ⟨83, by decide, by decide⟩
  · subst r; exact ⟨177, by decide, by decide⟩
  · subst r; exact ⟨236, by decide, by decide⟩
  · subst r; exact ⟨26, by decide, by decide⟩
  · subst r; exact ⟨389, by decide, by decide⟩
  · subst r; exact ⟨125, by decide, by decide⟩
  · subst r; exact ⟨542, by decide, by decide⟩
  · subst r; exact ⟨276, by decide, by decide⟩
  · subst r; exact ⟨695, by decide, by decide⟩
  · subst r; exact ⟨427, by decide, by decide⟩
  · subst r; exact ⟨848, by decide, by decide⟩
  · subst r; exact ⟨578, by decide, by decide⟩
  · subst r; exact ⟨997, by decide, by decide⟩
  · subst r; exact ⟨573, by decide, by decide⟩
  · subst r; exact ⟨846, by decide, by decide⟩
  · subst r; exact ⟨420, by decide, by decide⟩
  · subst r; exact ⟨695, by decide, by decide⟩
  · subst r; exact ⟨267, by decide, by decide⟩
  · subst r; exact ⟨544, by decide, by decide⟩
  · subst r; exact ⟨114, by decide, by decide⟩
  · subst r; exact ⟨393, by decide, by decide⟩
  · subst r; exact ⟨39, by decide, by decide⟩
  · subst r; exact ⟨242, by decide, by decide⟩
  · subst r; exact ⟨192, by decide, by decide⟩
  · subst r; exact ⟨91, by decide, by decide⟩
  · subst r; exact ⟨345, by decide, by decide⟩
  · subst r; exact ⟨60, by decide, by decide⟩
  · subst r; exact ⟨498, by decide, by decide⟩
  · subst r; exact ⟨211, by decide, by decide⟩

theorem slice_19 (r : Nat) (lo : 2015 ≤ r) (hi : r ≤ 2064) : covered r := by
  have h : r = 2015 ∨ r = 2016 ∨ r = 2017 ∨ r = 2018 ∨ r = 2019 ∨ r = 2020 ∨ r = 2021 ∨ r = 2022 ∨ r = 2023 ∨ r = 2024 ∨ r = 2025 ∨ r = 2026 ∨ r = 2027 ∨ r = 2028 ∨ r = 2029 ∨ r = 2030 ∨ r = 2031 ∨ r = 2032 ∨ r = 2033 ∨ r = 2034 ∨ r = 2035 ∨ r = 2036 ∨ r = 2037 ∨ r = 2038 ∨ r = 2039 ∨ r = 2040 ∨ r = 2041 ∨ r = 2042 ∨ r = 2043 ∨ r = 2044 ∨ r = 2045 ∨ r = 2046 ∨ r = 2047 ∨ r = 2048 ∨ r = 2049 ∨ r = 2050 ∨ r = 2051 ∨ r = 2052 ∨ r = 2053 ∨ r = 2054 ∨ r = 2055 ∨ r = 2056 ∨ r = 2057 ∨ r = 2058 ∨ r = 2059 ∨ r = 2060 ∨ r = 2061 ∨ r = 2062 ∨ r = 2063 ∨ r = 2064 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨651, by decide, by decide⟩
  · subst r; exact ⟨362, by decide, by decide⟩
  · subst r; exact ⟨804, by decide, by decide⟩
  · subst r; exact ⟨513, by decide, by decide⟩
  · subst r; exact ⟨957, by decide, by decide⟩
  · subst r; exact ⟨617, by decide, by decide⟩
  · subst r; exact ⟨911, by decide, by decide⟩
  · subst r; exact ⟨464, by decide, by decide⟩
  · subst r; exact ⟨760, by decide, by decide⟩
  · subst r; exact ⟨311, by decide, by decide⟩
  · subst r; exact ⟨609, by decide, by decide⟩
  · subst r; exact ⟨158, by decide, by decide⟩
  · subst r; exact ⟨458, by decide, by decide⟩
  · subst r; exact ⟨5, by decide, by decide⟩
  · subst r; exact ⟨307, by decide, by decide⟩
  · subst r; exact ⟨148, by decide, by decide⟩
  · subst r; exact ⟨156, by decide, by decide⟩
  · subst r; exact ⟨301, by decide, by decide⟩
  · subst r; exact ⟨5, by decide, by decide⟩
  · subst r; exact ⟨454, by decide, by decide⟩
  · subst r; exact ⟨146, by decide, by decide⟩
  · subst r; exact ⟨607, by decide, by decide⟩
  · subst r; exact ⟨297, by decide, by decide⟩
  · subst r; exact ⟨760, by decide, by decide⟩
  · subst r; exact ⟨448, by decide, by decide⟩
  · subst r; exact ⟨913, by decide, by decide⟩
  · subst r; exact ⟨599, by decide, by decide⟩
  · subst r; exact ⟨976, by decide, by decide⟩
  · subst r; exact ⟨508, by decide, by decide⟩
  · subst r; exact ⟨825, by decide, by decide⟩
  · subst r; exact ⟨355, by decide, by decide⟩
  · subst r; exact ⟨674, by decide, by decide⟩
  · subst r; exact ⟨202, by decide, by decide⟩
  · subst r; exact ⟨523, by decide, by decide⟩
  · subst r; exact ⟨49, by decide, by decide⟩
  · subst r; exact ⟨372, by decide, by decide⟩
  · subst r; exact ⟨104, by decide, by decide⟩
  · subst r; exact ⟨221, by decide, by decide⟩
  · subst r; exact ⟨257, by decide, by decide⟩
  · subst r; exact ⟨70, by decide, by decide⟩
  · subst r; exact ⟨410, by decide, by decide⟩
  · subst r; exact ⟨81, by decide, by decide⟩
  · subst r; exact ⟨563, by decide, by decide⟩
  · subst r; exact ⟨232, by decide, by decide⟩
  · subst r; exact ⟨716, by decide, by decide⟩
  · subst r; exact ⟨383, by decide, by decide⟩
  · subst r; exact ⟨869, by decide, by decide⟩
  · subst r; exact ⟨534, by decide, by decide⟩
  · subst r; exact ⟨1022, by decide, by decide⟩
  · subst r; exact ⟨552, by decide, by decide⟩

theorem slice_20 (r : Nat) (lo : 2065 ≤ r) (hi : r ≤ 2114) : covered r := by
  have h : r = 2065 ∨ r = 2066 ∨ r = 2067 ∨ r = 2068 ∨ r = 2069 ∨ r = 2070 ∨ r = 2071 ∨ r = 2072 ∨ r = 2073 ∨ r = 2074 ∨ r = 2075 ∨ r = 2076 ∨ r = 2077 ∨ r = 2078 ∨ r = 2079 ∨ r = 2080 ∨ r = 2081 ∨ r = 2082 ∨ r = 2083 ∨ r = 2084 ∨ r = 2085 ∨ r = 2086 ∨ r = 2087 ∨ r = 2088 ∨ r = 2089 ∨ r = 2090 ∨ r = 2091 ∨ r = 2092 ∨ r = 2093 ∨ r = 2094 ∨ r = 2095 ∨ r = 2096 ∨ r = 2097 ∨ r = 2098 ∨ r = 2099 ∨ r = 2100 ∨ r = 2101 ∨ r = 2102 ∨ r = 2103 ∨ r = 2104 ∨ r = 2105 ∨ r = 2106 ∨ r = 2107 ∨ r = 2108 ∨ r = 2109 ∨ r = 2110 ∨ r = 2111 ∨ r = 2112 ∨ r = 2113 ∨ r = 2114 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨890, by decide, by decide⟩
  · subst r; exact ⟨399, by decide, by decide⟩
  · subst r; exact ⟨739, by decide, by decide⟩
  · subst r; exact ⟨246, by decide, by decide⟩
  · subst r; exact ⟨588, by decide, by decide⟩
  · subst r; exact ⟨93, by decide, by decide⟩
  · subst r; exact ⟨437, by decide, by decide⟩
  · subst r; exact ⟨60, by decide, by decide⟩
  · subst r; exact ⟨286, by decide, by decide⟩
  · subst r; exact ⟨213, by decide, by decide⟩
  · subst r; exact ⟨135, by decide, by decide⟩
  · subst r; exact ⟨366, by decide, by decide⟩
  · subst r; exact ⟨16, by decide, by decide⟩
  · subst r; exact ⟨519, by decide, by decide⟩
  · subst r; exact ⟨167, by decide, by decide⟩
  · subst r; exact ⟨672, by decide, by decide⟩
  · subst r; exact ⟨318, by decide, by decide⟩
  · subst r; exact ⟨825, by decide, by decide⟩
  · subst r; exact ⟨469, by decide, by decide⟩
  · subst r; exact ⟨978, by decide, by decide⟩
  · subst r; exact ⟨596, by decide, by decide⟩
  · subst r; exact ⟨955, by decide, by decide⟩
  · subst r; exact ⟨443, by decide, by decide⟩
  · subst r; exact ⟨804, by decide, by decide⟩
  · subst r; exact ⟨290, by decide, by decide⟩
  · subst r; exact ⟨653, by decide, by decide⟩
  · subst r; exact ⟨137, by decide, by decide⟩
  · subst r; exact ⟨502, by decide, by decide⟩
  · subst r; exact ⟨16, by decide, by decide⟩
  · subst r; exact ⟨351, by decide, by decide⟩
  · subst r; exact ⟨169, by decide, by decide⟩
  · subst r; exact ⟨200, by decide, by decide⟩
  · subst r; exact ⟨322, by decide, by decide⟩
  · subst r; exact ⟨49, by decide, by decide⟩
  · subst r; exact ⟨475, by decide, by decide⟩
  · subst r; exact ⟨102, by decide, by decide⟩
  · subst r; exact ⟨628, by decide, by decide⟩
  · subst r; exact ⟨253, by decide, by decide⟩
  · subst r; exact ⟨781, by decide, by decide⟩
  · subst r; exact ⟨404, by decide, by decide⟩
  · subst r; exact ⟨934, by decide, by decide⟩
  · subst r; exact ⟨555, by decide, by decide⟩
  · subst r; exact ⟨1020, by decide, by decide⟩
  · subst r; exact ⟨487, by decide, by decide⟩
  · subst r; exact ⟨869, by decide, by decide⟩
  · subst r; exact ⟨334, by decide, by decide⟩
  · subst r; exact ⟨718, by decide, by decide⟩
  · subst r; exact ⟨181, by decide, by decide⟩
  · subst r; exact ⟨567, by decide, by decide⟩
  · subst r; exact ⟨28, by decide, by decide⟩

theorem slice_21 (r : Nat) (lo : 2115 ≤ r) (hi : r ≤ 2164) : covered r := by
  have h : r = 2115 ∨ r = 2116 ∨ r = 2117 ∨ r = 2118 ∨ r = 2119 ∨ r = 2120 ∨ r = 2121 ∨ r = 2122 ∨ r = 2123 ∨ r = 2124 ∨ r = 2125 ∨ r = 2126 ∨ r = 2127 ∨ r = 2128 ∨ r = 2129 ∨ r = 2130 ∨ r = 2131 ∨ r = 2132 ∨ r = 2133 ∨ r = 2134 ∨ r = 2135 ∨ r = 2136 ∨ r = 2137 ∨ r = 2138 ∨ r = 2139 ∨ r = 2140 ∨ r = 2141 ∨ r = 2142 ∨ r = 2143 ∨ r = 2144 ∨ r = 2145 ∨ r = 2146 ∨ r = 2147 ∨ r = 2148 ∨ r = 2149 ∨ r = 2150 ∨ r = 2151 ∨ r = 2152 ∨ r = 2153 ∨ r = 2154 ∨ r = 2155 ∨ r = 2156 ∨ r = 2157 ∨ r = 2158 ∨ r = 2159 ∨ r = 2160 ∨ r = 2161 ∨ r = 2162 ∨ r = 2163 ∨ r = 2164 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨416, by decide, by decide⟩
  · subst r; exact ⟨125, by decide, by decide⟩
  · subst r; exact ⟨265, by decide, by decide⟩
  · subst r; exact ⟨278, by decide, by decide⟩
  · subst r; exact ⟨114, by decide, by decide⟩
  · subst r; exact ⟨431, by decide, by decide⟩
  · subst r; exact ⟨37, by decide, by decide⟩
  · subst r; exact ⟨584, by decide, by decide⟩
  · subst r; exact ⟨188, by decide, by decide⟩
  · subst r; exact ⟨737, by decide, by decide⟩
  · subst r; exact ⟨339, by decide, by decide⟩
  · subst r; exact ⟨890, by decide, by decide⟩
  · subst r; exact ⟨490, by decide, by decide⟩
  · subst r; exact ⟨1043, by decide, by decide⟩
  · subst r; exact ⟨531, by decide, by decide⟩
  · subst r; exact ⟨934, by decide, by decide⟩
  · subst r; exact ⟨378, by decide, by decide⟩
  · subst r; exact ⟨783, by decide, by decide⟩
  · subst r; exact ⟨225, by decide, by decide⟩
  · subst r; exact ⟨632, by decide, by decide⟩
  · subst r; exact ⟨72, by decide, by decide⟩
  · subst r; exact ⟨481, by decide, by decide⟩
  · subst r; exact ⟨81, by decide, by decide⟩
  · subst r; exact ⟨330, by decide, by decide⟩
  · subst r; exact ⟨234, by decide, by decide⟩
  · subst r; exact ⟨179, by decide, by decide⟩
  · subst r; exact ⟨387, by decide, by decide⟩
  · subst r; exact ⟨28, by decide, by decide⟩
  · subst r; exact ⟨540, by decide, by decide⟩
  · subst r; exact ⟨123, by decide, by decide⟩
  · subst r; exact ⟨693, by decide, by decide⟩
  · subst r; exact ⟨274, by decide, by decide⟩
  · subst r; exact ⟨846, by decide, by decide⟩
  · subst r; exact ⟨425, by decide, by decide⟩
  · subst r; exact ⟨999, by decide, by decide⟩
  · subst r; exact ⟨575, by decide, by decide⟩
  · subst r; exact ⟨999, by decide, by decide⟩
  · subst r; exact ⟨422, by decide, by decide⟩
  · subst r; exact ⟨848, by decide, by decide⟩
  · subst r; exact ⟨269, by decide, by decide⟩
  · subst r; exact ⟨697, by decide, by decide⟩
  · subst r; exact ⟨116, by decide, by decide⟩
  · subst r; exact ⟨546, by decide, by decide⟩
  · subst r; exact ⟨37, by decide, by decide⟩
  · subst r; exact ⟨395, by decide, by decide⟩
  · subst r; exact ⟨190, by decide, by decide⟩
  · subst r; exact ⟨244, by decide, by decide⟩
  · subst r; exact ⟨343, by decide, by decide⟩
  · subst r; exact ⟨93, by decide, by decide⟩
  · subst r; exact ⟨496, by decide, by decide⟩

theorem slice_22 (r : Nat) (lo : 2165 ≤ r) (hi : r ≤ 2214) : covered r := by
  have h : r = 2165 ∨ r = 2166 ∨ r = 2167 ∨ r = 2168 ∨ r = 2169 ∨ r = 2170 ∨ r = 2171 ∨ r = 2172 ∨ r = 2173 ∨ r = 2174 ∨ r = 2175 ∨ r = 2176 ∨ r = 2177 ∨ r = 2178 ∨ r = 2179 ∨ r = 2180 ∨ r = 2181 ∨ r = 2182 ∨ r = 2183 ∨ r = 2184 ∨ r = 2185 ∨ r = 2186 ∨ r = 2187 ∨ r = 2188 ∨ r = 2189 ∨ r = 2190 ∨ r = 2191 ∨ r = 2192 ∨ r = 2193 ∨ r = 2194 ∨ r = 2195 ∨ r = 2196 ∨ r = 2197 ∨ r = 2198 ∨ r = 2199 ∨ r = 2200 ∨ r = 2201 ∨ r = 2202 ∨ r = 2203 ∨ r = 2204 ∨ r = 2205 ∨ r = 2206 ∨ r = 2207 ∨ r = 2208 ∨ r = 2209 ∨ r = 2210 ∨ r = 2211 ∨ r = 2212 ∨ r = 2213 ∨ r = 2214 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨58, by decide, by decide⟩
  · subst r; exact ⟨649, by decide, by decide⟩
  · subst r; exact ⟨209, by decide, by decide⟩
  · subst r; exact ⟨802, by decide, by decide⟩
  · subst r; exact ⟨360, by decide, by decide⟩
  · subst r; exact ⟨955, by decide, by decide⟩
  · subst r; exact ⟨511, by decide, by decide⟩
  · subst r; exact ⟨1064, by decide, by decide⟩
  · subst r; exact ⟨466, by decide, by decide⟩
  · subst r; exact ⟨913, by decide, by decide⟩
  · subst r; exact ⟨313, by decide, by decide⟩
  · subst r; exact ⟨762, by decide, by decide⟩
  · subst r; exact ⟨160, by decide, by decide⟩
  · subst r; exact ⟨611, by decide, by decide⟩
  · subst r; exact ⟨7, by decide, by decide⟩
  · subst r; exact ⟨460, by decide, by decide⟩
  · subst r; exact ⟨146, by decide, by decide⟩
  · subst r; exact ⟨309, by decide, by decide⟩
  · subst r; exact ⟨299, by decide, by decide⟩
  · subst r; exact ⟨158, by decide, by decide⟩
  · subst r; exact ⟨452, by decide, by decide⟩
  · subst r; exact ⟨7, by decide, by decide⟩
  · subst r; exact ⟨605, by decide, by decide⟩
  · subst r; exact ⟨144, by decide, by decide⟩
  · subst r; exact ⟨758, by decide, by decide⟩
  · subst r; exact ⟨295, by decide, by decide⟩
  · subst r; exact ⟨911, by decide, by decide⟩
  · subst r; exact ⟨446, by decide, by decide⟩
  · subst r; exact ⟨1064, by decide, by decide⟩
  · subst r; exact ⟨510, by decide, by decide⟩
  · subst r; exact ⟨978, by decide, by decide⟩
  · subst r; exact ⟨357, by decide, by decide⟩
  · subst r; exact ⟨827, by decide, by decide⟩
  · subst r; exact ⟨204, by decide, by decide⟩
  · subst r; exact ⟨676, by decide, by decide⟩
  · subst r; exact ⟨51, by decide, by decide⟩
  · subst r; exact ⟨525, by decide, by decide⟩
  · subst r; exact ⟨102, by decide, by decide⟩
  · subst r; exact ⟨374, by decide, by decide⟩
  · subst r; exact ⟨255, by decide, by decide⟩
  · subst r; exact ⟨223, by decide, by decide⟩
  · subst r; exact ⟨408, by decide, by decide⟩
  · subst r; exact ⟨72, by decide, by decide⟩
  · subst r; exact ⟨561, by decide, by decide⟩
  · subst r; exact ⟨79, by decide, by decide⟩
  · subst r; exact ⟨714, by decide, by decide⟩
  · subst r; exact ⟨230, by decide, by decide⟩
  · subst r; exact ⟨867, by decide, by decide⟩
  · subst r; exact ⟨381, by decide, by decide⟩
  · subst r; exact ⟨1020, by decide, by decide⟩

theorem slice_23 (r : Nat) (lo : 2215 ≤ r) (hi : r ≤ 2236) : covered r := by
  have h : r = 2215 ∨ r = 2216 ∨ r = 2217 ∨ r = 2218 ∨ r = 2219 ∨ r = 2220 ∨ r = 2221 ∨ r = 2222 ∨ r = 2223 ∨ r = 2224 ∨ r = 2225 ∨ r = 2226 ∨ r = 2227 ∨ r = 2228 ∨ r = 2229 ∨ r = 2230 ∨ r = 2231 ∨ r = 2232 ∨ r = 2233 ∨ r = 2234 ∨ r = 2235 ∨ r = 2236 := by omega
  rcases h with h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h | h
  · subst r; exact ⟨532, by decide, by decide⟩
  · subst r; exact ⟨1043, by decide, by decide⟩
  · subst r; exact ⟨401, by decide, by decide⟩
  · subst r; exact ⟨892, by decide, by decide⟩
  · subst r; exact ⟨248, by decide, by decide⟩
  · subst r; exact ⟨741, by decide, by decide⟩
  · subst r; exact ⟨95, by decide, by decide⟩
  · subst r; exact ⟨590, by decide, by decide⟩
  · subst r; exact ⟨58, by decide, by decide⟩
  · subst r; exact ⟨439, by decide, by decide⟩
  · subst r; exact ⟨211, by decide, by decide⟩
  · subst r; exact ⟨288, by decide, by decide⟩
  · subst r; exact ⟨364, by decide, by decide⟩
  · subst r; exact ⟨137, by decide, by decide⟩
  · subst r; exact ⟨517, by decide, by decide⟩
  · subst r; exact ⟨14, by decide, by decide⟩
  · subst r; exact ⟨670, by decide, by decide⟩
  · subst r; exact ⟨165, by decide, by decide⟩
  · subst r; exact ⟨823, by decide, by decide⟩
  · subst r; exact ⟨316, by decide, by decide⟩
  · subst r; exact ⟨976, by decide, by decide⟩
  · subst r; exact ⟨467, by decide, by decide⟩

theorem all_residues_covered (r : Nat) (hr : r < 3301) : covered r := by
  by_cases hlow : r ≤ 1064
  · exact direct_low r hlow
  by_cases hhigh : 2237 ≤ r
  · exact direct_high r hhigh hr
  by_cases h0 : r ≤ 1114
  · exact slice_0 r (by omega) h0
  by_cases h1 : r ≤ 1164
  · exact slice_1 r (by omega) h1
  by_cases h2 : r ≤ 1214
  · exact slice_2 r (by omega) h2
  by_cases h3 : r ≤ 1264
  · exact slice_3 r (by omega) h3
  by_cases h4 : r ≤ 1314
  · exact slice_4 r (by omega) h4
  by_cases h5 : r ≤ 1364
  · exact slice_5 r (by omega) h5
  by_cases h6 : r ≤ 1414
  · exact slice_6 r (by omega) h6
  by_cases h7 : r ≤ 1464
  · exact slice_7 r (by omega) h7
  by_cases h8 : r ≤ 1514
  · exact slice_8 r (by omega) h8
  by_cases h9 : r ≤ 1564
  · exact slice_9 r (by omega) h9
  by_cases h10 : r ≤ 1614
  · exact slice_10 r (by omega) h10
  by_cases h11 : r ≤ 1664
  · exact slice_11 r (by omega) h11
  by_cases h12 : r ≤ 1714
  · exact slice_12 r (by omega) h12
  by_cases h13 : r ≤ 1764
  · exact slice_13 r (by omega) h13
  by_cases h14 : r ≤ 1814
  · exact slice_14 r (by omega) h14
  by_cases h15 : r ≤ 1864
  · exact slice_15 r (by omega) h15
  by_cases h16 : r ≤ 1914
  · exact slice_16 r (by omega) h16
  by_cases h17 : r ≤ 1964
  · exact slice_17 r (by omega) h17
  by_cases h18 : r ≤ 2014
  · exact slice_18 r (by omega) h18
  by_cases h19 : r ≤ 2064
  · exact slice_19 r (by omega) h19
  by_cases h20 : r ≤ 2114
  · exact slice_20 r (by omega) h20
  by_cases h21 : r ≤ 2164
  · exact slice_21 r (by omega) h21
  by_cases h22 : r ≤ 2214
  · exact slice_22 r (by omega) h22
  exact slice_23 r (by omega) (by omega)

#print axioms all_residues_covered
end SplitPrimeUnitCover
