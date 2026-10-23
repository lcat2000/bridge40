"""
由 out/results.json 產生設計說明（docs/design-notes.md）用的兩張圖：
  docs/img/tendon_stress.png  四束鋼腱錨碇後沿梁長的應力
  docs/img/spectrum.png       等級 I / II / III 工址設計反應譜
用法：先執行 python run_all.py，再執行 python docs/make_figures.py
需要 matplotlib 與「Noto Sans CJK TC」字型。
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IMG = os.path.join(HERE, "img")

# 類別色依固定順序取用；文字一律用文字色，不用系列色
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SURFACE, INK, INK2, GRID, REF = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#8a8984"

plt.rcParams.update({
    "font.family": ["Noto Sans CJK TC", "sans-serif"],
    "font.size": 10.5,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "legend.frameon": False, "axes.unicode_minus": False,
})


def tendon_stress(S, path):
    pt = S["pt"]
    x, fs = pt["profile"]["x"], pt["profile"]["fs"]
    fpu, fy = 1860.0, 0.9 * 1860.0
    fig, ax = plt.subplots(figsize=(8.0, 4.2), dpi=160)
    for i, f in enumerate(fs):
        end = "左" if i % 2 == 0 else "右"
        ax.plot(x, f, color=SERIES[i], lw=2, label=f"T{i + 1}（{end}端張拉）", solid_capstyle="round")
    lim = 0.70 * fpu
    ax.axhline(lim, color=REF, lw=1.2, ls=(0, (4, 3)))
    ax.text(x[-1] * 0.53, lim - 3, "0.70 f's：錨碇後端錨上限", ha="center", va="top", color=INK2, fontsize=9)
    lim = 0.83 * fy
    ax.axhline(lim, color=REF, lw=1.2, ls=(0, (4, 3)))
    ax.text(x[-1], lim + 4, "0.83 fy*：滑動影響範圍末端上限", ha="right", va="bottom", color=INK2, fontsize=9)
    ax.set_xlim(0, x[-1])
    ax.set_ylim(1200, 1420)
    ax.set_xlabel("距梁端 (m)")
    ax.set_ylabel("鋼腱應力 (MPa)")
    ax.set_title("錨碇滑動後的鋼腱應力（未計長期損失）", loc="left", fontsize=12, pad=10)
    ax.legend(loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.32), labelcolor=INK)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def spectrum(S, path):
    z = S["seismic"]
    sp = z["spec"]
    T = sp["T"]
    fig, ax = plt.subplots(figsize=(8.0, 4.2), dpi=160)
    names = {"I": "等級 I", "II": "等級 II（475 年）", "III": "等級 III（2,500 年）"}
    for i, k in enumerate(("I", "II", "III")):
        ax.plot(T, sp[k], color=SERIES[i], lw=2, label=names[k], solid_capstyle="round")
    ax.axvline(z["T_pad"], color=REF, lw=1.2, ls=(0, (4, 3)))
    ax.text(z["T_pad"] + 0.04, max(sp["III"]) * 0.97,
            f"只靠橡膠墊 T = {z['T_pad']:.2f} s", color=INK2, fontsize=9, va="top")
    ax.set_xlim(0, max(T))
    ax.set_ylim(0, max(sp["III"]) * 1.08)
    ax.set_xlabel("週期 T (s)")
    ax.set_ylabel("譜加速度 Sa (g)")
    ax.set_title("台中市南屯區工址設計反應譜（第二類地盤，I = 1.0）", loc="left", fontsize=12, pad=10)
    ax.legend(loc="upper right", labelcolor=INK)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def main():
    with open(os.path.join(ROOT, "out", "results.json"), encoding="utf-8") as f:
        S = json.load(f)
    os.makedirs(IMG, exist_ok=True)
    tendon_stress(S, os.path.join(IMG, "tendon_stress.png"))
    spectrum(S, os.path.join(IMG, "spectrum.png"))
    print("docs/img/tendon_stress.png、docs/img/spectrum.png 已產生")


if __name__ == "__main__":
    main()
