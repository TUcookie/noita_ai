"""
Noita 魔杖模拟器。
按 spell 序列顺序模拟发射过程，计算 DPS 和法力可持续性。
"""

import math
from dataclasses import dataclass

from .wand import WandState, WandStats
from .spell import Spell, SpellType
from .spells_db import SPELLS


# ── 修正累积器 ────────────────────────────────────────────

@dataclass
class ModifierStack:
    """累积 modifier 效果，在下一个投射物发射时消费。"""
    projectile_mod: float = 0.0
    speed_mod: float = 1.0
    spread_mod: float = 0.0
    crit_mod: float = 0.0
    mana_mod: int = 0
    recharge_time_mod: float = 0.0

    def apply(self, spell: Spell):
        self.projectile_mod += spell.projectile_mod
        self.speed_mod *= spell.speed_mod
        self.spread_mod += spell.spread_mod
        self.crit_mod += spell.crit_mod
        self.mana_mod += spell.mana_mod
        self.recharge_time_mod += spell.recharge_time_mod

    def clear(self):
        self.projectile_mod = 0.0
        self.speed_mod = 1.0
        self.spread_mod = 0.0
        self.crit_mod = 0.0
        self.mana_mod = 0
        self.recharge_time_mod = 0.0


# ── 输入 / 输出 ────────────────────────────────────────────

@dataclass
class TargetInfo:
    """目标参数。"""
    distance_px: float = 300.0
    is_moving: bool = False


@dataclass
class SimResult:
    """模拟结果。"""

    # 核心指标
    dps: float                          # 每秒伤害
    total_damage: float                 # 总伤害
    total_projectiles: int              # 总发射数
    total_time_simulated: float         # 实际模拟时长

    # 续航
    mana_exhaustion_time: float         # 法力耗尽时刻（秒），未耗尽 = total_time_simulated
    total_mana_spent: float             # 总法力消耗
    mana_usage_per_second: float        # 每秒法力消耗

    # 伤害质量
    avg_damage_per_hit: float           # 单发期望伤害
    hit_rate: float                     # 平均命中率
    crit_ratio: float                   # 暴击伤害占比（0.0–1.0）

    # 调试信息
    total_rounds: int                   # 完整发射轮数
    avg_round_time: float               # 平均每轮耗时（秒）
    firing_uptime: float                # 有效发射时间占比
    avg_projectiles_per_second: float   # 每秒发射数

    # 安全 & 溯源
    self_damage_risk: float             # 自伤风险（0.0–1.0）
    spell_sequence: list[str]           # 输入序列


# ── 单发结果 ──────────────────────────────────────────────

@dataclass
class _FireResult:
    damage: float           # 实际伤害
    mana_consumed: bool     # 法力是否扣除成功
    mana_drained: int       # 扣除的法力值
    hit_chance: float       # 命中率
    crit_damage: float      # 暴击贡献的伤害


# ── 辅助函数 ──────────────────────────────────────────────

def _calc_hit_chance(
    distance: float, spread: float, explosion_radius: float, target_moving: bool,
) -> float:
    """估算命中率。explosion_radius 扩大有效命中范围（AoE 覆盖）。"""
    if spread < 0:
        spread = 0
    spread_rad = math.radians(spread)
    spread_width = 2 * distance * math.tan(spread_rad)
    hitbox_width = 20.0 + 2 * explosion_radius
    chance = min(1.0, hitbox_width / max(spread_width, 1.0))
    if target_moving:
        chance *= 0.7
    return chance


