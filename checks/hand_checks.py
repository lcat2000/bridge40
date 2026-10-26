"""
獨立核對計算書產生器
====================
把七個關鍵項目（預力損失、跨中梁底應力、φMn、Vcw、爆裂力、支承墊、止震塊）以規範公式
逐行重算，輸出 checks/hand_checks.md，最後與程式結果 out/results.json 對照。

獨立性：
- 只匯入 bridge40/params.py（輸入參數）；不匯入 section / analysis / design / report。
- 斷面性質用矩形與梯形拆塊、彎矩用簡支梁公式與卡車閉合解、摩擦與錨碇滑動用分段指數
  函數的解析積分，方法都和主程式不同。
- 程式的「設計選定值」（張拉應力、股數、支承墊尺寸）當作輸入讀入，本計算書檢查它們
  是否滿足規範。

注意：本計算書與主程式都由 AI 撰寫，尚未經人工複核。它的用途是讓結構技師逐行檢查。

用法：python run_all.py 之後執行 python checks/hand_checks.py
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from bridge40 import params as P  # noqa: E402  只用輸入參數

R = json.load(open(os.path.join(ROOT, "out", "results.json"), encoding="utf-8"))

# ---------------------------------------------------------------------------
# 輸出工具
# ---------------------------------------------------------------------------
out = []
compare = []          # (項目, 本計算書, 程式, 單位, 說明)
findings = []         # 核對時發現的事項


def f(x, nd=2):
    """數字格式：千分位、固定小數。"""
    if isinstance(x, str):
        return x
    s = f"{x:,.{nd}f}"
    return s.replace("-", "−")


def h2(t):
    out.append(f"\n## {t}\n")


def h3(t):
    out.append(f"\n### {t}\n")


def para(t):
    out.append(t + "\n")


class Table:
    def __init__(self, head=("#", "項目", "公式〔條號〕", "代入", "結果")):
        self.rows = []
        self.head = head
        self.n = 0

    def row(self, item, formula, subst, result):
        self.n += 1
        self.rows.append((str(self.n), item, formula, subst, result))

    def flush(self):
        out.append("| " + " | ".join(self.head) + " |")
        out.append("|" + " --- |" * len(self.head))
        for r in self.rows:
            out.append("| " + " | ".join(c.replace("|", "\\|") for c in r) + " |")
        out.append("")


def cmp(item, mine, prog, unit, nd=2, note=""):
    compare.append((item, mine, prog, unit, nd, note))


# ---------------------------------------------------------------------------
# 0. 常數與輸入
# ---------------------------------------------------------------------------
L = P.SPAN / 1000                     # 支承中心距 m
LG = P.GIRDER_LEN / 1000              # 梁長 m
XE = P.BEARING_TO_END / 1000          # 支承到梁端 m
HALF = LG / 2
g = P.GAMMA_RC                        # kN/m³
fc, fci, fcd = P.FC_GIRDER, P.FCI_GIRDER, P.FC_DECK
Ec_g, Ec_d, Eci = P.Ec(fc), P.Ec(fcd), P.Ec(fci)
pt = R["pt"]
ns = pt["ns"]
Aps_t = ns * P.AP                     # 每束 mm²
Aps = Aps_t * P.N_TENDON
fj = pt["fj"]
br = R["bearing"]

out.append("# 40 m 後拉預力 I 型梁：獨立核對計算書\n")
para("> 本計算書由 `checks/hand_checks.py` 產生，與主程式一樣由 AI 撰寫，**尚未經人工複核**。"
     "它的用途是讓結構技師逐行檢查：每一行都寫出公式、條號、代入的數字與結果。")
para("**獨立性**：產生器只讀 `bridge40/params.py` 的輸入參數，不呼叫主程式的斷面、分析與設計模組；"
     "斷面性質用拆塊、彎矩用簡支梁公式與卡車閉合解、摩擦與錨碇滑動用分段指數函數的解析積分。"
     "但條文的理解方式與主程式出自同一來源，條文讀錯時兩者會一起錯，這正是需要人工複核的地方。")
para("**依據**：交通部「公路橋梁設計規範」（98 年版，含 104、109 年修訂，以下稱〔設〕）、"
     "「公路橋梁耐震設計規範」（107 年 12 月版，以下稱〔耐〕）。〔設〕的公式以 kgf/cm² 編寫，"
     "本計算書使用規範並列的 MPa 版本。")
para("**單位**：長度 mm（另註 m 者除外）、力 kN 或 N、應力 MPa（拉為正、壓為負，另註明者除外）。")

h2("1. 輸入")
para("取自 `params.py`：")
t = Table(("項目", "值", "來源"))
t.rows = [
    ("跨徑 L／梁長 Lg", f"{f(L, 1)} m／{f(LG, 1)} m", "params"),
    ("梁數、梁距 S", f"{P.N_GIRDER} 支、{f(P.SPACING, 0)} mm", "params"),
    ("橋面版厚／托肩／鋪面", f"{P.DECK_T}／{P.HAUNCH}／{P.PAVEMENT_T} mm", "params"),
    ("梁 f'c／f'ci／版 f'c", f"{f(fc, 0)}／{f(fci, 0)}／{f(fcd, 0)} MPa", "params"),
    ("Ec = 0.0428 w^1.5 √f'c（w = 2,320）", f"梁 {f(Ec_g, 0)}、版與施預力時 {f(Ec_d, 0)} MPa", "〔設〕(8-8)"),
    ("單位重", f"{f(g, 3)} kN/m³（2,400 kgf/m³）", "〔設〕3.3"),
    ("鋼絞線 f's／Ep／單股面積", f"{f(P.FPU, 0)} MPa／{f(P.EP, 0)} MPa／{f(P.AP, 0)} mm²", "params"),
    ("摩擦 K／μ／錨碇滑動 Δ", f"{P.FRICTION_K}/m／{P.FRICTION_MU}／{P.ANCHOR_SET} mm", "〔設〕表 8.1；Δ 為假設"),
    ("側向 S 彎（每處）", f"{P.LATERAL_ALPHA} rad，位於 0.35–0.45 Lg 與 0.55–0.65 Lg", "假設"),
    ("相對濕度 RH", f"{f(P.RH, 0)} %", "〔設〕8.16.2"),
]
t.flush()
para("取自程式的**設計選定值**（本計算書當輸入，並檢查它們是否滿足規範）：")
t = Table(("項目", "值"))
t.rows = [
    ("每束股數", f"{ns} 股（每束 Aps = {f(Aps_t, 0)} mm²，全梁 {f(Aps, 0)} mm²）"),
    ("張拉應力 fj（T1–T4）", "、".join(f(v, 1) for v in fj) + " MPa；張拉端 " + "、".join(
        "左" if e == "L" else "右" for e in P.JACK_END)),
    ("支承墊", f"{br['L']} × {br['W']} mm；內層 {br['n_int']} × {br['hri']} mm、外層 2 × {f(br['hc'], 0)} mm、"
               f"鋼板 {br['n_int'] + 1} × {f(br['hs'], 0)} mm"),
]
t.flush()

# ---------------------------------------------------------------------------
# 2. 斷面性質（拆塊）
# ---------------------------------------------------------------------------


def rect(b, hgt, y0):
    return (b * hgt, y0 + hgt / 2, b * hgt ** 3 / 12)


def trap(a, b, hgt, y0):
    """a：下緣寬、b：上緣寬。"""
    A = (a + b) * hgt / 2
    yc = y0 + hgt * (a + 2 * b) / (3 * (a + b))
    I0 = hgt ** 3 * (a * a + 4 * a * b + b * b) / (36 * (a + b))
    return (A, yc, I0)


def combine(parts):
    A = sum(p[0] for p in parts)
    yb = sum(p[0] * p[1] for p in parts) / A
    I = sum(p[2] + p[0] * (p[1] - yb) ** 2 for p in parts)
    return A, yb, I


h2("2. 斷面性質（預備計算）")
para("跨中斷面拆成五塊（自梁底起算 y）：底翼 700 × 200、底部梯形 700→250 高 200、腹板 250 × 1,450、"
     "頂部梯形 250→1,000 高 100、頂翼 1,000 × 150。梯形形心 y = y0 + h(a + 2b)/[3(a + b)]，"
     "自身慣性矩 I0 = h³(a² + 4ab + b²)/[36(a + b)]，a 為下緣寬。")
parts = [rect(700, 200, 0), trap(700, 250, 200, 200), rect(250, 1450, 400),
         trap(250, 1000, 100, 1850), rect(1000, 150, 1950)]
names = ["底翼", "底部梯形", "腹板", "頂部梯形", "頂翼"]
t = Table(("塊", "A (mm²)", "y (mm)", "A·y (mm³)", "I0 (mm⁴)"))
t.rows = [(n, f(p[0], 0), f(p[1], 1), f(p[0] * p[1], 0), f(p[2], 0)) for n, p in zip(names, parts)]
A, yb, I = combine(parts)
t.rows.append(("合計", f(A, 0), f"yb = ΣAy/ΣA = {f(yb, 1)}", f(sum(p[0] * p[1] for p in parts), 0),
               f"I = Σ[I0 + A(y − yb)²] = {f(I, 0)}"))
t.flush()
yt = P.GIRDER_H - yb
Sb, St = I / yb, I / yt
para(f"Sb = I/yb = {f(I, 0)}/{f(yb, 1)} = **{f(Sb, 0)} mm³**；St = I/yt = {f(I, 0)}/{f(yt, 1)} = **{f(St, 0)} mm³**。")
cmp("梁斷面積 A", A, R["props"]["A"], "mm²", 0)
cmp("梁斷面慣性矩 I", I, R["props"]["I"], "mm⁴", 0)

# 端塊
pe = [rect(700, 1850, 0), trap(700, 1000, 100, 1850), rect(1000, 150, 1950)]
A_e, yb_e, I_e = combine(pe)
para(f"梁端加厚段（端塊，腹板 700）：700 × 1,850 + 梯形 700→1,000 高 100 + 1,000 × 150 → "
     f"A = {f(A_e, 0)} mm²，yb = {f(yb_e, 1)} mm，I = {f(I_e, 0)} mm⁴。")
cmp("端塊 yb", yb_e, R["props"]["yb_end"], "mm", 1)

# 有效翼寬與合成斷面
web_eff = min(6 * P.TOP_FLANGE_T + P.WEB_T, P.TOP_FLANGE_W)
b_eff = min(P.SPAN / 4, 12 * P.DECK_T + web_eff, P.SPACING)
n_m = Ec_d / Ec_g
Ad = b_eff * n_m * P.DECK_T
yd = P.GIRDER_H + P.HAUNCH + P.DECK_T / 2
Ac = A + Ad
ybc = (A * yb + Ad * yd) / Ac
Ic = I + A * (ybc - yb) ** 2 + b_eff * n_m * P.DECK_T ** 3 / 12 + Ad * (yd - ybc) ** 2
hc = P.GIRDER_H + P.HAUNCH + P.DECK_T
Sbc = Ic / ybc
t = Table()
t.row("有效腹板寬", "min(6 t翼 + bw, 頂翼寬)〔設〕8.8.3 1.", f"min(6 × 150 + 250, 1,000)", f"{f(web_eff, 0)} mm")
t.row("有效翼寬 b", "min(L/4, 12 t + 有效腹板寬, 梁距)〔設〕8.8.3 2.", f"min(10,000, 12 × 200 + {f(web_eff, 0)}, 2,400)",
      f"**{f(b_eff, 0)} mm**")
t.row("模數比 n", "Ec,版 / Ec,梁 = √(28/35)", f"{f(Ec_d, 0)}/{f(Ec_g, 0)}", f"{f(n_m, 4)}")
t.row("版轉換面積", "b · n · t（托肩只計重量，不計勁度）", f"{f(b_eff, 0)} × {f(n_m, 4)} × 200", f"{f(Ad, 0)} mm²")
t.row("合成斷面形心", "ybc = (A·yb + Ad·yd)/(A + Ad)，yd = 2,100 + 50 + 100",
      f"({f(A, 0)} × {f(yb, 1)} + {f(Ad, 0)} × {f(yd, 0)})/{f(Ac, 0)}", f"{f(ybc, 1)} mm")
t.row("合成斷面 Ic", "I + A(ybc − yb)² + b n t³/12 + Ad(yd − ybc)²", "—", f"{f(Ic, 0)} mm⁴")
t.row("Sbc", "Ic / ybc", f"{f(Ic, 0)}/{f(ybc, 1)}", f"**{f(Sbc, 0)} mm³**")
t.flush()
cmp("合成斷面 Ic", Ic, R["props"]["comp"]["I"], "mm⁴", 0)

# ---------------------------------------------------------------------------
# 3. 呆載重與彎矩
# ---------------------------------------------------------------------------
h2("3. 呆載重與跨中彎矩（預備計算）")
bar = P.BARRIER
A_bar = (0.5 * 0.075 + (0.5 + 0.35) / 2 * (0.33 - 0.075) + (0.35 + 0.2) / 2 * (0.85 - 0.33))
w_g = A / 1e6 * g
w_deck = P.SPACING / 1000 * P.DECK_T / 1000 * g
w_hau = P.TOP_FLANGE_W / 1000 * P.HAUNCH / 1000 * g
w_bar = 2 * A_bar * g / P.N_GIRDER
w_dw = P.PAVEMENT_T / 1000 * g * P.ROADWAY / 1000 / P.N_GIRDER
bay = (P.SPACING - P.WEB_T) / 1000
P_dm = P.DIAPHRAGM_T / 1000 * bay * P.DIAPHRAGM_H / 1000 * g
P_de = P.DIAPHRAGM_T / 1000 * bay * (P.GIRDER_H - 250) / 1000 * g
w_ex = (A_e - A) / 1e6 * g                  # 端塊增量（全寬段），kN/m
t = Table()
t.row("梁自重", "A · γ", f"{f(A / 1e6, 4)} m² × {f(g, 3)}", f"{f(w_g, 3)} kN/m")
t.row("端塊增量", "(A端 − A) · γ；全寬 1.2 m 後 1.5 m 線性漸減到 0", f"{f((A_e - A) / 1e6, 4)} × {f(g, 3)}",
      f"{f(w_ex, 3)} kN/m")
t.row("橋面版", "S · t · γ", f"2.4 × 0.2 × {f(g, 3)}", f"{f(w_deck, 3)} kN/m")
t.row("托肩", "1.0 × 0.05 × γ", "—", f"{f(w_hau, 3)} kN/m")
t.row("護欄", "2 × A護欄 · γ / 4 梁；A護欄 = 0.5×0.075 + (0.5+0.35)/2×0.255 + (0.35+0.2)/2×0.52",
      f"2 × {f(A_bar, 6)} × {f(g, 3)} / 4", f"{f(w_bar, 3)} kN/m")
t.row("鋪面", "0.075 × γ × 8.0 / 4", "—", f"{f(w_dw, 3)} kN/m")
t.row("跨中隔梁", "0.25 × (2.4 − 0.25) × 1.6 × γ", "—", f"{f(P_dm, 2)} kN")
t.row("梁端隔梁（只進反力）", "0.25 × 2.15 × 1.85 × γ", "—", f"{f(P_de, 2)} kN")
t.flush()


def extra_w(xg):
    """端塊增量分布載重（kN/m），xg 自梁端起算（m）。"""
    xe = min(xg, LG - xg)
    full, tap = P.END_BLOCK_FULL / 1000, P.END_BLOCK_TAPER / 1000
    if xe <= full:
        return w_ex
    if xe <= full + tap:
        return w_ex * (full + tap - xe) / tap
    return 0.0


def M_extra(x, span, offset, n=4000):
    """端塊增量在簡支梁上 x 處的彎矩（kN·m）。span：跨徑；offset：支承相對梁端的位置。
    以梯形法在端塊範圍內積分 w(a)·G(x, a)。"""
    tot = 0.0
    zone = (P.END_BLOCK_FULL + P.END_BLOCK_TAPER) / 1000
    for lo, hi in ((0.0, zone), (LG - zone, LG)):
        da = (hi - lo) / n
        for i in range(n + 1):
            ag = lo + i * da
            a = ag - offset
            if a < 0 or a > span:
                continue
            w = extra_w(ag) * (0.5 if i in (0, n) else 1.0) * da
            Gxa = a * (span - x) / span if a <= x else x * (span - a) / span
            tot += w * Gxa
    return tot


Mg_u = w_g * L ** 2 / 8
Mg_x = M_extra(L / 2, L, XE)
Mg = Mg_u + Mg_x
Mdk = (w_deck + w_hau) * L ** 2 / 8 + P_dm * L / 4
Mnc = Mg + Mdk
Mc = (w_bar + w_dw) * L ** 2 / 8
para("跨中彎矩（支承於兩端支承，跨徑 L = 40 m；梁端懸出 0.4 m 的重量只進支承反力，與程式相同，"
     "對跨中彎矩偏保守約 1.5 kN·m）：")
t = Table()
t.row("梁自重", "w L²/8 + 端塊增量", f"{f(w_g, 3)} × 40²/8 + {f(Mg_x, 2)}", f"{f(Mg, 1)} kN·m")
t.row("版、托肩、跨中隔梁", "w L²/8 + P L/4", f"{f(w_deck + w_hau, 3)} × 40²/8 + {f(P_dm, 2)} × 40/4", f"{f(Mdk, 1)} kN·m")
t.row("非合成斷面合計 Mnc", "", "", f"**{f(Mnc, 1)} kN·m**")
t.row("護欄、鋪面（合成斷面）Mc", "w L²/8", f"{f(w_bar + w_dw, 3)} × 40²/8", f"**{f(Mc, 1)} kN·m**")
t.flush()
Mg1_u = w_g * LG ** 2 / 8
Mg1_x = M_extra(LG / 2, LG, 0.0)
Mg1 = Mg1_u + Mg1_x
para(f"施預力時梁在預鑄場以梁長 Lg = 40.8 m 簡支：Mg1 = {f(w_g, 3)} × 40.8²/8 + 端塊增量 {f(Mg1_x, 2)} = "
     f"**{f(Mg1, 1)} kN·m**。")
cmp("跨中 Mnc", Mnc, R["moments"]["Mnc"], "kN·m", 1)
cmp("跨中 Mc", Mc, R["moments"]["Mc"], "kN·m", 1)

# ---------------------------------------------------------------------------
# 4. 活載重
# ---------------------------------------------------------------------------
h2("4. 活載重彎矩（預備計算）")
axles = [(0.0, P.FRONT_AXLE), (P.AXLE_GAP / 1000, P.AXLE), (2 * P.AXLE_GAP / 1000, P.AXLE)]
Rtot = sum(p for _, p in axles)
xbar = sum(x * p for x, p in axles) / Rtot


def M_under(k):
    """經典閉合解：使跨中平分軸 k 與合力的距離，求軸 k 下的彎矩。"""
    xk = axles[k][0]
    d = xbar - xk
    pos_k = L / 2 - d / 2                       # 軸 k 的位置（自左支承）
    shift = pos_k - xk
    pos = [(x + shift, p) for x, p in axles]
    if any(x < 0 or x > L for x, _ in pos):
        return 0.0, pos_k
    RA = sum(p * (L - x) for x, p in pos) / L
    M = RA * pos_k - sum(p * (pos_k - x) for x, p in pos if x < pos_k)
    return M, pos_k


cands = [M_under(k) for k in range(3)]
k_best = max(range(3), key=lambda k: cands[k][0])
M_tr, pos_tr = cands[k_best]
M_lane = P.LANE_W * L ** 2 / 8 + P.LANE_PM * L / 4
Imp = min(15.24 / (L + 38.1), 0.30)
DF = P.SPACING / 1000 / 1.65
M_LL = DF / 2 * (1 + Imp) * max(M_tr, M_lane)
t = Table()
t.row("合力位置", "x̄ = ΣPx/ΣP（自前軸）", f"(144 × 4.25 + 144 × 8.5)/324", f"{f(xbar, 4)} m")
t.row("卡車最大彎矩", "跨中平分臨界軸與合力之距離；M = RA·x − Σ左側軸 P(x − xi)",
      f"臨界軸 = 第 {k_best + 1} 軸，位於 {f(pos_tr, 4)} m", f"**{f(M_tr, 1)} kN·m**（每車道）")
t.row("車道載重彎矩", "w L²/8 + P L/4〔設〕3.7", f"9.4 × 40²/8 + 80 × 40/4", f"{f(M_lane, 1)} kN·m → 卡車控制")
t.row("衝擊係數", "I = 15.24/(L + 38.1) ≤ 0.30〔設〕3.13", f"15.24/(40 + 38.1)", f"{f(Imp, 4)}")
t.row("輪重分擔", "S/1.65 輪重線〔設〕4.2.2、表 4.1；外梁槓桿法 1.083 較小，取內梁值", "2.4/1.65", f"{f(DF, 4)} 輪重線")
t.row("每梁活載重加衝擊 M(L+I)", "DF/2 × (1 + I) × M", f"{f(DF, 4)}/2 × {f(1 + Imp, 4)} × {f(M_tr, 1)}",
      f"**{f(M_LL, 1)} kN·m**")
t.flush()
para(f"卡車絕對最大彎矩發生在距支承 {f(pos_tr, 2)} m，不在跨中；本計算書把它與跨中呆載重直接相加，略偏保守。")
cmp("HS20-44 卡車最大彎矩", M_tr, R["live"]["M_truck"], "kN·m", 1, "主程式為 OpenSees 影響線")
cmp("每梁 M(L+I)", M_LL, R["moments"]["M_LL"], "kN·m", 1)

# ---------------------------------------------------------------------------
# 5. 摩擦與錨碇滑動
# ---------------------------------------------------------------------------
h2("5. 預力：摩擦、錨碇滑動與跨中應力")
para("鋼腱垂直線形為拋物線 y = y中 + Δy(1 − x/h)²，h = Lg/2 = 20.4 m，曲率 κ = 2Δy/h² 沿全長不變，"
     "所以垂直轉角 αv = κx。側向 S 彎在 0.35–0.45 Lg 與 0.55–0.65 Lg 各線性累計 0.10 rad。"
     "於是摩擦後應力是分段指數函數 f(x) = f(xk)·exp[−ck(x − xk)]，ck = K + μκ + μ·(側彎轉角/段長)"
     "〔設〕8.16.1 (8-1)。")
para("錨碇滑動影響範圍 xset 由 2∫₀^xset [f(x) − f(xset)] dx = Ep·Δ 求得，"
     "每段積分用解析式 ∫f dx = f(xk)[1 − e^(−ck·Δx)]/ck，再以二分法求 xset。")
bounds = [0.0, 0.35 * LG, 0.45 * LG, 0.55 * LG, 0.65 * LG, LG]
lat_rate = [0.0, P.LATERAL_ALPHA / (0.10 * LG), 0.0, P.LATERAL_ALPHA / (0.10 * LG), 0.0]


def tendon_model(tdn, fjack):
    dy = (tdn["y_end"] - tdn["y_mid"]) / 1000
    kappa = 2 * dy / HALF ** 2
    cs = [P.FRICTION_K + P.FRICTION_MU * (kappa + r) for r in lat_rate]
    fk = [fjack]
    for i in range(5):
        fk.append(fk[-1] * math.exp(-cs[i] * (bounds[i + 1] - bounds[i])))

    def fr(x):
        for i in range(5):
            if x <= bounds[i + 1] + 1e-12:
                return fk[i] * math.exp(-cs[i] * (x - bounds[i]))
        return fk[-1]

    def integ(x):
        s = 0.0
        for i in range(5):
            a, b = bounds[i], min(bounds[i + 1], x)
            if b <= a:
                break
            s += fk[i] * (1 - math.exp(-cs[i] * (b - a))) / cs[i]
        return s

    target = P.EP * P.ANCHOR_SET / 1000      # MPa·m
    lo, hi = 0.0, LG
    for _ in range(80):
        mid = (lo + hi) / 2
        area = 2 * (integ(mid) - mid * fr(mid))
        lo, hi = (mid, hi) if area < target else (lo, mid)
    xset = (lo + hi) / 2
    fset = fr(xset)

    def fs(x):
        return 2 * fset - fr(x) if x < xset else fr(x)

    return dict(dy=dy, kappa=kappa, cs=cs, fk=fk, fr=fr, fs=fs, xset=xset, fset=fset,
                anchor=2 * fset - fjack)


TM = [tendon_model(td, fv) for td, fv in zip(P.TENDONS, fj)]
t = Table(("鋼腱", "Δy (m)", "κ = 2Δy/h² (1/m)", "c（無側彎段）", "c（側彎段）", "xset (m)",
           "f(xset) 峰值", "錨碇後端錨 2f(xset) − fj", "跨中 f(20.4 m)"))
f_mid = []
for td, m in zip(P.TENDONS, TM):
    fm = m["fr"](HALF)
    f_mid.append(fm)
    t.rows.append((td["name"], f(m["dy"], 3), f(m["kappa"], 6), f(m["cs"][0], 6), f(m["cs"][1], 6),
                   f(m["xset"], 2), f(m["fset"], 1), f(m["anchor"], 1), f(fm, 1)))
t.flush()
lim_j, lim_a, lim_s = 0.90 * P.FY_STAR, 0.70 * P.FPU, 0.83 * P.FY_STAR
para(f"〔設〕8.15.1 的三個上限：暫時張拉 fj ≤ 0.90 fy\\* = {f(lim_j, 1)}；錨碇後端錨 ≤ 0.70 f's = {f(lim_a, 1)}；"
     f"滑動影響範圍末端 ≤ 0.83 fy\\* = {f(lim_s, 1)} MPa。")
ok_j = all(v <= lim_j for v in fj)
ok_a = all(m["anchor"] <= lim_a + 0.05 for m in TM)
ok_s = all(m["fset"] <= lim_s for m in TM)
para(f"結果：fj 最大 {f(max(fj), 1)}（{'通過' if ok_j else '不通過'}）；端錨最大 {f(max(m['anchor'] for m in TM), 1)}"
     f"（{'通過' if ok_a else '不通過'}）；峰值最大 {f(max(m['fset'] for m in TM), 1)}（{'通過' if ok_s else '不通過'}）。"
     f"跨中位於滑動影響範圍之外，跨中應力只受摩擦影響。")
for i, (m, td) in enumerate(zip(TM, P.TENDONS)):
    cmp(f"{td['name']} 滑動影響範圍 xset", m["xset"], pt["xset"][i], "m", 2)
cmp("四束跨中摩擦後平均應力", sum(f_mid) / 4, sum(pt["mid_after_set"]) / 4, "MPa", 1)

# ---------------------------------------------------------------------------
# 6. 預力損失
# ---------------------------------------------------------------------------
h2("6. 預力損失（〔設〕8.16.2）")
y_mid = [td["y_mid"] for td in P.TENDONS]
F0 = sum(Aps_t * v for v in f_mid)
ycg = sum(Aps_t * v * y for v, y in zip(f_mid, y_mid)) / F0
e_m = yb - ycg
SH = 0.8 * (117.2 - 1.034 * P.RH)
r_m = P.EP / Eci
k_s = 1 / A + e_m ** 2 / I
mg_term = Mg1 * 1e6 * e_m / I
# fcir = (F0 − Aps·ES)·k − Mg1·e/I，ES = 0.5·r·fcir → 線性方程直接解
ES = 0.5 * r_m * (F0 * k_s - mg_term) / (1 + 0.5 * r_m * Aps * k_s)
fcir = ES / (0.5 * r_m)
Pi = F0 - Aps * ES
fcds = Mdk * 1e6 * e_m / I + Mc * 1e6 * (ybc - ycg) / Ic
CRc = 12 * fcir - 7 * fcds
FR = max(0.0, lim_a - sum(f_mid) / 4)
CRs = 34.5 - 0.07 * FR - 0.1 * ES - 0.05 * (SH + CRc)
loss = SH + ES + CRc + CRs
t = Table()
t.row("鋼腱重心（跨中）", "ycg = Σ(F·y)/ΣF", f"四束 y = 270、270、130、130，依各束力加權", f"{f(ycg, 2)} mm")
t.row("偏心 e", "yb − ycg", f"{f(yb, 1)} − {f(ycg, 2)}", f"{f(e_m, 1)} mm")
t.row("乾縮 SH", "0.8(117.2 − 1.034 RH)〔設〕(8-5)", f"0.8 × (117.2 − 1.034 × 80)", f"**{f(SH, 2)} MPa**")
t.row("fcir 的表示式", "fcir = Pi/A + Pi·e²/I − Mg1·e/I，Pi = F0 − Aps·ES〔設〕8.16.2(2)",
      f"F0 = {f(F0 / 1e3, 1)} kN，Mg1 = {f(Mg1, 1)} kN·m", "—")
t.row("彈性縮短 ES", "0.5 (Ep/Eci) fcir〔設〕(8-7)；與上式聯立，ES = 0.5r(F0·k − Mg1e/I)/(1 + 0.5r·Aps·k)，"
      "r = Ep/Eci，k = 1/A + e²/I",
      f"r = {f(r_m, 4)}，k = {k_s:.4e} 1/mm²", f"**{f(ES, 2)} MPa**")
t.row("fcir", "ES/(0.5 r)", f"{f(ES, 2)}/(0.5 × {f(r_m, 4)})", f"{f(fcir, 2)} MPa")
t.row("Pi（施預力後）", "F0 − Aps·ES", f"{f(F0 / 1e3, 1)} − {f(Aps, 0)} × {f(ES, 2)}/1,000", f"{f(Pi / 1e3, 1)} kN")
t.row("fcds", "M版·e/I + Mc·(ybc − ycg)/Ic〔設〕(8-9) 式中定義",
      f"{f(Mdk, 1)}e6 × {f(e_m, 1)}/I + {f(Mc, 1)}e6 × {f(ybc - ycg, 1)}/Ic", f"{f(fcds, 2)} MPa")
t.row("潛變 CRc", "12 fcir − 7 fcds〔設〕(8-9)", f"12 × {f(fcir, 2)} − 7 × {f(fcds, 2)}", f"**{f(CRc, 2)} MPa**")
t.row("FR", "跨中摩擦後應力低於 0.70 f's 的差值〔設〕8.16.2(4)",
      f"平均 {f(sum(f_mid) / 4, 1)} > {f(lim_a, 1)}", f"{f(FR, 2)}")
t.row("鬆弛 CRs", "34.5 − 0.07 FR − 0.1 ES − 0.05(SH + CRc)〔設〕(8-11A)",
      f"34.5 − 0 − 0.1 × {f(ES, 2)} − 0.05 × ({f(SH, 2)} + {f(CRc, 2)})", f"**{f(CRs, 2)} MPa**")
t.row("總損失 Δfs", "SH + ES + CRc + CRs〔設〕(8-3)", f"{f(SH, 2)} + {f(ES, 2)} + {f(CRc, 2)} + {f(CRs, 2)}",
      f"**{f(loss, 2)} MPa**")
fse = [v - loss for v in f_mid]
Pe = sum(Aps_t * v for v in fse)
ycg_e = sum(Aps_t * v * y for v, y in zip(fse, y_mid)) / Pe
t.row("跨中有效預力 Pe", "Σ Aps,束 × (f跨中 − Δfs)", f"1,400 × Σ({', '.join(f(v, 1) for v in fse)})",
      f"**{f(Pe / 1e3, 1)} kN**（fse 平均 {f(sum(fse) / 4, 1)} MPa）")
t.flush()
para(f"〔設〕表 8.2 後拉低鬆弛鋼腱的總損失估計值約 138 MPa；本例詳算 {f(loss, 1)} MPa 較大，偏保守。")
for k, v in (("SH", SH), ("ES", ES), ("CRc", CRc), ("CRs", CRs), ("total", loss)):
    cmp(f"損失 {k if k != 'total' else '合計'}", v, pt["losses"][k], "MPa", 2)
cmp("跨中有效預力 Pe", Pe / 1e3, pt["Pe_mid"], "kN", 1)

# ---------------------------------------------------------------------------
# 7. 跨中梁底使用應力
# ---------------------------------------------------------------------------
h2("7. 跨中梁底使用應力（〔設〕8.15.2 2.）")
e_e = yb - ycg_e
terms = [-Pe / A, -Pe * e_e / Sb, Mnc * 1e6 / Sb, (Mc + M_LL) * 1e6 / Sbc]
fb = sum(terms)
lim_t = 0.498 * math.sqrt(fc)
t = Table()
t.row("預力軸壓", "−Pe/A", f"−{f(Pe, 0)}/{f(A, 0)}", f"{f(terms[0], 3)}")
t.row("預力偏心", "−Pe·e/Sb", f"−{f(Pe, 0)} × {f(e_e, 1)}/{f(Sb, 0)}", f"{f(terms[1], 3)}")
t.row("非合成斷面呆載重", "+Mnc/Sb", f"{f(Mnc, 1)}e6/{f(Sb, 0)}", f"+{f(terms[2], 3)}")
t.row("合成斷面呆載重 + 活載重", "+(Mc + M(L+I))/Sbc", f"({f(Mc, 1)} + {f(M_LL, 1)})e6/{f(Sbc, 0)}",
      f"+{f(terms[3], 3)}")
t.row("梁底應力", "合計", "", f"**{f(fb, 3)} MPa（拉）**")
t.row("容許拉應力", "0.498√f'c（配置握裹鋼筋，一般橋梁）〔設〕8.15.2 2.", f"0.498 × √35",
      f"{f(lim_t, 2)} MPa → 比值 {f(fb / lim_t, 2)}")
t.flush()
cmp("跨中梁底使用應力", fb, R["stress"]["fin_bot_max"], "MPa", 3, "程式值為全梁最大")

# 施預力時（附帶：淨斷面）
Ah = math.pi * (P.DUCT_OD / 2) ** 2
Ih = math.pi * P.DUCT_OD ** 4 / 64


def net_section(ys):
    An = A - len(ys) * Ah
    ybn = (A * yb - Ah * sum(ys)) / An
    In = I + A * (yb - ybn) ** 2 - sum(Ah * (y - ybn) ** 2 + Ih for y in ys)
    return An, ybn, In


def transfer_bottom(xg, net, es=None, dy=0.0):
    """施預力時梁底應力。net：扣除套管開孔；es：彈性縮短損失；dy：鋼絞線重心相對套管中心上移量。"""
    es = ES if es is None else es
    ys_d = [td["y_mid"] + (td["y_end"] - td["y_mid"]) * (1 - xg / HALF) ** 2 for td in P.TENDONS]
    ys = [y + dy for y in ys_d]
    Fi = [Aps_t * (m["fs"](xg if e == "L" else LG - xg) - es) for m, e in zip(TM, P.JACK_END)]
    Pi_ = sum(Fi)
    yc = sum(F * y for F, y in zip(Fi, ys)) / Pi_
    if net:
        Aa, yy, II = net_section(ys_d)
    else:
        Aa, yy, II = A, yb, I
    mg = (w_g * xg * (LG - xg) / 2 + M_extra(xg, LG, 0.0, n=400)) * 1e6
    return -Pi_ / Aa - Pi_ * (yy - yc) * yy / II + mg * yy / II


xs = [2.7 + 0.1 * i for i in range(int((LG - 5.4) / 0.1) + 1)]
fb_g = min((transfer_bottom(x, False), x) for x in xs)
lim_c = -0.55 * fci
# 淨斷面：跨中 fcir 與 ES 也改用淨斷面
An_m, ybn_m, In_m = net_section(y_mid)
e_n = ybn_m - ycg
k_n = 1 / An_m + e_n ** 2 / In_m
ES_n = 0.5 * r_m * (F0 * k_n - Mg1 * 1e6 * e_n / In_m) / (1 + 0.5 * r_m * Aps * k_n)
fb_n = min((transfer_bottom(x, True, ES_n), x) for x in xs)
# 鋼絞線在套管內偏上（跨中下凹段受拉時貼向套管上緣）：重心上移 (ID − 束徑)/2 的估計
d_bundle = 2 * math.sqrt(ns * P.AP / math.pi / 0.6)      # 填充率約 0.6 的等效束徑
dy_s = (P.DUCT_ID - d_bundle) / 2
fb_n2 = min((transfer_bottom(x, True, ES_n, dy_s), x) for x in xs)
fci_req = -fb_n[0] / 0.55


def transfer_terms(xg, net, es):
    ys = [td["y_mid"] + (td["y_end"] - td["y_mid"]) * (1 - xg / HALF) ** 2 for td in P.TENDONS]
    Fi = [Aps_t * (m["fs"](xg if e == "L" else LG - xg) - es) for m, e in zip(TM, P.JACK_END)]
    Pi_ = sum(Fi)
    yc = sum(F * y for F, y in zip(Fi, ys)) / Pi_
    Aa, yy, II = net_section(ys) if net else (A, yb, I)
    mg = w_g * xg * (LG - xg) / 2 + M_extra(xg, LG, 0.0, n=400)
    return dict(Pi=Pi_, yc=yc, A=Aa, yb=yy, I=II, Sb=II / yy, e=yy - yc, Mg=mg,
                t1=-Pi_ / Aa, t2=-Pi_ * (yy - yc) / (II / yy), t3=mg * 1e6 / (II / yy))


h3("附：施預力時梁底壓應力（毛斷面與扣除套管的淨斷面）")
para(f"〔設〕8.15.2 1. 後拉構材施預力時壓應力 ≤ 0.55 f'ci = {f(lim_c, 2)} MPa。施預力時梁以梁長 40.8 m 簡支，"
     f"沿梁長每 0.1 m 計算，取最不利位置。淨斷面扣除 4 支外徑 {f(P.DUCT_OD, 0)} mm 套管（每支 {f(Ah, 0)} mm²），"
     "套管中心取鋼腱線形位置；〔設〕8.17.1。")
tg = transfer_terms(fb_g[1], False, ES)
tn = transfer_terms(fb_n[1], True, ES_n)
t = Table(("#", "項目", "公式", "毛斷面（程式做法）", "淨斷面"))
t.rows = [
    ("1", "位置", "距梁端", f"{f(fb_g[1], 1)} m", f"{f(fb_n[1], 1)} m"),
    ("2", "A／yb／I", "淨：A − 4Ah；yb、I 扣除各孔", f"{f(tg['A'], 0)}／{f(tg['yb'], 1)}／{tg['I']:.4e}",
     f"{f(tn['A'], 0)}／{f(tn['yb'], 1)}／{tn['I']:.4e}"),
    ("3", "ES", "第 6 節公式，A、e、I 換成各自斷面", f"{f(ES, 2)} MPa", f"{f(ES_n, 2)} MPa"),
    ("4", "Pi", "Σ Aps,束 × (錨碇後應力 − ES)", f"{f(tg['Pi'] / 1e3, 1)} kN", f"{f(tn['Pi'] / 1e3, 1)} kN"),
    ("5", "e", "yb − ycg", f"{f(tg['e'], 1)} mm", f"{f(tn['e'], 1)} mm"),
    ("6", "Mg1(x)", "w x(Lg − x)/2 + 端塊增量", f"{f(tg['Mg'], 1)} kN·m", f"{f(tn['Mg'], 1)} kN·m"),
    ("7", "−Pi/A", "", f(tg["t1"], 3), f(tn["t1"], 3)),
    ("8", "−Pi·e/Sb", "", f(tg["t2"], 3), f(tn["t2"], 3)),
    ("9", "+Mg1/Sb", "", f"+{f(tg['t3'], 3)}", f"+{f(tn['t3'], 3)}"),
    ("10", "梁底應力", "7 + 8 + 9", f"**{f(fb_g[0], 2)} MPa**（比值 {f(fb_g[0] / lim_c, 2)}）",
     f"**{f(fb_n[0], 2)} MPa**（比值 {f(fb_n[0] / lim_c, 2)}）"),
]
t.flush()
# 淨斷面對長期損失與使用應力的影響（fcds 在灌漿後，仍用毛斷面）
fcir_n = ES_n / (0.5 * r_m)
CRc_n = 12 * fcir_n - 7 * fcds
CRs_n = 34.5 - 0.07 * FR - 0.1 * ES_n - 0.05 * (SH + CRc_n)
loss_n = SH + ES_n + CRc_n + CRs_n
Pe_n = sum(Aps_t * (v - loss_n) for v in f_mid)
fb_sn = -Pe_n / A - Pe_n * e_e / Sb + Mnc * 1e6 / Sb + (Mc + M_LL) * 1e6 / Sbc
cmp("施預力時梁底最大壓應力（毛斷面）", fb_g[0], R["stress"]["rel_bot_min"], "MPa", 2, f"發生於距梁端 {f(fb_g[1], 1)} m")

# ---------------------------------------------------------------------------
# 8. φMn
# ---------------------------------------------------------------------------
h2("8. 撓曲強度 φMn（〔設〕8.17、8.18）")
dp = hc - ycg_e
p_s = Aps / (b_eff * dp)
beta1 = 0.85
gam = 0.28
fsu = P.FPU * (1 - gam / beta1 * p_s * P.FPU / fcd)
a_blk = Aps * fsu / (0.85 * fcd * b_eff)
Mn = Aps * fsu * dp * (1 - 0.6 * p_s * fsu / fcd)
phi_f = 0.95
phiMn = phi_f * Mn / 1e6
Mu = 1.3 * (Mnc + Mc + 1.67 * M_LL)
idx = p_s * fsu / fcd
t = Table()
t.row("d", "合成斷面高 − 鋼腱重心 = 2,350 − ycg", f"2,350 − {f(ycg_e, 2)}", f"{f(dp, 1)} mm")
t.row("p\\*", "As\\*/(b·d)", f"{f(Aps, 0)}/({f(b_eff, 0)} × {f(dp, 1)})", f"{p_s:.6f}")
t.row("fsu\\*", "f's[1 − (γ\\*/β1)(p\\* f's/f'c)]〔設〕(8-17)；γ\\* = 0.28（低鬆弛），β1 = 0.85；壓力區在橋面版，f'c = 28",
      f"1,860 × [1 − (0.28/0.85) × ({p_s:.6f} × 1,860/28)]", f"**{f(fsu, 1)} MPa**")
t.row("應力塊深 a", "As\\* fsu\\*/(0.85 f'c b)", f"{f(Aps, 0)} × {f(fsu, 1)}/(0.85 × 28 × {f(b_eff, 0)})",
      f"{f(a_blk, 1)} mm < 版厚 200 → 矩形斷面")
t.row("Mn", "As\\* fsu\\* d (1 − 0.6 p\\* fsu\\*/f'c)〔設〕(8-13)",
      f"{f(Aps, 0)} × {f(fsu, 1)} × {f(dp, 1)} × (1 − 0.6 × {f(idx, 4)})", f"{f(Mn / 1e6, 1)} kN·m")
t.row("φMn", "φ = 0.95（後拉場鑄）〔設〕8.14", f"0.95 × {f(Mn / 1e6, 1)}", f"**{f(phiMn, 1)} kN·m**")
t.row("Mu", "1.3[Mnc + Mc + 1.67 M(L+I)]〔設〕3.23 Group I", f"1.3 × [{f(Mnc, 1)} + {f(Mc, 1)} + 1.67 × {f(M_LL, 1)}]",
      f"{f(Mu, 1)} kN·m → Mu/φMn = {f(Mu / phiMn, 3)}")
t.row("鋼材量指數", "p\\* fsu\\*/f'c ≤ 0.36 β1〔設〕(8-20)", f"{f(idx, 4)} ≤ {f(0.36 * beta1, 3)}",
      "通過" if idx <= 0.36 * beta1 else "不通過")
t.flush()
cmp("跨中 φMn", phiMn, R["strength"]["mid"]["phiMn"], "kN·m", 1)
cmp("跨中 Mu", Mu, R["moments"]["Mu"], "kN·m", 1)

# ---------------------------------------------------------------------------
# 9. Vcw
# ---------------------------------------------------------------------------
h2("9. 臨界斷面 Vcw（〔設〕8.20.2 3.）")
x_cr = br["L"] / 2 / 1000 + hc / 2 / 1000          # 支承中心起算 m
xg_cr = x_cr + XE
xe_cr = xg_cr * 1000
bw = P.BOT_FLANGE_W + (P.WEB_T - P.BOT_FLANGE_W) * (xe_cr - P.END_BLOCK_FULL) / P.END_BLOCK_TAPER
tt = (bw - P.WEB_T) / (P.BOT_FLANGE_W - P.WEB_T)
A_x = A + tt * (A_e - A)
yb_x = yb + tt * (yb_e - yb)
I_x = I + tt * (I_e - I)
ys_x = [td["y_mid"] + (td["y_end"] - td["y_mid"]) * (1 - xg_cr / HALF) ** 2 for td in P.TENDONS]
slp = [2 * (td["y_end"] - td["y_mid"]) / 1000 / HALF * (1 - xg_cr / HALF) for td in P.TENDONS]
fs_x = [m["fs"](xg_cr if e == "L" else LG - xg_cr) for m, e in zip(TM, P.JACK_END)]
Pe_i = [Aps_t * (v - loss) for v in fs_x]
Pe_x = sum(Pe_i)
ycg_x = sum(F * y for F, y in zip(Pe_i, ys_x)) / Pe_x
e_x = yb_x - ycg_x
d_x = max(hc - ycg_x, 0.8 * hc)
Vp = sum(F * math.sin(math.atan(s)) for F, s in zip(Pe_i, slp))
Mnc_x = (w_g * x_cr * (L - x_cr) / 2 + M_extra(x_cr, L, XE)
         + (w_deck + w_hau) * x_cr * (L - x_cr) / 2 + P_dm / 2 * x_cr)
# 合成斷面形心：本斷面（端塊漸變段）自己的合成斷面
ybc_x = (A_x * yb_x + Ad * yd) / (A_x + Ad)
yj = ybc_x if ybc_x < 1850 else 1850.0
fpc = Pe_x / A_x - Pe_x * e_x * (yj - yb_x) / I_x + Mnc_x * 1e6 * (yj - yb_x) / I_x
Vcw = (0.29 * math.sqrt(fc) + 0.3 * fpc) * bw * d_x + Vp
# 程式的做法：fpc 取在跨中合成斷面形心高度
yj_p = ybc
fpc_p = Pe_x / A_x - Pe_x * e_x * (yj_p - yb_x) / I_x + Mnc_x * 1e6 * (yj_p - yb_x) / I_x
Vcw_p = (0.29 * math.sqrt(fc) + 0.3 * fpc_p) * bw * d_x + Vp
t = Table()
t.row("臨界斷面位置", "支承面外 h/2 = 墊長/2 + 合成斷面高/2", f"350/2 + 2,350/2", f"距支承中心 {f(x_cr * 1000, 0)} mm（距梁端 {f(xe_cr, 0)}）")
t.row("腹板寬 b'", "端塊 700 自梁端 1.2 m 起 1.5 m 內線性漸變到 250", f"700 − 450 × ({f(xe_cr, 0)} − 1,200)/1,500", f"{f(bw, 0)} mm")
t.row("斷面性質", "依腹板寬在跨中斷面與端塊之間線性內插（與程式相同的近似）",
      f"t = {f(tt, 4)}", f"A = {f(A_x, 0)}，yb = {f(yb_x, 1)}，I = {I_x:.4e}")
t.row("各束有效應力", "錨碇後應力 − Δfs（T1、T3 自本端張拉，T2、T4 為遠端）",
      ", ".join(f(v, 1) for v in fs_x) + f" − {f(loss, 1)}", ", ".join(f(v - loss, 1) for v in fs_x) + " MPa")
t.row("Pe、ycg", "Σ Aps,束 · fse；力加權重心", "", f"Pe = {f(Pe_x / 1e3, 1)} kN，ycg = {f(ycg_x, 1)} mm")
t.row("Vp", "Σ Pe,束 · sin(arctan y')，y' = 2Δy/h·(1 − x/h)", "斜率 " + ", ".join(f(s, 4) for s in slp),
      f"{f(Vp / 1e3, 1)} kN")
t.row("d", "max(hc − ycg, 0.8 h)〔設〕8.20.2 3.", f"max(2,350 − {f(ycg_x, 0)}, 1,880)", f"{f(d_x, 0)} mm")
t.row("Mnc（本斷面）", "w x(L − x)/2 + 端塊增量 + 版托肩 + 隔梁 P/2·x", f"x = {f(x_cr, 3)} m", f"{f(Mnc_x, 1)} kN·m")
t.row("合成斷面形心 yj", "本斷面的合成形心（ybc < 1,850 在腹板內）", f"({f(A_x, 0)} × {f(yb_x, 1)} + {f(Ad, 0)} × 2,250)/{f(A_x + Ad, 0)}",
      f"{f(yj, 1)} mm")
t.row("fpc（壓為正）", "Pe/A − Pe·e·(yj − yb)/I + Mnc·(yj − yb)/I",
      f"{f(Pe_x / A_x, 3)} − {f(Pe_x * e_x * (yj - yb_x) / I_x, 3)} + {f(Mnc_x * 1e6 * (yj - yb_x) / I_x, 3)}",
      f"{f(fpc, 3)} MPa")
t.row("Vcw", "(0.29√f'c + 0.3 fpc) b'd + Vp〔設〕(8-29)",
      f"(0.29 × √35 + 0.3 × {f(fpc, 3)}) × {f(bw, 0)} × {f(d_x, 0)} + {f(Vp / 1e3, 1)} kN", f"**{f(Vcw / 1e3, 1)} kN**")
t.flush()
para(f"若照程式把 yj 取在跨中合成斷面的形心高度 {f(ybc, 1)} mm：fpc = {f(fpc_p, 3)} MPa，Vcw = {f(Vcw_p / 1e3, 1)} kN。")
cmp("臨界斷面 Vcw", Vcw / 1e3, R["shear"]["rc"]["Vcw"] / 1e3, "kN", 1, "差異見第 14 節")
cmp("臨界斷面 Vp", Vp / 1e3, R["shear"]["rc"]["Vp"] / 1e3, "kN", 1)

# ---------------------------------------------------------------------------
# 10. 爆裂力
# ---------------------------------------------------------------------------
h2("10. 錨碇區爆裂力（〔設〕8.21.6 3.）")
Pu = [1.2 * v * Aps_t for v in fj]
slope0 = [2 * (td["y_end"] - td["y_mid"]) / 1000 / HALF for td in P.TENDONS]
para("乘因數鋼腱力 Pu = 1.2 × fj × Aps,束〔設〕8.14："
     + "、".join(f"{td['name']} {f(p / 1e3, 1)} kN" for td, p in zip(P.TENDONS, Pu))
     + "。依張拉順序 T1→T4 逐階段計算（8.21.6 3. 要求考量施預力順序）。"
     "a 取錨碇組在垂直方向的範圍（最上與最下錨碇距離 + 承壓板 270 mm；錨碇間距 400 mm < 1.5a = 405 mm，"
     "屬 8.21.6 1.(4) 的密排）；h = 梁高 2,100；e 取錨碇合力到端塊形心的距離；α 取合力傾角。")
t = Table(("階段", "ΣPu (kN)", "a (mm)", "e (mm)", "α (rad)", "Tburst = 0.25ΣPu(1 − a/h) + 0.5ΣPu·sinα (kN)",
           "dburst = 0.5(h − 2e) + 5e·sinα (mm)"))
stg = []
for m in range(1, 5):
    idxs = list(range(m))
    sP = sum(Pu[i] for i in idxs)
    ys = [P.TENDONS[i]["y_end"] for i in idxs]
    yres = sum(Pu[i] * P.TENDONS[i]["y_end"] for i in idxs) / sP
    a = max(ys) - min(ys) + P.ANCHOR_PLATE
    e = abs(yres - yb_e)
    al = sum(Pu[i] * slope0[i] for i in idxs) / sP
    T = 0.25 * sP * (1 - a / P.GIRDER_H) + 0.5 * sP * math.sin(al)
    dB = 0.5 * (P.GIRDER_H - 2 * e) + 5 * e * math.sin(al)
    stg.append((T, m, dB))
    t.rows.append((f"前 {m} 束", f(sP / 1e3, 1), f(a, 0), f(e, 1), f(al, 4),
                   f"0.25 × {f(sP / 1e3, 1)} × (1 − {f(a, 0)}/2,100) + 0.5 × {f(sP / 1e3, 1)} × {f(math.sin(al), 4)} = **{f(T / 1e3, 1)}**",
                   f(dB, 0)))
t.flush()
Tg, mg_, dg = max(stg)
As_v = Tg / (0.85 * P.FY)
nv = math.ceil(As_v / (2 * 198.6))
T_h = 0.25 * max(Pu) * (1 - P.ANCHOR_PLATE / P.BOT_FLANGE_W)
para(f"控制階段為前 {mg_} 束：Tburst = **{f(Tg / 1e3, 1)} kN**，dburst = {f(dg, 0)} mm。"
     f"需要鋼筋 As = T/(φ fy) = {f(Tg, 0)}/(0.85 × 420) = **{f(As_v, 0)} mm²**〔φ = 0.85，〔設〕8.14〕，"
     f"D16 雙肢閉合箍每組 397.2 mm² → 需 {f(As_v / 397.2, 2)} 組，取 {nv} 組。")
para(f"水平向（端塊寬 700，每個錨碇各自擴散，e = 0、α = 0）：T = 0.25 × {f(max(Pu) / 1e3, 1)} × (1 − 270/700) = "
     f"**{f(T_h / 1e3, 1)} kN**。")
cmp("垂直爆裂力 Tburst", Tg / 1e3, R["anchor"]["gov"]["T"], "kN", 1)
cmp("dburst", dg, R["anchor"]["gov"]["d"], "mm", 0)
cmp("水平爆裂力（每束）", T_h / 1e3, R["anchor"]["T_h"], "kN", 1)

# ---------------------------------------------------------------------------
# 11. 支承墊
# ---------------------------------------------------------------------------
h2("11. 支承墊（〔設〕10.6.6 方法 B）")
over = XE * (w_g + w_ex + w_deck + w_hau + w_bar + w_dw)
ext_span = w_ex * (P.END_BLOCK_FULL / 1000 - XE) + w_ex * P.END_BLOCK_TAPER / 1000 / 2
R_D = (w_g * L / 2 + ext_span + (w_deck + w_hau) * L / 2 + P_dm / 2 + (w_bar + w_dw) * L / 2 + over + P_de)
DFv = 1.75          # 梁端剪力：橋面版橫向簡支於梁的槓桿法〔設〕4.2.1（程式值，見說明）
Iv = min(15.24 / (L + 38.1), 0.30)
v_tr = (P.AXLE / 2 * DFv * 1.0 + P.AXLE / 2 * DF * (L - 4.25) / L + P.FRONT_AXLE / 2 * DF * (L - 8.5) / L)
v_ln = P.LANE_PV / 2 * DFv + P.LANE_W / 2 * DF * L / 2
R_L = (1 + Iv) * max(v_tr, v_ln)
Lp, Wp, hri, n_int, hce, hs = br["L"], br["W"], br["hri"], br["n_int"], br["hc"], br["hs"]
Gm = 0.86
S_ = Lp * Wp / (2 * hri * (Lp + Wp))
sig = (R_D + R_L) * 1e3 / (Lp * Wp)
lim_sig = min(6.86, 1.0 * Gm * S_)
d_th = P.ALPHA_T * P.TEMP_RANGE * P.SPAN
d_lt = P.LONG_TERM_STRAIN * P.SPAN
d_s = d_th + d_lt
hrt = n_int * hri + 2 * hce
h_tot = hrt + (n_int + 1) * hs
# 轉角：活載重以卡車軸重直接求端部轉角（與程式的均布等值近似不同）
EIc = Ec_g * Ic                                  # N·mm²
best_th = 0.0
for i in range(0, 4001):
    x0 = i * 0.01                                # 後軸位置（m，自左支承），卡車朝右
    th = 0.0
    for off, p in ((0.0, P.AXLE), (4.25, P.AXLE), (8.5, P.FRONT_AXLE)):
        a = x0 - off
        if 0 <= a <= L:
            b_ = L - a
            th += p * 1e3 * (a * 1e3) * (b_ * 1e3) * ((L + b_) * 1e3) / (6 * EIc * L * 1e3)
    best_th = max(best_th, th)
th_ll = best_th * DF / 2 * (1 + Imp)
th_dl = R["bearing"]["th_dl_ps"]
theta = th_dl + th_ll + 0.005
sig_up = 0.5 * Gm * S_ * (Lp / hri) ** 2 * theta / n_int
hs_req = 3 * hri * sig / 250.0
t = Table()
t.row("呆載重反力 Rd", "梁 wL/2 + 端塊增量 + 版托肩 wL/2 + 中隔梁 P/2 + 護欄鋪面 wL/2 + 懸出 0.4 m + 端隔梁",
      f"{f(w_g * L / 2, 1)} + {f(ext_span, 1)} + {f((w_deck + w_hau) * L / 2, 1)} + {f(P_dm / 2, 1)} + "
      f"{f((w_bar + w_dw) * L / 2, 1)} + {f(over, 1)} + {f(P_de, 1)}", f"**{f(R_D, 1)} kN**")
t.row("活載重反力 RL", "(1 + I)·max(卡車, 車道)；支點軸 DF = 1.75（〔設〕4.2.1 簡支法），其餘軸 S/1.65",
      f"卡車 {f(v_tr, 1)}、車道 {f(v_ln, 1)}；× {f(1 + Iv, 4)}", f"**{f(R_L, 1)} kN**")
t.row("形狀係數 S", "L·W/[2 hri (L + W)]（最厚層）", f"{Lp} × {Wp}/(2 × {hri} × {Lp + Wp})", f"{f(S_, 3)}")
t.row("平均壓應力 σTL", "(Rd + RL)/(L·W)", f"{f((R_D + R_L) * 1e3, 0)}/{Lp * Wp:,}", f"**{f(sig, 2)} MPa**")
t.row("壓應力上限", "min(70 kgf/cm² = 6.86, 1.0 G S)〔設〕10.6.6 3.(2)，G = 0.86",
      f"min(6.86, 0.86 × {f(S_, 3)})", f"{f(lim_sig, 2)} MPa → 比值 {f(sig / lim_sig, 2)}")
t.row("水平位移 Δs", "α ΔT L + 0.0004 L（溫度 ±20 °C 全由一端承受 + 架設後縮短）",
      f"10.8e-6 × 20 × 40,000 + 0.0004 × 40,000", f"{f(d_s, 2)} mm")
t.row("剪力變形", "hrt ≥ 2Δs〔設〕10.6.6 3.(4)", f"hrt = {n_int} × {hri} + 2 × {f(hce, 0)} = {f(hrt, 0)} ≥ {f(2 * d_s, 1)}",
      "通過" if hrt >= 2 * d_s else "不通過")
t.row("轉角 θ", "呆載重與預力（程式值）+ 活載重（卡車直接計算）+ 施工誤差 0.005",
      f"{th_dl * 1e3:.2f} + {th_ll * 1e3:.2f} + 5.00 mrad", f"{theta * 1e3:.2f} mrad")
t.row("不上揚", "σTL ≥ 0.5 G S (L/hri)² θ/n〔設〕(10-36)，n = 5（外層 6 mm 未多於內層之半，不加 0.5）",
      f"0.5 × 0.86 × {f(S_, 3)} × ({Lp}/{hri})² × {theta:.5f}/5", f"需 {f(sig_up, 2)} ≤ {f(sig, 2)} MPa → "
      + ("通過" if sig >= sig_up else "不通過"))
t.row("穩定", "總厚 ≤ min(L, W)/3〔設〕10.6.6 3.(6)", f"{f(h_tot, 0)} ≤ {f(min(Lp, Wp) / 3, 1)}",
      "通過" if h_tot <= min(Lp, Wp) / 3 else "不通過")
t.row("鋼板厚", "hs > 3 hmax σTL / Fy〔設〕(10-32)，Fy = 250", f"3 × {hri} × {f(sig, 2)}/250", f"需 {f(hs_req, 2)} < {f(hs, 0)} mm")
t.flush()
para("說明：呆載重與預力造成的轉角沿用程式值（由預拱計算而來），本計算書未獨立重算；"
     "它只佔總轉角的四分之一，施工誤差 0.005 rad 是主要來源。")
cmp("支承呆載重反力 Rd", R_D, R["bearing"]["R_D"], "kN", 1)
cmp("支承活載重反力 RL", R_L, R["bearing"]["R_L"], "kN", 1)
cmp("支承墊壓應力 σTL", sig, R["bearing"]["sig"], "MPa", 2)
cmp("活載重轉角", th_ll * 1e3, R["bearing"]["th_ll"] * 1e3, "mrad", 2, "本書以卡車直接計算，程式以均布等值")
cmp("不上揚所需 σ", sig_up, R["bearing"]["sig_up"], "MPa", 2)

# ---------------------------------------------------------------------------
# 12. 止震塊
# ---------------------------------------------------------------------------
h2("12. 止震塊（〔耐〕4.5.2、〔設〕7.3.6 4.）")
NA2 = max(v[0] for v in P.NEAR_FAULTS.values())
Ss_adj = P.SS_II * NA2
Fa3 = 1.0 if Ss_adj >= 0.8 else None
Fa2 = 1.0 + (Fa3 - 1.0) * (270 - P.VS30) / 90
SIIS = Fa2 * Ss_adj
W = 2 * P.N_GIRDER * R_D
H_el = P.IMPORTANCE * SIIS * W
H_T = H_el / 2
Vk = H_T / P.N_STOPPER
Avf = Vk * 1e3 / (0.85 * P.FY * 1.0)
Acv = Vk * 1e3 / (0.85 * min(0.2 * 28.0, 5.52))
t = Table()
t.row("近斷層調整", "NA 取鄰近斷層中較大者〔耐〕表 2-7、解說 C2.3",
      "、".join(f"{k} {v[0]}" for k, v in P.NEAR_FAULTS.items()), f"NA = {NA2}")
t.row("調整後 SS", "0.8 NA〔耐〕(2-15a)", f"0.8 × {NA2}", f"{f(Ss_adj, 3)}")
t.row("Fa", "第二類：Fa,2 = 1 + (Fa,3 − 1)(270 − Vs30)/90；SS ≥ 0.8 時 Fa,3 = 1.0〔耐〕表 2-3(a)",
      f"1 + (1.0 − 1) × (270 − 180)/90", f"{f(Fa2, 2)}")
t.row("SII,S", "Fa · 0.8 NA〔耐〕(2-15a)", f"{f(Fa2, 2)} × {f(Ss_adj, 3)}", f"**{f(SIIS, 3)}**（譜平台值）")
t.row("上部結構重 W", "8 個支承的呆載重反力", f"8 × {f(R_D, 1)}", f"{f(W, 0)} kN")
t.row("支承系統水平力", "I·Sa,II·W，週期未知取平台；單跨無橋柱塑鉸，取 4.5.2 的上限（見第 14 節）",
      f"1.0 × {f(SIIS, 3)} × {f(W, 0)}", f"**{f(H_el, 0)} kN**")
t.row("每座橋台橫向", "兩座橋台平分", f"{f(H_el, 0)}/2", f"**{f(H_T, 0)} kN**")
t.row("每塊（梁間 3 塊）", "", f"{f(H_T, 0)}/3", f"{f(Vk, 0)} kN")
t.row("剪力摩擦鋼筋 Avf", "Vu/(φ fy μ)〔設〕(7-44)；φ = 0.85〔設〕7.3.1 2.；μ = 1.0（澆於刻意粗糙的硬化面）",
      f"{f(Vk * 1e3, 0)}/(0.85 × 420 × 1.0)", f"**{f(Avf, 0)} mm²**")
t.row("剪力面積 Acv", "Vn ≤ 0.2 f'c Acv 且 ≤ 5.52 Acv〔設〕7.3.6 4.(4)d；下部結構 f'c = 28（假設）",
      f"{f(Vk * 1e3, 0)}/(0.85 × 5.52)", f"{f(Acv / 1e6, 3)} m²")
t.flush()
cmp("上部結構重 W", W, R["seismic"]["W"], "kN", 0)
cmp("每座橋台橫向止震力", H_T, R["seismic"]["H_T"], "kN", 0)
cmp("每塊 Avf", Avf, R["seismic"]["Avf_T"], "mm²", 0)

# ---------------------------------------------------------------------------
# 13. 對照
# ---------------------------------------------------------------------------
h2("13. 與程式結果對照")
t = Table(("項目", "本計算書", "程式", "差異", "單位", "說明"))
worst = 0.0
for item, mine, prog, unit, nd, note in compare:
    dlt = (mine - prog) / prog * 100 if prog else 0.0
    worst = max(worst, abs(dlt))
    t.rows.append((item, f(mine, nd), f(prog, nd), f"{dlt:+.2f}%".replace("-", "−"), unit, note))
t.flush()
para(f"最大差異 {worst:.2f}%。")

# ---------------------------------------------------------------------------
# 14. 發現
# ---------------------------------------------------------------------------
h2("14. 核對時發現、需要技師判斷的事項")
red = 0.70
findings.append(
    f"**止震塊設計力可能偏保守**：〔耐〕4.5.2 規定支承系統極限承載力「不必大於地震力 VII 乘以 1.2αyFu,II 所引致之水平力」。"
    f"依 (2-10)、(2-11) 式，VII·1.2αy·Fu,II = I·(Sa,II/Fu,II)m·Fu,II·W，其值隨 Fu,II 介於 "
    f"{f(red * SIIS, 3)}W（Fu,II = 1，(Sa/Fu)m = 0.70 Sa/Fu）到 {f(SIIS, 3)}W（Fu,II ≥ {f(SIIS / 0.3, 2)}）之間。"
    f"程式取上界 {f(SIIS, 3)}W = {f(H_el, 0)} kN；若技師依下部結構與支承系統確定 Fu,II，止震塊力最多可降到約 70%"
    f"（{f(red * H_el, 0)} kN）。")
findings.append(
    f"**施預力時應扣除套管開孔（最重要）**：〔設〕8.17.1 規定後拉構材在灌漿前計算斷面性質，應扣除套管開口面積。"
    f"程式用毛斷面計算施預力時應力與 fcir。扣除 4 支外徑 {f(P.DUCT_OD, 0)} mm 套管後，跨中淨斷面 A = {f(An_m, 0)} mm²、"
    f"yb = {f(ybn_m, 1)} mm、I = {In_m:.4e} mm⁴（Sb 減少 {(1 - In_m / ybn_m / Sb) * 100:.1f}%），ES 由 {f(ES, 2)} 變為 "
    f"{f(ES_n, 2)} MPa。施預力時梁底最大壓應力由 {f(fb_g[0], 2)} 變為 **{f(fb_n[0], 2)} MPa**"
    f"（距梁端 {f(fb_n[1], 1)} m；容許 0.55 f'ci = {f(lim_c, 2)}，比值 {f(fb_n[0] / lim_c, 2)}），"
    + ("通過。" if fb_n[0] >= lim_c else "**超過容許值**。")
    + f"若鋼絞線在套管內貼向上緣（跨中下凹段受拉時的情形，重心上移約 {f(dy_s, 0)} mm 的估計），為 {f(fb_n2[0], 2)} MPa"
    f"（比值 {f(fb_n2[0] / lim_c, 3)}），仍在邊緣。要確實通過，施預力時 f'ci 需提高到約 {f(fci_req, 1)} MPa 以上"
    f"（例如 30 MPa），或調整鋼腱配置、分階段施預力。"
    f"另外淨斷面使 fcir 由 {f(fcir, 2)} 增為 {f(fcir_n, 2)} MPa，總損失由 {f(loss, 1)} 增為 {f(loss_n, 1)} MPa，"
    f"使用載重下跨中梁底拉應力由 {f(fb, 2)} 增為 {f(fb_sn, 2)} MPa（容許 {f(lim_t, 2)}），仍通過。")
findings.append(
    f"**Vcw 的 fpc 取點**：〔設〕8.20.2 的 fpc 為合成斷面形心處的壓應力。程式在端塊漸變段仍用跨中合成斷面的形心高度 "
    f"{f(ybc, 0)} mm；本斷面自己的合成形心為 {f(yj, 0)} mm。前者 Vcw = {f(Vcw_p / 1e3, 0)} kN，後者 {f(Vcw / 1e3, 0)} kN，"
    f"相差 {abs(Vcw - Vcw_p) / Vcw_p * 100:.1f}%。臨界斷面 Vu/φ = {f(R['shear']['rc']['Vu'] / 0.9 / 1e3, 0)} kN，兩者都足夠。")
edge = P.BOT_FLANGE_W / 2
findings.append(
    f"**爆裂力近似法的適用條件**：〔設〕8.21.6 1.(3) 要求端錨在構材主平面的最小邊距 ≥ 1.5a = {f(1.5 * P.ANCHOR_PLATE, 0)} mm。"
    f"垂直方向最上、最下錨碇到梁頂、梁底各 450 mm，符合；橫向邊距只有 {f(edge, 0)} mm。"
    f"若技師認為此條件也適用於橫向，近似法就不適用，需改用 8.21.4 壓拉桿模型或 8.21.5 彈性分析。")
findings.append(
    "**端塊漸變段斷面性質為近似**：程式與本計算書都以腹板寬在跨中斷面與端塊之間線性內插 A、yb、I，"
    "未依實際幾何計算；影響 Vcw 與梁端附近的應力。")
findings.append(
    "**全梁沿用跨中損失**：程式把跨中算出的長期損失套用到全梁各斷面；梁端附近 fcir 不同，損失也不同。"
    "對 Vcw 與梁端應力影響小，但非嚴格做法。")
for i, s in enumerate(findings, 1):
    out.append(f"{i}. {s}")
out.append("")

h2("15. 本計算書沒有核對的項目")
para("活載重剪力包絡與 Vci、橋面版、撓度與預拱、垂直地震、支承拉拔、防落長度、局部區承壓，"
     "以及呆載重與預力造成的支承轉角，本計算書沒有獨立重算，以程式結果為準，仍需人工複核。")

path = os.path.join(HERE, "hand_checks.md")
with open(path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")
print(f"已輸出 {os.path.relpath(path, ROOT)}；與程式最大差異 {worst:.2f}%")
