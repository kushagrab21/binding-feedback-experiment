"""Diagram figures: exit decision trees (fig5) + experiment workflow (fig6)."""
import os
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import style
style.apply()
C = style
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

def box(ax, x, y, w, h, text, fc, ec, tc=C.INK, fs=9.5, weight="normal"):
    p = FancyBboxPatch((x - w/2, y - h/2), w, h,
                       boxstyle="round,pad=0.012,rounding_size=0.015",
                       fc=fc, ec=ec, lw=1.2, zorder=3)
    ax.add_patch(p)
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=tc,
            zorder=4, linespacing=1.35, fontweight=weight)

def arrow(ax, x1, y1, x2, y2, label=None, lx=0, ly=0):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13,
                        color=C.MUTED, lw=1.3, zorder=2, shrinkA=2, shrinkB=2)
    ax.add_patch(a)
    if label:
        ax.text((x1+x2)/2 + lx, (y1+y2)/2 + ly, label, fontsize=8.6,
                color=C.INK2, ha="center", va="center", zorder=4,
                bbox=dict(fc=C.SURFACE, ec="none", pad=1.2))

NODE  = "#eef4fc"; NEDGE = C.S1_BLUE
GOOD  = "#e6f4e6"; GEDGE = C.S6_GREEN
BAD   = "#fdecec"; BEDGE = C.CRITICAL

