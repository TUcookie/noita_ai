from pathlib import Path

from wand_sim.engine.wand import WandStats
from wand_sim.engine.simulator import simulate, TargetInfo
from optimizer.es_search import run_es
from viz.evolution_plot import (
    make_evolution_animation,
    plot_evolution_summary,
    plot_timeline_metrics,
    plot_population_boxplot,
)


def _next_run_dir(base: str = "viz") -> Path:
    n = 1
    while (Path(base) / f"run{n}").exists():
        n += 1
    run_dir = Path(base) / f"run{n}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def main():
    wand = WandStats(
        mana_max=200,
        mana_charge_speed=30,
        cast_delay=0.17,
        recharge_time=0.33,
        spread=3.0,
        capacity=8,
    )
    target = TargetInfo(distance_px=300, is_moving=False)

    print("=" * 60)
    print("Noita 遗传算法找最优法术序列")
    print(f"法杖: 法力上限={wand.mana_max}, 法力充能速度={wand.mana_charge_speed}, "
          f"施放延迟={wand.cast_delay}s, 容量={wand.capacity}")
    print(f"目标: 距离={target.distance_px}px")
    print("=" * 60)

    # 遗传算法
    history, all_fitness, all_pop = run_es(
        wand=wand,
        target=target,
        pop_size=100,
        elite_count=20,
        generations=50,
        return_pop=True,
        verbose=True,
    )

    best = history[-1]
    print("\n" + "=" * 60)
    print("结果：")
    print(f"最优序列：{' -> '.join(best.sequence)}")
    print(f"分数：{best.fitness:.1f}")

    # 30s 验证
    final = simulate(best.sequence, wand, target, simulate_duration=30.0)
    print(f"DPS (30s): {final.dps:.1f}")
    print(f"首次法力耗尽时间: {final.mana_exhaustion_time:.1f}s")
    print(f"每秒命中: {final.avg_projectiles_per_second:.1f}")
    print(f"暴击占比: {final.crit_ratio:.1%}")

    # 输出
    run_dir = _next_run_dir()
    print(f"\n可视化生成中 -> {run_dir}/")

    def _sub(path: str) -> str:
        p = run_dir / path
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)

    plot_evolution_summary(history, _sub("convergence/evolution_summary.png"))

    plot_timeline_metrics(history, wand, _sub("sequence/best_timeline.png"))

    make_evolution_animation(history, _sub("animation/evolution.gif"))

    plot_population_boxplot(all_fitness, _sub("convergence/population_boxplot.png"))

    print("全部生成完毕!")


if __name__ == "__main__":
    main()