"""
块内 first-touch 缓存仿真器。

语义对应 Erigon 的 intra_block_state：
  - 块内首次访问某 slot → t_miss（从 DB 加载到内存）
  - 块内重复访问同一 slot → t_hit（已在内存中）
  - 新块开始 → reset_block() 清空缓存

预取注入（prefetch）：在交易「执行」前调用，将预测 slots
标记为已就绪，后续访问即命中 t_hit。
"""

from __future__ import annotations

from dataclasses import dataclass

from simulation.prefetch_executor import AsyncPrefetchExecutor


@dataclass
class TxResult:
    n_true_unique: int       # 该笔交易去重后真实 slot 数（含已在块缓存中的）
    n_true_accesses: int     # 含重复的原始访问次数
    n_predicted: int         # 预测 slot 数（去重）
    n_would_be_miss: int     # 若无预取，本交易会产生的 first-touch miss 数
    n_miss_prevented: int    # 预取将其中多少 miss 转为了 hit
    cache_hits: int          # 访问时缓存命中次数（含块内重复 + 预取命中）
    cache_misses: int        # 访问时缓存缺失次数（块内真实 first-touch miss）
    cost_us: float           # 本次交易总仿真代价（µs）
    prefetch_issued: int = 0
    prefetch_relevant: int = 0
    prefetch_timely: int = 0
    prefetch_late: int = 0
    prefetch_queue_wait_us: float = 0.0
    tx_exec_us: float = 0.0


class CacheSim:
    def __init__(
        self,
        t_hit_ns: float = 30.0,
        t_miss_us: float = 3.0,
        prefetch_timing: str = "ideal",
        t_prefetch_us: float = 0.0,
        prefetch_concurrency: int = 1,
        queue_delay_us: float = 0.0,
        tx_exec_us_per_slot: float = 0.0,
        tx_exec_us_base: float = 0.0,
    ):
        self.t_hit_us = t_hit_ns / 1000.0
        self.t_miss_us = t_miss_us
        self.prefetch_timing = prefetch_timing
        self.t_prefetch_us = t_prefetch_us
        self.prefetch_concurrency = prefetch_concurrency
        self.queue_delay_us = queue_delay_us
        self.tx_exec_us_per_slot = tx_exec_us_per_slot
        self.tx_exec_us_base = tx_exec_us_base

        self._cache: set[str] = set()
        self._baseline_cache: set[str] = set()
        self._pending_prefetch: dict[str, float] = {}
        self._clock_us = 0.0

        if self.prefetch_timing not in ("ideal", "timed"):
            raise ValueError("prefetch_timing 仅支持 ideal 或 timed")
        self._executor = None
        if self.prefetch_timing == "timed":
            self._executor = AsyncPrefetchExecutor(
                service_time_us=self.t_prefetch_us,
                concurrency=self.prefetch_concurrency,
                queue_delay_us=self.queue_delay_us,
            )

    def reset_block(self) -> None:
        """块边界处调用，对应 intra_block_state 重置。"""
        self._cache.clear()
        self._baseline_cache.clear()
        self._pending_prefetch.clear()
        self._clock_us = 0.0
        if self._executor is not None:
            self._executor.reset()

    def _materialize_ready_prefetch(self, now_us: float) -> None:
        ready = [slot for slot, finish in self._pending_prefetch.items() if finish <= now_us]
        for slot in ready:
            self._cache.add(slot)
            del self._pending_prefetch[slot]

    def _issue_prefetch(self, predicted: set[str]) -> tuple[int, float]:
        if not predicted:
            return 0, 0.0

        if self.prefetch_timing == "ideal":
            self._cache.update(predicted)
            return len(predicted), 0.0

        assert self._executor is not None
        finish_times, queue_wait = self._executor.schedule(predicted, issue_time_us=self._clock_us)
        for slot, finish in finish_times.items():
            prev = self._pending_prefetch.get(slot)
            self._pending_prefetch[slot] = finish if prev is None else min(prev, finish)
        return len(predicted), queue_wait

    def process_tx(self, tx: dict, predicted_slots: list[str]) -> TxResult:
        """
        处理一笔交易：先注入预取，再顺序遍历 accessed_slots 计费。

        关键顺序：
          1. 计算「若无预取本次会 miss 的 slot 集合」（在注入前用旧缓存状态）
          2. 将 predicted_slots 注入缓存
          3. 遍历 accessed_slots，按当前缓存状态计 hit/miss
        """
        true_slots: list[str] = tx.get("accessed_slots", [])
        true_unique = set(true_slots)
        pred_set = set(predicted_slots)

        # 步骤 1：计算“无预取”基准 first-touch miss（独立基准缓存，避免被预取污染）
        would_be_miss = true_unique - self._baseline_cache
        prefetch_relevant = len(pred_set & would_be_miss)

        # 步骤 2：先收割此前已完成的异步预取，再发起本次预取
        self._materialize_ready_prefetch(self._clock_us)
        prefetch_issued, queue_wait_us = self._issue_prefetch(pred_set)

        # 步骤 3：模拟执行，按缓存状态计费
        first_seen: set[str] = set()
        hits, misses, cost = 0, 0, 0.0
        n_miss_prevented = 0
        prefetch_timely = 0
        prefetch_late = 0

        for slot in true_slots:
            self._materialize_ready_prefetch(self._clock_us)
            is_first = slot not in first_seen
            if is_first:
                first_seen.add(slot)

            if slot in self._cache:
                hits += 1
                access_cost = self.t_hit_us
                cost += access_cost
                if is_first and slot in would_be_miss:
                    n_miss_prevented += 1
                    if slot in pred_set:
                        prefetch_timely += 1
            else:
                misses += 1
                access_cost = self.t_miss_us
                cost += access_cost
                self._cache.add(slot)
                if is_first and slot in would_be_miss and slot in pred_set:
                    prefetch_late += 1

            self._clock_us += access_cost

        # 更新”无预取基准缓存”：只由真实访问驱动
        self._baseline_cache.update(true_unique)

        tx_exec_us = len(true_slots) * self.tx_exec_us_per_slot + self.tx_exec_us_base

        return TxResult(
            n_true_unique=len(true_unique),
            n_true_accesses=len(true_slots),
            n_predicted=len(pred_set),
            n_would_be_miss=len(would_be_miss),
            n_miss_prevented=n_miss_prevented,
            cache_hits=hits,
            cache_misses=misses,
            cost_us=cost,
            prefetch_issued=prefetch_issued,
            prefetch_relevant=prefetch_relevant,
            prefetch_timely=prefetch_timely,
            prefetch_late=prefetch_late,
            prefetch_queue_wait_us=queue_wait_us,
            tx_exec_us=tx_exec_us,
        )