def _fire(
    wand: WandState,
    spell: Spell,
    mods: ModifierStack,
    target: TargetInfo,
    use_random: bool,
) -> _FireResult:
    """发射一个法术，返回详细的单发结果。"""
    mana_drain = spell.mana_drain + mods.mana_mod
    mana_taken = max(0, mana_drain)

    if not wand.consume_mana(mana_taken):
        return _FireResult(
            damage=0.0, mana_consumed=False, mana_drained=0,
            hit_chance=0.0, crit_damage=0.0,
        )

    base_damage = (
        spell.projectile + spell.explosion + spell.slice
        + mods.projectile_mod
    )
    total_crit = spell.critical_chance + mods.crit_mod
    crit_chance = total_crit / 100.0

    total_spread = (
        wand.stats.spread + spell.spread
        + spell.spread_mod + mods.spread_mod
    )
    hit_chance = _calc_hit_chance(
        target.distance_px, total_spread,
        spell.explosion_radius, target.is_moving,
    )

    if use_random:
        import random
        if random.random() >= hit_chance:
            return _FireResult(
                damage=0.0, mana_consumed=True, mana_drained=mana_taken,
                hit_chance=hit_chance, crit_damage=0.0,
            )
        if random.random() < crit_chance:
            return _FireResult(
                damage=base_damage * 5.0, mana_consumed=True,
                mana_drained=mana_taken, hit_chance=hit_chance,
                crit_damage=base_damage * 4.0,  # 5x - 1x
            )
        return _FireResult(
            damage=base_damage, mana_consumed=True,
            mana_drained=mana_taken, hit_chance=hit_chance, crit_damage=0.0,
        )

    # 确定性模式：期望值
    expected_crit_mult = 1.0 + 4.0 * crit_chance
    final_damage = base_damage * hit_chance * expected_crit_mult
    crit_damage = base_damage * hit_chance * 4.0 * crit_chance
    return _FireResult(
        damage=final_damage, mana_consumed=True,
        mana_drained=mana_taken, hit_chance=hit_chance,
        crit_damage=crit_damage,
    )


def _estimate_self_damage(sequence: list[str]) -> float:
    """自伤风险（0.0–1.0）。"""
    risk_map: dict[str, float] = {}
    return max((risk_map.get(sid, 0.0) for sid in sequence), default=0.0)


# ── 主函数 ────────────────────────────────────────────────

