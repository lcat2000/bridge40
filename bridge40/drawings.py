"""
設計圖：由 params.py 的幾何與 results.json 的設計結果產生 SVG（A3 橫式）。
圖上的尺寸與數字都從這兩個來源讀取，不另外手打。
S-01 一般配置圖、S-02 預力梁與鋼腱詳圖、S-03 配筋、支承與耐震配置。
"""
import math

from . import params as P
from . import design as D

W, H = 1680, 1188                       # A3 橫式；1 單位 = 0.25 mm 圖紙

SANS = "'Noto Sans TC','Noto Sans CJK TC','PingFang TC','Microsoft JhengHei',sans-serif"
MONO = "'IBM Plex Mono','DejaVu Sans Mono',ui-monospace,monospace"
CSS = """
.paper{fill:var(--paper)}
.frame{stroke:var(--ink);stroke-width:2.4;fill:none}
.fthin{stroke:var(--ink);stroke-width:1;fill:none}
.obj{stroke:var(--ink);stroke-width:1.5;fill:var(--conc)}
.cut{stroke:var(--ink);stroke-width:1.5;fill:var(--cut)}
.cut2{stroke:var(--ink);stroke-width:1.1;fill:var(--cut2)}
.thin{stroke:var(--ink);stroke-width:.8;fill:none}
.hid{stroke:var(--ink2);stroke-width:1;stroke-dasharray:7 4;fill:none}
.cl{stroke:var(--ink2);stroke-width:.8;stroke-dasharray:22 4 3 4;fill:none}
.dim{stroke:var(--dim);stroke-width:.8;fill:none}
.dimtick{stroke:var(--dim);stroke-width:1.4}
.dimtxt{fill:var(--dim);font:13px MONO}
.leader{stroke:var(--ink2);stroke-width:.8;fill:none}
.lbl{fill:var(--ink);font:14px SANS}
.lbl2{fill:var(--ink2);font:13px SANS}
.lbls{fill:var(--ink2);font:12px SANS}
.lblacc{fill:var(--acc);font:500 14px SANS}
.vtitle{fill:var(--ink);font:600 18px SANS}
.vline{stroke:var(--ink);stroke-width:1.6}
.vscale{fill:var(--ink2);font:13px SANS}
.tendon{stroke:var(--acc);stroke-width:1.8;fill:none}
.tendon2{stroke:var(--acc);stroke-width:1.8;stroke-dasharray:10 4;fill:none}
.duct{stroke:var(--acc);stroke-width:1.4;fill:var(--paper)}
.ductc{fill:var(--acc)}
.anchor{stroke:var(--acc);stroke-width:1.4;fill:var(--accbg)}
.bar{stroke:var(--ink);stroke-width:1.3;fill:none}
.barb{stroke:var(--acc);stroke-width:1.8;fill:none}
.dot{fill:var(--ink)}
.rubber{stroke:var(--ink);stroke-width:1;fill:var(--cut2)}
.plate{stroke:var(--ink);stroke-width:.8;fill:var(--ink2)}
.key{stroke:var(--ink);stroke-width:1.4;fill:var(--keybg)}
.hatch{stroke:var(--ink2);stroke-width:.6}
.brk{stroke:var(--ink);stroke-width:1;fill:none}
.hdr{fill:var(--ink);font:600 15px SANS}
.note{fill:var(--ink);font:13.5px SANS}
.notes{fill:var(--ink2);font:12.5px SANS}
.tbk{fill:var(--ink2);font:12.5px SANS}
.tbv{fill:var(--ink);font:14px SANS}
.tbvb{fill:var(--ink);font:600 17px SANS}
.stamp{fill:none;stroke:var(--stamp);stroke-width:2.4}
.stamptxt{fill:var(--stamp);font:700 20px SANS;letter-spacing:3px}
.tbl{stroke:var(--ink2);stroke-width:.7;fill:none}
.tbltxt{fill:var(--ink);font:13px MONO}
.tblhdr{fill:var(--ink);font:600 13px SANS}
""".replace("SANS", SANS).replace("MONO", MONO)

LIGHT = {"--paper": "#fbfcfc", "--ink": "#1b2429", "--ink2": "#56656f", "--dim": "#2f5b7c",
         "--conc": "#eef1f2", "--cut": "#d9e0e5", "--cut2": "#e7ecef", "--acc": "#1f5fbf",
         "--accbg": "#dbe7fa", "--keybg": "#f3e6c8", "--stamp": "#b42318"}
DARK = {"--paper": "#141a1e", "--ink": "#dfe6ea", "--ink2": "#98a8b2", "--dim": "#8fb6d6",
        "--conc": "#1c2429", "--cut": "#2a353c", "--cut2": "#222b31", "--acc": "#6ea4ff",
        "--accbg": "#1d2c44", "--keybg": "#3a3220", "--stamp": "#f2735f"}


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def f0(v):
    return f"{v:,.0f}"


