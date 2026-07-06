"""法术数据模型。"""
import math

from dataclasses import dataclass, field
from enum import Enum

class SpellType(Enum):
    PROJECTILE = "projectile"               # 投射物(122)
    STATIC_PROJECTILE = "static_projectile" # 静态投射物(45)
    MODIFIER = "modifier"                   # 投射修正(143)
    MULTICAST = "multicast"                 # 多重释放(14)
    MATERIAL = "material"                   # 材料(26)
    OTHER = "other"                         # 其他(42)
    UTILITY = "utility"                     # 实用(25)
    PASSIVE = "passive"                     # 被动(5)

@dataclass
class Spell:
    '''法术数据模型'''

    # === 基础属性 ===
    id: str
    name_zh: str
    type: SpellType
    uses: int = -1 # 可使用次数
    mana_drain: int = 0 # 法力消耗
    cast_delay: float = 0.0 # 施放延迟（秒）

    # === 修正 ===
    recharge_time_mod: float = 0.0 # 充能时间修正（秒）
    critical_chance: float = 0.0 # 暴击率（%）
    spread: float = 0.0 # 散射角度（°）
    recoil: int = 0 # 后坐力

    # === 投射物 ===
    explosion_radius: float = 0.0  # 爆炸半径(像素)

    # == 投射物-时间 ==
    lifetime_min: int = 0 # 存在时间（帧）
    lifetime_max: int = 0 
    damage_every: int = 0 # 伤害间隔（帧）
    timer_Lifetime: int = 0 # 定时时间（帧）
    can_hit_time: int = 0 # 命中后可再次射击时间（帧）
    

    # == 投射物-运动 ==
    initial_speed_min: int = 0 # 初始速度（像素/秒）
    initial_speed_max: int = 0
    dead_speed: int = 0 # 最低存在速度——低于阈值时消失
    bounces: int = 0 # 可弹跳次数
    motion_spread: float = 0 # 运动中的散射角度（°）
    gravity: int = 200 # 重力
    air_friction: float = 1.0 # 空气摩擦力
    mass: float = 0.10 # 重量

    # === 伤害 ===
    projectile: float = 0.0 # 投射物伤害
    explosion: float = 0.0 # 爆炸伤害
    slice: float = 0.0 # 切割伤害
    fire: float = 0.0 # 火焰伤害


    # === 额外属性 ===
    digging_strength: int = 0 # 挖掘强度
    digging_power: int = 0 # 挖掘力

    # === 触发 ===
    has_trigger: bool = False
    trigger_type: str | None = None
    trigger_capacity: int = 0   # 触发时取后续几个 spell

    # === 修正值 ===
    projectile_mod: float = 0.0     # 伤害增量
    speed_mod: float = 1.0     # 速度倍率
    spread_mod: float = 0.0    # 散射角度修正（°）
    crit_mod: float = 0.0      # 暴击率增量
    mana_mod: int = 0          # 法力消耗增量

    # === 多重施法 ===
    multicast_count: int = 0   # 一次取几个 spell
    draw_actions: int = 0      # modifier 额外抽取数

    # === 特殊效果 ===
    special_effects: list[str] = field(default_factory=list)

    # === 标签 ===
    tags: list[str] = field(default_factory=list)