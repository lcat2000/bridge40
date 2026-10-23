"""
結構分析：OpenSeesPy 簡支梁 + 影響線疊加
==========================================
1. 用 OpenSeesPy 建 40 m 簡支梁（800 個 elasticBeamColumn，節點間距 0.05 m）。
2. 單位載重依序放在每個節點求解一次，得到彎矩、剪力、撓度的影響線矩陣。
3. 移動 HS20-44 卡車（雙向、後軸距 4.25–9.15 m）與車道載重，用疊加取包絡。
4. 獨立核對：影響線解析解（不經 OpenSees）與經典閉合解。
單位：kN、m。
"""
import numpy as np
import openseespy.opensees as ops

from . import params as P

L = P.SPAN / 1000.0
DX = 0.05
N = int(round(L / DX))
X = np.arange(N + 1) * DX


def influence_matrices(EI=1.0e6):
    """回傳 (IM, IV, ID)：第 j 欄為單位載重在節點 j 時，各節點的彎矩、
    剪力（節點左側斷面，載重在該節點視為斷面右側）、撓度。"""
    ops.wipe()
    ops.model("basic", "-ndm", 2, "-ndf", 3)
    for i, x in enumerate(X):
        ops.node(i, float(x), 0.0)
    ops.fix(0, 1, 1, 0)
    ops.fix(N, 0, 1, 0)
    ops.geomTransf("Linear", 1)
    for e in range(N):
        ops.element("elasticBeamColumn", e + 1, e, e + 1, 1.0, 1.0, EI, 1)
    ops.timeSeries("Constant", 1)
    ops.pattern("Plain", 1, 1)
    ops.system("BandGeneral")
    ops.numberer("Plain")
    ops.constraints("Plain")
    ops.integrator("LoadControl", 1.0)
    ops.algorithm("Linear")
    ops.analysis("Static")
    IM = np.zeros((N + 1, N + 1))
    IV = np.zeros((N + 1, N + 1))
    ID = np.zeros((N + 1, N + 1))
    for j in range(1, N):
        ops.remove("loadPattern", 1)
        ops.pattern("Plain", 1, 1)
        ops.load(j, 0.0, -1.0, 0.0)
        ops.reset()
        ops.analyze(1)
        M = np.zeros(N + 1)
        Vl = np.zeros(N + 1)
        for e in range(N):
            f = ops.eleResponse(e + 1, "localForce")
            M[e] = -f[2]
            M[e + 1] = f[5]
            Vl[e + 1] = -f[4]          # 元素 e 右端剪力 = 節點 e+1 左側斷面剪力
        ops.reactions()
        RA = ops.nodeReaction(0, 2)
        Vl[0] = RA
        IM[:, j] = M
        IV[:, j] = Vl
        ID[:, j] = [-ops.nodeDisp(i, 2) for i in range(N + 1)]
    # 載重在支點：彎矩 0，支點反力 1（左支點）或 0
    IV[0, 0] = 1.0
    return IM, IV, ID


def il_closed(x, a):
    """單位載重在 a 時，x 處彎矩與剪力（左側斷面）的解析解。"""
    M = np.where(x <= a, x * (L - a) / L, a * (L - x) / L)
    V = np.where(a >= x, (L - a) / L, -a / L)
    return M, V


def truck(rear):
    """回傳 [(相對中軸位置 m, 軸重 kN)]；前軸在 +。"""
    return [(+P.AXLE_GAP / 1000, P.FRONT_AXLE), (0.0, P.AXLE), (-rear / 1000, P.AXLE)]