def exit_trees():
    fig, axes = plt.subplots(1, 2, figsize=(13.4, 6.4))
    for ax in axes:
        ax.set_xlim(0, 11.6); ax.set_ylim(0, 13); ax.axis("off")

    LOOP = "#f1f1ee"

    def edge(ax, x1, y1, x2, y2, cond=None, side="left"):
        a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13,
                            color=C.MUTED, lw=1.3, zorder=2, shrinkA=3, shrinkB=3)
        ax.add_patch(a)
        if cond:
            mx, my = (x1+x2)/2, (y1+y2)/2
            dx = -0.5 if side == "left" else 0.5
            ha = "right" if side == "left" else "left"
            ax.text(mx + dx, my, cond, fontsize=9, color=C.INK2, ha=ha,
                    va="center", zorder=5,
                    bbox=dict(fc=C.SURFACE, ec="none", pad=1.5))

    # ---------------- Advisory  (leaf grid: 1.6, 4.4, 7.2, 10.0 — uniform 2.8)
    ax = axes[0]
    ax.set_title("Advisory: the model may end the episode", fontsize=12, pad=8)
    box(ax, 5.8, 12.0, 6.0, 1.0, "one step: model submits code,\nchecker runs", NODE, NEDGE)
    box(ax, 5.8, 9.7, 4.2, 0.95, "did the model\ndeclare DONE?", NODE, NEDGE)
    edge(ax, 5.8, 11.5, 5.8, 10.2)
    box(ax, 3.0, 7.3, 3.1, 0.95, "is the checker\ngreen?", NODE, NEDGE)
    box(ax, 8.6, 7.3, 3.1, 0.95, "are all 8 steps\nused?", NODE, NEDGE)
    edge(ax, 4.7, 9.25, 3.3, 7.8, "yes", side="left")
    edge(ax, 6.9, 9.25, 8.3, 7.8, "no", side="right")
    box(ax, 1.6, 4.7, 2.5, 1.25, "true-DONE\nSUCCESS", GOOD, GEDGE, fs=9)
    box(ax, 4.4, 4.7, 2.5, 1.25, "false-DONE\nFAILURE", BAD, BEDGE, fs=9)
    edge(ax, 2.5, 6.8, 1.8, 5.35, "yes", side="left")
    edge(ax, 3.5, 6.8, 4.2, 5.35, "no", side="right")
    box(ax, 7.2, 4.7, 2.7, 0.95, "is the checker\ngreen?", NODE, NEDGE, fs=9)
    box(ax, 10.0, 4.7, 1.9, 0.95, "continue \u21ba", LOOP, C.MUTED, fs=9)
    edge(ax, 8.1, 6.8, 7.4, 5.2, "yes", side="left")
    edge(ax, 9.1, 6.8, 9.8, 5.2, "no", side="right")
    box(ax, 5.7, 2.0, 2.8, 1.25, "cap, code passing\nSUCCESS*", GOOD, GEDGE, fs=8.7)
    box(ax, 8.7, 2.0, 2.8, 1.25, "cap, code failing\nFAILURE", BAD, BEDGE, fs=8.7)
    edge(ax, 6.7, 4.2, 5.9, 2.65, "yes", side="left")
    edge(ax, 7.7, 4.2, 8.5, 2.65, "no", side="right")
    ax.text(5.8, 0.35, "*the model wrote passing code but never recognized it as done",
            ha="center", fontsize=8.8, color=C.INK2)

    # ---------------- Binding  (same uniform leaf grid)
    ax = axes[1]
    ax.set_title("Binding: only the checker ends it as solved", fontsize=12, pad=8)
    box(ax, 5.8, 12.0, 6.4, 1.0, "one step: model submits code,\nchecker runs (DONE is ignored)", NODE, NEDGE)
    box(ax, 5.8, 9.7, 4.0, 0.95, "is the checker\ngreen?", NODE, NEDGE)
    edge(ax, 5.8, 11.5, 5.8, 10.2)
    box(ax, 1.6, 7.3, 2.6, 1.25, "solved\nSUCCESS", GOOD, GEDGE, fs=9)
    box(ax, 5.8, 7.3, 3.9, 0.95, "same code as the\nlast failed try?", NODE, NEDGE)
    edge(ax, 4.2, 9.35, 2.0, 7.95, "yes", side="left")
    edge(ax, 5.8, 9.25, 5.8, 7.8, "no", side="right")
    box(ax, 3.0, 4.7, 3.0, 0.95, "third identical\nfailure?", NODE, NEDGE)
    box(ax, 8.6, 4.7, 2.9, 0.95, "are all 8 steps\nused?", NODE, NEDGE)
    edge(ax, 4.6, 6.85, 3.4, 5.2, "yes", side="left")
    edge(ax, 7.0, 6.85, 8.3, 5.2, "no", side="right")
    box(ax, 1.6, 2.0, 2.4, 1.25, "escalated\nFAILURE", BAD, BEDGE, fs=9)
    box(ax, 4.4, 2.0, 2.7, 1.25, "verdict re-sent,\ncontinue \u21ba", LOOP, C.MUTED, fs=8.7)
    edge(ax, 2.4, 4.2, 1.8, 2.7, "yes", side="left")
    edge(ax, 3.6, 4.2, 4.3, 2.7, "no", side="right")
    box(ax, 7.2, 2.0, 2.4, 1.25, "step cap\nFAILURE", BAD, BEDGE, fs=9)
    box(ax, 10.0, 2.0, 1.8, 1.25, "continue\n\u21ba", LOOP, C.MUTED, fs=8.6)
    edge(ax, 8.0, 4.2, 7.4, 2.7, "yes", side="left")
    edge(ax, 9.2, 4.2, 9.9, 2.7, "no", side="right")
    ax.text(5.8, 0.35, "\u21ba means the episode returns to the top box for its next step",
            ha="center", fontsize=8.8, color=C.INK2)

    fig.suptitle("Episode exits under the two modes", fontweight="bold", fontsize=13, y=1.00)
    fig.savefig(f"{OUT}/fig5_exit_trees.png")
    plt.close(fig)

