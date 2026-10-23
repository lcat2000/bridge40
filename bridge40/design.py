"""
40 m 後拉預力 I 型梁：依交通部公路橋梁設計規範與耐震設計規範設計
=================================================================
每一步引用的條文寫在函式說明；單位 N、mm、MPa（另註明 kN、m 者除外）。
"""
import math

import numpy as np

from . import analysis as A
from . import params as P
from . import section as S

L = A.L                      # m
LG = P.GIRDER_LEN / 1000     # m
XE = P.BEARING_TO_END / 1000
X = A.X                      # 支承座標（m），0..L


# ===========================================================================
# 共用：簡支梁在分布載重與集中載重下的彎矩與剪力
# ===========================================================================
def beam_effects(span, w_func, points=(), xs=None, n=8000):
    xx = np.linspace(0.0, span, n + 1)
    w = w_func(xx)
    dx = xx[1] - xx[0]
    W = np.trapezoid(w, xx)
    Mw = np.trapezoid(w * xx, xx)
    RB = (Mw + sum(p * a for a, p in points)) / span
    RA = W + sum(p for _, p in points) - RB
    cumW = np.concatenate([[0.0], np.cumsum((w[1:] + w[:-1]) / 2 * dx)])
    V = RA - cumW - sum(p * (xx > a) for a, p in points)
    M = np.concatenate([[0.0], np.cumsum((V[1:] + V[:-1]) / 2 * dx)])
    if xs is None:
        xs = xx
    return np.interp(xs, xx, M), np.interp(xs, xx, V), RA, RB


def end_block_extra(xg):
    """端塊多出的面積（mm²），xg 自梁端起算（m）。"""
    xe = np.minimum(xg, LG - xg) * 1000
    full = P.END_BLOCK_FULL
    tap = P.END_BLOCK_TAPER
    t = np.clip((full + tap - xe) / tap, 0.0, 1.0)
    props = S.properties()
    return t * (props["A_end"] - props["A"])


# ===========================================================================
# 1. 輪重分擔（表 4.1、4.2 節）
# ===========================================================================
def lever_reaction(wheels, g, gx, s):
    r = 0.0
    for w in wheels:
        xg = gx[g]
        if g > 0 and gx[g - 1] <= w <= xg:
            r += (w - gx[g - 1]) / s
        elif g < len(gx) - 1 and xg <= w <= gx[g + 1]:
            r += (gx[g + 1] - w) / s
        elif g == 0 and w < xg:
            r += 1 + (xg - w) / s
    return r


def distribution():
    s = P.SPACING / 1000
    df_m = s / 1.65                                   # 預力混凝土梁上之混凝土橋面，兩車道以上
    gx = [P.OVERHANG / 1000 + i * s for i in range(P.N_GIRDER)]
    xmin = P.BARRIER_W / 1000 + 0.6                   # 車道載重寬 3.0 m、輪距 1.8 m → 輪距寬邊 0.6 m
    xmax = P.DECK_WIDTH / 1000 - P.BARRIER_W / 1000 - 0.6
    best_ext = best_int = 0.0
    for x1 in np.arange(xmin, xmax - 1.8 + 1e-9, 0.01):
        cfgs = [[x1, x1 + 1.8]]
        for gap in np.arange(1.2, 3.0, 0.05):
            x3 = x1 + 1.8 + gap
            if x3 + 1.8 <= xmax + 1e-9:
                cfgs.append([x1, x1 + 1.8, x3, x3 + 1.8])
        for wh in cfgs:
            best_ext = max(best_ext, lever_reaction(wh, 0, gx, s))
            best_int = max(best_int, lever_reaction(wh, 1, gx, s))
    return dict(DF_M_int=df_m, DF_ext=best_ext, DF_M=max(df_m, best_ext),
                DF_V_end=max(best_int, best_ext), DF_V_int=best_int)


# ===========================================================================
# 2. 呆載重（3.3 單位重）
# ===========================================================================
def dead_loads(props):
    g = P.GAMMA_RC
    bar = P.BARRIER
    A_bar = abs(sum(bar[i][0] * bar[(i + 1) % 6][1] - bar[(i + 1) % 6][0] * bar[i][1]
                    for i in range(6))) / 2
    bay = (P.SPACING - P.WEB_T) / 1000
    d = dict(
        w_girder=props["A"] / 1e6 * g,
        w_deck=P.SPACING / 1000 * P.DECK_T / 1000 * g,
        w_haunch=P.TOP_FLANGE_W / 1000 * P.HAUNCH / 1000 * g,
        w_barrier=2 * A_bar * g / P.N_GIRDER,
        w_dw=P.PAVEMENT_T / 1000 * P.GAMMA_AC * P.ROADWAY / 1000 / P.N_GIRDER,
        P_dia_mid=P.DIAPHRAGM_T / 1000 * bay * P.DIAPHRAGM_H / 1000 * g,
        P_dia_end=P.DIAPHRAGM_T / 1000 * bay * (P.GIRDER_H - 250) / 1000 * g,
        A_bar=A_bar,
    )
    return d


def dl_along(d, xs):
    """支承座標 xs（m）的各階段呆載重彎矩、剪力（kN·m、kN）與支承反力。"""
    def w_g(x):
        return d["w_girder"] + end_block_extra(x + XE) / 1e6 * P.GAMMA_RC
    Mg, Vg, RAg, _ = beam_effects(L, w_g, xs=xs)
    w_nc2 = d["w_deck"] + d["w_haunch"]
    Mnc2, Vnc2, RAnc2, _ = beam_effects(L, lambda x: np.full_like(x, w_nc2),
                                        points=[(L / 2, d["P_dia_mid"])], xs=xs)
    wc = d["w_barrier"] + d["w_dw"]
    Mc, Vc, RAc, _ = beam_effects(L, lambda x: np.full_like(x, wc), xs=xs)
    # 梁端懸出 0.4 m（梁、版、托肩、護欄、鋪面）與端隔梁只進支承反力
    over = XE * (d["w_girder"] + end_block_extra(np.array([XE / 2]))[0] / 1e6 * P.GAMMA_RC
                 + w_nc2 + wc)
    R_D = RAg + RAnc2 + RAc + over + d["P_dia_end"]
    return dict(Mg=Mg, Vg=Vg, Mnc=Mg + Mnc2, Vnc=Vg + Vnc2, Mc=Mc, Vc=Vc,
                R_D=R_D, R_g=RAg, R_nc=RAnc2, R_c=RAc, R_over=over)


def stage1_girder_moment(d, xg):
    """施預力時：梁自重、支承於梁端（跨徑為梁長）。xg 自梁端（m）。"""
    def w_g(x):
        return d["w_girder"] + end_block_extra(x) / 1e6 * P.GAMMA_RC
    M, V, _, _ = beam_effects(LG, w_g, xs=xg)
    return M