def simulate(
    spell_sequence: list[str],
    wand_stats: WandStats,
    target: TargetInfo = TargetInfo(),
    simulate_duration: float = 10.0,
    use_random: bool = False,
) -> SimResult:
    """
    模拟魔杖持续发射 spell_sequence。

    Args:
        spell_sequence: spell key 列表
        wand_stats: 魔杖静态属性
        target: 目标参数
        simulate_duration: 模拟多少秒
        use_random: True = 真随机；False = 期望值

    Returns:
        SimResult: 详细的模拟结果
    """
    if not spell_sequence:
        return SimResult(
            dps=0.0, total_damage=0.0, total_projectiles=0,
            total_time_simulated=0.0,
            mana_exhaustion_time=0.0, total_mana_spent=0.0,
            mana_usage_per_second=0.0,
            avg_damage_per_hit=0.0, hit_rate=0.0, crit_ratio=0.0,
            total_rounds=0, avg_round_time=0.0, firing_uptime=1.0,
            avg_projectiles_per_second=0.0,
            self_damage_risk=0.0, spell_sequence=[],
        )

    wand = WandState(stats=wand_stats)
    mods = ModifierStack()

    total_damage = 0.0
    total_crit_damage = 0.0
    total_projectiles = 0
    total_time = 0.0
    total_mana_spent = 0.0
    total_hit_chance = 0.0
    recharge_mod = 0.0
    total_rounds = 0
    mana_exhaustion_time = -1.0
    firing_time = 0.0
    idx = 0
    multicast_stack: list[int] = []  # 每个元素 = 该层多重还需要几个投射物

    while total_time < simulate_duration:
        # ── 序列到底 → 充能（弃牌堆洗回牌库）──
        if idx >= len(spell_sequence):
            effective_recharge = max(0, wand.stats.recharge_time + recharge_mod)
            total_time += effective_recharge
            wand.regen_mana(effective_recharge)
            recharge_mod = 0.0
            total_rounds += 1
            idx = 0
            # 不 clear mods 和 stack：修正/多重跨轮持续生效

        spell = SPELLS.get(spell_sequence[idx])
        if spell is None:
            idx += 1
            continue

        # ── 多重施法 ──
        if spell.type == SpellType.MULTICAST:
            if multicast_stack:
                # 嵌套：本多重作为父多重的一个"投射物"
                multicast_stack[-1] -= 1
                while multicast_stack and multicast_stack[-1] <= 0:
                    multicast_stack.pop()
            multicast_stack.append(spell.multicast_count)
            idx += 1
            continue

        # ── 投射修正（不消耗多重配额）──
        if spell.type == SpellType.MODIFIER:
            mods.apply(spell)
            idx += 1
            continue

        # ── 投射物 / 实用 ──
        if spell.type in (SpellType.PROJECTILE, SpellType.UTILITY):
            fr = _fire(wand, spell, mods, target, use_random)
            if fr.mana_consumed:
                total_damage += fr.damage
                total_crit_damage += fr.crit_damage
                total_projectiles += 1
                total_mana_spent += fr.mana_drained
                total_hit_chance += fr.hit_chance
                recharge_mod += spell.recharge_time_mod + mods.recharge_time_mod
            elif mana_exhaustion_time < 0:
                mana_exhaustion_time = total_time

            # 消耗一重配额
            if multicast_stack:
                multicast_stack[-1] -= 1
                while multicast_stack and multicast_stack[-1] <= 0:
                    multicast_stack.pop()

            if not multicast_stack:
                # 多重组结束 → 结算延迟 + 清修正
                delay = wand.stats.cast_delay + spell.cast_delay
                total_time += max(delay, 0.0167)
                firing_time += max(delay, 0.0167)
                mods.clear()
            # 组内不结算延迟（投射物共享同一个 cast_delay）

            idx += 1
            if idx >= len(spell_sequence) and not multicast_stack:
                effective_recharge = max(0, wand.stats.recharge_time + recharge_mod)
                total_time += effective_recharge
                wand.regen_mana(effective_recharge)
                recharge_mod = 0.0
                total_rounds += 1
                idx = 0
            continue

        idx += 1

    # ── 汇总 ──
    if total_time == 0:
        return SimResult(
            dps=0.0, total_damage=0.0, total_projectiles=0,
            total_time_simulated=0.0,
            mana_exhaustion_time=0.0, total_mana_spent=0.0,
            mana_usage_per_second=0.0,
            avg_damage_per_hit=0.0, hit_rate=0.0, crit_ratio=0.0,
            total_rounds=0, avg_round_time=0.0, firing_uptime=1.0,
            avg_projectiles_per_second=0.0,
            self_damage_risk=0.0, spell_sequence=spell_sequence,
        )

    dps = total_damage / total_time
    mana_usage = total_mana_spent / total_time

    if mana_exhaustion_time < 0:
        mana_exhaustion_time = total_time

    avg_damage_per_hit = total_damage / total_projectiles if total_projectiles else 0.0
    hit_rate = total_hit_chance / total_projectiles if total_projectiles else 0.0
    crit_ratio = total_crit_damage / total_damage if total_damage else 0.0
    avg_round_time = total_time / total_rounds if total_rounds else 0.0
    firing_uptime = firing_time / total_time if total_time else 0.0

    return SimResult(
        dps=dps,
        total_damage=total_damage,
        total_projectiles=total_projectiles,
        total_time_simulated=total_time,
        mana_exhaustion_time=mana_exhaustion_time,
        total_mana_spent=total_mana_spent,
        mana_usage_per_second=mana_usage,
        avg_damage_per_hit=avg_damage_per_hit,
        hit_rate=hit_rate,
        crit_ratio=crit_ratio,
        total_rounds=total_rounds,
        avg_round_time=avg_round_time,
        firing_uptime=firing_uptime,
        avg_projectiles_per_second=total_projectiles / total_time,
        self_damage_risk=_estimate_self_damage(spell_sequence),
        spell_sequence=spell_sequence,
    )
