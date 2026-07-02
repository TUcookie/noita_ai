from .spell import Spell, SpellType
'''
法术数据来源：
1.中文wiki:https://noita.wiki.gg/zh/wiki/%E6%B3%95%E6%9C%AF
2.英文wiki:https://noita.wiki.gg/wiki/Spells
'''

SPELLS : dict[str, Spell] = {
    # 投射物(4/122)
    "spark_bolt": Spell(
        id="LIGHT_BULLET",
        name_zh="火花弹",
        type=SpellType.PROJECTILE,
        mana_drain=5,
        cast_delay=0.05,
        spread_mod=-1.0,
        critical_chance=5,
        projectile=3.0,
        explosion_radius=2,
        lifetime_min=33,
        lifetime_max=47,
        initial_speed=800,
    ),
    "magic_arrow": Spell(
        id="BULLET",
        name_zh="魔法箭",
        type=SpellType.PROJECTILE,
        mana_drain=20,
        cast_delay=0.07,
        spread_mod=2.0,
        critical_chance=5,
        projectile=10.0,
        explosion_radius=2,
        lifetime_min=33,
        lifetime_max=47,
        initial_speed=625,
        spread=0.6,
    ),
    "energy_orb": Spell(
        id="SLOW_BULLET",
        name_zh="能量球",
        type=SpellType.PROJECTILE,
        mana_drain=30,
        cast_delay=0.10,
        spread_mod=4.0,
        projectile=11.25,
        explosion=4.5,
        explosion_radius=15,
        lifetime_min=50,
        lifetime_max=50,
        initial_speed=210,
        spread=1.7,
    ),
    "bouncing_burst": Spell(
        id="RUBBER_BALL",
        name_zh="弹跳爆发",
        type=SpellType.PROJECTILE,
        mana_drain=5,
        cast_delay=-0.03,
        spread_mod=-1.0,
        projectile=3.0,
        lifetime_min=750,
        lifetime_max=750,
        initial_speed=700,
        spread=0.6,
    ),
    # 静态投射物(0/45)
    # 投射修正(0/143)
    # 多重释放(2/14)
    "double_spell": Spell(
        id="BURST_2",
        name_zh="二重施法",
        type=SpellType.MULTICAST,
        mana_drain=0,
        multicast_count=2,
    ),
    "triple_spell": Spell(
        id="BURST_3",
        name_zh="三重施法",
        type=SpellType.MULTICAST,
        mana_drain=2,
        multicast_count=3,
    ),
    # 材料(0/26)
    # 其他(0/42)
    # 实用(0/25)
    # 被动(0/5)
}