# ===========================================================================
# 3. 鋼腱幾何、摩擦與錨碇滑動（8.15.1、8.16.1）
# ===========================================================================
def tendon_y(t, xg):
    """拋物線：梁端 y_end → 跨中 y_mid。xg 自左梁端（m）。"""
    h = LG / 2
    u = 1 - np.asarray(xg) / h
    return t["y_mid"] + (t["y_end"] - t["y_mid"]) * u ** 2


def tendon_slope(t, xg):
    h = LG / 2
    return -2 * (t["y_end"] - t["y_mid"]) / 1000 / h * (1 - np.asarray(xg) / h)   # rad


def alpha_lateral(xs_from_jack):
    """側向 S 形彎轉的累計轉角（假設）：鋼腱進入底翼後才側移，0.35Lg–0.45Lg 與
    0.55Lg–0.65Lg 各累計 LATERAL_ALPHA。"""
    a = P.LATERAL_ALPHA
    x = np.asarray(xs_from_jack) / LG
    return (a * np.clip((x - 0.35) / 0.10, 0, 1) + a * np.clip((x - 0.55) / 0.10, 0, 1))


def friction_profile(t, fj, xs):
    """自張拉端起算 xs（m）的摩擦後應力（8-1 式）。"""
    h = LG / 2
    curv = 2 * (t["y_end"] - t["y_mid"]) / 1000 / h ** 2          # y''（1/m）
    alpha = curv * xs + alpha_lateral(xs)
    return fj * np.exp(-(P.FRICTION_K * xs + P.FRICTION_MU * alpha)), alpha


def seat_profile(t, fj, xs):
    """錨碇滑動：找 xset 使 ∫2(f − f(xset))dx = Ep·Δ。回傳錨碇後應力與 xset。"""
    f, alpha = friction_profile(t, fj, xs)
    target = P.EP * P.ANCHOR_SET / 1000                            # MPa·m
    dx = xs[1] - xs[0]
    area = 2 * (np.cumsum(f) - (np.arange(len(xs)) + 1) * f) * dx
    hit = np.nonzero(area >= target)[0]
    xset = xs[hit[0]] if len(hit) else xs[-1]
    fk = np.interp(xset, xs, f)
    fs = np.where(xs < xset, 2 * fk - f, f)
    return fs, f, xset, alpha


def jack_stress(t):
    """8.15.1：錨碇剛完成時端錨處 ≤ 0.70 f's、滑動影響範圍末端 ≤ 0.83 fy*；
    暫時施預力 ≤ 0.90 fy*。取滿足三者的最大張拉應力。"""
    xs = np.linspace(0, LG, 4081)
    fj = 0.90 * P.FY_STAR
    while fj > 0.5 * P.FPU:
        fs, f, xset, _ = seat_profile(t, fj, xs)
        if fs[0] <= 0.70 * P.FPU + 1e-9 and fs.max() <= 0.83 * P.FY_STAR + 1e-9:
            return fj
        fj -= 1.0
    raise RuntimeError("找不到可行的張拉應力")


def tendon_stresses(fj_list):
    """各鋼腱沿梁長（自左梁端 xg）錨碇後應力。"""
    xs = np.linspace(0, LG, 4081)
    out = []
    for t, fj, end in zip(P.TENDONS, fj_list, P.JACK_END):
        fs, f, xset, alpha = seat_profile(t, fj, xs)
        if end == "R":
            fs, f, alpha = fs[::-1], f[::-1], alpha[::-1]
        out.append(dict(name=t["name"], fj=fj, fs=fs, f=f, xset=xset, alpha=alpha,
                        end=end))
    return xs, out


