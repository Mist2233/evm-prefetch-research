"""
指标收集与聚合。

每笔交易调用 record() 记录原始数据；
run 结束后调用 summary() 返回聚合指标字典。
"""

from __future__ import annotations

from dataclasses import dataclass

from simulation.cache_sim import TxResult


@dataclass
class RunSummary:
    prefetcher_name: str
    data_mode: str
    prefetch_timing: str
    t_hit_ns: float
    t_miss_us: float
    block_size: int

    n_blocks: int = 0
    n_tx: int = 0
    n_true_accesses: int = 0     # 含重复的原始访问次数
    n_true_unique: int = 0       # 每笔交易去重后 slot 数的总和
    n_predicted: int = 0         # 预测 slot 总数（per tx 去重后求和）
    n_would_be_miss: int = 0     # 若无预取，应产生的 first-touch miss 总数（块级）
    n_miss_prevented: int = 0    # 预取实际防止的 miss 总数

    total_cost_us: float = 0.0
    cache_hits_total: int = 0
    cache_misses_total: int = 0  # 实际剩余的 first-touch miss 次数
    prefetch_issued_total: int = 0
    prefetch_relevant_total: int = 0
    prefetch_timely_total: int = 0
    prefetch_late_total: int = 0
    prefetch_queue_wait_us_total: float = 0.0
    predict_overhead_us: float = 0.0
    e2e_elapsed_s: float = 0.0

    @property
    def recall(self) -> float:
        """预取覆盖率：防止了多少比例的块级 first-touch miss。"""
        return self.n_miss_prevented / self.n_would_be_miss if self.n_would_be_miss else 0.0

    @property
    def precision(self) -> float:
        """预测精度：预测的 slots 中有多少真正防止了 miss。"""
        return self.n_miss_prevented / self.n_predicted if self.n_predicted else 0.0

    @property
    def miss_rate(self) -> float:
        total = self.cache_hits_total + self.cache_misses_total
        return self.cache_misses_total / total if total else 0.0

    @property
    def avg_cost_per_tx_us(self) -> float:
        return self.total_cost_us / self.n_tx if self.n_tx else 0.0

    @property
    def avg_cost_per_access_us(self) -> float:
        return self.total_cost_us / self.n_true_accesses if self.n_true_accesses else 0.0

    @property
    def avg_predict_overhead_per_tx_us(self) -> float:
        return self.predict_overhead_us / self.n_tx if self.n_tx else 0.0

    def speedup_vs(self, baseline: "RunSummary") -> float:
        if self.total_cost_us <= 0:
            return float("inf")
        return baseline.total_cost_us / self.total_cost_us

    @property
    def e2e_cost_proxy_us(self) -> float:
        """
        端到端近似代价（用于净收益对比）：
        存储仿真代价 + 预测器真实开销。
        """
        return self.total_cost_us + self.predict_overhead_us

    def net_speedup_vs(self, baseline: "RunSummary") -> float:
        current = self.e2e_cost_proxy_us
        base = baseline.e2e_cost_proxy_us
        if current <= 0:
            return float("inf")
        return base / current

    @property
    def prefetch_timely_rate(self) -> float:
        return (
            self.prefetch_timely_total / self.prefetch_relevant_total
            if self.prefetch_relevant_total else 0.0
        )

    def as_dict(self) -> dict:
        return {
            "prefetcher": self.prefetcher_name,
            "data_mode": self.data_mode,
            "prefetch_timing": self.prefetch_timing,
            "t_hit_ns": self.t_hit_ns,
            "t_miss_us": self.t_miss_us,
            "block_size": self.block_size,
            "n_blocks": self.n_blocks,
            "n_tx": self.n_tx,
            "n_true_accesses": self.n_true_accesses,
            "n_would_be_miss": self.n_would_be_miss,
            "n_miss_prevented": self.n_miss_prevented,
            "n_predicted": self.n_predicted,
            "recall": round(self.recall, 6),
            "precision": round(self.precision, 6),
            "miss_rate": round(self.miss_rate, 6),
            "total_cost_us": round(self.total_cost_us, 4),
            "avg_cost_per_tx_us": round(self.avg_cost_per_tx_us, 4),
            "avg_cost_per_access_us": round(self.avg_cost_per_access_us, 6),
            "cache_hits": self.cache_hits_total,
            "cache_misses": self.cache_misses_total,
            "prefetch_issued_total": self.prefetch_issued_total,
            "prefetch_relevant_total": self.prefetch_relevant_total,
            "prefetch_timely_total": self.prefetch_timely_total,
            "prefetch_late_total": self.prefetch_late_total,
            "prefetch_timely_rate": round(self.prefetch_timely_rate, 6),
            "prefetch_queue_wait_us_total": round(self.prefetch_queue_wait_us_total, 4),
            "predict_overhead_us": round(self.predict_overhead_us, 4),
            "avg_predict_overhead_per_tx_us": round(self.avg_predict_overhead_per_tx_us, 4),
            "e2e_cost_proxy_us": round(self.e2e_cost_proxy_us, 4),
            "e2e_elapsed_s": round(self.e2e_elapsed_s, 6),
        }


class MetricLog:
    def __init__(
        self,
        prefetcher_name: str,
        data_mode: str,
        prefetch_timing: str,
        t_hit_ns: float,
        t_miss_us: float,
        block_size: int,
    ):
        self._summary = RunSummary(
            prefetcher_name=prefetcher_name,
            data_mode=data_mode,
            prefetch_timing=prefetch_timing,
            t_hit_ns=t_hit_ns,
            t_miss_us=t_miss_us,
            block_size=block_size,
        )

    def new_block(self) -> None:
        self._summary.n_blocks += 1

    def record(self, result: TxResult) -> None:
        s = self._summary
        s.n_tx += 1
        s.n_true_accesses += result.n_true_accesses
        s.n_true_unique += result.n_true_unique
        s.n_predicted += result.n_predicted
        s.n_would_be_miss += result.n_would_be_miss
        s.n_miss_prevented += result.n_miss_prevented
        s.total_cost_us += result.cost_us
        s.cache_hits_total += result.cache_hits
        s.cache_misses_total += result.cache_misses
        s.prefetch_issued_total += result.prefetch_issued
        s.prefetch_relevant_total += result.prefetch_relevant
        s.prefetch_timely_total += result.prefetch_timely
        s.prefetch_late_total += result.prefetch_late
        s.prefetch_queue_wait_us_total += result.prefetch_queue_wait_us

    def summary(self) -> RunSummary:
        return self._summary

    def add_predict_overhead_us(self, overhead_us: float) -> None:
        self._summary.predict_overhead_us += overhead_us

    def set_elapsed_s(self, elapsed_s: float) -> None:
        self._summary.e2e_elapsed_s = elapsed_s