class Sheet:
    def __init__(self, no, title, R):
        self.no, self.title, self.R = no, title, R
        self.o = []

    # ---- 基本圖元 ----
    def line(self, x1, y1, x2, y2, cls="thin"):
        self.o.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" class="{cls}"/>')

    def poly(self, pts, cls="obj", closed=True):
        p = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        tag = "polygon" if closed else "polyline"
        self.o.append(f'<{tag} points="{p}" class="{cls}"/>')

    def rect(self, x, y, w, h, cls="obj"):
        if w < 0:
            x, w = x + w, -w
        if h < 0:
            y, h = y + h, -h
        self.o.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" class="{cls}"/>')

    def circle(self, x, y, r, cls):
        self.o.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" class="{cls}"/>')

    def text(self, x, y, s, cls="lbl", anchor="start", rot=None):
        tr = f' transform="rotate({rot} {x:.2f} {y:.2f})"' if rot else ""
        self.o.append(f'<text x="{x:.2f}" y="{y:.2f}" class="{cls}" text-anchor="{anchor}"{tr}>'
                      f'{esc(s)}</text>')

    def tick(self, x, y):
        self.line(x - 4, y + 4, x + 4, y - 4, "dimtick")

    def hdim(self, x1, x2, y, label, ext=None, pos="mid"):
        if ext:
            for x, yf in ((x1, ext[0]), (x2, ext[1])):
                if yf is None:
                    continue
                dd = 1 if y > yf else -1
                self.line(x, yf + 3 * dd, x, y + 5 * dd, "dim")
        self.line(x1, y, x2, y, "dim")
        self.tick(x1, y)
        self.tick(x2, y)
        if pos == "left":
            self.text(x1 - 6, y + 4, label, "dimtxt", "end")
        elif pos == "right":
            self.text(x2 + 6, y + 4, label, "dimtxt", "start")
        else:
            self.text((x1 + x2) / 2, y - 5, label, "dimtxt", "middle")

    def vdim(self, y1, y2, x, label, ext=None, side="right"):
        if ext:
            for yy, xf in ((y1, ext[0]), (y2, ext[1])):
                if xf is None:
                    continue
                dd = 1 if x > xf else -1
                self.line(xf + 3 * dd, yy, x + 5 * dd, yy, "dim")
        self.line(x, y1, x, y2, "dim")
        self.tick(x, y1)
        self.tick(x, y2)
        ym = (y1 + y2) / 2
        if side == "right":
            self.text(x + 6, ym + 4.5, label, "dimtxt", "start")
        elif side == "left":
            self.text(x - 6, ym + 4.5, label, "dimtxt", "end")
        else:
            self.text(x - 5, ym, label, "dimtxt", "middle", rot=-90)

    def leader(self, pts, label, cls="lbl", anchor="start", dy=-4):
        self.poly(pts, "leader", closed=False)
        x, y = pts[-1]
        self.text(x + (4 if anchor == "start" else -4), y + dy, label, cls, anchor)

    def vtitle(self, x, y, title, scale, w=None):
        self.text(x, y, title, "vtitle", "middle")
        ww = w or (len(title) * 18 + 20)
        self.line(x - ww / 2, y + 7, x + ww / 2, y + 7, "vline")
        if scale:
            self.text(x, y + 26, scale, "vscale", "middle")

    def notes(self, x, y, title, lines, lh=21, w=None):
        self.text(x, y, title, "hdr")
        yy = y + 26
        for ln in lines:
            cls = "note"
            if isinstance(ln, tuple):
                ln, cls = ln
            self.text(x, yy, ln, cls)
            yy += lh
        return yy

    def table(self, x, y, cols, rows, widths, rh=22):
        tw = sum(widths)
        allr = [cols] + rows
        for i, r in enumerate(allr):
            yy = y + i * rh
            xx = x
            for j, (c, w_) in enumerate(zip(r, widths)):
                cls = "tblhdr" if i == 0 or j == 0 else "tbltxt"
                self.text(xx + w_ / 2, yy + 15.5, c, cls, "middle")
                xx += w_
        self.rect(x, y, tw, rh * len(allr), "tbl")
        for i in range(1, len(allr)):
            self.line(x, y + i * rh, x + tw, y + i * rh, "tbl")
        xx = x
        for w_ in widths[:-1]:
            xx += w_
            self.line(xx, y, xx, y + rh * len(allr), "tbl")

    def frame(self, scale_note):
        self.rect(0, 0, W, H, "paper")
        self.rect(20, 20, W - 40, H - 40, "frame")
        y0 = 1062
        self.line(20, y0, W - 20, y0, "frame")
        cells = [(20, 520, "工程名稱", "40 m 簡支後拉預力 I 型梁橋（示範設計）"),
                 (520, 1000, "圖名", self.title),
                 (1000, 1150, "圖號", self.no),
                 (1150, 1330, "比例", scale_note),
                 (1330, 1660, "依據", "交通部公路橋梁設計規範、耐震設計規範")]
        for x1, x2, k, v in cells:
            self.line(x2, y0, x2, H - 20, "fthin")
            self.text(x1 + 12, y0 + 24, k, "tbk")
            self.text(x1 + 12, y0 + 58, v, "tbvb" if k in ("圖號", "圖名") else "tbv")
        self.text(32, y0 + 92, "所有尺寸以 mm 計，高程與座標自梁底、梁端起算；本圖由程式自計算結果產生。",
                  "tbk")
        self.text(1342, y0 + 92, f"{P.DRAWING_DATE} 修訂 {P.REVISION}　設計：AI 示範（未經技師簽證）", "tbk")
        sx, sy = 1415, 30
        self.rect(sx, sy, 230, 44, "stamp")
        self.text(sx + 115, sy + 30, "示範・非施工圖", "stamptxt", "middle")

    def svg(self, theme="web"):
        css = CSS
        if theme != "web":
            pal = LIGHT if theme == "light" else DARK
            for k, v in pal.items():
                css = css.replace(f"var({k})", v)
            # 出圖（cairosvg）只取第一個字型，改用本機的思源黑體
            css = css.replace(SANS, "'Noto Sans CJK TC'").replace(MONO, "'Noto Sans CJK TC'")
        body = "\n".join(self.o)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
                f'width="{W}" height="{H}" role="img" aria-label="{esc(self.no + " " + self.title)}">'
                f"<style>{css}</style>{body}</svg>")


class View:
    """實尺寸（mm，y 向上）→ 圖面座標。"""

    def __init__(self, ox, oy, kx, ky=None):
        self.ox, self.oy, self.kx = ox, oy, kx
        self.ky = ky if ky is not None else kx

    def X(self, x):
        return self.ox + x * self.kx

    def Y(self, y):
        return self.oy - y * self.ky

    def P(self, pts, dx=0.0, dy=0.0, mirror=False):
        return [(self.X((-x if mirror else x) + dx), self.Y(y + dy)) for x, y in pts]


def barrier_pts(left=True):
    out = []
    for bx, by in P.BARRIER:
        x = bx * 1000 if left else P.DECK_WIDTH - bx * 1000
        out.append((x - P.DECK_WIDTH / 2, by * 1000 + P.GIRDER_H + P.HAUNCH + P.DECK_T))
    return out


