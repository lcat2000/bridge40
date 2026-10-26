"""
斷面性質：多邊形公式（shoelace），並以拆成矩形與梯形的手算核對。
"""
import functools
import math

from . import params as P


def polygon_props(pts):
    """回傳 (面積, 形心 y, 對形心水平軸慣性矩)。"""
    A = Sy = Ixx = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        c = x0 * y1 - x1 * y0
        A += c
        Sy += (y0 + y1) * c
        Ixx += (y0 * y0 + y0 * y1 + y1 * y1) * c
    A /= 2
    yc = Sy / (6 * A)
    Ic = Ixx / 12 - A * yc * yc
    return A, yc, Ic


def width_at(pts, y):
    """多邊形在高度 y 的寬度。"""
    xs = []
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        if y0 != y1 and (y0 - y) * (y1 - y) <= 0:
            xs.append(x0 + (x1 - x0) * (y - y0) / (y1 - y0))
    return max(xs) - min(xs) if len(xs) >= 2 else 0.0


def effective_flange():
    """8.8.3：有效腹板寬與合成斷面有效翼寬。"""
    web_eff = min(6 * P.TOP_FLANGE_T + P.WEB_T, P.TOP_FLANGE_W)
    b = min(P.SPAN / 4, 2 * 6 * P.DECK_T + web_eff,
            (P.SPACING - web_eff) + web_eff)
    return web_eff, b


def composite(A, yb, I, Ec_g, Ec_d, b_eff):
    """合成斷面（版轉換成梁混凝土；托肩只計重量、不計勁度，偏保守）。"""
    n = Ec_d / Ec_g
    Ad = b_eff * n * P.DECK_T
    yd = P.GIRDER_H + P.HAUNCH + P.DECK_T / 2
    Ac = A + Ad
    ybc = (A * yb + Ad * yd) / Ac
    Id = b_eff * n * P.DECK_T ** 3 / 12
    Icc = I + A * (ybc - yb) ** 2 + Id + Ad * (yd - ybc) ** 2
    return dict(n=n, A=Ac, yb=ybc, I=Icc)


@functools.lru_cache(maxsize=1)
def properties():
    A, yb, I = polygon_props(P.GIRDER)
    # 手算核對：底翼 + 梯形 + 腹板 + 梯形 + 頂翼
    hand = (P.BOT_FLANGE_W * P.BOT_FLANGE_T
            + (P.BOT_FLANGE_W + P.WEB_T) / 2 * P.BOT_TAPER
            + P.WEB_T * (P.GIRDER_H - P.BOT_FLANGE_T - P.BOT_TAPER - P.TOP_TAPER - P.TOP_FLANGE_T)
            + (P.WEB_T + P.TOP_FLANGE_W) / 2 * P.TOP_TAPER
            + P.TOP_FLANGE_W * P.TOP_FLANGE_T)
    assert abs(hand - A) < 1e-6, (hand, A)
    # 薄條積分核對慣性矩
    ys = [i + 0.5 for i in range(P.GIRDER_H)]
    ws = [width_at(P.GIRDER, y) for y in ys]
    A2 = sum(ws)
    yb2 = sum(w * y for w, y in zip(ws, ys)) / A2
    I2 = sum(w * (y - yb2) ** 2 for w, y in zip(ws, ys)) + sum(w / 12 for w in ws)
    assert abs(A2 - A) / A < 1e-3 and abs(I2 - I) / I < 2e-3, (A2, A, I2, I)
    Ae, ybe, Ie = polygon_props(P.END_BLOCK)
    Ecg, Ecd = P.Ec(P.FC_GIRDER), P.Ec(P.FC_DECK)
    web_eff, b_eff = effective_flange()
    comp = composite(A, yb, I, Ecg, Ecd, b_eff)
    comp_end = composite(Ae, ybe, Ie, Ecg, Ecd, b_eff)
    return dict(
        A=A, yb=yb, I=I, yt=P.GIRDER_H - yb, Sb=I / yb, St=I / (P.GIRDER_H - yb),
        A_end=Ae, yb_end=ybe, I_end=Ie,
        Ec_girder=Ecg, Ec_deck=Ecd, Eci=P.Ec(P.FCI_GIRDER),
        web_eff=web_eff, b_eff=b_eff, comp=comp, comp_end=comp_end,
        Sbc=comp["I"] / comp["yb"], Stc=comp["I"] / (P.GIRDER_H - comp["yb"]),
        Stc_deck=comp["I"] / (P.GIRDER_H + P.HAUNCH + P.DECK_T - comp["yb"]) / comp["n"],
        h_comp=P.GIRDER_H + P.HAUNCH + P.DECK_T,
        check_strip=dict(A=A2, yb=yb2, I=I2),
    )


def web_width(x_from_end):
    """梁腹寬沿梁長（端塊 700 → 漸變 → 250 mm）。x 自梁端起算（mm）。"""
    xe = min(x_from_end, P.GIRDER_LEN - x_from_end)
    if xe <= P.END_BLOCK_FULL:
        return P.BOT_FLANGE_W
    if xe <= P.END_BLOCK_FULL + P.END_BLOCK_TAPER:
        t = (xe - P.END_BLOCK_FULL) / P.END_BLOCK_TAPER
        return P.BOT_FLANGE_W + (P.WEB_T - P.BOT_FLANGE_W) * t
    return P.WEB_T


def net_section(sec, ys):
    """扣除套管開孔的淨斷面：後拉構材灌漿前的斷面性質（〔設〕8.17.1）。
    sec：section_at() 的毛斷面；ys：各套管中心高度（mm，取鋼腱線形位置）。"""
    Ah = math.pi * (P.DUCT_OD / 2) ** 2
    Ih = math.pi * P.DUCT_OD ** 4 / 64
    A, yb, I = sec["A"], sec["yb"], sec["I"]
    An = A - Ah * len(ys)
    ybn = (A * yb - Ah * sum(ys)) / An
    In = I + A * (yb - ybn) ** 2 - sum(Ah * (y - ybn) ** 2 + Ih for y in ys)
    return dict(bw=sec["bw"], A=An, yb=ybn, I=In, Sb=In / ybn, St=In / (P.GIRDER_H - ybn))


def section_at(x_from_end, props):
    """沿梁長的非合成斷面性質（端塊段依腹板寬線性內插面積與慣性矩，近似）。"""
    bw = web_width(x_from_end)
    t = (bw - P.WEB_T) / (P.BOT_FLANGE_W - P.WEB_T)
    A = props["A"] + t * (props["A_end"] - props["A"])
    yb = props["yb"] + t * (props["yb_end"] - props["yb"])
    I = props["I"] + t * (props["I_end"] - props["I"])
    return dict(bw=bw, A=A, yb=yb, I=I, Sb=I / yb, St=I / (P.GIRDER_H - yb))
