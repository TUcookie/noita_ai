"""
进化过程可视化
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import font_manager
import numpy as np

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
        seq_str = "  ->  ".join(best.sequence)
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
    history: list,
    wand,
    output_path: str = "best_timeline.png",
):
    """每代最优序列链级指标 2×3 图。x 轴 = Generation。无趋势线，3 秒可读。

    上行 — 火力结构：
      1. 单发伤害 (avg + 25%-75% 链间带)
      2. 平均每链投射物
      3. 每秒投射物

    下行 — 资源代价：
      4. 每轮耗时 (cast + recharge 堆叠柱)
      5. 法力效率 (total_dmg / total_mana)
      6. 序列 SpellType 彩色条
    """
    from wand_sim.engine.simulator import simulate, TargetInfo
    from wand_sim.engine.spells_db import SPELLS
    from wand_sim.engine.spell import SpellType

    target = TargetInfo(distance_px=300)
    LINE_W = 2.0

    gens = list(range(1, len(history) + 1))
    dmg_max, dmg_min = [], []           # 每轮最强链 / 最弱链的单发伤害，跨轮均值
    avg_proj, proj_per_s = [], []
    cast_times, recharge_times, mana_eff = [], [], []

    for c in history:
        r = simulate(c.sequence, wand, target, simulate_duration=30.0, trace=True)
        chains = [e for e in r.chain_log if e.get("type") == "chain"]
        recharges = [e for e in r.chain_log if e.get("type") == "recharge"]

        if chains:
            n = len(chains)
            # 每轮按链汇总单发伤害，取最强链和最弱链
            round_chains: dict[int, list[float]] = {}
            for ch in chains:
                rd = ch["round"]
                round_chains.setdefault(rd, []).append(ch["dmg_per_hit"])
            max_per_round = [max(v) for v in round_chains.values()]
            min_per_round = [min(v) for v in round_chains.values()]
            dmg_max.append(sum(max_per_round) / len(max_per_round))
            dmg_min.append(sum(min_per_round) / len(min_per_round))
            avg_proj.append(sum(ch["proj"] for ch in chains) / n)
            cast_times.append(sum(ch["cast_delay"] for ch in chains) / n)
        else:
            dmg_max.append(0); dmg_min.append(0)
            avg_proj.append(0); cast_times.append(0)

        recharge_times.append(
            sum(rch["duration"] for rch in recharges) / max(len(recharges), 1)
            if recharges else 0
        )
        proj_per_s.append(r.avg_projectiles_per_second)
        mana_eff.append(r.total_damage / max(r.total_mana_spent, 1))

    fig, axes = plt.subplots(2, 3, figsize=(20, 10))
    fig.suptitle("Best Sequence — Per-Chain Metrics over Generations", fontsize=14)

    # ── Panel 1: 单发伤害 (max / min 链) ──
    ax = axes[0][0]
    ax.fill_between(gens, dmg_min, dmg_max, alpha=0.12, color="#4A90D9")
    ax.plot(gens, dmg_max, color="#E8833A", linewidth=LINE_W, label="Max chain")
    ax.plot(gens, dmg_min, color="#4A90D9", linewidth=LINE_W, label="Min chain")
    ax.set_ylabel("Damage")
    ax.set_title("Damage per Hit (max / min chain)")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # ── Panel 2: 平均每链投射物 ──
    ax = axes[0][1]
    ax.plot(gens, avg_proj, color="#4A90D9", linewidth=LINE_W)
    ax.set_ylabel("Projectiles")
    ax.set_title("Avg Projectiles per Chain")
    ax.grid(True, alpha=0.3)

    # ── Panel 3: 每秒投射物 ──
    ax = axes[0][2]
    ax.plot(gens, proj_per_s, color="#4A90D9", linewidth=LINE_W)
    ax.set_ylabel("Proj / s")
    ax.set_title("Projectiles per Second")
    ax.grid(True, alpha=0.3)

    # ── Panel 4: 每轮耗时分解 ──
    ax = axes[1][0]
    ax.bar(gens, cast_times, color="#4A90D9", label="Cast Delay")
    ax.bar(gens, recharge_times, bottom=cast_times, color="#E8833A", label="Recharge")
    ax.set_ylabel("Seconds")
    ax.set_title("Time per Round (Cast + Recharge)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    # ── Panel 5: 法力效率 ──
    ax = axes[1][1]
    ax.plot(gens, mana_eff, color="#50B86C", linewidth=LINE_W)
    ax.set_ylabel("Dmg / Mana")
    ax.set_title("Mana Efficiency")
    ax.grid(True, alpha=0.3)

    # ── Panel 6: 序列 SpellType 构成 ──
    TYPE_COLORS = {
        SpellType.PROJECTILE: "#4A90D9",
        SpellType.MODIFIER: "#E8833A",
        SpellType.MULTICAST: "#50B86C",
        SpellType.UTILITY: "#9B59B6",
    }
    ax = axes[1][2]
    bar_h = 0.9
    for i, c in enumerate(history):
        y = i + 1
        for j, spell_key in enumerate(c.sequence):
            st = SPELLS[spell_key].type if spell_key in SPELLS else SpellType.OTHER
            ax.barh(y, 1, left=j, height=bar_h, color=TYPE_COLORS.get(st, "#999"),
                    edgecolor="white", linewidth=0.2)

    legend_patches = [plt.Rectangle((0, 0), 1, 1, fc=c, label=t.value)
                      for t, c in TYPE_COLORS.items() if any(
                          SPELLS[s].type == t for gen in history for s in gen.sequence if s in SPELLS)]
    ax.legend(handles=legend_patches, fontsize=7, loc="lower right")
    ax.set_xlabel("Slot")
    ax.set_ylabel("Generation")
    ax.set_title("SpellType Composition")
    ax.set_ylim(len(history) + 0.5, 0.5)
    _yticks6 = [1] + [i for i in range(5, len(history) + 1, 5)]
    ax.set_yticks(_yticks6)
    ax.set_xlim(0, max(len(c.sequence) for c in history))

    # ── x 轴每 5 代一个刻度（面板 1-5）──
    xticks5 = [1] + [i for i in range(5, len(history) + 1, 5)]
    for row in range(2):
        for col in range(3):
            ax = axes[row][col]
            if row == 1:
                ax.set_xlabel("Generation")
            if not (row == 1 and col == 2):  # 跳过 SpellType 面板
                ax.set_xticks(xticks5)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Timeline saved to {output_path}")
    plt.close(fig)

def plot_population_boxplot(
    all_fitnesses: list[list[float]],
    output_path: str = "population_boxplot.png",
):
    """每代种群 fitness 分布箱线图。"""
    fig, ax = plt.subplots(figsize=(14, 6))

    bp = ax.boxplot(all_fitnesses, patch_artist=True,
                     showfliers=False,  # 隐藏极端离群值
                     widths=0.7)

    # 箱子配色
    n_gens = len(all_fitnesses)
    colors = plt.cm.Blues([0.3 + 0.7 * i / n_gens for i in range(n_gens)])
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)

    # 中位数连线
    medians = [np.median(f) if f else 0 for f in all_fitnesses]
    ax.plot(range(1, n_gens + 1), medians, "r-", linewidth=2, label="Median")

    # x 轴标签（每 5 代）
    ax.set_xticks(list(range(5, n_gens + 1, 5)))
    ax.set_xticklabels([f"Gen {t}" for t in range(5, n_gens + 1, 5)])
    ax.set_ylabel("Fitness (DPS)")
    ax.set_title("Population Fitness Distribution per Generation")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)