# ===========================================================================
# S-01 一般配置圖
# ===========================================================================
def sheet_s01(R):
    S = Sheet("S-01", "一般配置圖", R)
    S.frame("如圖示")
    z, b = R["seismic"], R["bearing"]
    hdeck = P.GIRDER_H + P.HAUNCH + P.DECK_T
    # ---------------- 立面圖 1:120 ----------------
    k = 4 / 120
    v = View(170, 310, k)
    Lg = P.GIRDER_LEN
    S.vtitle(840, 54, "立面圖", "S = 1:120", w=150)
    # 橋台（示意，虛線）
    for side in (0, 1):
        def mx(x):
            return x if side == 0 else Lg - x
        bw_, gap, ln = 400, P.STOPPER_GAP + 15, P.SEAT_LN
        seat_y = -b["h_tot"] - 60
        pts = [(mx(-gap - bw_), hdeck + 75), (mx(-gap), hdeck + 75), (mx(-gap), seat_y),
               (mx(ln), seat_y), (mx(ln), -2600), (mx(-gap - bw_ - 900), -2600),
               (mx(-gap - bw_ - 900), -1200), (mx(-gap - bw_), -1200)]
        S.poly(v.P(pts), "hid")
        S.rect(v.X(mx(P.BEARING_TO_END - 250)), v.Y(-b["h_tot"]), 500 * k * (1 if side == 0 else -1),
               -60 * k, "thin")
    S.text(v.X(-1500), v.Y(-2900), "橋台（下部結構另案設計，需地質資料）", "lbls", "start")
    # 梁、托肩、版、鋪面、護欄
    S.rect(v.X(0), v.Y(P.GIRDER_H), Lg * k, P.GIRDER_H * k, "obj")
    S.rect(v.X(0), v.Y(hdeck), Lg * k, P.DECK_T * k, "cut2")
    S.line(v.X(0), v.Y(hdeck + 850), v.X(Lg), v.Y(hdeck + 850), "thin")
    S.line(v.X(0), v.Y(hdeck + 850), v.X(0), v.Y(hdeck), "thin")
    S.line(v.X(Lg), v.Y(hdeck + 850), v.X(Lg), v.Y(hdeck), "thin")
    S.text(v.X(Lg * 0.70), v.Y(hdeck + 850) - 6, "護欄頂", "lbls", "middle")
    # 支承與隔梁
    for xb in (P.BEARING_TO_END, Lg - P.BEARING_TO_END):
        S.rect(v.X(xb - b["L"] / 2), v.Y(0), b["L"] * k, b["h_tot"] * k, "obj")
        S.rect(v.X(xb - 125), v.Y(P.GIRDER_H), 250 * k, (P.GIRDER_H - 250) * k, "hid")
    S.rect(v.X(Lg / 2 - 125), v.Y(250 + P.DIAPHRAGM_H), 250 * k, P.DIAPHRAGM_H * k, "hid")
    S.line(v.X(Lg / 2), v.Y(hdeck + 1000), v.X(Lg / 2), v.Y(-900), "cl")
    S.text(v.X(Lg / 2), v.Y(-900) + 16, "CL 跨中", "lbl2", "middle")
    # 鋼腱（示意）
    for t in P.TENDONS:
        pts = [(v.X(x * 1000), v.Y(D.tendon_y(t, x))) for x in
               [i * Lg / 1000 / 80 for i in range(81)]]
        S.poly(pts, "tendon2", closed=False)
    # 標註
    S.leader([(v.X(Lg * 0.23), v.Y(700)), (v.X(Lg * 0.23) + 30, v.Y(-1500)),
              (v.X(Lg * 0.23) + 60, v.Y(-1500))], f"後拉鋼腱 {P.N_TENDON} 束（拋物線）", "lblacc")
    S.leader([(v.X(Lg / 2 + 100), v.Y(1200)), (v.X(Lg / 2) + 40, v.Y(-1300)),
              (v.X(Lg / 2) + 70, v.Y(-1300))], "跨中隔梁 t = 250", "lbl2")
    S.leader([(v.X(Lg - 400), v.Y(-b["h_tot"] / 2)), (v.X(Lg - 400) - 20, v.Y(-1700)),
              (v.X(Lg - 400) - 50, v.Y(-1700))],
             f"鋼板加勁橡膠支承 {b['L']}×{b['W']}×{b['h_tot']:.0f}", "lbl2", "end")
    yd = v.Y(hdeck + 1700)
    S.hdim(v.X(0), v.X(Lg), yd - 34, f"梁長 {f0(Lg)}", ext=(v.Y(hdeck + 850), v.Y(hdeck + 850)))
    S.hdim(v.X(0), v.X(P.BEARING_TO_END), yd, f0(P.BEARING_TO_END), pos="left")
    S.hdim(v.X(P.BEARING_TO_END), v.X(Lg - P.BEARING_TO_END), yd,
           f"跨徑（支承中心距）{f0(P.SPAN)}")
    S.hdim(v.X(Lg - P.BEARING_TO_END), v.X(Lg), yd, f0(P.BEARING_TO_END), pos="right")
    S.vdim(v.Y(0), v.Y(P.GIRDER_H), v.X(Lg) + 30, f"{f0(P.GIRDER_H)}", ext=(v.X(Lg), v.X(Lg)))
    S.vdim(v.Y(P.GIRDER_H), v.Y(hdeck), v.X(Lg) + 30, f"{P.HAUNCH}+{P.DECK_T}", side="right")
    # 防落長度與間隙（左端放大說明）
    yl = v.Y(-b["h_tot"] - 60) + 40
    S.hdim(v.X(0), v.X(P.SEAT_LN), yl,
           f"LN = {P.SEAT_LN}（≥ {z['LN_min'] * 10:.0f}）", pos="right")
    S.leader([(v.X(-(P.STOPPER_GAP + 15) / 2), v.Y(P.GIRDER_H * 0.5)), (v.X(-1300), v.Y(-300)),
              (v.X(-1300) - 10, v.Y(-300))],
             f"梁端間隙 ≥ {z['SB'] * 10:.0f}", "lbl2", "end")

    # ---------------- 標準橫斷面 1:50 ----------------
    k2 = 4 / 50
    v2 = View(430, 900, k2)
    S.vtitle(430, 448, "標準橫斷面", "S = 1:50", w=200)
    half = P.DECK_WIDTH / 2
    gxs = [-half + P.OVERHANG + i * P.SPACING for i in range(P.N_GIRDER)]
    S.rect(v2.X(-half), v2.Y(hdeck), P.DECK_WIDTH * k2, P.DECK_T * k2, "cut")
    S.rect(v2.X(-half + P.BARRIER_W), v2.Y(hdeck + P.PAVEMENT_T),
           (P.DECK_WIDTH - 2 * P.BARRIER_W) * k2, P.PAVEMENT_T * k2, "cut2")
    for left in (True, False):
        S.poly(v2.P(barrier_pts(left)), "cut")
    for gx_ in gxs:
        S.poly(v2.P(P.GIRDER, dx=gx_), "cut")
        S.rect(v2.X(gx_ - P.TOP_FLANGE_W / 2), v2.Y(hdeck - P.DECK_T),
               P.TOP_FLANGE_W * k2, P.HAUNCH * k2, "cut2")
        S.rect(v2.X(gx_ - b["W"] / 2), v2.Y(0), b["W"] * k2, b["h_tot"] * k2, "obj")
    for i in range(P.N_GIRDER - 1):
        x1 = gxs[i] + P.WEB_T / 2
        x2 = gxs[i + 1] - P.WEB_T / 2
        S.rect(v2.X(x1), v2.Y(250 + P.DIAPHRAGM_H), (x2 - x1) * k2, P.DIAPHRAGM_H * k2, "hid")
    S.line(v2.X(0), v2.Y(hdeck + 1800), v2.X(0), v2.Y(-400), "cl")
    S.text(v2.X(0), v2.Y(hdeck + 1850), "CL 橋梁中心", "lbl2", "middle")
    S.text(v2.X(-2000), v2.Y(hdeck + 300), "車道 4,000", "lbls", "middle")
    S.text(v2.X(2000), v2.Y(hdeck + 300), "車道 4,000", "lbls", "middle")
    yt = v2.Y(hdeck + 1150)
    S.hdim(v2.X(-half), v2.X(half), yt - 30, f"橋面寬 {f0(P.DECK_WIDTH)}")
    S.hdim(v2.X(-half), v2.X(-half + P.BARRIER_W), yt, f0(P.BARRIER_W), pos="left")
    S.hdim(v2.X(-half + P.BARRIER_W), v2.X(half - P.BARRIER_W), yt, f"路面 {f0(P.ROADWAY)}")
    S.hdim(v2.X(half - P.BARRIER_W), v2.X(half), yt, f0(P.BARRIER_W), pos="right")
    yb_ = v2.Y(-500)
    S.hdim(v2.X(-half), v2.X(gxs[0]), yb_, f0(P.OVERHANG), pos="left")
    for i in range(P.N_GIRDER - 1):
        S.hdim(v2.X(gxs[i]), v2.X(gxs[i + 1]), yb_, f0(P.SPACING))
    S.hdim(v2.X(gxs[-1]), v2.X(half), yb_, f0(P.OVERHANG), pos="right")
    S.vdim(v2.Y(0), v2.Y(P.GIRDER_H), v2.X(half) + 40, f0(P.GIRDER_H))
    S.vdim(v2.Y(P.GIRDER_H), v2.Y(hdeck), v2.X(half) + 40, f"{P.HAUNCH}+{P.DECK_T}")
    S.leader([(v2.X(gxs[1]), v2.Y(1100)), (v2.X(gxs[1]) + 60, v2.Y(1100) + 0)],
             "PCI 梁（後拉）", "lbl2")
    S.leader([(v2.X(half - 300), v2.Y(hdeck + 400)), (v2.X(half + 250), v2.Y(hdeck + 750)),
              (v2.X(half + 280), v2.Y(hdeck + 750))], "混凝土護欄", "lbl2")
    S.leader([(v2.X(1700), v2.Y(hdeck + 40)), (v2.X(1900), v2.Y(hdeck + 700)),
              (v2.X(1950), v2.Y(hdeck + 700))], f"瀝青鋪面 {P.PAVEMENT_T}", "lbls")
    S.text(v2.X(0), v2.Y(-1100), "中隔梁僅設於跨中；梁端另設端隔梁", "lbls", "middle")

    # ---------------- 設計條件 ----------------
    pt, sp = R["pt"], z["sp"]
    lines = [
        "1. 規範：交通部公路橋梁設計規範（98 年版及 104、109 年修訂）、",
        "   公路橋梁耐震設計規範（107 年 12 月版）。",
        "2. 活載重：HS20-44(MS18)；衝擊 I = 15.24/(L+38.1)，跨中 "
        f"{R['live']['IM_M']:.3f}。",
        "3. 設計法：強度 1.3[D + 1.67(L+I)]；預力構件另檢核施工與使用應力。",
        "4. 用途係數 I = 1.0；設計年限 50 年；一般環境（離海岸 > 3 km）。",
        f"5. 橋址：{P.SITE}；第二類地盤（Vs30 取 {P.VS30:.0f} m/s，無地質資料）。",
        f"   等級 II：SS = {sp['II'][0]:.2f}、S1 = {sp['II'][1]:.3f}（含近斷層 NA {sp['NA2']:.2f}、"
        f"NV {sp['NV2']:.2f}）。",
        ("材料", "hdr"),
        f"6. 梁混凝土 f'c = {P.FC_GIRDER:.0f} MPa，施預力時 f'ci ≥ {P.FCI_GIRDER:.0f} MPa；",
        f"   橋面版 f'c = {P.FC_DECK:.0f} MPa；鋼筋 SD420W。",
        f"7. 預力鋼材：15.2 mm 七線低鬆弛鋼絞線，f's = {P.FPU:.0f} MPa；",
        f"   {P.N_TENDON} 束 × {pt['ns']} 股，套管內徑 {P.DUCT_ID:.0f} mm，完成後全長灌漿。",
        f"8. 保護層：版頂 {P.COVER_DECK_TOP:.0f}、版底 {P.COVER_DECK_BOT:.0f}、梁箍筋 "
        f"{P.COVER_STIRRUP:.0f} mm。",
        ("主要結果（每支梁）", "hdr"),
        f"9. Mu = {f0(R['moments']['Mu'])} kN·m ≤ φMn = {f0(R['strength']['mid']['phiMn'])} kN·m"
        f"（φ = {R['strength']['phi']}）。",
        f"10. 使用載重梁底應力 {R['stress']['fin_bot_max']:+.2f} MPa ≤ "
        f"{R['stress']['lim']['t_fin']:.2f} MPa。",
        f"11. 活載重撓度 {R['defl']['d']:.1f} mm ≤ L/800 = {R['defl']['lim']:.0f} mm。",
        f"12. 上部結構重 {f0(z['W'])} kN；止震塊每座橋台橫向 {f0(z['H_T'])} kN。",
    ]
    S.notes(900, 470, "設計條件", lines, lh=25)
    return S


