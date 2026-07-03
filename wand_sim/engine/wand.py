"""魔杖数据模型。
- WandTemplate: 范围值
- WandStats:   单值
"""

import random
from dataclasses import dataclass, field

@dataclass(frozen=True)
class FloatRange:
    min: float
    max: float

    def sample(self, rng: random.Random | None = None) -> float:
        if self.min == self.max:
            return self.min
        r = rng or random
        return r.uniform(self.min, self.max)


@dataclass(frozen=True)
class IntRange:
    min: int
    max: int

    def sample(self, rng: random.Random | None = None) -> int:
        if self.min == self.max:
            return self.min
        r = rng or random
        return r.randint(self.min, self.max)

@dataclass
class WandTemplate:
    shuffle: bool = False
    cast_delay: FloatRange = field(default_factory=lambda: FloatRange(0.15, 0.25))
    recharge_time: FloatRange = field(default_factory=lambda: FloatRange(0.33, 0.47))
    mana_max: FloatRange = field(default_factory=lambda: FloatRange(80, 80))
    mana_charge_speed: FloatRange = field(default_factory=lambda: FloatRange(25, 40))
    capacity: IntRange = field(default_factory=lambda: IntRange(2, 3))
    spread: FloatRange = field(default_factory=lambda: FloatRange(0.0, 0.0))
    speed: FloatRange = field(default_factory=lambda: FloatRange(1.0, 1.0))
    always_cast: list[str] = field(default_factory=list)

    def sample(self, rng: random.Random | None = None) -> "WandStats":
        return WandStats(
            shuffle=self.shuffle,
            cast_delay=self.cast_delay.sample(rng),
            recharge_time=self.recharge_time.sample(rng),
            mana_max=self.mana_max.sample(rng),
            mana_charge_speed=self.mana_charge_speed.sample(rng),
            capacity=self.capacity.sample(rng),
            spread=self.spread.sample(rng),
        )

@dataclass
class WandStats:
    shuffle: bool = False          # 是否乱序
    cast_delay: float = 0.15       # 施放延迟（秒）
    recharge_time: float = 0.30    # 充能延迟（秒）
    mana_max: float = 80.0         # 法力上限
    mana_charge_speed: float = 25.0  # 法力回复/秒
    capacity: int = 3              # 最大 spell 槽位
    spread: float = 0.0            # 散射角度（°）

@dataclass
class WandState:
    stats: WandStats
    current_mana: float = 0.0

    def __post_init__(self):
        if self.current_mana == 0.0:
            self.current_mana = self.stats.mana_max

    def consume_mana(self, amount : float) -> bool:
        '''消耗法力，返回是否成功'''
        if self.current_mana >= amount:
            self.current_mana -= amount
            return True
        return False
    
    def regen_mana(self, dt : float):
        '''回复法力'''
        self.current_mana = min(
            self.current_mana + self.stats.mana_charge_speed * dt,
            self.stats.mana_max
        )
