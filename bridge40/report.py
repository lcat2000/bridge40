"""
把設計結果整理成 results.json 與純文字計算書 calc_report.txt。
"""
import json
import math

import numpy as np

from . import params as P
from . import design as D


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()
                if k not in ("IM", "IV", "ID", "sec")}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return [_clean(v) for v in o.tolist()]
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def tendon_table(R, step=2.0):
    """鋼腱座標表（自梁端，每 step m）。"""
    xs = list(np.arange(0, D.LG / 2 + 1e-9, step))
    if abs(xs[-1] - D.LG / 2) > 1e-6:
        xs.append(D.LG / 2)
    rows = []
    for x in xs:
        rows.append([round(float(x), 2)] + [round(float(D.tendon_y(t, x))) for t in P.TENDONS])
    return rows


def elongations(R):
    """張拉伸長量（錨碇前）：Δ = ∫ f(x) dx / Ep。"""
    g = R["girder"]
    out = []
    for t in g["tend"]:
        f = t["f"] if t["end"] == "L" else t["f"][::-1]
        xs = g["xs_t"]
        out.append(float(np.trapezoid(f, xs) * 1000 / P.EP))
    return out


def summary(R):
    g, s, az, dk, br, sz = (R["girder"], R["shear"], R["anchor"], R["deck"], R["bearing"],
                            R["seismic"])
    an = R["an"]
    fin = [r for r in g["rows"] if "fb_f" in r]
    rel = g["rows"]
    k = len(g["xs_t"]) // 2
    out = dict(
        span=P.SPAN, girder_len=P.GIRDER_LEN,
        props=R["props"], dead=R["dead"], dist=R["dist"],
        live=dict(M_truck=float(an["Mt"].max()), M_truck_closed=float(an["Mtc"].max()),
                  M_classic=float(an["M_cf"]), V_truck=float(an["Vt"][0]),
                  V_truck_closed=float(an["Vtc"][0]), M_lane=float(an["Ml"].max()),
                  V_lane=float(an["Vl"][0]), IM_M=float(an["IM_M"]), IM_V0=float(an["IM_V"][0]),
                  M_LLI_lane=float(an["M_lane"].max()), V_LLI_lane=float(an["V_lane"][0]),
                  sweep=an["sweep"], err_il=float(an["err_il"])),
        moments=dict(Mg=float(g["dl"]["Mg"][len(D.X) // 2]),
                     Mnc=float(g["dl"]["Mnc"][len(D.X) // 2]),
                     Mc=float(g["dl"]["Mc"][len(D.X) // 2]),
                     M_LL=float(g["M_LL"].max()), Mu=float(g["Mu"].max()),
                     R_D=float(g["dl"]["R_D"])),
        pt=dict(ns=g["ns"], n_tendon=P.N_TENDON, Aps=g["Aps"], fj=g["fj"],
                anchor_after=[float(t["fs"][0] if t["end"] == "L" else t["fs"][-1])
                              for t in g["tend"]],
                peak=[float(t["fs"].max()) for t in g["tend"]],
                mid_after_set=[float(t["fs"][k]) for t in g["tend"]],
                xset=[float(t["xset"]) for t in g["tend"]], ends=P.JACK_END,
                losses=g["losses"], fse_mid=float(np.mean([t["fs"][k] for t in g["tend"]])
                                                  - g["losses"]["total"]),
                elong=elongations(R), table=tendon_table(R),
                Pi_mid=float(min(rel, key=lambda r: abs(r["xg"] - D.LG / 2))["Pi"] / 1e3),
                Pe_mid=float(min(fin, key=lambda r: abs(r["xg"] - D.LG / 2))["Pe"] / 1e3),
                profile=dict(x=g["xs_t"][::40].tolist(),
                             fs=[t["fs"][::40].tolist() for t in g["tend"]],
                             f=[t["f"][::40].tolist() for t in g["tend"]])),
        stress=dict(lim=g["lim"],
                    rel_bot_min=min(r["fb_i"] for r in rel), rel_top_max=max(r["ft_i"] for r in rel),
                    rel_top_min=min(r["ft_i"] for r in rel),
                    fin_bot_max=max(r["fb_f"] for r in fin),
                    fin_bot_perm_max=max(r["fb_perm"] for r in fin),
                    top_perm_min=min(r["ft_perm"] for r in fin),
                    top_mix_min=min(r["ft_mix"] for r in fin),
                    top_all_min=min(r["ft_all"] for r in fin),
                    deck_top_min=min(r["fd_top"] for r in fin),
                    fse_max=max(float(t["fs"].max()) for t in g["tend"]) - g["losses"]["total"],
                    top_bars=g["top_bars"]),
        strength=dict(mid=g["s_mid"], worst=g["worst_flex"], Mcr=g["Mcr"], phi=g["phi"]),
        defl=dict(d=g["defl"], truck=g["defl_truck"], lane=g["defl_lane"],
                  lim=P.SPAN / 800, camber=g["camber"]),
        shear=dict(Vu0=float(s["Vu0"]), V_LL0=float(s["V_LL0"]), x_crit=s["x_crit"],
                   rc={k_: v for k_, v in s["rc"].items()}, zones=s["zones"],
                   zones_req=s["zones_req"], worst=s["worst"], phiVnh=s["phiVnh"],
                   s_tie=s["s_tie_raw"], chart=s["chart"][::4]),
        anchor=az, deck=dk, bearing=br, seismic=sz,
    )
    return _clean(out)


def text_report(S):
    L = []
    w = L.append
    pt, st, sh = S["pt"], S["stress"], S["shear"]
    w("40 m 簡支後拉預力 I 型梁橋 計算摘要")
    w("=" * 40)
    w(f"跨徑 {S['span'] / 1000:.1f} m（支承中心距），梁長 {S['girder_len'] / 1000:.1f} m")
    p = S["props"]
    w(f"梁斷面 A = {p['A'] / 1e6:.3f} m²，yb = {p['yb']:.1f} mm，I = {p['I'] / 1e12:.4f} m⁴；"
      f"合成 I = {p['comp']['I'] / 1e12:.4f} m⁴，ybc = {p['comp']['yb']:.1f} mm")
    lv = S["live"]
    w(f"\n[活載重] HS20-44 每車道：卡車 M = {lv['M_truck']:.1f}（影響線核對 {lv['M_truck_closed']:.1f}、"
      f"閉合解 {lv['M_classic']:.1f}），車道 {lv['M_lane']:.1f} kN·m；支點 V：卡車 {lv['V_truck']:.1f}、"
      f"車道 {lv['V_lane']:.1f} kN")
    w(f"  衝擊 {lv['IM_M']:.4f}；每車道 (L+I) M = {lv['M_LLI_lane']:.1f}，V = {lv['V_LLI_lane']:.1f}")
    ds = S["dist"]
    w(f"  分擔：S/1.65 = {ds['DF_M_int']:.4f}、外梁槓桿 {ds['DF_ext']:.4f} → {ds['DF_M']:.4f}；"
      f"梁端剪力 {ds['DF_V_end']:.4f}")
    m = S["moments"]
    w(f"\n[跨中彎矩/每支梁] 梁 {m['Mg']:.0f}、非合成 {m['Mnc']:.0f}、合成 {m['Mc']:.0f}、"
      f"(L+I) {m['M_LL']:.0f}、Mu {m['Mu']:.0f} kN·m；支承呆載重反力 {m['R_D']:.0f} kN")
    w(f"\n[預力] {pt['n_tendon']} 束 × {pt['ns']} 股 15.2 mm（Aps = {pt['Aps']:.0f} mm²）")
    for i, t in enumerate(P.TENDONS):
        w(f"  {t['name']}（{pt['ends'][i]} 端張拉）fj = {pt['fj'][i]:.0f}，錨碇後端錨 "
          f"{pt['anchor_after'][i]:.0f}、峰值 {pt['peak'][i]:.0f}、跨中 {pt['mid_after_set'][i]:.0f} MPa；"
          f"滑動影響 {pt['xset'][i]:.2f} m；伸長 {pt['elong'][i]:.0f} mm")
    ls = pt["losses"]
    w(f"  損失（跨中）SH {ls['SH']:.1f}、ES {ls['ES']:.1f}、CRc {ls['CRc']:.1f}、CRs {ls['CRs']:.1f}"
      f" = {ls['total']:.1f} MPa；fcir {ls['fcir']:.2f}、fcds {ls['fcds']:.2f}")
    w(f"  跨中 Pi = {pt['Pi_mid']:.0f} kN、Pe = {pt['Pe_mid']:.0f} kN、fse = {pt['fse_mid']:.0f} MPa")
    lim = st["lim"]
    w(f"\n[應力] 施預力（淨斷面，扣除套管）：底 {st['rel_bot_min']:.2f} ≥ {lim['c_rel']:.2f}；頂 {st['rel_top_max']:.2f} ≤ "
      f"{lim['t_rel_nb']:.2f}")
    w(f"  使用：底 {st['fin_bot_max']:.2f} ≤ {lim['t_fin']:.2f}；頂 Pe+DL {st['top_perm_min']:.2f}、"
      f"0.5(Pe+DL)+LL {st['top_mix_min']:.2f} ≥ {lim['c_perm']:.1f}；全載重 {st['top_all_min']:.2f} ≥ "
      f"{lim['c_all']:.1f}；版頂 {st['deck_top_min']:.2f}")
    sm = S["strength"]["mid"]
    w(f"\n[強度] φ = {S['strength']['phi']}，fsu* = {sm['fsu']:.0f}，a = {sm['a']:.0f} mm，"
      f"φMn = {sm['phiMn']:.0f} ≥ Mu {sm['Mu']:.0f}；全梁最大 Mu/φMn = {S['strength']['worst']:.3f}；"
      f"1.2Mcr* = {1.2 * S['strength']['Mcr']:.0f}")
    df = S["defl"]
    w(f"  撓度 {df['d']:.1f} ≤ {df['lim']:.0f} mm；預拱：施預力 {df['camber']['at_tension']:.1f} mm 上拱，"
      f"全部呆載重後（瞬時）{df['camber']['final_inst']:.1f} mm")
    rc = sh["rc"]
    w(f"\n[剪力] 支點 Vu = {sh['Vu0']:.0f} kN；臨界斷面 {sh['x_crit']:.0f} mm：Vu {rc['Vu'] / 1e3:.0f}、"
      f"Vci {rc['Vci'] / 1e3:.0f}、Vcw {rc['Vcw'] / 1e3:.0f}（b' {rc['bw']:.0f}、Vp {rc['Vp'] / 1e3:.0f}）")
    w("  箍筋需求：" + "；".join(f"{z['start'] / 1000:.2f}–{z['end'] / 1000:.2f} m D{z['bar']}@{z['s']}"
                               for z in sh["zones_req"]))
    w("  採用：" + "；".join(f"{z['start'] / 1000:.2f}–{z['end'] / 1000:.2f} m D{z['bar']}@{z['s']}"
                           for z in sh["zones"]) + f"（水平剪力繫筋 s ≤ {sh['s_tie']:.0f}）")
    w(f"  最大 Vu/φVn = {sh['worst']:.3f}；水平剪力 φVnh = {sh['phiVnh']:.0f} kN")
    az = S["anchor"]
    gv = az["gov"]
    w(f"\n[錨碇區] Pu = {', '.join(f'{p:.0f}' for p in az['Pu'])} kN；爆裂力 {gv['T']:.0f} kN"
      f"（前 {gv['n']} 束），dburst {gv['d']:.0f} mm → As {az['As_v']:.0f} mm²；水平 {az['T_h']:.0f} kN/束；"
      f"剝裂 {az['spall']:.0f} kN；承壓 fb {az['fb']:.1f} vs {min(az['lim1'], az['lim2']):.1f} MPa")
    dk = S["deck"]
    w(f"\n[橋面版] S = {dk['S']:.2f} m，Mu = {dk['Mu']:.1f}；底 D{dk['pos']['bar']}@{dk['pos']['s']}、"
      f"頂 D{dk['over']['bar']}@{dk['over']['s']}；分佈筋 D{dk['dist']['bar']}@{dk['dist']['s']}")
    b = S["bearing"]
    w(f"\n[支承] {b['L']}×{b['W']}×{b['h_tot']:.0f} mm，σ = {b['sig']:.2f} ≤ {b['lim']:.2f}；"
      f"Δs = {b['d_s']:.1f}；θ = {b['theta'] * 1e3:.2f} mrad")
    z = S["seismic"]
    sp = z["sp"]
    w(f"\n[耐震] SII,S = {sp['II'][0]:.3f}、SII,1 = {sp['II'][1]:.3f}；W = {z['W']:.0f} kN；"
      f"只靠支承墊 T = {z['T_pad']:.2f} s、位移 {z['u2']:.0f} mm")
    w(f"  止震塊：每座橋台橫向 {z['H_T']:.0f} kN（梁間 {z['n_key']} 塊兩向共用，各 Avf {z['Avf_T']:.0f} mm²）；"
      f"縱向 {z['H_L']:.0f} kN")
    w(f"  垂直 kv = {z['kv']:.3f}；拉拔 Q/Rd = {z['Q_ratio']:.2f}、QBT = {z['QBT']:.0f} kN；"
      f"LN ≥ {z['LN_req']:.0f} cm；間隙 ≥ {z['SB']:.1f} cm")
    return "\n".join(L)


def run(path_json="results.json", path_txt="calc_report.txt"):
    R = D.run()
    S = summary(R)
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(S, f, ensure_ascii=False, indent=1)
    txt = text_report(S)
    with open(path_txt, "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    return R, S, txt