# ===========================================================================
# S-02 預力梁與鋼腱詳圖
# ===========================================================================
def sheet_s02(R):
    S = Sheet("S-02", "預力梁與鋼腱詳圖", R)
    S.frame("如圖示")
    pt = R["pt"]
    half = P.GIRDER_LEN / 2
    kx, ky = 4 / 60, 4 / 30
    v = View(120, 400, kx, ky)
    S.vtitle(800, 58, "預力梁半立面與鋼腱線形", "水平 S = 1:60、垂直 S = 1:30（垂直放大 2 倍）",
             w=330)
    S.rect(v.X(0), v.Y(P.GIRDER_H), half * kx, P.GIRDER_H * ky, "obj")
    S.line(v.X(0), v.Y(P.GIRDER_H - P.TOP_FLANGE_T), v.X(half), v.Y(P.GIRDER_H - P.TOP_FLANGE_T),
           "hid")
    S.line(v.X(P.END_BLOCK_FULL + P.END_BLOCK_TAPER), v.Y(P.BOT_FLANGE_T + P.BOT_TAPER),
           v.X(half), v.Y(P.BOT_FLANGE_T + P.BOT_TAPER), "hid")
    S.line(v.X(P.END_BLOCK_FULL), v.Y(250), v.X(P.END_BLOCK_FULL), v.Y(1850), "hid")
    S.line(v.X(P.END_BLOCK_FULL + P.END_BLOCK_TAPER), v.Y(400),
           v.X(P.END_BLOCK_FULL + P.END_BLOCK_TAPER), v.Y(1850), "hid")
    S.rect(v.X(half - 125), v.Y(250 + P.DIAPHRAGM_H), 125 * kx, P.DIAPHRAGM_H * ky, "hid")
    S.line(v.X(half), v.Y(P.GIRDER_H + 150), v.X(half), v.Y(-300), "cl")
    S.text(v.X(half) - 6, v.Y(P.GIRDER_H) - 8, "CL 跨中", "lbl2", "end")
    b = R["bearing"]
    S.rect(v.X(P.BEARING_TO_END - b["L"] / 2), v.Y(0), b["L"] * kx, b["h_tot"] * ky, "obj")
    for i, t in enumerate(P.TENDONS):
        xs = [half * j / 120 for j in range(121)]
        pts = [(v.X(x), v.Y(D.tendon_y(t, x / 1000))) for x in xs]
        S.poly(pts, "tendon", closed=False)
        ya = v.Y(t["y_end"])
        S.rect(v.X(0) - 6, ya - P.ANCHOR_PLATE / 2 * ky, 6, P.ANCHOR_PLATE * ky, "anchor")
        S.text(v.X(0) - 12, ya + 5, t["name"], "lblacc", "end")
    # 測站
    for xm in range(0, int(half / 1000) + 1, 2):
        S.line(v.X(xm * 1000), v.Y(0) + 4, v.X(xm * 1000), v.Y(0) + 12, "thin")
        S.text(v.X(xm * 1000), v.Y(0) + 28, f"{xm}", "lbls", "middle")
    S.text(v.X(half) + 14, v.Y(0) + 28, "x（m，自梁端）", "lbls", "start")
    S.hdim(v.X(0), v.X(P.END_BLOCK_FULL), v.Y(P.GIRDER_H) - 22, f"端塊 {f0(P.END_BLOCK_FULL)}",
           pos="right")
    S.hdim(v.X(P.END_BLOCK_FULL), v.X(P.END_BLOCK_FULL + P.END_BLOCK_TAPER), v.Y(P.GIRDER_H) - 46,
           f"漸變 {f0(P.END_BLOCK_TAPER)}", pos="right")
    S.vdim(v.Y(0), v.Y(P.GIRDER_H), v.X(0) - 44, f0(P.GIRDER_H), side="left")
    S.leader([(v.X(16200), v.Y(330)), (v.X(16800), v.Y(900)), (v.X(17400), v.Y(900))],
             "鋼腱於 x ≈ 14–18 m 進入底翼並側移至 ±150", "lbls")
    # 鋼腱座標表
    tbl = pt["table"]
    cols = ["x (m)"] + [f"{r[0]:g}" for r in tbl]
    rows = [[t["name"]] + [f0(r[i + 1]) for r in tbl] for i, t in enumerate(P.TENDONS)]
    widths = [92] + [94] * len(tbl)
    S.text(120, 452, "鋼腱中心高度（mm，自梁底；左右對稱）", "hdr")
    S.table(120, 462, cols, rows, widths, rh=21)

    # ---------------- 斷面 1:25 ----------------
    k = 4 / 25
    hdeck = P.GIRDER_H + P.HAUNCH + P.DECK_T

    # A-A 跨中
    va = View(250, 1010, k)
    S.vtitle(250, 612, "斷面 A-A（跨中）S = 1:25", None, w=270)
    S.poly(va.P(P.GIRDER), "cut")
    c = P.COVER_STIRRUP
    stir = [(-125 + c, 200 + c), (125 - c, 200 + c), (125 - c, P.GIRDER_H + P.HAUNCH + 100),
            (-125 + c, P.GIRDER_H + P.HAUNCH + 100)]
    S.poly([(va.X(x), va.Y(y)) for x, y in [(-350 + c, c), (350 - c, c), (350 - c, 200 - 20),
                                             (125 - c, 400 - 20), (125 - c, 2100 - c),
                                             (-125 + c, 2100 - c), (-125 + c, 400 - 20),
                                             (-350 + c, 200 - 20)]], "bar")
    for t in P.TENDONS:
        S.circle(va.X(t["x_mid"]), va.Y(t["y_mid"]), P.DUCT_OD / 2 * k, "duct")
        S.circle(va.X(t["x_mid"]), va.Y(t["y_mid"] - 12), 3.2, "ductc")
    for xb in (-450, -300, -150, 0, 150, 300, 450):
        S.circle(va.X(xb), va.Y(2100 - c - 8), 2.6, "dot")
    for xb in (-290, 290):
        S.circle(va.X(xb), va.Y(c + 8), 2.6, "dot")
    S.hdim(va.X(-500), va.X(500), va.Y(P.GIRDER_H) - 16, f0(P.TOP_FLANGE_W))
    S.hdim(va.X(-350), va.X(350), va.Y(0) + 26, f0(P.BOT_FLANGE_W))
    S.vdim(va.Y(0), va.Y(P.GIRDER_H), va.X(-500) - 22, f0(P.GIRDER_H), side="left")
    S.leader([(va.X(150), va.Y(270)), (va.X(420), va.Y(560)), (va.X(450), va.Y(560))],
             f"套管 ID {P.DUCT_ID:.0f}", "lbls")
    S.leader([(va.X(-125), va.Y(1100)), (va.X(-330), va.Y(1300)), (va.X(-360), va.Y(1300))],
             f"腹板 {P.WEB_T}", "lbls", "end")
    S.leader([(va.X(125 - c), va.Y(900)), (va.X(330), va.Y(1000)), (va.X(360), va.Y(1000))],
             "D13 箍筋", "lbls")
    S.leader([(va.X(300), va.Y(2100 - c - 8)), (va.X(560), va.Y(1800)), (va.X(590), va.Y(1800))],
             "頂翼 7-D16", "lbls")
    # B-B 端塊
    vb = View(560, 1010, k)
    S.vtitle(560, 612, "斷面 B-B（端塊）S = 1:25", None, w=270)
    S.poly(vb.P(P.END_BLOCK), "cut")
    S.poly([(vb.X(x), vb.Y(y)) for x, y in [(-350 + c, c), (350 - c, c), (350 - c, 2100 - c),
                                             (-350 + c, 2100 - c)]], "barb")
    xb_ = 0.6
    for t in P.TENDONS:
        S.circle(vb.X(0), vb.Y(D.tendon_y(t, xb_)), P.DUCT_OD / 2 * k, "duct")
    S.hdim(vb.X(-350), vb.X(350), vb.Y(0) + 26, f0(P.BOT_FLANGE_W))
    S.leader([(vb.X(350 - c), vb.Y(1300)), (vb.X(520), vb.Y(1450)), (vb.X(540), vb.Y(1450))],
             "爆裂筋 D16 閉合箍", "lbls")
    S.text(560, 1048, "（距梁端 0.6 m）", "lbls", "middle")
    # C 梁端錨碇配置
    vc = View(870, 1010, k)
    S.vtitle(870, 612, "梁端面錨碇配置 S = 1:25", None, w=270)
    S.poly(vc.P(P.END_BLOCK), "obj")
    for t in P.TENDONS:
        y = t["y_end"]
        a = P.ANCHOR_PLATE
        S.rect(vc.X(-a / 2), vc.Y(y + a / 2), a * k, a * k, "anchor")
        S.circle(vc.X(0), vc.Y(y), P.DUCT_OD / 2 * k, "duct")
        S.text(vc.X(350) + 8, vc.Y(y) + 5, f"{t['name']}  {f0(y)}", "tbltxt")
    S.vdim(vc.Y(0), vc.Y(P.TENDONS[3]["y_end"]), vc.X(-350) - 20, f0(P.TENDONS[3]["y_end"]),
           side="left")
    for i in range(3, 0, -1):
        S.vdim(vc.Y(P.TENDONS[i]["y_end"]), vc.Y(P.TENDONS[i - 1]["y_end"]), vc.X(-350) - 20,
               f0(P.TENDONS[i - 1]["y_end"] - P.TENDONS[i]["y_end"]), side="left")
    S.text(870, 1048, f"承壓板 {P.ANCHOR_PLATE:.0f}×{P.ANCHOR_PLATE:.0f}（廠商特殊錨碇＋螺旋筋）",
           "lbls", "middle")
    # 預力施工說明
    lines = [f"1. {P.N_TENDON} 束 × {pt['ns']} 股 15.2 mm 低鬆弛鋼絞線，Aps = {f0(pt['Aps'])} mm²。",
             "2. 單端張拉、左右交替，依 T1→T2→T3→T4 順序。"]
    for i, t in enumerate(P.TENDONS):
        lines.append(f"   {t['name']}：{'左' if pt['ends'][i] == 'L' else '右'}端張拉 "
                     f"{pt['fj'][i]:.0f} MPa（{pt['fj'][i] / P.FPU:.3f} f's），"
                     f"伸長約 {pt['elong'][i]:.0f} mm")
    lines += [
        f"3. 錨碇滑動 {P.ANCHOR_SET:.0f} mm；錨碇後端錨 ≤ 0.70 f's、",
        "   滑動影響範圍末端 ≤ 0.83 fy*（8.15.1）。",
        f"4. 摩擦 K = {P.FRICTION_K} /m、μ = {P.FRICTION_MU}（鍍鋅金屬套管）。",
        f"5. 施預力時梁混凝土 f'ci ≥ {P.FCI_GIRDER:.0f} MPa。",
        f"6. 損失（跨中）{pt['losses']['total']:.0f} MPa；有效預力 Pe ≈ {f0(pt['Pe_mid'])} kN。",
        "7. 張拉完成後 48 小時內以無收縮水泥漿全長灌漿。",
        f"8. 預拱：張拉時跨中上拱約 {R['defl']['camber']['at_tension']:.0f} mm。",
        "9. 張拉力與伸長量差異超過 ±7% 時應停工檢討。",
    ]
    S.notes(1060, 650, "預力施工說明", lines, lh=24)
    return S


