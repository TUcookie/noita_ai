"""
Noita 魔杖模拟器。
按 spell 序列顺序模拟发射过程，计算 DPS 和法力可持续性。
"""

import math
import random
from dataclasses import dataclass, field

from .wand import WandState, WandStats
from .spell import Spell, SpellType
from .spells_db import SPELLS

DT: float = 1.0 / 60.0 #每帧时间

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
        self.speed_mod = max(0.0, min(20.0, self.speed_mod))  # 游戏上限 [0, 20]
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


@dataclass
class TargetInfo:
    """目标参数。"""
    distance_px: float = 300.0
    is_moving: bool = False


@dataclass
class SimResult:
    """模拟结果。"""
    dps: float                          # 每秒伤害
    total_damage: float                 # 总伤害
    total_projectiles: int              # 总发射数
    total_time_simulated: float         # 实际模拟时长

    mana_exhaustion_time: float         # 法力耗尽时刻（秒）
    total_mana_spent: float             # 总法力消耗
    mana_usage_per_second: float        # 每秒法力消耗

    avg_damage_per_hit: float           # 单发期望伤害
    hit_rate: float                     # 平均命中率
    crit_ratio: float                   # 暴击伤害占比

    total_rounds: int                   # 完整发射轮数
    avg_round_time: float               # 平均每轮耗时（秒）
    firing_uptime: float                # 有效发射时间占比
    avg_projectiles_per_second: float   # 每秒发射数

    self_damage_risk: float             # 自伤风险
    spell_sequence: list[str]           # 输入序列
    round_log: list = field(default_factory=list)  # trace 逐轮数据（已弃用）
    chain_log: list = field(default_factory=list)   # trace 逐链数据
    all_tarj: list[list[dict]] = field(default_factory=list) # 轨迹


@dataclass
class _FireResult:
    damage: float           # 实际伤害
    mana_consumed: bool     # 法力是否扣除成功
    mana_drained: int       # 扣除的法力值
    hit_chance: float       # 命中率
    crit_damage: float      # 暴击贡献的伤害

