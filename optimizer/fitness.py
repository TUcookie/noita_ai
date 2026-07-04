'''
适应度函数
'''

import math
from wand_sim.engine.wand import WandStats
from wand_sim.engine.simulator import simulate, SimResult, TargetInfo

def fitness(
        sequence: list[str],
        wand: WandStats,
        target: TargetInfo = TargetInfo(),
) -> float:
    if not sequence:
        return 0.0
    
    result = simulate(sequence, wand, target, use_random=False)
    score = result.dps

    # 自伤风险
    if result.self_damage_risk > 0:
        score *= (1 - result.self_damage_risk)
    
    return score