# ===========================================================================
# 4. 預力梁設計
# ===========================================================================
def girder_design(props, d, an, dist):
    fc, fci, fcd = P.FC_GIRDER, P.FCI_GIRDER, P.FC_DECK
    comp = props["comp"]
    Ic, ybc = comp["I"], comp["yb"]
    Sbc, Stc, Stc_d = props["Sbc"], props["Stc"], props["Stc_deck"]
    hc = props["h_comp"]
    xs_b = X                                         # 支承座標
    xg_b = X + XE                                    # 換到梁座標
    dl = dl_along(d, xs_b)
    M_LL = dist["DF_M"] / 2 * an["M_lane"]
    Mu = 1.3 * (dl["Mnc"] + dl["Mc"] + 1.67 * M_LL)
    # 鋼腱
    fj_list = [jack_stress(t) for t in P.TENDONS]
    xs_t, tend = tendon_stresses(fj_list)
    Mg1 = stage1_girder_moment(d, xs_t)
    Ep, Eci = P.EP, props["Eci"]
    lim = dict(
        c_rel=-0.55 * fci, t_rel_nb=min(1.38, 0.25 * math.sqrt(fci)),
        t_rel_b=0.623 * math.sqrt(fci), t_fin=0.498 * math.sqrt(fc),
        c_perm=-0.40 * fc, c_all=-0.60 * fc, c_deck=-0.60 * fcd,
        fse_max=0.80 * P.FY_STAR,
    )
    SH = 0.8 * (117.2 - 1.034 * P.RH)
    imid_t = len(xs_t) // 2
    imid_b = int(np.argmin(np.abs(xs_b - L / 2)))

    def evaluate(ns):
        Aps_t = ns * P.AP
        y_t = np.array([tendon_y(t, xs_t) for t in P.TENDONS])         # (4, n)
        f_fs = np.array([tt["fs"] for tt in tend])
        f_fr = np.array([tt["f"] for tt in tend])
        # 跨中的損失（8.16.2）
        sec = S.section_at(LG / 2 * 1000, props)
        A_, I_, yb_ = sec["A"], sec["I"], sec["yb"]
        Pm = Aps_t * f_fs[:, imid_t]
        ym = y_t[:, imid_t]
        e_m = yb_ - np.sum(Pm * ym) / np.sum(Pm)
        ES = 0.0
        for _ in range(30):
            Pi = Aps_t * (f_fs[:, imid_t] - ES)
            fcir = Pi.sum() / A_ + Pi.sum() * e_m ** 2 / I_ - Mg1[imid_t] * 1e6 * e_m / I_
            ES = 0.5 * Ep / Eci * fcir
        y_cg = yb_ - e_m
        fcds = ((dl["Mnc"][imid_b] - dl["Mg"][imid_b]) * 1e6 * e_m / I_
                + dl["Mc"][imid_b] * 1e6 * (ybc - y_cg) / Ic)
        CRc = max(12 * fcir - 7 * fcds, 0.0)
        FR = max(0.0, 0.70 * P.FPU - f_fr[:, imid_t].mean())
        CRs = 34.5 - 0.07 * FR - 0.1 * ES - 0.05 * (SH + CRc)
        loss = SH + ES + CRc + CRs
        # 沿梁長：施預力時（ES 已發生）與最終
        Pi_t = Aps_t * (f_fs - ES)
        Pe_t = Aps_t * (f_fs - loss)
        rows = []
        for k in range(0, len(xs_t), 10):
            xg = xs_t[k]
            sec = S.section_at(xg * 1000, props)
            e_t = sec["yb"] - y_t[:, k]
            Pi, Mpi = Pi_t[:, k].sum(), np.sum(Pi_t[:, k] * e_t)
            Pe, Mpe = Pe_t[:, k].sum(), np.sum(Pe_t[:, k] * e_t)
            mg1 = Mg1[k] * 1e6
            ft_i = -Pi / sec["A"] + Mpi / sec["St"] - mg1 / sec["St"]
            fb_i = -Pi / sec["A"] - Mpi / sec["Sb"] + mg1 / sec["Sb"]
            row = dict(xg=xg, ft_i=ft_i, fb_i=fb_i, Pi=Pi, Pe=Pe, Mpe=Mpe, Mpi=Mpi,
                       ycg=float(np.sum(Pe_t[:, k] * y_t[:, k]) / Pe), sec=sec)
            xb = xg - XE
            if 0 <= xb <= L:
                mnc = np.interp(xb, xs_b, dl["Mnc"]) * 1e6
                mc = np.interp(xb, xs_b, dl["Mc"]) * 1e6
                mll = np.interp(xb, xs_b, M_LL) * 1e6
                row.update(
                    fb_f=-Pe / sec["A"] - Mpe / sec["Sb"] + mnc / sec["Sb"] + (mc + mll) / Sbc,
                    fb_perm=-Pe / sec["A"] - Mpe / sec["Sb"] + mnc / sec["Sb"] + mc / Sbc,
                    ft_perm=-Pe / sec["A"] + Mpe / sec["St"] - mnc / sec["St"] - mc / Stc,
                    ft_ll=-mll / Stc,
                    fd_top=-(mc + mll) / Stc_d)
                row["ft_all"] = row["ft_perm"] + row["ft_ll"]
                row["ft_mix"] = 0.5 * row["ft_perm"] + row["ft_ll"]
            rows.append(row)
        fin = [r for r in rows if "fb_f" in r]
        ok = dict(
            rel_c=min(r["fb_i"] for r in rows) >= lim["c_rel"] and
            min(r["ft_i"] for r in rows) >= lim["c_rel"],
            rel_t=max(r["ft_i"] for r in rows) <= lim["t_rel_b"] and
            max(r["fb_i"] for r in rows) <= lim["t_rel_b"],
            fin_t=max(r["fb_f"] for r in fin) <= lim["t_fin"],
            fin_c1=min(r["ft_perm"] for r in fin) >= lim["c_perm"],
            fin_c2=min(r["ft_mix"] for r in fin) >= lim["c_perm"],
            fin_c3=min(r["ft_all"] for r in fin) >= lim["c_all"],
        )
        losses = dict(SH=SH, ES=ES, CRc=CRc, CRs=CRs, FR=FR, fcir=fcir, fcds=fcds, total=loss)
        return ok, rows, losses, Pe_t, Pi_t, y_t

    chosen = None
    for ns in range(6, P.MAX_STRANDS_PER_TENDON + 1):
        ok, rows, losses, Pe_t, Pi_t, y_t = evaluate(ns)
        if all(ok.values()):
            chosen = ns
            break
    if chosen is None:
        raise RuntimeError(f"12 股仍不足：{ok}")
    ns = chosen
    Aps = ns * P.AP * P.N_TENDON
    fin = [r for r in rows if "fb_f" in r]
    # 載重因數設計：沿梁長 φMn 與 Mu（8.17、φ = 0.95 後拉場鑄）
    phi = 0.95
    beta1 = 0.85
    b = props["b_eff"]
    t_fl = P.DECK_T
    st = []
    for r in fin:
        xb = r["xg"] - XE
        dp = hc - r["ycg"]
        p_ = Aps / (b * dp)
        fsu = P.FPU * (1 - 0.28 / beta1 * p_ * P.FPU / fcd)
        a = Aps * fsu / (0.85 * fcd * b)
        if a <= t_fl:
            Mn = Aps * fsu * dp * (1 - 0.6 * p_ * fsu / fcd)
            Asr = Aps
            bw_ = b
            flanged = False
        else:
            bw_ = P.TOP_FLANGE_W
            Asf = 0.85 * fcd * (b - bw_) * t_fl / fsu
            Asr = Aps - Asf
            Mn = (Asr * fsu * dp * (1 - 0.6 * Asr * fsu / (bw_ * dp * fcd))
                  + 0.85 * fcd * (b - bw_) * t_fl * (dp - 0.5 * t_fl))
            flanged = True
        mu = np.interp(xb, xs_b, Mu)
        st.append(dict(x=xb, dp=dp, fsu=fsu, a=a, phiMn=phi * Mn / 1e6, Mu=mu,
                       index=Asr * fsu / (bw_ * dp * fcd), flanged=flanged))
    i_mid = int(np.argmin([abs(s["x"] - L / 2) for s in st]))
    s_mid = st[i_mid]
    worst_flex = max(s["Mu"] / s["phiMn"] for s in st if s["Mu"] > 0)
    # 最少鋼材量 φMn ≥ 1.2 Mcr*
    r_mid = min(fin, key=lambda r: abs(r["xg"] - LG / 2))
    sec = r_mid["sec"]
    fpe_b = r_mid["Pe"] / sec["A"] + r_mid["Mpe"] / sec["Sb"]
    fr = 0.623 * math.sqrt(fc)
    Mdnc = dl["Mnc"][imid_b] * 1e6
    Mcr = ((fr + fpe_b) * Sbc - Mdnc * (Sbc / sec["Sb"] - 1)) / 1e6
    # 放鬆／施預力時梁頂拉應力的握裹鋼筋
    worst_t = max(rows, key=lambda r: r["ft_i"])
    top_bars = None
    if worst_t["ft_i"] > lim["t_rel_nb"]:
        sec_w = worst_t["sec"]
        poly = P.END_BLOCK if sec_w["bw"] > P.WEB_T + 1 else P.GIRDER
        ft_, fb_ = worst_t["ft_i"], worst_t["fb_i"]
        c_t = ft_ / (ft_ - fb_) * P.GIRDER_H
        ys_ = np.linspace(P.GIRDER_H - c_t, P.GIRDER_H, 400)
        f_ = ft_ * (ys_ - (P.GIRDER_H - c_t)) / c_t
        T = np.trapezoid(f_ * np.array([S.width_at(poly, v) for v in ys_]), ys_)
        As = T / (0.5 * P.FY)
        top_bars = dict(x=worst_t["xg"], c_t=c_t, T=T / 1e3, As=As,
                        n_d16=math.ceil(As / 198.6))
    # 撓度：活載重 + 衝擊（8.11.3，L/800）
    EI_g = props["Ec_girder"] * 1e3 * comp["I"] / 1e12          # kN·m²（一支梁）
    EI_lane = EI_g * P.N_GIRDER / P.N_LANES
    ID = an["ID"] * (1.0e6 / EI_lane)                            # m
    veh = A.truck(P.AXLE_GAP)
    offs = [int(round(o / A.DX)) for o, _ in veh]
    dmax = 0.0
    for dd in (1, -1):
        for k in range(-A.N, 2 * A.N + 1):
            cols = [k + dd * oi for oi in offs if 0 <= k + dd * oi <= A.N]
            ws = [p for (o, p), oi in zip(veh, offs) if 0 <= k + dd * oi <= A.N]
            if cols:
                dmax = max(dmax, float((ID[:, cols] @ np.array(ws)).max()))
    d_lane = (5 * P.LANE_W * L ** 4 / (384 * EI_lane) + P.LANE_PM * L ** 3 / (48 * EI_lane))
    defl = (1 + an["IM_M"]) * max(dmax, d_lane) * 1000
    # 預拱（瞬時）：施預力時、加上橋面版後、全部呆載重
    camber = camber_calc(props, d, dl, xs_t, Pi_t, Pe_t, y_t)
    return dict(
        ns=ns, Aps=Aps, fj=fj_list, tend=tend, xs_t=xs_t, rows=rows, losses=losses,
        lim=lim, Mu=Mu, M_LL=M_LL, dl=dl, Pe_t=Pe_t, Pi_t=Pi_t, y_t=y_t,
        strength=st, s_mid=s_mid, worst_flex=worst_flex, Mcr=Mcr, phi=phi,
        top_bars=top_bars, defl=defl, defl_truck=dmax * 1000 * (1 + an["IM_M"]),
        defl_lane=d_lane * 1000 * (1 + an["IM_M"]), camber=camber,
    )


