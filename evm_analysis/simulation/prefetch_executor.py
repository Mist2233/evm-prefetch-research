"""
异步预取执行器（工程层近似模型）。

目标：在不引入真实网络/数据库 I/O 的情况下，模拟“请求队列 + worker 并发”
对预取完成时间的影响，支撑并行预取有效性评估。
"""

from __future__ import annotations


class AsyncPrefetchExecutor:
    def __init__(
        self,
        service_time_us: float,
        concurrency: int = 1,
        queue_delay_us: float = 0.0,
    ):
        if concurrency <= 0:
            raise ValueError("concurrency 必须 > 0")
        if service_time_us < 0:
            raise ValueError("service_time_us 不能为负")
        if queue_delay_us < 0:
            raise ValueError("queue_delay_us 不能为负")

        self.service_time_us = float(service_time_us)
        self.concurrency = int(concurrency)
        self.queue_delay_us = float(queue_delay_us)
        self._worker_available_us = [0.0 for _ in range(self.concurrency)]

    def reset(self) -> None:
        self._worker_available_us = [0.0 for _ in range(self.concurrency)]

    def schedule(self, slots: set[str], issue_time_us: float) -> tuple[dict[str, float], float]:
        """
        为一批 slots 分配预取完成时间。

        返回:
        - finish_times: slot -> 完成时间(µs)
        - queue_wait_total_us: 本批请求累计队列等待时间
        """
        finish_times: dict[str, float] = {}
        queue_wait_total_us = 0.0
        ready_to_queue_at = issue_time_us + self.queue_delay_us

        # 排序仅用于复现实验时的确定性输出
        for slot in sorted(slots):
            worker_idx = min(
                range(self.concurrency),
                key=lambda i: self._worker_available_us[i],
            )
            start_at = max(ready_to_queue_at, self._worker_available_us[worker_idx])
            finish_at = start_at + self.service_time_us
            self._worker_available_us[worker_idx] = finish_at

            queue_wait_total_us += max(0.0, start_at - ready_to_queue_at)
            finish_times[slot] = finish_at

        return finish_times, queue_wait_total_us