# ===========================================================================
# S-03 配筋、支承與耐震配置
# ===========================================================================
def sheet_s03(R):
    S = Sheet("S-03", "配筋、支承與耐震配置", R)
    S.frame("如圖示")
    sh, az, dk, b, z = R["shear"], R["anchor"], R["deck"], R["bearing"], R["seismic"]
    hdeck = P.GIRDER_H + P.HAUNCH + P.DECK_T
    # ---------------- 梁端配筋 1:30 ----------------
    k = 4 / 30
    v = View(110, 400, k)
    S.vtitle(390, 52, "梁端配筋（立面）", "S = 1:30", w=200)
    Lx = 4200
    S.rect(v.X(0), v.Y(P.GIRDER_H), Lx * k, P.GIRDER_H * k, "obj")
    S.rect(v.X(0), v.Y(hdeck), Lx * k, P.DECK_T * k, "cut2")
    zz = v.X(Lx)
    S.poly([(zz, v.Y(hdeck) - 6), (zz - 6, v.Y(1500)), (zz + 6, v.Y(900)), (zz, v.Y(0) + 6)],
           "brk", closed=False)
    s0 = sh["zones"][0]["s"]
    x = 50
    while x < Lx - 20:
        S.line(v.X(x), v.Y(P.COVER_STIRRUP), v.X(x), v.Y(hdeck - P.COVER_DECK_TOP - 10), "bar")
        x += s0
    nb = az["n_v"]
    zl = az["zone_len"]
    sp_b = 25 * math.floor(zl / nb / 25)
    for i in range(nb):
        xx = 150 + i * sp_b
        S.line(v.X(xx), v.Y(P.COVER_STIRRUP), v.X(xx), v.Y(P.GIRDER_H - P.COVER_STIRRUP), "barb")
    for xx in (50, 120):
        S.line(v.X(xx), v.Y(P.COVER_STIRRUP), v.X(xx), v.Y(P.GIRDER_H - P.COVER_STIRRUP), "barb")
    for t in P.TENDONS:
        pts = [(v.X(x_), v.Y(D.tendon_y(t, x_ / 1000))) for x_ in range(0, Lx + 1, 100)]
        S.poly(pts, "tendon2", closed=False)
        S.rect(v.X(0) - 5, v.Y(t["y_end"] + P.ANCHOR_PLATE / 2), 5, P.ANCHOR_PLATE * k, "anchor")
        S.text(v.X(0) - 9, v.Y(t["y_end"]) + 5, t["name"], "lblacc", "end")
    S.rect(v.X(P.BEARING_TO_END - b["L"] / 2), v.Y(0), b["L"] * k, b["h_tot"] * k, "obj")
    S.hdim(v.X(150), v.X(150 + (nb - 1) * sp_b), v.Y(0) + 36,
           f"爆裂筋 {nb} 組 @{sp_b}", pos="right")
    S.hdim(v.X(0), v.X(zl), v.Y(0) + 62, f"錨碇一般區 {f0(zl)}", pos="right")
    legend = [
        (f"黑線：D13 @{s0} 雙肢箍筋全長，伸入橋面版兼作水平剪力繫筋", "notes"),
        (f"藍線：爆裂筋 D16 閉合箍 {nb} 組 @{sp_b}（梁端 {zl / 1000:.1f} m 內）、"
         "剝裂筋 2-D16（梁端 150 內）", "notes"),
        (f"每個錨碇另加水平繫筋 {az['n_h']}-D13 U 形（錨碇後 {az['d_h']:.0f} mm 內）；"
         "錨碇局部區螺旋筋依廠商", "notes"),
    ]
    yy = 490
    for ln, cls in legend:
        S.text(70, yy, ln, cls)
        yy += 21
    # ---------------- 橋面版配筋 1:25 ----------------
    k2 = 4 / 25
    v2 = View(760, 300, k2)
    S.vtitle(1180, 52, "橋面版配筋", "S = 1:25", w=170)
    Lx2 = P.OVERHANG + P.SPACING + P.SPACING / 2
    S.rect(v2.X(0), v2.Y(P.DECK_T), Lx2 * k2, P.DECK_T * k2, "cut")
    S.poly(v2.P([(bx * 1000, by * 1000 + P.DECK_T) for bx, by in P.BARRIER]), "cut")
    for gx_ in (P.OVERHANG, P.OVERHANG + P.SPACING):
        h0 = -P.HAUNCH
        pts = [(gx_ - 500, h0), (gx_ + 500, h0), (gx_ + 500, h0 - 150), (gx_ + 125, h0 - 250),
               (gx_ + 125, h0 - 650), (gx_ - 125, h0 - 650), (gx_ - 125, h0 - 250),
               (gx_ - 500, h0 - 150)]
        S.poly(v2.P(pts), "obj")
        S.rect(v2.X(gx_ - 500), v2.Y(0), 1000 * k2, P.HAUNCH * k2, "cut2")
    ct, cb = P.COVER_DECK_TOP, P.COVER_DECK_BOT
    S.line(v2.X(60), v2.Y(P.DECK_T - ct), v2.X(Lx2), v2.Y(P.DECK_T - ct), "bar")
    S.line(v2.X(60), v2.Y(cb), v2.X(Lx2), v2.Y(cb), "bar")
    xx = 100
    while xx < Lx2:
        S.circle(v2.X(xx), v2.Y(P.DECK_T - ct - 14), 2.2, "dot")
        xx += 300
    xx = 100
    while xx < Lx2:
        S.circle(v2.X(xx), v2.Y(cb + 14), 2.2, "dot")
        xx += dk["dist"]["s"]
    S.line(v2.X(Lx2), v2.Y(P.DECK_T + 500), v2.X(Lx2), v2.Y(-800), "cl")
    S.text(v2.X(Lx2), v2.Y(P.DECK_T + 560), "CL", "lbl2", "middle")
    S.leader([(v2.X(1900), v2.Y(P.DECK_T - ct)), (v2.X(2000), v2.Y(P.DECK_T + 450)),
              (v2.X(2060), v2.Y(P.DECK_T + 450))],
             f"頂層橫向 D{dk['over']['bar']}@{dk['over']['s']}（全寬）", "lbl")
    S.leader([(v2.X(1600), v2.Y(P.DECK_T - ct - 14)), (v2.X(1650), v2.Y(P.DECK_T + 250)),
              (v2.X(1710), v2.Y(P.DECK_T + 250))], "頂層縱向 D13@300", "lbls")
    S.leader([(v2.X(1500), v2.Y(cb)), (v2.X(1560), v2.Y(-300)), (v2.X(1600), v2.Y(-300))],
             f"底層橫向 D{dk['pos']['bar']}@{dk['pos']['s']}", "lbl")
    S.leader([(v2.X(1700), v2.Y(cb + 14)), (v2.X(1760), v2.Y(-520)), (v2.X(1800), v2.Y(-520))],
             f"底層縱向 D{dk['dist']['bar']}@{dk['dist']['s']}", "lbls")
    S.vdim(v2.Y(0), v2.Y(P.DECK_T), v2.X(Lx2) + 26, f0(P.DECK_T))
    S.text(v2.X(0), v2.Y(-850), f"保護層：頂 {ct:.0f}、底 {cb:.0f} mm；有效跨徑 S = {dk['S']:.2f} m"
           "（頂翼寬/厚 ≥ 4：翼緣淨距加半翼寬）", "lbls")
    # ---------------- 支承墊 ----------------
    S.vtitle(270, 585, "支承墊詳圖", "平面 S = 1:10、斷面 S = 1:5", w=180)
    k3 = 4 / 10
    v3 = View(110, 850, k3)
    S.rect(v3.X(0), v3.Y(b["W"]), b["L"] * k3, b["W"] * k3, "rubber")
    S.hdim(v3.X(0), v3.X(b["L"]), v3.Y(0) + 24, f"{b['L']}（順橋向）")
    S.vdim(v3.Y(0), v3.Y(b["W"]), v3.X(0) - 18, f"{b['W']}", side="left")
    k4 = 4 / 5
    v4 = View(300, 760, k4)
    y = 0.0
    layers = [("c", b["hc"])] + [("s", b["hs"]), ("r", b["hri"])] * (b["n_int"]) + \
        [("s", b["hs"]), ("c", b["hc"])]
    for kind, t in layers:
        cls = "plate" if kind == "s" else "rubber"
        inset = 0 if kind != "s" else 6
        S.rect(v4.X(inset), v4.Y(y + t), (b["L"] - 2 * inset) * k4, t * k4, cls)
        y += t
    S.vdim(v4.Y(0), v4.Y(y), v4.X(b["L"]) + 20, f"{y:.0f}")
    S.text(v4.X(0), v4.Y(y) - 14, f"橡膠 {b['n_int']}×{b['hri']:.0f} + 2×{b['hc']:.0f}、"
           f"鋼板 {b['n_int'] + 1}×{b['hs']:.0f}", "lbls")
    lines = [f"G = {b['G']} MPa（硬度約 55）；形狀係數 S = {b['S']:.2f}",
             f"σ = {b['sig']:.2f} ≤ {b['lim']:.2f} MPa（10.6.6 方法 B）",
             f"Δs = {b['d_s']:.1f} mm；hrt = {b['hrt']:.0f} ≥ 2Δs",
             f"θ = {b['theta'] * 1e3:.1f} mrad，檢核不上揚",
             f"抗拉拔裝置極限拉力 ≥ {z['QBT']:.0f} kN（每個支承）"]
    yy = 810
    for ln in lines:
        S.text(300, yy, ln, "notes")
        yy += 22
    # ---------------- 橋台座平面（止震塊）1:50 ----------------
    k5 = 4 / 50
    v5 = View(1150, 672, k5)
    S.vtitle(1150, 492, "橋台座平面（止震塊與防落長度）", "S = 1:50", w=330)
    half = P.DECK_WIDTH / 2
    gxs = [-half + P.OVERHANG + i * P.SPACING for i in range(P.N_GIRDER)]
    gap = P.STOPPER_GAP
    seat = P.SEAT_LN
    sg = P.STOPPER_GAP + 15
    S.rect(v5.X(-half - 200), v5.Y(seat), (P.DECK_WIDTH + 400) * k5, seat * k5, "obj")
    S.rect(v5.X(-half - 200), v5.Y(-sg), (P.DECK_WIDTH + 400) * k5, 400 * k5, "cut")
    S.text(v5.X(0), v5.Y(-sg - 200) + 5, "背牆", "lbls", "middle")
    for gx_ in gxs:
        S.rect(v5.X(gx_ - 350), v5.Y(seat + 700), 700 * k5, (seat + 700) * k5, "hid")
        S.rect(v5.X(gx_ - b["W"] / 2), v5.Y(P.BEARING_TO_END + b["L"] / 2), b["W"] * k5,
               b["L"] * k5, "rubber")
    for i in range(P.N_GIRDER - 1):
        x1 = gxs[i] + 350 + gap
        x2 = gxs[i + 1] - 350 - gap
        S.rect(v5.X(x1), v5.Y(seat - 100), (x2 - x1) * k5, (seat - 200) * k5, "key")
        S.text(v5.X((x1 + x2) / 2), v5.Y(seat / 2) + 5, "止震塊", "lbls", "middle")
    S.vdim(v5.Y(0), v5.Y(seat), v5.X(half + 200) + 24, f"LN {seat}")
    S.vdim(v5.Y(-sg), v5.Y(0), v5.X(half + 200) + 24, f"{sg:.0f}")
    S.leader([(v5.X(gxs[0]), v5.Y(seat + 500)), (v5.X(-half - 200) - 10, v5.Y(seat + 500))],
             "梁（底翼 700）", "lbls", "end")
    S.leader([(v5.X(gxs[1] + 350 + gap / 2), v5.Y(seat - 300)),
              (v5.X(gxs[1] + 700), v5.Y(-sg - 400) + 22), (v5.X(gxs[1] + 760), v5.Y(-sg - 400) + 22)],
             f"止震塊與梁間隙 {gap:.0f}（設緩衝材）", "lbls")
    S.text(v5.X(-half - 200), v5.Y(-sg - 400) + 44, "支承中心距梁端 400；座緣距梁端 LN；"
           "背牆與梁端間隙同時作為縱向緩衝", "lbls")
    lines = [
        f"1. 橋址 {P.SITE}，近斷層（車籠埔、彰化等）；用途係數 {P.IMPORTANCE}。",
        f"2. 等級 II：SII,S = {z['sp']['II'][0]:.2f}、SII,1 = {z['sp']['II'][1]:.3f}；"
        f"等級 III：{z['sp']['III'][0]:.2f}、{z['sp']['III'][1]:.3f}。",
        f"3. 只靠支承墊：週期 {z['T_pad']:.2f} s、等級 II 位移 {z['u2']:.0f} mm，不可行。",
        f"4. 梁間止震塊每座橋台 {z['n_key']} 塊，兩向共用；橫向設計力 {f0(z['H_T'])} kN，",
        f"   每塊剪力摩擦筋 ≥ {f0(z['Avf_T'])} mm²、剪力面積 ≥ {z['Acv_T'] / 1e6:.2f} m²。",
        f"5. 縱向設計力 {f0(z['H_L'])} kN，由背牆承受（保守按單一橋台）。",
        f"6. 垂直地震係數 {z['kv']:.3f}；拉拔 Q/Rd = {z['Q_ratio']:.2f}，需設抗拉拔裝置。",
        f"7. 防落長度 LN = {seat} mm（規範最小 {z['LN_min'] * 10:.0f}；uR + uG = "
        f"{(z['gap'] + z['uG']) * 10:.0f}）。",
        f"8. 梁端間隙 ≥ {z['SB'] * 10:.0f} mm；伸縮縫伸縮量 ≥ {z['LE'] * 10:.0f} mm 並滿足常時需求。",
        "9. 橋台、基礎、液化檢核需地質資料，另案設計。",
    ]
    S.notes(700, 805, "耐震與支承配置說明", lines, lh=22)
    return S


def build_all(R):
    return [sheet_s01(R), sheet_s02(R), sheet_s03(R)]
