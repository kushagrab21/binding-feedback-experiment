"""Plot all data figures for the binding-feedback write-up, reading only ./data/*.csv.

Usage:  python3 plot_all.py          (writes PNGs into ./figures/)

Every number comes from the CSVs in ./data, which were distilled from the
repository's deterministic analysis outputs (phase6_analysis/results.md,
v2_ladder/analysis/results.{md,json}, v3_window/analysis/results.md).
Nothing is hardcoded in this script except layout and annotations.
"""
import csv
import os
import matplotlib.pyplot as plt
import numpy as np
import style
style.apply()
C = style

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "figures")
os.makedirs(OUT, exist_ok=True)

def rows(name):
    with open(os.path.join(DATA, name)) as f:
        return list(csv.DictReader(f))

# ------------------------------------------------ Fig 1: Experiment 1 2x2
def fig1():
    r = rows("exp1_results.csv")
    get = lambda m, mode: next(x for x in r if x["model"] == m and x["mode"] == mode)
    labels = ["weak\n(gpt-4o-mini)", "strong\n(gpt-4.1)"]
    adv = [float(get("gpt-4o-mini", "advisory")["success_pct"]),
           float(get("gpt-4.1", "advisory")["success_pct"])]
    bnd = [float(get("gpt-4o-mini", "binding")["success_pct"]),
           float(get("gpt-4.1", "binding")["success_pct"])]
    ca = [f'{get(m,"advisory")["solved"]}/{get(m,"advisory")["total"]}' for m in ("gpt-4o-mini", "gpt-4.1")]
    cb = [f'{get(m,"binding")["solved"]}/{get(m,"binding")["total"]}' for m in ("gpt-4o-mini", "gpt-4.1")]

    x = np.arange(2); w = 0.36
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    b1 = ax.bar(x - w/2 - 0.01, adv, w, color=C.ADVISORY, label="advisory", zorder=3)
    b2 = ax.bar(x + w/2 + 0.01, bnd, w, color=C.BINDING, label="binding", zorder=3)
    ax.set_ylim(0, 128); ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xticks(x, labels)
    ax.set_ylabel("test tasks solved (%)")
    ax.set_title("Experiment 1 — success rate by model and mode", pad=14)
    ax.grid(axis="x", visible=False)
    for rect, pct, n in zip(list(b1)+list(b2), adv+bnd, ca+cb):
        cx = rect.get_x() + rect.get_width()/2
        ax.annotate(f"{pct:.1f}%", (cx, rect.get_height()), ha="center", va="bottom",
                    fontsize=10.5, color=C.INK, xytext=(0, 3), textcoords="offset points")
        ax.annotate(n, (cx, rect.get_height()), ha="center", va="top", fontsize=9.5,
                    color="#ffffff", xytext=(0, -6), textcoords="offset points")
    # bracket over each bar pair, with its Δ and p on the bracket
    def bracket(cx, text):
        lx, rx = cx - w/2 - 0.01, cx + w/2 + 0.01
        y0, y1 = 108, 111
        ax.plot([lx, lx, rx, rx], [y0, y1, y1, y0], color=C.INK2, lw=1.1,
                zorder=4, clip_on=False)
        ax.annotate(text, (cx, y1), ha="center", va="bottom", fontsize=10,
                    color=C.INK, xytext=(0, 4), textcoords="offset points")
    bracket(0.0, "Δ = +9.2 pp,  McNemar p = 0.0078")
    bracket(1.0, "Δ = +0.0 pp  (no discordant tasks)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 0.9), fontsize=10)
    fig.savefig(f"{OUT}/fig1_experiment1_2x2.png"); plt.close(fig)

# ------------------------------------------------ Fig 2: Experiment 2 ladder
def fig2():
    r = sorted(rows("exp2_ladder.csv"), key=lambda x: int(x["rank"]))
    names = [x["model"].replace("Gemini-2.5-Flash-Lite", "Gemini-2.5-\nFlash-Lite")
                       .replace("Claude-3-Haiku", "Claude-3-\nHaiku") for x in r]
    delta = [float(x["delta_pp"]) for x in r]
    sig = [float(x["mcnemar_p"]) < 0.05 for x in r]
    x = np.arange(len(r))

    # regimes: ceiling = rank 1, window = ranks 2-5 (McNemar-significant), floor = ranks 6-7
    CEIL_TINT, CEIL_ACC = "#eceff1", "#546675"
    WIN_TINT,  WIN_ACC  = "#e3edf6", C.BINDING
    FLR_TINT,  FLR_ACC  = "#f7ebe8", C.S_BRICK

    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    ax.axvspan(-0.6, 0.5, color=CEIL_TINT, zorder=1)
    ax.axvspan(0.5, 4.5, color=WIN_TINT, zorder=1)
    ax.axvspan(4.5, 6.6, color=FLR_TINT, zorder=1)
    ax.axhline(0, color=C.BASELINE, linewidth=1.4, zorder=2)
    ax.plot(x, delta, color=C.BINDING, linewidth=2, zorder=3)

    # per-point label offsets chosen to keep every number clear of the line
    offs = [(0, -16), (-10, 9), (2, -16), (-9, 9), (0, 10), (16, 0), (2, -18)]
    has  = ["center", "right", "center", "right", "center", "left", "center"]
    for xi, d, s, (ox, oy), ha in zip(x, delta, sig, offs, has):
        if s: ax.plot(xi, d, "o", ms=9, mfc=C.BINDING, mec=C.BINDING, zorder=4)
        else: ax.plot(xi, d, "o", ms=9, mfc=C.SURFACE, mec=C.BINDING, mew=2, zorder=4)
        ax.annotate(f"{d:+.1f}", (xi, d), ha=ha, va="center", fontsize=10.5,
                    color=C.INK, xytext=(ox, oy), textcoords="offset points", zorder=5)

    # regime titles, colored to their band
    ytop = 17.6
    ax.text(0.0, ytop, "ceiling", ha="center", fontsize=11, color=CEIL_ACC,
            fontweight="bold")
    ax.text(2.5, ytop, "window", ha="center", fontsize=11, color=WIN_ACC,
            fontweight="bold")
    ax.text(5.5, ytop, "floor", ha="center", fontsize=11, color=FLR_ACC,
            fontweight="bold")

    ax.set_xticks(x, names, fontsize=9.5)
    tick_cols = [CEIL_ACC] + [WIN_ACC]*4 + [FLR_ACC]*2
    for lab, col in zip(ax.get_xticklabels(), tick_cols):
        lab.set_color(col)
    ax.set_xlim(-0.6, 6.6)
    ax.set_ylabel("Δ = binding − advisory (pp)")
    ax.set_ylim(-8.5, 19)
    ax.grid(axis="x", visible=False)
    ax.set_title("Experiment 2: the capability window")
    from matplotlib.lines import Line2D
    handles = [Line2D([0],[0], marker="o", color=C.BINDING, lw=0, ms=9, label="McNemar p < 0.05"),
               Line2D([0],[0], marker="o", mfc=C.SURFACE, mec=C.BINDING, mew=2, lw=0, ms=9,
                      label="not significant")]
    ax.legend(handles=handles, loc="lower left", fontsize=9.5, bbox_to_anchor=(0.015, 0.04))
    # direction arrow under the model names
    from matplotlib.patches import FancyArrowPatch
    arr = FancyArrowPatch((0.32, -0.175), (0.68, -0.175), transform=ax.transAxes,
                          arrowstyle="-|>", mutation_scale=16, color=C.INK2,
                          lw=1.4, clip_on=False)
    ax.add_patch(arr)
    ax.text(0.5, -0.235, "strongest to weakest", transform=ax.transAxes,
            ha="center", va="center", fontsize=10.5, color=C.INK2)
    fig.subplots_adjust(bottom=0.22)
    fig.savefig(f"{OUT}/fig2_capability_window.png"); plt.close(fig)

# ------------------------------------------------ Fig 3: Experiment 3 two-panel
ORDER = ["GPT-4.1", "GPT-4o-mini", "Gemini-2.5-Flash-Lite", "Claude-3-Haiku",
         "Qwen2.5-7B", "Llama-3.1-8B"]
COLORS = {"GPT-4.1": C.S_BLUE, "GPT-4o-mini": C.S_JADE,
          "Gemini-2.5-Flash-Lite": C.S_OCHRE, "Claude-3-Haiku": C.S_PLUM,
          "Qwen2.5-7B": C.S_BRICK, "Llama-3.1-8B": C.S_PERI}

def fig3():
    r = rows("exp3_matrix.csv")
    series = {m: sorted([x for x in r if x["model"] == m], key=lambda x: int(x["k"]))
              for m in ORDER}
    ks = [0, 1, 2]
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.8), sharex=True)
    for ax, key, ylab, title in [
        (axes[0], "delta_pp", "Δ = binding − advisory (pp)", "Binding advantage vs difficulty"),
        (axes[1], "false_done_rate_pct", "advisory false-DONE rate (%)", "The mediator vs difficulty"),
    ]:
        ax.axhline(0, color=C.BASELINE, linewidth=1.2, zorder=2)
        for m in ORDER:
            vals = [float(x[key]) for x in series[m]]
            ls = (0, (4, 3)) if m == "Gemini-2.5-Flash-Lite" else "-"
            ax.plot(ks, vals, color=COLORS[m], linewidth=2, marker="o", ms=6, zorder=3,
                    mec=C.SURFACE, mew=1.2, linestyle=ls)
        ax.set_xticks(ks, ["k0\n(1 bug)", "k1\n(2 bugs)", "k2\n(3 bugs)"])
        ax.set_ylabel(ylab); ax.set_title(title, fontsize=12)
        ax.grid(axis="x", visible=False); ax.set_ylim(-4, 44)
    def leg_label(m):
        if m == "Gemini-2.5-Flash-Lite":
            return "Gemini-2.5-Flash-Lite (dashed: values identical to GPT-4o-mini)"
        return m
    handles = [plt.Line2D([0],[0], color=COLORS[m], lw=2, marker="o", ms=6, mec=C.SURFACE,
                          mew=1.2, linestyle=(0, (4, 3)) if m == "Gemini-2.5-Flash-Lite" else "-",
                          label=leg_label(m)) for m in ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=9.5,
               bbox_to_anchor=(0.5, -0.11))
    fig.suptitle("Experiment 3: the window deepens in place and does not slide",
                 fontweight="bold", fontsize=13, y=1.01)
    fig.savefig(f"{OUT}/fig3_composition_window.png"); plt.close(fig)