@dataclass
class SimWindow:
    '''战场模拟器'''
    width: float = 800.0
    height: float = 600.0
    wand_pos: tuple[float, float] = (50.0, 300.0)
    target_pos: tuple[float, float] = (350.0, 300.0)
    target_radius: float = 15.0
    # AABB 矩形: [(x, y, w, h), ...]  — 
    obstacles: list[tuple[float, float, float, float]] = field(
        default_factory=list,
    )

    @property
    def direction(self) -> tuple[float, float]:
        "wand -> target 的单位方向向量"
        dx = self.target_pos[0] - self.wand_pos[0]
        dy = self.target_pos[1] - self.wand_pos[1]
        len = (dx**2 + dy**2) ** 0.5
        return (dx / len, dy / len)


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
        spell.projectile + spell.explosion + spell.slice + spell.fire
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

    # === 对由物理效果产生的偏差进行修正 ===
    ## 1. 弹跳
    if spell.bounces > 0:
        hit_chance = min(1.0, hit_chance * (1 + spell.bounces * 0.5))

    ## 2.帧伤
    if spell.damage_every > 0:
        avg_lifetime = (spell.lifetime_min + spell.lifetime_max) // 2
        overlap_ticks = min(avg_lifetime // max(spell.damage_every, 1), 30)
        base_damage *= (1 + overlap_ticks)

    ## 3.穿透
    if "piercing" in spell.special_effects:
        hit_chance = min(1.0, hit_chance * 1.5)

    expected_crit_mult = 1.0 + 4.0 * crit_chance
    final_damage = base_damage * hit_chance * expected_crit_mult
    crit_damage = base_damage * hit_chance * 4.0 * crit_chance
    return _FireResult(
        damage=final_damage, mana_consumed=True,
        mana_drained=mana_taken, hit_chance=hit_chance,
        crit_damage=crit_damage,
    )


def _estimate_self_damage(sequence: list[str]) -> float:
    """自伤风险"""
    risk_map: dict[str, float] = {}
    return max((risk_map.get(sid, 0.0) for sid in sequence), default=0.0)

def _simulate_flight(
        spell: Spell,
        mods: "ModifierStack",
        total_spread: float,
        window: "SimWindow",
        use_random: bool,
) -> tuple[float, list[dict], int, bool, float]:
    '''
    逐帧模拟投射物飞行

    Args:
        spell: 发射的投射物法术
        mods: 当前累积的 modifier 效果
        total_spread: 总散射角（度）
        window: 战场窗口
        use_random: 是否用真随机

    Returns:
        total_damage: 实际造成伤害
        trajectory: 弹道轨迹
        
        frames_lived: 存活帧数
        hit_target: 是否命中目标
        crit_damage: 暴击贡献的伤害
    '''

    # === 发射阶段 ===
    dx, dy = window.direction
    if use_random:
        base_speed = random.randint(spell.initial_speed_min, spell.initial_speed_max)
    else:
        base_speed = (spell.initial_speed_min + spell.initial_speed_max) / 2
    speed = base_speed * mods.speed_mod

    if total_spread > 0 and use_random:
        half = math.radians(total_spread) / 2
        angle = random.uniform(-half, half)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        vx = (dx * cos_a - dy * sin_a) * speed
        vy = (dx * sin_a + dy * cos_a) * speed
    else:
        vx = dx * speed
        vy = dy * speed

    px, py = window.wand_pos
    bounces_left = spell.bounces
    has_piercing = "piercing" in spell.special_effects
    frames_lived = 0
    total_damage = 0.0
    crit_damage = 0.0
    trajectory: list[dict] = []
    if use_random:
        lifetime = random.randint(spell.lifetime_min, spell.lifetime_max)
    else:
        lifetime = (spell.lifetime_min + spell.lifetime_max) // 2
    hit_target = False

    # === 逐帧模拟阶段 ===
    while frames_lived < lifetime:
        frames_lived += 1

        # 重力
        vy += spell.gravity * DT

        # 空气摩擦
        air_friction = 1.0 - spell.air_friction * DT
        vx *= air_friction
        vy *= air_friction

        # 更新位置
        px += vx * DT
        py += vy * DT

        # 记录轨迹
        trajectory.append({
            "frame": frames_lived,
            "x": px, "y": py,
            "vx": vx, "vy": vy,
        })    

        # == 碰撞检测 ==
        ## 1.窗口边界反射
        bounced = False
        if px < 0 or px > window.width:
            vx = -vx
            bounced = True
        if py < 0 or py > window.height:
            vy = -vy
            bounced = True
        if bounced:
            bounces_left -= 1
            if bounces_left < 0:
                break

        ## 2.障碍物碰撞
        for (ox, oy, ow, oh) in window.obstacles:
            if ox <= px <= ox + ow and oy <= py <= oy + oh:
                # 忽略入射角的反弹
                vx = -vx
                vy = -vy
                bounces_left -= 1
                if bounces_left < 0:
                    break
                break

        ## 3.目标命中判定
        tx, ty = window.target_pos
        dx_t = px - tx
        dy_t = py - ty
        dist_to_target = (dx_t**2 + dy_t**2) ** 0.5
        if dist_to_target <= window.target_radius:
            base = (spell.projectile + spell.explosion + spell.slice
                    + spell.fire + mods.projectile_mod)
            if not hit_target:
                # 暴击判定
                total_crit = spell.critical_chance + mods.crit_mod
                if use_random and random.random() < total_crit / 100.0:
                    total_damage += base * 5.0
                    crit_damage += base * 4.0
                else:
                    total_damage += base
                hit_target = True

            # 帧伤
            if spell.damage_every > 0 and frames_lived % spell.damage_every == 0:
                total_damage += base

            # 无穿透则命中后消失
            if not has_piercing:
                break

        ## 4.超时或出界太远
        if px < -500 or px > window.width + 500 or py < -500 or py >window.height + 500:
            break

    return total_damage, trajectory, frames_lived, hit_target, crit_damage

def simulate(
    spell_sequence: list[str],
    wand_stats: WandStats,
    target: TargetInfo = TargetInfo(),
    simulate_duration: float = 10.0,
    use_random: bool = False,
    trace: bool = False,
    window: SimWindow | None = None,
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
            round_log=[],
            chain_log=[],
            all_tarj=[[]],
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
    batch_slots: int = 0
    _cast_delay_sum: float = 0.0
    chain_log: list[dict] = []
    all_tarj: list[list[dict]] = []
    # trace 链级追踪
    _chain_idx: int = 0
    _chain_proj: int = 0
    _chain_dmg: float = 0.0
    _chain_hits: int = 0

    while total_time < simulate_duration:
        if idx >= len(spell_sequence):
            # 充能前结算未完成的批次（如 modifiers 的 draw_actions 未消耗完）
            if batch_slots > 0:
                delay = wand.stats.cast_delay + _cast_delay_sum
                total_time += max(delay, DT)
                firing_time += max(delay, DT)

            _mod_before_clear = recharge_mod
            effective_recharge = max(DT, wand.stats.recharge_time + recharge_mod)
            total_time += effective_recharge
            wand.regen_mana(effective_recharge)
            recharge_mod = 0.0
            total_rounds += 1
            mods.clear()
            batch_slots = 0
            _cast_delay_sum = 0.0
            _chain_idx = 0
            if trace:
                chain_log.append({
                    "round": total_rounds,
                    "time": total_time,
                    "type": "recharge",
                    "duration": effective_recharge,
                    "recharge_mod": _mod_before_clear,
                    "mana_pct": wand.current_mana / wand.stats.mana_max,
                })
            idx = 0

        # 统一抽牌模型：魔杖每轮抽 1 张，每张牌消耗 1 抽
        if batch_slots == 0:
            batch_slots = 1
        batch_slots -= 1

        spell = SPELLS.get(spell_sequence[idx])
        if spell is None:
            idx += 1
            continue

        # === 多重释放 ===
        if spell.type == SpellType.MULTICAST:
            batch_slots += spell.multicast_count
            idx += 1
            continue

        if spell.type == SpellType.MODIFIER:
            mods.apply(spell)
            _cast_delay_sum += spell.cast_delay
            batch_slots += spell.draw_actions
            idx += 1
            continue

        # === 投射物 & 实用 ===
        if spell.type in (SpellType.PROJECTILE, SpellType.UTILITY):
            fired_ok = False
            if use_random and window is not None:
                total_spread = (
                    wand.stats.spread + spell.spread
                    + spell.spread_mod + mods.spread_mod
                )
                dmg, traj, frames, hit, crit_dmg = _simulate_flight(
                    spell, mods, total_spread, window, use_random,
                )
                fired_ok = True
                total_damage += dmg
                total_crit_damage += crit_dmg
                total_projectiles += 1
                total_mana_spent += max(0, spell.mana_drain + mods.mana_mod)
                total_hit_chance += (1.0 if hit else 0.0)
                all_tarj.append(traj)
            else:
                fr = _fire(wand, spell, mods, target, use_random)
                dmg = fr.damage
                if fr.mana_consumed:
                    total_damage += fr.damage
                    total_crit_damage += fr.crit_damage
                    total_projectiles += 1
                    total_mana_spent += fr.mana_drained
                    total_hit_chance += fr.hit_chance
                    fired_ok = True
                elif mana_exhaustion_time < 0:
                    mana_exhaustion_time = total_time

            if fired_ok:
                recharge_mod += spell.recharge_time_mod + mods.recharge_time_mod
                _chain_proj += 1
                _chain_dmg += dmg
                if use_random and window is not None:
                    if hit:
                        _chain_hits += 1
                else:
                    if fr.hit_chance > 0:
                        _chain_hits += 1

            _cast_delay_sum += spell.cast_delay

            if batch_slots == 0:
                delay = wand.stats.cast_delay + _cast_delay_sum
                total_time += max(delay, DT)
                firing_time += max(delay, DT)
                # 链级 trace: 每链 snapshot
                if trace and _chain_proj > 0:
                    chain_log.append({
                        "round": total_rounds,
                        "chain": _chain_idx,
                        "time": total_time,
                        "type": "chain",
                        "proj": _chain_proj,
                        "dmg": _chain_dmg,
                        "dmg_per_hit": _chain_dmg / _chain_proj,
                        "hit_rate": _chain_hits / _chain_proj,
                        "cast_delay": delay,
                        "mana_pct": wand.current_mana / wand.stats.mana_max,
                    })
                    _chain_idx += 1
                    _chain_proj = 0
                    _chain_dmg = 0.0
                    _chain_hits = 0
                mods.clear()
                _cast_delay_sum = 0.0

            idx += 1
            continue

        idx += 1

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
            round_log=[],
            chain_log=[],
            all_tarj=[[]]
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
        round_log=chain_log,
        chain_log=chain_log,
        all_tarj=all_tarj,
    )
