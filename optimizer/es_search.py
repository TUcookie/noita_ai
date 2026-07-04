'''
遗传算法 -> 最优 spell 序列
'''

import random
from copy import copy, deepcopy
from dataclasses import dataclass

from wand_sim.engine.wand import WandStats
from wand_sim.engine.simulator import TargetInfo
from wand_sim.engine.spells_db import BUILDABLE_IDS
from optimizer.fitness import fitness

@dataclass
class Candidate:
    '''种群中的个体'''
    sequence: list[str]
    fitness: float = 0.0

def _random_spell() -> str:
    '''随机一个 spell'''
    return random.choice(BUILDABLE_IDS)

def random_sequence(max_len: int) -> list[str]:
    '''生成长度为 1 ~ max_len - 1 的随机 spell 序列'''
    len = random.randint(1, max_len)
    return [_random_spell() for _ in range(len)]

def _mutate_insert(seq: list[str], max_len: int) -> list[str]:
    '''在 0 ~ max_len - 1 位置上随机插入一个 spell'''
    if len(seq) >= max_len:
        return seq
    new_seq = copy(seq)
    new_seq.insert(random.randint(0, len(seq)), _random_spell())
    return new_seq

def _mutate_delete(seq: list[str]) -> list[str]:
    '''在 0 ~ max_len - 1 位置上随机删除一个 spell'''
    if len(seq) <= 1:
        return seq
    new_seq = copy(seq)
    del new_seq[random.randint(0, len(new_seq)) - 1]
    return new_seq

def _mutate_replace(seq: list[str]) -> list[str]:
    '''在 0 ~ max_len - 1 位置上随机替换一个 spell'''
    new_seq = copy(seq)
    new_seq[random.randint(0, len(new_seq) - 1)] = _random_spell()
    return new_seq

def mutate(seq: list[str], max_len: int) -> list[str]:
    '''随机变异'''
    r = random.random()
    if r < 0.35:
        return _mutate_insert(seq, max_len)
    elif r < 0.65:
        return _mutate_delete(seq)
    else:
        return _mutate_replace(seq)
    
def _crossover(a: list[str], b: list[str], max_len: int) -> list[str]:
    '''单点交叉: A 前半 + B 后半'''
    if len(a) < 2 or len(b) < 2:
        return copy(a)
    cut_a = random.randint(1, len(a) - 1)
    cut_b = random.randint(1, len(b) - 1)
    child = a[:cut_a] + b[cut_b:]
    return child[:max_len]

def _select(pop: list[Candidate], k: int = 3) -> Candidate:
    '''从种群中随机选 k 个， 返回 fitness 最高的'''
    pool = random.sample(
        pop, min(k, len(pop))
    )
    return max(pool, key=lambda c: c.fitness)

# === 主循环 ===
def run_es(
        wand: WandStats,
        target: TargetInfo = TargetInfo(),
        pop_size: int = 100,
        elite_count: int = 20,
        generations: int = 50,
        max_seq_len: int = 8,
        k: int = 3,
        immigrant_ratio: float = 0.10,
        verbose: bool = True,
) -> list[Candidate]:
    """
    运行遗传算法

    Args:
        wand: 魔杖属性
        target: 目标参数
        pop_size: 种群大小
        elite_count: 精英数量
        generations: 迭代代数
        max_seq_len: 序列最大长度
        k: 锦标赛每次抽几个
        immigrant_ratio: 每代随机移民比例
        verbose: 是否打印每代信息

    Returns:
        history: 每代最优个体列表
    """

    pop = [
        Candidate(sequence=random_sequence(max_seq_len))
        for _ in range(pop_size)
    ]
    history: list[Candidate] = []

    for gen in range(generations):
        # 评估
        for c in pop:
            c.fitness = fitness(c.sequence, wand, target)

        pop.sort(key=lambda c: c.fitness, reverse=True)
        best = pop[0]
        history.append(deepcopy(best))

        # 打印
        if verbose:
            seq_str = " -> ".join(best.sequence)
            print(
                f"Gen {gen+1:3d} | best: {best.fitness:8.1f} | {seq_str}"
            )

        # 锦标赛选择
        elites: list[Candidate] = []
        for _ in range(elite_count):
            elites.append(deepcopy(
                _select(pop, k),
            ))

        # 去重：重复精英用种群中未入选的个体替换
        seen: set[tuple] = set()
        deduped: list[Candidate] = []
        for c in elites:
            key = tuple(c.sequence)
            if key in seen:
                for alt in pop:
                    alt_key = tuple(alt.sequence)
                    if alt_key not in seen:
                        deduped.append(deepcopy(alt))
                        seen.add(alt_key)
                        break
            else:
                deduped.append(c)
                seen.add(key)
        elites = deduped

        new_pop = elites
        immigrant_count = int(pop_size * immigrant_ratio)
        for _ in range(immigrant_count):
            new_pop.append(
                Candidate(sequence=random_sequence(max_seq_len)),
            )

        while len(new_pop) < pop_size:
            r = random.random()
            if r < 0.40 and len(elites) >= 2:
                # 双亲遗传变异
                a = random.choice(elites)
                b = random.choice(elites)
                child_seq = _crossover(a.sequence, b.sequence, max_seq_len)
                child_seq = mutate(child_seq, max_seq_len)
            elif r < 0.85:
                # 单亲变异
                parent = random.choice(elites)
                child_seq = mutate(parent.sequence, max_seq_len)
            else:
                # 随机序列
                child_seq = random_sequence(max_seq_len)
            
            new_pop.append(Candidate(sequence=child_seq))
        pop = new_pop[:pop_size]
    return history