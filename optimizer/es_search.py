'''
遗传算法 -> 最优 spell 序列
'''

import random
from collections import Counter
from copy import copy, deepcopy
from dataclasses import dataclass

from wand_sim.engine.wand import WandStats
from wand_sim.engine.simulator import TargetInfo
from wand_sim.engine.spells_db import BUILDABLE_IDS
from optimizer.fitness import fitness

SpellInventory = dict[str, int] # 法术库存


@dataclass
class Candidate:
    '''种群中的个体'''
    sequence: list[str]
    fitness: float = 0.0


def _normalize_inventory(spell_inventory: SpellInventory | None) -> SpellInventory | None:
    '''法术库存标准化与校验'''
    if spell_inventory is None:
        return None # 无限法术

    normalized: SpellInventory = {}
    for spell_id, count in spell_inventory.items():
        if spell_id not in BUILDABLE_IDS:
            raise ValueError(f'未知法术: {spell_id}')
        if count < 0:
            raise ValueError(f'法术数量不能为负: {spell_id}={count}')
        if count > 0:
            normalized[spell_id] = int(count)
    return normalized


def _sequence_counts(seq: list[str]) -> Counter[str]:
    return Counter(seq)


def _remaining_inventory(
    spell_inventory: SpellInventory | None,
    seq: list[str],
) -> SpellInventory | None:
    '''检索当前可用法术'''
    if spell_inventory is None:
        return None

    remaining = dict(spell_inventory)
    for spell_id, used in _sequence_counts(seq).items():
        remaining[spell_id] = remaining.get(spell_id, 0) - used
    return remaining


def _random_spell(
    spell_inventory: SpellInventory | None = None,
    *,
    seq: list[str] | None = None,
) -> str | None:
    '''随机一个 spell'''
    if spell_inventory is None:
        return random.choice(BUILDABLE_IDS)

    remaining = _remaining_inventory(spell_inventory, seq or [])
    choices = [spell_id for spell_id, count in remaining.items() if count > 0]
    if not choices:
        return None
    return random.choice(choices)


def _repair_sequence(
    seq: list[str],
    max_len: int,
    spell_inventory: SpellInventory | None = None,
) -> list[str]:
    '''把序列裁剪到 max_len 并删除超库存的法术'''
    seq = copy(seq[:max_len])
    if not seq:
        return seq

    if spell_inventory is None:
        return seq

    repaired: list[str] = []
    used: Counter[str] = Counter()
    for spell_id in seq:
        limit = spell_inventory.get(spell_id, 0)
        if used[spell_id] < limit:
            repaired.append(spell_id)
            used[spell_id] += 1
    return repaired


def random_sequence(
    max_len: int,
    spell_inventory: SpellInventory | None = None,
) -> list[str]:
    '''生成长度在 1 ~ max_len 的随机 spell 序列'''
    if max_len <= 0:
        return []

    if spell_inventory is None:
        seq_len = random.randint(1, max_len)
        return [_random_spell() for _ in range(seq_len)]

    available = [
        spell_id
        for spell_id, count in spell_inventory.items()
        for _ in range(count)
    ]
    if not available:
        return []

    seq_len = random.randint(1, min(max_len, len(available)))
    return random.sample(available, k=seq_len)


def _mutate_insert(
    seq: list[str],
    max_len: int,
    spell_inventory: SpellInventory | None = None,
) -> list[str]:
    '''在随机位置插入一个 spell'''
    if len(seq) >= max_len:
        return seq

    spell_id = _random_spell(spell_inventory, seq=seq)
    if spell_id is None:
        return seq

    new_seq = copy(seq)
    new_seq.insert(random.randint(0, len(seq)), spell_id)
    return new_seq


def _mutate_delete(seq: list[str]) -> list[str]:
    '''在随机位置删除一个 spell'''
    if len(seq) <= 1:
        return seq
    new_seq = copy(seq)
    del new_seq[random.randint(0, len(new_seq)) - 1]
    return new_seq