def camber_calc(props, d, dl, xs_t, Pi_t, Pe_t, y_t):
    """以曲率雙重積分求撓度（向上為正，mm）。"""
    n = len(xs_t)
    dx = xs_t[1] - xs_t[0]

    def deflect(kappa, span_idx):
        # kappa：1/m（下凹為正）；簡支在 span_idx 兩端
        i0, i1 = span_idx
        k = kappa[i0:i1 + 1]
        th = np.concatenate([[0.0], np.cumsum((k[1:] + k[:-1]) / 2 * dx)])
        y = np.concatenate([[0.0], np.cumsum((th[1:] + th[:-1]) / 2 * dx)])
        xl = xs_t[i0:i1 + 1] - xs_t[i0]
        y = y - y[-1] * xl / xl[-1]
        out = np.zeros(n)
        out[i0:i1 + 1] = -y
        return out * 1000                                      # mm，下垂為正

    Eci = props["Eci"]
    Ec = props["Ec_girder"]
    secs = [S.section_at(x * 1000, props) for x in xs_t]
    I_x = np.array([s["I"] for s in secs])
    e_x = np.array([s["yb"] for s in secs])[None, :] - y_t
    Mpi = np.sum(Pi_t * e_x, axis=0) / 1e6                      # kN·m（向上）
    Mpe = np.sum(Pe_t * e_x, axis=0) / 1e6
    Mg1 = stage1_girder_moment(d, xs_t)
    full = (0, n - 1)
    k1 = (Mg1 - Mpi) * 1e6 / (Eci * I_x) * 1000                 # 1/m
    d1 = deflect(k1, full)
    i0 = int(round(XE / dx))
    i1 = n - 1 - i0
    xb = xs_t - XE
    Mnc2 = np.interp(xb, X, dl["Mnc"] - dl["Mg"], left=0, right=0)
    Mc = np.interp(xb, X, dl["Mc"], left=0, right=0)
    Ic = props["comp"]["I"]
    k2 = Mnc2 * 1e6 / (Ec * I_x) * 1000
    k3 = Mc * 1e6 / (Ec * Ic) * 1000
    d2 = deflect(k2, (i0, i1))
    d3 = deflect(k3, (i0, i1))
    dp = deflect((Mpi - Mpe) * 1e6 / (Ec * I_x) * 1000, full)  # 預力損失使上拱減少
    mid = n // 2
    return dict(at_tension=-d1[mid], deck=d2[mid], comp_dl=d3[mid], loss=dp[mid],
                final_inst=-(d1[mid] + d2[mid] + d3[mid] + dp[mid]))