def workflow():
    fig, ax = plt.subplots(figsize=(14.2, 5.4))
    ax.set_xlim(0, 15.8); ax.set_ylim(-0.6, 6.6); ax.axis("off")
    LOOP = "#f1f1ee"
    HID  = "#e9e9e4"

    def state(x, y, text, fc="#eef4fc", ec=C.S1_BLUE, w=2.4, h=1.2, fs=9.3, ls="-"):
        p = FancyBboxPatch((x - w/2, y - h/2), w, h,
                           boxstyle="round,pad=0.012,rounding_size=0.015",
                           fc=fc, ec=ec, lw=1.2, linestyle=ls, zorder=3)
        ax.add_patch(p)
        ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=C.INK,
                zorder=4, linespacing=1.4)

    def action(x1, y1, x2, y2, label=None, lx=0, ly=0.6):
        a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=15,
                            color=C.INK2, lw=1.5, zorder=2, shrinkA=4, shrinkB=4)
        ax.add_patch(a)
        if label:
            ax.text((x1+x2)/2 + lx, (y1+y2)/2 + ly, label, fontsize=8.6,
                    color=C.INK2, ha="center", va="center", zorder=5,
                    linespacing=1.35, style="italic",
                    bbox=dict(fc=C.SURFACE, ec="none", pad=1.5))

    # states
    state(1.5, 3.1, "25 hand-written\nPython functions", fc=LOOP, ec=C.MUTED, w=2.6)
    state(4.9, 3.1, "97 buggy tasks\n(never edited again)", w=2.6, h=1.5)
    state(7.9, 5.1, "10 open tasks\n(for trial runs)", w=2.7)
    state(7.9, 1.1, "87 hidden tasks\n(nobody looks at them)", fc=HID, ec=C.MUTED,
          w=2.9, ls=(0, (4, 3)))
    state(11.6, 5.1, "written predictions\n(date-stamped)", w=2.8, h=1.5)
    state(11.6, 1.1, "a saved record of\nevery model attempt", w=2.8)
    state(14.6, 3.1, "results\ntables", fc="#e6f4e6", ec=C.S6_GREEN, w=1.8)

    # actions
    action(2.8, 3.1, 3.6, 3.1, "copy each function\nand break one line", lx=0.35, ly=1.0)
    action(6.1, 3.6, 6.9, 4.7, "opened", lx=-0.85, ly=0.15)
    action(6.1, 2.6, 6.9, 1.5, "hidden", lx=-0.85, ly=-0.15)
    action(9.25, 5.1, 10.2, 5.1, "run trials and then\nwrite predictions", lx=0, ly=1.05)
    action(11.6, 4.35, 11.6, 1.7, "the full run may\nstart only after this", lx=-1.75, ly=0.2)
    action(9.35, 1.1, 10.2, 1.1, "every model tries every\ntask in both modes", lx=0, ly=-0.85)
    action(12.75, 1.65, 14.05, 2.6, "count the outcomes\nfrom the record", lx=0.85, ly=-0.75)

    ax.set_title("The experiment workflow", fontsize=12.5, pad=10)
    ax.text(7.9, -0.45, "boxes show states and arrows show actions. frozen or saved things are never edited afterwards",
            ha="center", fontsize=8.8, color=C.INK2)
    fig.savefig(f"{OUT}/fig6_workflow.png")
    plt.close(fig)