# ------------------------------------------------ Fig 4: mediator scatter
def fig4():
    r = rows("mediator_scatter.csv")
    MCOL = dict(COLORS)                     # model -> color, same as fig3
    MCOL["Llama-3.2-3B"] = "#546675"        # dropped-after-v2 model: slate
    # dodge identical stacked points so every model stays visible
    def dodge(model, tier, x):
        # coincident cells separated slightly so every marker stays visible;
        # data values are unchanged in the CSV
        if model == "Gemini-2.5-Flash-Lite":
            return x + {"k0": 0.45, "k1": 0.55, "k2": 1.95}[tier]
        if model == "GPT-4o-mini":
            return x - {"k0": 0.45, "k1": 0.55, "k2": 1.35}[tier]
        if model == "GPT-4.1":
            return x + {"k0": 0.0, "k1": 0.8, "k2": 1.7}[tier]
        return x

    fig, ax = plt.subplots(figsize=(7.4, 5.6))
    ax.axhline(0, color=C.INK2, linewidth=1.4, zorder=2)
    ax.axvline(0, color=C.GRID, linewidth=1.0, zorder=1)
    ax.plot([0, 42], [0, 42], linestyle=(0, (4, 4)), color=C.MUTED, linewidth=1.2, zorder=2)
    for x in r:
        fd, d = float(x["false_done_rate_pct"]), float(x["delta_pp"])
        m, tier, exp = x["model"], x["tier"], x["experiment"]
        mk = {"k0": "o", "k1": "^", "k2": "s"}[tier]
        ax.plot(dodge(m, tier, fd), d, mk, ms=10 if mk == "^" else 9,
                mfc=MCOL[m], mec=C.SURFACE, mew=1.2, zorder=4)
    ax.set_xlabel("advisory false-DONE rate (%)")
    ax.set_ylabel("Δ = binding − advisory (pp)")
    ax.set_xlim(-2.5, 44); ax.set_ylim(-7, 36)
    ax.set_title("The mechanism: Δ tracks the advisory false-DONE rate")

    from matplotlib.lines import Line2D
    model_order = ["GPT-4.1", "GPT-4o-mini", "Gemini-2.5-Flash-Lite", "Claude-3-Haiku",
                   "Qwen2.5-7B", "Llama-3.1-8B", "Llama-3.2-3B"]
    mh = [Line2D([0], [0], marker="o", lw=0, ms=9, mfc=MCOL[m], mec=C.SURFACE, mew=1.2,
                 label=m) for m in model_order]
    leg1 = ax.legend(handles=mh, loc="upper left", fontsize=8.8, title="model",
                     title_fontsize=9.5, alignment="left", frameon=True,
                     facecolor=C.SURFACE, edgecolor="none", framealpha=1.0)
    ax.add_artist(leg1)
    sh = [Line2D([0], [0], marker="o", lw=0, ms=9, mfc=C.MUTED, mec=C.SURFACE, mew=1.2,
                 label="Experiment 2 (1 bug)"),
          Line2D([0], [0], marker="^", lw=0, ms=10, mfc=C.MUTED, mec=C.SURFACE, mew=1.2,
                 label="Experiment 3 (2 bugs)"),
          Line2D([0], [0], marker="s", lw=0, ms=9, mfc=C.MUTED, mec=C.SURFACE, mew=1.2,
                 label="Experiment 3 (3 bugs)"),
          Line2D([0], [0], linestyle=(0, (4, 4)), color=C.MUTED, lw=1.2,
                 label="45° line: binding converted every\nfalse claim into a solved task")]
    ax.legend(handles=sh, loc="lower right", fontsize=8.8, frameon=True,
              facecolor=C.SURFACE, edgecolor="none", framealpha=1.0)
    fig.savefig(f"{OUT}/fig4_mediator_scatter.png"); plt.close(fig)

if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4()
    print("wrote 4 figures to ./figures/")