# ===========================================================================
# 5. 剪力（8.20）、水平剪力、錨碇區（8.21）
# ===========================================================================
def shear_design(props, d, an, dist, gd, pad_len):
    fc = P.FC_GIRDER
    hc = props["h_comp"]
    comp = props["comp"]
    Ic, ybc = comp["I"], comp["yb"]
    Sbc = props["Sbc"]
    dl = gd["dl"]
    DF_M, DF_V = dist["DF_M"], dist["DF_V_end"]
    x_q = L / 4

    def df_v(x):
        return DF_V + (DF_M - DF_V) * min(x / x_q, 1.0)

    IV = an["IV"]
    veh_list = []
    for d_ in (1, -1):
        veh_list.append([(d_ * o, p) for o, p in A.truck(P.AXLE_GAP)])
    V_LL = np.zeros(A.N + 1)
    for i, x in enumerate(X):
        if x > L / 2 + 1e-9:
            break
        Iv = A.impact(L - x)
        best = 0.0
        for veh in veh_list:
            for k in range(len(veh)):
                ref = x - veh[k][0]
                v = 0.0
                for j, (o, p) in enumerate(veh):
                    a = ref + o
                    if a < x - 1e-9 or a > L:
                        continue
                    v += p / 2 * (df_v(x) if j == k else DF_M) * (L - a) / L
                best = max(best, v)
        v_lane = (P.LANE_PV / 2 * df_v(x) * (L - x) / L
                  + P.LANE_W / 2 * DF_M * (L - x) ** 2 / (2 * L))
        V_LL[i] = (1 + Iv) * max(best, v_lane)
    Vd = dl["Vnc"] + dl["Vc"]
    Md = dl["Mnc"] + dl["Mc"]
    Vu = 1.3 * (Vd + 1.67 * V_LL)
    Mu_env = gd["Mu"]
    xs_t = gd["xs_t"]
    Pe_t, y_t = gd["Pe_t"], gd["y_t"]
    slopes = np.array([tendon_slope(t, xs_t) for t in P.TENDONS])
    rows = []
    for i, x in enumerate(X):
        if x > L / 2 + 1e-9:
            break
        xg = x + XE
        k = int(round(xg / (xs_t[1] - xs_t[0])))
        sec = S.section_at(xg * 1000, props)
        bw = sec["bw"]
        Pe = Pe_t[:, k].sum()
        ycg = float(np.sum(Pe_t[:, k] * y_t[:, k]) / Pe)
        e = sec["yb"] - ycg
        dd = max(hc - ycg, 0.8 * hc)
        Vp = float(np.sum(Pe_t[:, k] * np.sin(np.arctan(-slopes[:, k]))))
        yj = ybc if ybc < 1850 else 1850.0
        fpc = Pe / sec["A"] - Pe * e * (yj - sec["yb"]) / sec["I"] + \
            dl["Mnc"][i] * 1e6 * (yj - sec["yb"]) / sec["I"]
        fpe = Pe / sec["A"] + Pe * e / sec["Sb"]
        fd = dl["Mnc"][i] * 1e6 / sec["Sb"] + dl["Mc"][i] * 1e6 / Sbc
        Mcr = Sbc * (0.498 * math.sqrt(fc) + fpe - fd)
        Vi = max(Vu[i] - Vd[i], 1e-6) * 1e3
        Mmax = max(Mu_env[i] - Md[i], 1e-6) * 1e6
        Vci = 0.05 * math.sqrt(fc) * bw * dd + Vd[i] * 1e3 + Vi * Mcr / Mmax
        Vci = max(Vci, 0.14 * math.sqrt(fc) * bw * dd)
        Vcw = (0.29 * math.sqrt(fc) + 0.3 * fpc) * bw * dd + Vp
        rows.append(dict(x=x * 1000, Vu=Vu[i] * 1e3, Vd=Vd[i] * 1e3, d=dd, bw=bw, Vp=Vp,
                         fpc=fpc, Vci=Vci, Vcw=Vcw, Vc=min(Vci, Vcw)))
    x_crit = pad_len / 2 + hc / 2
    rc = min(rows, key=lambda r: abs(r["x"] - x_crit))
    phi, fsy = 0.90, P.FY
    bars = [(13, 2 * 126.7), (16, 2 * 198.6)]
    out = []
    for r in rows:
        rr = rc if r["x"] < x_crit else r
        Vs_req = max(rr["Vu"] / phi - rr["Vc"], 0.0)
        half = Vs_req > 0.33 * math.sqrt(fc) * rr["bw"] * rr["d"]
        s_max = min(0.75 * hc, 600) / (2 if half else 1)
        res = None
        for db, Av in bars:
            s_req = Av * fsy * rr["d"] / Vs_req if Vs_req > 0 else 1e9
            s_min = Av * fsy / (0.345 * rr["bw"])
            s = min(s_req, s_min, s_max)
            if s >= 100 or db == 16:
                res = (db, Av, s, s_req, s_min)
                break
        out.append(dict(**r, rr=rr, Vs_req=Vs_req, s_max=s_max, bar=res[0], Av=res[1],
                        s=res[2], s_req=res[3], s_min=res[4],
                        Vs_cap=0.66 * math.sqrt(fc) * rr["bw"] * rr["d"]))
    cands = [100, 125, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600]
    zones = []
    for r in out:
        s = max([c for c in cands if c <= r["s"]] or [75])
        key = (r["bar"], s)
        if zones and zones[-1][2] == key:
            zones[-1][1] = r["x"]
        else:
            zones.append([r["x"], r["x"], key])
    # 間距由支承往跨中只增不減（同鋼筋號數比較）
    for i in range(len(zones) - 2, -1, -1):
        b0, s0 = zones[i][2]
        b1, s1 = zones[i + 1][2]
        if b0 == b1 and s0 > s1:
            zones[i][2] = (b1, s1)
    merged = []
    for z in zones:
        if merged and merged[-1][2] == z[2]:
            merged[-1][1] = z[1]
        else:
            merged.append(list(z))
    zones = merged
    while len(zones) > 5:
        k = min(range(len(zones) - 1), key=lambda i: zones[i][1] - zones[i][0])
        a, b = zones[k], zones[k + 1]
        key = a[2] if (a[2][0] > b[2][0] or (a[2][0] == b[2][0] and a[2][1] <= b[2][1])) else b[2]
        zones[k:k + 2] = [[a[0], b[1], key]]
    # 水平剪力最小繫筋（8.20.4.5）：箍筋伸入版內兼作繫筋，Av ≥ 0.345 bv s / fy
    bv = P.TOP_FLANGE_W
    s_tie = min(2 * 126.7 * fsy / (0.345 * bv), 4 * P.WEB_T, 600)
    s_tie25 = 25 * math.floor(s_tie / 25)
    zones_req = [dict(start=z[0], end=z[1], bar=z[2][0], s=z[2][1]) for z in zones]
    zones = [[z[0], z[1], (z[2][0], min(z[2][1], s_tie25))] for z in zones]
    merged = []
    for z in zones:
        if merged and merged[-1][2] == z[2]:
            merged[-1][1] = z[1]
        else:
            merged.append(list(z))
    zones = merged
    zl = []
    start = 0.0
    for i, (z0, z1, (db, s)) in enumerate(zones):
        end = L * 1000 / 2 if i == len(zones) - 1 else 500 * math.ceil((z1 + 1) / 500)
        if end <= start:
            continue
        zl.append(dict(start=start, end=end, bar=db, s=s, n=math.ceil((end - start) / s)))
        start = end
    worst = 0.0
    chart = []
    for r in out:
        z = next(z for z in zl if z["start"] <= r["x"] <= z["end"] + 1)
        Av = 2 * (126.7 if z["bar"] == 13 else 198.6)
        rr = r["rr"]
        Vs = min(Av * fsy * rr["d"] / z["s"], 0.66 * math.sqrt(fc) * rr["bw"] * rr["d"])
        phiVn = phi * (rr["Vc"] + Vs)
        worst = max(worst, rr["Vu"] / phiVn)
        Vs_r = min(Av * fsy * r["d"] / z["s"], r["Vs_cap"])
        chart.append((r["x"] / 1000, r["Vu"] / 1e3, phi * (r["Vc"] + Vs_r) / 1e3,
                      r["Vci"] / 1e3, r["Vcw"] / 1e3))
    # 水平剪力（8.20.4）
    Vnh = 2.40 * bv * hc
    return dict(V_LL=V_LL, Vu=Vu, x_crit=x_crit, rc=rc, zones=zl, zones_req=zones_req,
                worst=worst, s_tie_raw=s_tie,
                chart=chart, phiVnh=phi * Vnh / 1e3, Vu0=Vu[0], s_tie=s_tie,
                V_LL0=V_LL[0])


