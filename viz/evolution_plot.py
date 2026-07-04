"""
进化过程可视化
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import font_manager

from optimizer.es_search import Candidate


def _setup_cn_font():
    candidates = [
        "Microsoft YaHei", "SimHei", "SimSun",
        "Noto Sans CJK SC", "WenQuanYi Micro Hei",
        "PingFang SC", "Heiti SC",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            matplotlib.rcParams["font.family"] = name
            return
    for f in font_manager.fontManager.ttflist:
        if any(tag in f.name for tag in ["CJK", "Hei", "Song", "Ming"]):
            matplotlib.rcParams["font.family"] = f.name
            return

_setup_cn_font()

def make_evolution_animation(
        history: list[Candidate],
        output_path: str = "evolution.gif",
        title: str = "Wand Sequence Evolution",
):
    '''创建进化过程动画'''
    fitnesses = [c.fitness for c in history]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8),
        gridspec_kw={"height_ratios": [3, 1]},
    )

    # fitness
    ax1.set_xlim(-0.5, len(history) - 0.5)
    ax1.set_ylim(0, max(fitnesses) * 1.1)
    ax1.set_xlabel("Generation")
    ax1.set_ylabel("Fitness")
    ax1.set_title(title)
    ax1.grid(True, alpha=0.3)

    line, = ax1.plot([], [], "b-", linewidth=2)
    scatter, = ax1.plot([], [], "ro", markersize=4)

    # 最优序列
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.axis("off")
    seq_text = ax2.text(
        0.5, 0.5, "", transform=ax2.transAxes,
        fontsize=12, ha="center", va="center",
        bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.5),
    )

    def init():
        line.set_data([], [])
        scatter.set_data([], [])
        seq_text.set_text("")
        return line, scatter, seq_text

    def animate(frame):
        x = list(range(frame + 1))
        y = fitnesses[:frame + 1]
        line.set_data(x, y)
        scatter.set_data(x, y)
        best = history[frame]
        ax1.set_title(f"{title}  (Gen {frame+1}/{len(history)})")
        seq_str = "  →  ".join(best.sequence)
        seq_text.set_text(seq_str)
        return line, scatter, seq_text

    anim = animation.FuncAnimation(
        fig, animate, init_func=init,
        frames=len(history), interval=200, blit=False,
    )
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    anim.save(output_path, writer="pillow", fps=5)
    print(f"Animation saved to {output_path}")
    plt.close(fig)
    return anim

def plot_evolution_summary(
    history: list[Candidate],
    output_path: str = "evolution_summary.png",
):
    """上排 = Fitness 曲线，下排 = 最优序列"""
    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(12, 5),
        gridspec_kw={"height_ratios": [3, 1]},
    )

    # ── 上：Fitness 收敛曲线 ──
    generations = range(len(history))
    fitnesses = [c.fitness for c in history]
    ax_top.plot(generations, fitnesses, "b-", linewidth=2)
    ax_top.fill_between(generations, 0, fitnesses, alpha=0.2)
    ax_top.set_xlim(-1, len(history))
    step = 5
    ticks = [0]
    for t in range(step - 1, len(history) - 1, step):
        ticks.append(t)
    if ticks[-1] != len(history) - 1:
        ticks.append(len(history) - 1)
    ax_top.set_xticks(ticks)
    ax_top.set_xticklabels([f"{t+1}" for t in ticks])
    ax_top.set_xlabel("Generation")
    ax_top.set_ylabel("Fitness")
    ax_top.set_title(f"Fitness Convergence  —  Best: {fitnesses[-1]:.0f}")
    ax_top.grid(True, alpha=0.3)

    # ── 下：序列 ──
    ax_bot.axis("off")
    best = history[-1]
    seq_str = "  →  ".join(best.sequence)
    ax_bot.text(
        0.5, 0.5, seq_str, transform=ax_bot.transAxes,
        fontsize=11, ha="center", va="center",
        bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.5),
    )

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Summary saved to {output_path}")
    plt.close(fig)

def plot_timeline_metrics(
    round_log: list[dict],
    output_path: str = "best_timeline.png",
):
    """最优序列逐轮指标 3×2 折线图。"""
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle("Best Sequence — Per-Round Metrics", fontsize=14)

    rounds = [r["round"] for r in round_log]

    panels = [
        # 上行：续航相关
        ("mana_rate",     "Mana / s",      "Mana Usage Rate",      0, 0),
        ("firing_uptime", "Uptime",        "Firing Uptime",        0, 1),
        ("self_damage",   "Risk",          "Self Damage Risk",     0, 2),
        # 下行：伤害相关
        ("avg_dmg",       "Damage",        "Avg Damage per Hit",   1, 0),
        ("hit_rate",      "Hit Rate",      "Average Hit Rate",     1, 1),
        ("crit_ratio",    "Crit Ratio",    "Critical Hit Share",   1, 2),
    ]

    for key, ylabel, title, row, col in panels:
        ax = axes[row][col]
        values = [r[key] for r in round_log]
        ax.plot(rounds, values, "b-", linewidth=1.5, alpha=0.7)

        # 移动平均趋势线
        if len(values) >= 5:
            window = max(3, len(values) // 8)
            trend = [
                sum(values[max(0, i-window):i+1]) / min(i+1, window+1)
                for i in range(len(values))
            ]
            ax.plot(rounds, trend, "r--", linewidth=1.5, alpha=0.5)

        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        if row == 1:
            ax.set_xlabel("Round")

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)