def vehicle_envelope(IM, IV, vehicle):
    """車輛軸重落在節點上、雙向移動的包絡（疊加影響線矩陣）。"""
    Mmax = np.zeros(N + 1)
    Vmax = np.zeros(N + 1)
    offs = [int(round(o / DX)) for o, _ in vehicle]
    for d in (1, -1):
        for k in range(-N, 2 * N + 1):
            cols = []
            w = []
            for (o, p), oi in zip(vehicle, offs):
                j = k + d * oi
                if 0 <= j <= N:
                    cols.append(j)
                    w.append(p)
            if not cols:
                continue
            m = IM[:, cols] @ np.array(w)
            v = IV[:, cols] @ np.array(w)
            Mmax = np.maximum(Mmax, m)
            Vmax = np.maximum(Vmax, v)
    return Mmax, Vmax


def vehicle_envelope_closed(vehicle, step=0.002):
    """獨立核對：影響線解析解，每 2 mm 移動一次。"""
    Mmax = np.zeros(N + 1)
    Vmax = np.zeros(N + 1)
    for d in (1, -1):
        for xm in np.arange(-15, L + 15, step):
            m = np.zeros(N + 1)
            v = np.zeros(N + 1)
            for o, p in vehicle:
                a = xm + d * o
                if 0 <= a <= L:
                    mm, vv = il_closed(X, a)
                    m += p * mm
                    v += p * vv
            Mmax = np.maximum(Mmax, m)
            Vmax = np.maximum(Vmax, v)
    return Mmax, Vmax


def closed_form_truck_moment(vehicle):
    """經典定理：最大彎矩發生在最靠近合力的軸下，跨中平分該軸與合力。"""
    Ptot = sum(p for _, p in vehicle)
    xr = sum(o * p for o, p in vehicle) / Ptot
    best = 0.0
    for o, _ in vehicle:
        a = L / 2 + (o - xr) / 2          # 軸位置
        loads = [(a - o + oo, pp) for oo, pp in vehicle]
        if not all(0 <= x <= L for x, _ in loads):
            continue
        RA = sum(pp * (L - x) / L for x, pp in loads)
        M = RA * a - sum(pp * (a - x) for x, pp in loads if x < a)
        best = max(best, M)
    return best


def lane_envelope():
    M = P.LANE_W * X * (L - X) / 2 + P.LANE_PM * X * (L - X) / L
    V = P.LANE_W * (L - X) ** 2 / (2 * L) + P.LANE_PV * (L - X) / L
    return M, V


def impact(Lload):
    """3.8：I = 15.24/(L + 38.1) ≤ 0.30。"""
    return min(15.24 / (Lload + 38.1), 0.30)


def run():
    """回傳每車道 (L+I) 包絡與核對結果。"""
    IM, IV, ID = influence_matrices()
    sweep = []
    for rear in list(range(int(P.AXLE_GAP), int(P.REAR_GAP_MAX), 450)) + [P.REAR_GAP_MAX]:
        Mr, _ = vehicle_envelope(IM, IV, truck(rear))
        sweep.append((rear / 1000, float(Mr.max())))
    Mt, Vt = vehicle_envelope(IM, IV, truck(P.AXLE_GAP))
    Mtc, Vtc = vehicle_envelope_closed(truck(P.AXLE_GAP))
    M_cf = closed_form_truck_moment(truck(P.AXLE_GAP))
    Ml, Vl = lane_envelope()
    IM_M = impact(L)
    IM_V = np.array([impact(L - x) for x in X])
    M_lane = (1 + IM_M) * np.maximum(Mt, Ml)
    V_lane = (1 + IM_V) * np.maximum(Vt, Vl)
    # 核對：單位載重矩陣對解析解（每一欄）
    j = N // 3
    m_cf, v_cf = il_closed(X, X[j])
    err_il = max(np.abs(IM[:, j] - m_cf).max(), np.abs(IV[1:, j] - v_cf[1:]).max())
    return dict(
        IM=IM, IV=IV, ID=ID, Mt=Mt, Vt=Vt, Mtc=Mtc, Vtc=Vtc, M_cf=M_cf, Ml=Ml, Vl=Vl,
        IM_M=IM_M, IM_V=IM_V, M_lane=M_lane, V_lane=V_lane, sweep=sweep, err_il=err_il,
    )