def anchorage_zone(props, gd):
    """8.21：Pu = 1.2 × 最大張拉力（8.14）；近似法 8-37、8-38；局部區承壓 8-39、8-40。"""
    phi = 0.85
    fci = P.FCI_GIRDER
    Aps_t = gd["ns"] * P.AP
    Pu = [1.2 * fj * Aps_t for fj in gd["fj"]]
    yb_end = props["yb_end"]
    h = P.GIRDER_H
    a_plate = P.ANCHOR_PLATE
    slopes0 = [float(tendon_slope(t, 0.0)) for t in P.TENDONS]   # 梁端斜率（rad，負＝往跨中下降）
    stages = []
    order = list(range(len(P.TENDONS)))
    for m in range(1, len(order) + 1):
        idx = order[:m]
        sP = sum(Pu[i] for i in idx)
        ys = [P.TENDONS[i]["y_end"] for i in idx]
        yres = sum(Pu[i] * P.TENDONS[i]["y_end"] for i in idx) / sP
        a = (max(ys) - min(ys)) + a_plate
        e = abs(yres - yb_end)
        alpha = sum(Pu[i] * abs(slopes0[i]) for i in idx) / sP
        T = 0.25 * sP * (1 - a / h) + 0.5 * abs(sP * math.sin(alpha))
        dburst = 0.5 * (h - 2 * e) + 5 * e * math.sin(alpha)
        stages.append(dict(n=m, sumPu=sP / 1e3, a=a, e=e, alpha=alpha, T=T / 1e3,
                           d=dburst))
    gov = max(stages, key=lambda s: s["T"])
    As_v = gov["T"] * 1e3 / (phi * P.FY)
    # 水平向（端塊寬 700）：每個錨碇各自擴散
    bw = P.BOT_FLANGE_W
    T_h = 0.25 * max(Pu) * (1 - a_plate / bw)
    d_h = 0.5 * bw
    As_h = T_h / (phi * P.FY)
    spall = 0.02 * sum(Pu)
    As_sp = spall / (phi * P.FY)
    # 局部區承壓（基本錨碇裝置）
    Ag = a_plate ** 2
    Ab = Ag - math.pi * (P.DUCT_OD / 2) ** 2
    Amax = min(400.0, bw) ** 2
    fb = max(Pu) / Ab
    lim1 = 0.7 * phi * fci * math.sqrt(Amax / Ag)
    lim2 = 2.25 * phi * fci
    return dict(Pu=[p / 1e3 for p in Pu], stages=stages, gov=gov, As_v=As_v,
                n_v=math.ceil(As_v / (2 * 198.6)), T_h=T_h / 1e3, d_h=d_h, As_h=As_h,
                n_h=math.ceil(As_h / (2 * 126.7)), spall=spall / 1e3, As_sp=As_sp,
                fb=fb, lim1=lim1, lim2=lim2, basic_ok=fb <= min(lim1, lim2),
                zone_len=min(2.5 * gov["d"], 1.5 * h))


# ===========================================================================
# 6. 橋面版（4.3、7）
# ===========================================================================
def deck_design(d):
    fcd, fy, t = P.FC_DECK, P.FY, P.DECK_T
    thin = P.TOP_FLANGE_W / P.TOP_FLANGE_T >= 4.0
    clear = (P.SPACING - P.TOP_FLANGE_W) / 1000
    S_eff = clear + P.TOP_FLANGE_W / 2000 if thin else clear
    I_d = A.impact(S_eff)
    M_ll = 0.8 * (S_eff + 0.6) / 9.6 * P.P20
    M_lli = (1 + I_d) * M_ll
    w_dl = t / 1000 * P.GAMMA_RC + P.PAVEMENT_T / 1000 * P.GAMMA_AC
    M_dl = w_dl * S_eff ** 2 / 10
    Mu = 1.3 * (M_dl + 1.67 * M_lli)
    Ms = M_dl + M_lli
    beta1 = 0.85
    rho_b = 0.85 * beta1 * fcd / fy * 600 / (600 + fy)
    fr = 0.623 * math.sqrt(fcd)
    Mcr = fr * 1000 * t ** 2 / 6 / 1e6
    n_mod = P.ES / P.Ec(fcd)

    def As_req(Mu_, d_, phi=0.9):
        Rn = Mu_ * 1e6 / (phi * 1000 * d_ ** 2)
        k = 0.85 * fcd / fy
        return k * (1 - math.sqrt(1 - 2 * Rn / (0.85 * fcd))) * 1000 * d_

    def pick(As, smin=125):
        for bar, ab in ((13, 126.7), (16, 198.6), (19, 286.5), (22, 387.1)):
            s = 25 * math.floor(ab * 1000 / As / 25)
            if s >= smin:
                return bar, ab, min(s, 450, 3 * t)
        return 22, 387.1, 100

    def design(Mu_, d_, label, Ms_, cover):
        As = As_req(Mu_, d_)
        As_use = max(As, min(As_req(1.2 * Mcr, d_), 4 / 3 * As))
        bar, ab, s = pick(As_use)
        As_p = ab * 1000 / s
        a = As_p * fy / (0.85 * fcd * 1000)
        phiMn = 0.9 * As_p * fy * (d_ - a / 2) / 1e6
        rho = As_p / (1000 * d_)
        k = math.sqrt(2 * rho * n_mod + (rho * n_mod) ** 2) - rho * n_mod
        fs = Ms_ * 1e6 / (As_p * (1 - k / 3) * d_)
        dc = min(cover, 50) + bar / 2
        fs_lim = min(30000.0 / (dc * 2 * dc * s) ** (1 / 3), 0.6 * fy)
        return dict(label=label, Mu=Mu_, d=d_, As=As_use, bar=bar, s=s, As_prov=As_p,
                    phiMn=phiMn, rho=rho, rho_max=0.75 * rho_b, fs=fs, fs_lim=fs_lim)

    d_bot = t - P.COVER_DECK_BOT - 6.5
    d_top = t - P.COVER_DECK_TOP - 6.5
    pos = design(Mu, d_bot, "正彎矩（底層橫向）", Ms, P.COVER_DECK_BOT)
    neg = design(Mu, d_top, "負彎矩（頂層橫向）", Ms, P.COVER_DECK_TOP)
    # 懸臂：臨界斷面取外梁頂翼緣；設計輪重距欄杆面 0.3 m（4.3.2）
    edge_face = P.BARRIER_W / 1000
    x_wheel = edge_face + 0.3
    x_fl = P.OVERHANG / 1000 - P.TOP_FLANGE_W / 2000
    xc_bar = 0.2
    P_bar = d["A_bar"] * P.GAMMA_RC
    Md = t / 1000 * P.GAMMA_RC * x_fl ** 2 / 2 + P_bar * max(x_fl - xc_bar, 0) \
        + P.PAVEMENT_T / 1000 * P.GAMMA_AC * max(x_fl - edge_face, 0) ** 2 / 2
    Xw = x_fl - x_wheel
    M_w = (1 + 0.30) * P.P20 * Xw / (0.8 * Xw + 1.14) if Xw > 0 else 0.0
    Xr = max(x_fl - xc_bar, 0.0)
    Er = 0.8 * Xr + 1.52
    M_r = P.RAIL_P * (P.BARRIER_H / 1000 + t / 2000) / Er
    Mu_ov = 1.3 * (Md + 1.67 * max(M_w, M_r))
    over = design(max(Mu_ov, Mu), d_top, "懸臂與梁頂負彎矩（頂層）",
                  Md + max(M_w, M_r), P.COVER_DECK_TOP)
    pct = min(121 / math.sqrt(S_eff), 67) / 100
    As_dist = pct * pos["As_prov"]
    dist = pick(As_dist)
    temp = pick(270.0)
    return dict(S=S_eff, thin=thin, clear=clear, I=I_d, M_ll=M_ll, M_lli=M_lli,
                M_dl=M_dl, Mu=Mu, pos=pos, neg=neg, over=over,
                overhang=dict(x=x_fl, Md=Md, M_w=M_w, M_r=M_r, Er=Er, Mu=Mu_ov),
                dist=dict(pct=pct, As=As_dist, bar=dist[0], s=dist[2]),
                temp=dict(bar=temp[0], s=temp[2]), Mcr=Mcr)