def _mutate_replace(
    seq: list[str],
    spell_inventory: SpellInventory | None = None,
) -> list[str]:
    '''在随机位置替换一个 spell'''
    if not seq:
        return seq

    new_seq = copy(seq)
    idx = random.randint(0, len(new_seq) - 1)
    current = new_seq.pop(idx)
    spell_id = _random_spell(spell_inventory, seq=new_seq)
    if spell_id is None:
        new_seq.insert(idx, current)
        return new_seq
    new_seq.insert(idx, spell_id)
    return new_seq


def mutate(
    seq: list[str],
    max_len: int,
    spell_inventory: SpellInventory | None = None,
) -> list[str]:
    '''随机变异'''
    r = random.random()
    if r < 0.35:
        mutated = _mutate_insert(seq, max_len, spell_inventory)
    elif r < 0.65:
        mutated = _mutate_delete(seq)
    else:
        mutated = _mutate_replace(seq, spell_inventory)
    return _repair_sequence(mutated, max_len, spell_inventory)


def _crossover(
    a: list[str],
    b: list[str],
    max_len: int,
    spell_inventory: SpellInventory | None = None,
) -> list[str]:
    '''单点交叉: A 前半 + B 后半'''
    if len(a) < 2 or len(b) < 2:
        return _repair_sequence(copy(a), max_len, spell_inventory)
    cut_a = random.randint(1, len(a) - 1)
    cut_b = random.randint(1, len(b) - 1)
    child = a[:cut_a] + b[cut_b:]
    return _repair_sequence(child, max_len, spell_inventory)


def _select(pop: list[Candidate], k: int = 3) -> Candidate:
    '''从种群中随机选 k 个， 返回 fitness 最高的'''
    pool = random.sample(pop, min(k, len(pop)))
    return max(pool, key=lambda c: c.fitness)


def _select_rank_weighted(pop: list[Candidate]) -> Candidate:
    '''排名加权随机选择'''
    weights = [1.0 / (i + 1) for i in range(len(pop))]
    return random.choices(pop, weights=weights, k=1)[0]


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
        spell_inventory: SpellInventory | None = None,
        verbose: bool = True,
        return_pop: bool = False,
):
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
        spell_inventory: 可用法术库存；不传则使用无限法术池
        verbose: 是否打印每代信息
        return_pop: 是否记录全部个体的 fitness 和完整序列

    Returns:
        history: 每代最优个体列表
    """

    spell_inventory = _normalize_inventory(spell_inventory)
    if spell_inventory is not None and not spell_inventory:
        raise ValueError('spell_inventory is empty after filtering zero-count spells')


    pop = [
        Candidate(sequence=random_sequence(max_seq_len, spell_inventory))
        for _ in range(pop_size)
    ]
    history: list[Candidate] = []
    all_fitness = []
    all_pop = []

    for gen in range(generations):
        # 评估
        for c in pop:
            c.fitness = fitness(c.sequence, wand, target)

        pop.sort(key=lambda c: c.fitness, reverse=True)
        best = pop[0]
        history.append(deepcopy(best))

        # 记录
        if return_pop:
            all_fitness.append([c.fitness for c in pop])
            all_pop.append(deepcopy(pop))

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
                Candidate(sequence=random_sequence(max_seq_len, spell_inventory)),
            )

        while len(new_pop) < pop_size:
            r = random.random()
            if r < 0.45 and len(elites) >= 2:
                # 双亲遗传变异
                a = _select_rank_weighted(pop)
                b = _select_rank_weighted(pop)
                child_seq = _crossover(
                    a.sequence, b.sequence, max_seq_len, spell_inventory,
                )
                child_seq = mutate(child_seq, max_seq_len, spell_inventory)
            elif r < 0.95:
                # 单亲变异
                parent = _select_rank_weighted(pop)
                child_seq = mutate(parent.sequence, max_seq_len, spell_inventory)
            else:
                # 随机序列
                child_seq = random_sequence(max_seq_len, spell_inventory)

            new_pop.append(Candidate(sequence=child_seq))
        pop = new_pop[:pop_size]
    if return_pop:
        return history, all_fitness, all_pop
    return history