def modes():
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 5.2))
    for ax in axes:
        ax.set_xlim(0, 10.6); ax.set_ylim(0, 7.6); ax.axis("off")

    def node(ax, x, y, text, ec, lw, fc="#eef4fc"):
        p = FancyBboxPatch((x - 1.25, y - 0.65), 2.5, 1.3,
                           boxstyle="round,pad=0.012,rounding_size=0.02",
                           fc=fc, ec=ec, lw=lw, zorder=3)
        ax.add_patch(p)
        ax.text(x, y, text, ha="center", va="center", fontsize=11.5, color=C.INK,
                zorder=4, fontweight="bold")

    def curve(ax, x1, y1, x2, y2, rad, label, ly):
        a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=15,
                            color=C.INK2, lw=1.5, zorder=2, shrinkA=4, shrinkB=4,
                            connectionstyle=f"arc3,rad={rad}")
        ax.add_patch(a)
        ax.text((x1+x2)/2, (y1+y2)/2 + ly, label, fontsize=9.2, color=C.INK2,
                ha="center", va="center", zorder=5, style="italic",
                linespacing=1.35, bbox=dict(fc=C.SURFACE, ec="none", pad=1.5))

    def exit_arrow(ax, x1, y1, x2, y2, color, label, lx, dashed=False, crossed=False):
        a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=15,
                            color=color, lw=2.0, zorder=2, shrinkA=4, shrinkB=4,
                            linestyle=(0, (4, 3)) if dashed else "-")
        ax.add_patch(a)
        mx, my = (x1+x2)/2, (y1+y2)/2
        if crossed:
            ax.plot(mx, my, "x", ms=13, mew=3, color=C.CRITICAL, zorder=6)
        ax.text(mx + lx, my, label, fontsize=9.2, color=color, ha="center",
                va="center", zorder=5, style="italic", linespacing=1.35,
                bbox=dict(fc=C.SURFACE, ec="none", pad=1.5))

    # ---------------- Advisory
    ax = axes[0]
    ax.set_title("Advisory: the LLM may end the loop", fontsize=12, pad=8)
    node(ax, 2.6, 5.3, "LLM", C.ADVISORY, 3.0)
    node(ax, 8.0, 5.3, "checker", C.S1_BLUE, 1.2)
    ax.text(2.2, 3.85, "holds the authority\nto end the loop", ha="center", fontsize=8.8,
            color=C.ADVISORY, fontweight="bold", linespacing=1.35,
            bbox=dict(fc=C.SURFACE, ec="none", pad=1.5))
    curve(ax, 3.9, 5.75, 6.7, 5.75, -0.35, "writes code", 0.95)
    curve(ax, 6.7, 4.85, 3.9, 4.85, -0.35, "returns a verdict\n(pass or fail)", -1.35)
    box(ax, 5.3, 1.3, 3.0, 1.15, "episode ends", "#e6f4e6", C.S6_GREEN, fs=10)
    exit_arrow(ax, 2.6, 3.6, 4.6, 1.85, C.ADVISORY, "the LLM\ndeclares DONE", -1.35)
    ax.text(5.3, 0.35, "the declaration ends the loop even when the verdict was fail",
            ha="center", fontsize=8.8, color=C.INK2)

    # ---------------- Binding
    ax = axes[1]
    ax.set_title("Binding: only the checker may end the loop", fontsize=12, pad=8)
    node(ax, 2.6, 5.3, "LLM", C.MUTED, 1.2)
    node(ax, 8.0, 5.3, "checker", C.BINDING, 3.0)
    ax.text(8.5, 3.85, "holds the authority\nto end the loop", ha="center", fontsize=8.8,
            color=C.BINDING, fontweight="bold", linespacing=1.35,
            bbox=dict(fc=C.SURFACE, ec="none", pad=1.5))
    curve(ax, 3.9, 5.75, 6.7, 5.75, -0.35, "writes code", 0.95)
    curve(ax, 6.7, 4.85, 3.9, 4.85, -0.35, "returns a verdict\n(pass or fail)", -1.35)
    box(ax, 5.3, 1.3, 3.0, 1.15, "episode ends", "#e6f4e6", C.S6_GREEN, fs=10)
    exit_arrow(ax, 8.0, 3.6, 6.0, 1.85, C.BINDING, "the verdict\nturns pass", 1.35)
    exit_arrow(ax, 2.6, 3.6, 4.6, 1.85, C.MUTED, "saying DONE\nis ignored", -1.35,
               dashed=True, crossed=True)
    ax.text(5.3, 0.35, "the loop continues until the checker passes the code",
            ha="center", fontsize=8.8, color=C.INK2)

    fig.suptitle("The two modes: who may end the loop", fontweight="bold",
                 fontsize=13, y=1.00)
    fig.savefig(f"{OUT}/fig7_modes.png")
    plt.close(fig)

if __name__ == "__main__":
    exit_trees(); workflow(); modes()
    print("wrote figures 5, 6 and 7 to ./figures/")