# ===========================================================================
# 7. 支承墊（10.6.6 方法 B）
# ===========================================================================
def bearing_design(props, d, gd, sd):
    R_D = gd["dl"]["R_D"]
    R_L = sd["V_LL0"]
    P_ = (R_D + R_L) * 1e3
    d_th = P.ALPHA_T * P.TEMP_RANGE * P.SPAN
    d_lt = P.LONG_TERM_STRAIN * P.SPAN
    d_s = d_th + d_lt
    G = 0.86
    # 轉角：最終呆載重＋預力的梁端斜率、活載重、施工 0.005
    cam = gd["camber"]
    th_dl_ps = 4 * abs(cam["final_inst"]) / (P.SPAN) * 1.0      # 拋物線近似：θ = 4δ/L
    EIc = props["Ec_girder"] * props["comp"]["I"]
    th_ll = gd["M_LL"].max() * 1e6 * P.SPAN / (3 * EIc)
    theta = th_dl_ps + th_ll + 0.005
    best = None
    for Lp in (300, 350, 400, 450, 500):
        for Wp in (500, 550, 600, 650, 700):
            for hri in (10, 12, 15):
                for n_int in range(2, 9):
                    hc = hri / 2
                    hs = 3.0
                    hrt = n_int * hri + 2 * hc
                    S_ = Lp * Wp / (2 * hri * (Lp + Wp))
                    sig = P_ / (Lp * Wp)
                    lim = min(6.86, G * S_)
                    n_eff = n_int
                    sig_up = 0.5 * G * S_ * (Lp / hri) ** 2 * theta / n_eff
                    h_tot = hrt + (n_int + 1) * hs
                    ok = (sig <= lim and hrt >= 2 * d_s and sig >= sig_up
                          and h_tot <= min(Lp, Wp) / 3)
                    if ok:
                        key = (Lp * Wp, h_tot)
                        if best is None or key < best[0]:
                            best = (key, dict(L=Lp, W=Wp, hri=hri, hc=hc, n_int=n_int, hs=hs,
                                              hrt=hrt, S=S_, sig=sig, lim=lim, sig_up=sig_up,
                                              h_tot=h_tot, n_eff=n_eff))
    b = best[1]
    hs_req = max(3 * b["hri"] * b["sig"] / 250.0,
                 2 * b["hri"] * (R_L * 1e3 / (b["L"] * b["W"])) / 165.0)
    b.update(R_D=R_D, R_L=R_L, P=R_D + R_L, d_th=d_th, d_lt=d_lt, d_s=d_s, G=G,
             theta=theta, th_dl_ps=th_dl_ps, th_ll=th_ll, hs_req=hs_req,
             k=G * b["L"] * b["W"] / b["hrt"])
    return b


# ===========================================================================
# 8. 耐震（公路橋梁耐震設計規範 107 年版）
# ===========================================================================
def fa3(Ss):
    if Ss <= 0.6:
        return 1.2
    if Ss <= 0.7:
        return 1.2 - (Ss - 0.6)
    if Ss <= 0.8:
        return 1.1 - (Ss - 0.7)
    return 1.0


def fv3(S1):
    if S1 <= 0.3:
        return 1.8
    if S1 <= 0.5:
        return 1.8 - 2 * (S1 - 0.3)
    return 1.4


def site_factor(f3, vs30):
    if vs30 >= 270:
        return 1.0
    if vs30 < 180:
        return f3
    return 1.0 + (f3 - 1.0) * (270 - vs30) / 90


def spectrum(SS, S1, T):
    T0 = S1 / SS
    if T <= 0.2 * T0:
        return SS * (0.4 + 3 * T / T0)
    if T <= T0:
        return SS
    return S1 / T


def site_spectra(vs):
    NA2 = max(v[0] for v in P.NEAR_FAULTS.values())
    NV2 = max(v[1] for v in P.NEAR_FAULTS.values())
    NA3 = max(v[2] for v in P.NEAR_FAULTS.values())
    NV3 = max(v[3] for v in P.NEAR_FAULTS.values())
    SSI, S1I = P.SS_II / 3.25, P.S1_II / 3.25
    ss2, s12 = P.SS_II * NA2, P.S1_II * NV2
    ss3, s13 = P.SS_III * NA3, P.S1_III * NV3
    out = dict(
        NA2=NA2, NV2=NV2, NA3=NA3, NV3=NV3,
        I=(site_factor(fa3(SSI), vs) * SSI, site_factor(fv3(S1I), vs) * S1I),
        II=(site_factor(fa3(ss2), vs) * ss2, site_factor(fv3(s12), vs) * s12),
        III=(site_factor(fa3(ss3), vs) * ss3, site_factor(fv3(s13), vs) * s13),
        Fa=(site_factor(fa3(SSI), vs), site_factor(fa3(ss2), vs), site_factor(fa3(ss3), vs)),
        Fv=(site_factor(fv3(S1I), vs), site_factor(fv3(s12), vs), site_factor(fv3(s13), vs)),
    )
    return out


