"""
进化过程可视化
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import font_manager
from matplotlib.ticker import MaxNLocator
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
    """Plot build-explanation metrics for each generation's best sequence."""
    from wand_sim.engine.simulator import simulate, TargetInfo
    from wand_sim.engine.spells_db import SPELLS
    from wand_sim.engine.spell import SpellType

    target = TargetInfo(distance_px=300)
    line_w = 2.0
    duration = 30.0

    colors = {
        "blue": "#2356A7",
        "sky": "#83B6E1",
        "orange": "#ED342F",
        "green": "#178642",
        "purple": "#A0D293",
        "accent": "#F69A9B",
        "gray": "#666666",
        "grid": "#D9D9D9",
        "empty": "#EAEAEA",
    }

    def _style_axis(ax, grid_axis: str = "both", integer_y: bool = False):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#B8B8B8")
        ax.spines["bottom"].set_color("#B8B8B8")
        ax.tick_params(colors="#444444", labelsize=9)
        ax.grid(True, axis=grid_axis, color=colors["grid"], linewidth=0.8, alpha=0.8)
        ax.set_axisbelow(True)
        ax.margins(y=0.06)

        locator = MaxNLocator(nbins=6, min_n_ticks=5, integer=integer_y)
        ax.yaxis.set_major_locator(locator)
        lo, hi = ax.get_ylim()
        ticks = locator.tick_values(lo, hi)
        ticks = np.asarray(ticks, dtype=float)
        ticks = ticks[np.isfinite(ticks)]
        if ticks.size >= 2:
            lower_candidates = ticks[ticks <= lo + 1e-12]
            upper_candidates = ticks[ticks >= hi - 1e-12]
            lower = float(lower_candidates[-1]) if lower_candidates.size else float(ticks[0])
            upper = float(upper_candidates[0]) if upper_candidates.size else float(ticks[-1])
            if upper <= lower:
                upper = float(ticks[-1])
            visible_ticks = ticks[(ticks >= lower - 1e-12) & (ticks <= upper + 1e-12)]
            ax.set_ylim(lower, upper)
            ax.set_yticks(visible_ticks)

    gens = list(range(1, len(history) + 1))
    damage_per_round = []
    mana_pressure = []
    cast_times = []
    recharge_times = []
    non_projectile_per_chain = []
    damage_stability = []

    for c in history:
        result = simulate(c.sequence, wand, target, simulate_duration=duration, trace=True)
        chains = [e for e in result.chain_log if e.get("type") == "chain"]
        rounds = max(result.total_rounds, 1)
        chain_count = len(chains)

        damage_per_round.append(result.total_damage / rounds)
        mana_pressure.append(
            result.mana_usage_per_second / max(wand.mana_charge_speed, 1e-9)
        )

        if chain_count:
            cast_times.append(sum(ch["cast_delay"] for ch in chains) / rounds)
        else:
            cast_times.append(0.0)

        recharge_times.append(
            sum(e["duration"] for e in result.chain_log if e.get("type") == "recharge") / rounds
        )

        non_projectile_count = 0
        for spell_key in c.sequence:
            spell = SPELLS.get(spell_key)
            if spell is None:
                continue
            if spell.type not in (SpellType.PROJECTILE, SpellType.STATIC_PROJECTILE):
                non_projectile_count += 1
        non_projectile_per_chain.append(
            non_projectile_count / chain_count if chain_count else 0.0
        )

        round_damage: dict[int, float] = {}
        for ch in chains:
            rd = ch["round"]
            round_damage[rd] = round_damage.get(rd, 0.0) + ch["dmg"]
        damages = [round_damage.get(rd, 0.0) for rd in range(rounds)]
        if damages:
            mean_damage = sum(damages) / len(damages)
            if mean_damage > 1e-9 and len(damages) > 1:
                variance = sum((d - mean_damage) ** 2 for d in damages) / len(damages)
                damage_stability.append((variance ** 0.5) / mean_damage)
            else:
                damage_stability.append(0.0)
        else:
            damage_stability.append(0.0)

    fig, axes = plt.subplots(2, 3, figsize=(20, 10), facecolor="white")
    fig.suptitle("Best Sequence Build Metrics over Generations", fontsize=14, color="#222222")

    ax = axes[0][0]
    ax.plot(gens, damage_per_round, color=colors["orange"], linewidth=line_w)
    ax.set_ylabel("Damage / Round")
    ax.set_title("Damage per Round", fontsize=11)
    _style_axis(ax, integer_y=True)

    ax = axes[0][1]
    ax.plot(gens, mana_pressure, color=colors["blue"], linewidth=line_w)
    ax.axhline(1.0, color=colors["gray"], linewidth=1.0, linestyle="--", alpha=0.8)
    ax.set_ylabel("Usage / Regen")
    ax.set_title("Mana Pressure", fontsize=11)
    _style_axis(ax)

    ax = axes[0][2]
    ax.bar(gens, cast_times, color=colors["blue"], label="Cast", width=0.8)
    ax.bar(gens, recharge_times, bottom=cast_times, color=colors["green"], label="Recharge", width=0.8)
    ax.set_ylabel("Seconds / Round")
    ax.set_title("Cast vs Recharge", fontsize=11)
    ax.legend(frameon=False, fontsize=8)
    _style_axis(ax, grid_axis="y")

    ax = axes[1][0]
    ax.plot(gens, non_projectile_per_chain, color=colors["accent"], linewidth=line_w)
    ax.set_ylabel("Cards / Chain")
    ax.set_title("Non-Projectile Cards per Chain", fontsize=11)
    _style_axis(ax)

    ax = axes[1][1]
    ax.plot(gens, damage_stability, color=colors["green"], linewidth=line_w)
    ax.set_ylabel("CV")
    ax.set_title("Std / Mean", fontsize=11)
    _style_axis(ax)

    type_colors = {
        SpellType.PROJECTILE: colors["blue"],
        SpellType.STATIC_PROJECTILE: colors["sky"],
        SpellType.MODIFIER: colors["accent"],
        SpellType.MULTICAST: colors["green"],
        SpellType.UTILITY: colors["purple"],
    }
    ax = axes[1][2]
    bar_h = 0.9
    for i, c in enumerate(history):
        y = i + 1
        for j in range(wand.capacity):
            if j < len(c.sequence):
                spell_key = c.sequence[j]
                st = SPELLS[spell_key].type if spell_key in SPELLS else SpellType.OTHER
                color = type_colors.get(st, "#999999")
            else:
                color = colors["empty"]
            ax.barh(
                y, 1, left=j, height=bar_h, color=color,
                edgecolor="white", linewidth=0.3,
            )

    legend_patches = [
        plt.Rectangle((0, 0), 1, 1, fc=color, label=spell_type.value)
        for spell_type, color in type_colors.items()
        if any(
            SPELLS[s].type == spell_type
            for gen in history
            for s in gen.sequence
            if s in SPELLS
        )
    ]
    legend_patches.append(plt.Rectangle((0, 0), 1, 1, fc=colors["empty"], label="empty"))
    ax.legend(
        handles=legend_patches,
        fontsize=9,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=True,
        fancybox=False,
        framealpha=0.97,
        facecolor="white",
        edgecolor="#D0D0D0",
        handlelength=1.2,
        handletextpad=0.45,
        borderpad=0.45,
        labelspacing=0.55,
    )
    ax.set_xlabel("Slot")
    ax.set_ylabel("Generation")
    ax.set_title("Sequence Structure Map", fontsize=11)
    ax.set_ylim(len(history) + 0.5, 0.5)
    y_ticks = [1] + [i for i in range(5, len(history) + 1, 5)]
    ax.set_yticks(y_ticks)
    ax.set_xlim(0, wand.capacity)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#B8B8B8")
    ax.spines["bottom"].set_color("#B8B8B8")
    ax.tick_params(colors="#444444", labelsize=9)

    xticks5 = [1] + [i for i in range(5, len(history) + 1, 5)]
    for row in range(2):
        for col in range(3):
            ax = axes[row][col]
            if row == 1 and col != 2:
                ax.set_xlabel("Generation")
            if not (row == 1 and col == 2):
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