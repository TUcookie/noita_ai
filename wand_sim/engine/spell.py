"""法术数据模型。"""
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
    mana_drain: int # 法力消耗
    cast_delay: float = 0.0 # 施放延迟（秒）
    recharge_time_mod: float = 0.0 # 充能时间修正（秒）
    critical_chance: float = 0.0 # 暴击率（%）
    projectile: float = 0.0 # 投射物伤害
    spread: float = 0.0 # 散射角度（°）
    explosion: float = 0.0 # 爆炸伤害
    slice: float = 0.0 # 切割伤害
    explosion_radius: float = 0.0  # 爆炸半径(像素)
    lifetime_min: int = 0 # 存在时间下限（帧）
    lifetime_max: int = 0 # 存在时间上限（帧）
    initial_speed: float = 0.0 # 初始速度（像素/秒）

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

    # === 特殊效果 ===
    special_effects: list[str] = field(default_factory=list)