def seismic(props, d, gd, br):
    sp = site_spectra(P.VS30)
    S2S, S21 = sp["II"]
    S3S, S31 = sp["III"]
    SIS, SI1 = sp["I"]
    I = P.IMPORTANCE
    dlr = gd["dl"]
    W = 2 * dlr["R_D"] * P.N_GIRDER                         # 上部結構靜載重（全橋）
    Rd = dlr["R_D"]
    # (a) 只靠支承墊
    k_tot = br["k"] * 2 * P.N_GIRDER                        # N/mm
    m = W * 1e3 / 9810.0
    T_pad = 2 * math.pi * math.sqrt(m / k_tot)
    sd = lambda Sa, T: Sa * 9810 * T ** 2 / (4 * math.pi ** 2)
    u2 = sd(spectrum(S2S, S21, T_pad), T_pad)
    u3 = sd(spectrum(S3S, S31, T_pad), T_pad)
    u1 = sd(spectrum(SIS, SI1, T_pad), T_pad)
    F_fric = 0.15 * W                                       # 表 2-8 合成橡膠支承墊
    # (b) 支承系統水平力（4.5.2 上限：彈性力；週期未知取平台）
    H_total = I * S2S * W
    H_T = H_total / 2
    H_L = H_total
    fy, fcs, phi, mu = P.FY, 28.0, 0.85, 1.0
    n_key = P.N_STOPPER                                    # 每座橋台梁間止震塊數（兩向共用）
    Avf_T = H_T * 1e3 / (phi * mu * fy) / n_key
    Acv_T = H_T * 1e3 / (phi * min(0.2 * fcs, 5.52)) / n_key
    Avf_L = H_L * 1e3 / (phi * mu * fy)
    # (c) 垂直地震（2.6）
    kv = (2 / 3) * I * S2S / P.ALPHA_Y
    rmid = min([r for r in gd["rows"] if "fb_f" in r], key=lambda r: abs(r["xg"] - LG / 2))
    sec = rmid["sec"]
    Pe, Mpe = rmid["Pe"], rmid["Mpe"]
    i_mid = int(np.argmin(np.abs(X - L / 2)))
    Mnc, Mc = dlr["Mnc"][i_mid] * 1e6, dlr["Mc"][i_mid] * 1e6
    Stc, Sbc = props["Stc"], props["Sbc"]
    f_top_up = -Pe / sec["A"] + Mpe / sec["St"] - (1 - kv) * (Mnc / sec["St"] + Mc / Stc)
    f_bot_up = -Pe / sec["A"] - Mpe / sec["Sb"] + (1 - kv) * (Mnc / sec["Sb"] + Mc / Sbc)
    f_top_dn = -Pe / sec["A"] + Mpe / sec["St"] - (1 + kv) * (Mnc / sec["St"] + Mc / Stc)
    f_bot_dn = -Pe / sec["A"] - Mpe / sec["Sb"] + (1 + kv) * (Mnc / sec["Sb"] + Mc / Sbc)
    Mu_dn = 1.3 * (1 + kv) * (Mnc + Mc) / 1e6
    # (d) 支承拉拔（4.5.3）
    parts = [(d["w_girder"], props["yb"] / 1000),
             (d["w_deck"] + d["w_haunch"], (P.GIRDER_H + P.HAUNCH + P.DECK_T / 2) / 1000),
             (d["w_barrier"], (P.GIRDER_H + P.HAUNCH + P.DECK_T) / 1000 + 0.35),
             (d["w_dw"], (P.GIRDER_H + P.HAUNCH + P.DECK_T + P.PAVEMENT_T / 2) / 1000)]
    hcg = sum(w * y for w, y in parts) / sum(w for w, _ in parts) + br["h_tot"] / 1000
    gx = [(-1.5 + i) * P.SPACING / 1000 for i in range(P.N_GIRDER)]
    R_HEQ = H_T * hcg * max(gx) / sum(g * g for g in gx)
    R_VEQ = kv * Rd
    RBV = max(Rd + R_HEQ + 0.3 * R_VEQ, Rd + 0.3 * R_HEQ + R_VEQ)
    Q = R_HEQ + 0.3 * R_VEQ
    QBT = max(R_HEQ + 0.3 * R_VEQ - Rd, 0.3 * R_HEQ + R_VEQ - Rd, 0.15 * Rd)
    # (e) 防落長度、間隙（8.5–8.7）
    LN_min = 50 + 0.25 * L + 1.0 * 0
    uG = P.EPS_G[2] * L * 100 * S3S / S2S
    gap = P.STOPPER_GAP / 10
    LA = 1.5
    Ts = np.linspace(0, 3, 121)
    return dict(
        sp=sp, sites={name: site_spectra(v) for name, v in
                      (("第一類", 300.0), ("第二類 Vs30 225", 225.0),
                       ("第二類 Vs30 180", 180.0), ("第三類", 150.0))},
        W=W, Rd=Rd, T_pad=T_pad, u1=u1, u2=u2, u3=u3, gam2=u2 / br["hrt"], F_fric=F_fric,
        H_total=H_total, H_T=H_T, H_L=H_L, n_key=n_key, Avf_T=Avf_T, Acv_T=Acv_T,
        Avf_L=Avf_L, kv=kv, f_top_up=f_top_up, f_bot_up=f_bot_up, f_top_dn=f_top_dn,
        f_bot_dn=f_bot_dn, Mu_dn=Mu_dn, hcg=hcg, R_HEQ=R_HEQ, R_VEQ=R_VEQ, RBV=RBV,
        sig_RBV=RBV * 1e3 / (br["L"] * br["W"]), Q=Q, Q_ratio=Q / Rd, QBT=QBT,
        need_uplift=Q >= 0.5 * Rd, LN_min=LN_min, uG=uG, gap=gap,
        LN_req=max(LN_min, gap + uG), LN_adopt=P.SEAT_LN / 10, SB=gap + LA, LE=gap + LA,
        SB_pad=u2 / 10 + LA, LN_pad=u3 / 10 + uG,
        spec=dict(T=Ts.tolist(), I=[spectrum(SIS, SI1, t) for t in Ts],
                  II=[spectrum(S2S, S21, t) for t in Ts],
                  III=[spectrum(S3S, S31, t) for t in Ts]),
    )


# ===========================================================================
def run():
    props = S.properties()
    an = A.run()
    dist = distribution()
    d = dead_loads(props)
    gd = girder_design(props, d, an, dist)
    # 剪力臨界斷面需要支承墊長度：先用 400 mm 估算，支承設計後再算一次
    sd = shear_design(props, d, an, dist, gd, pad_len=400.0)
    br = bearing_design(props, d, gd, sd)
    sd = shear_design(props, d, an, dist, gd, pad_len=br["L"])
    az = anchorage_zone(props, gd)
    dk = deck_design(d)
    sz = seismic(props, d, gd, br)
    return dict(props=props, an=an, dist=dist, dead=d, girder=gd, shear=sd, anchor=az,
                deck=dk, bearing=br, seismic=sz)
