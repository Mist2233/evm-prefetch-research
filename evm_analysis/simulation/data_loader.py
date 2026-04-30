"""
数据加载器：支持两种块划分模式。

1) pseudo_block（默认）：
   按固定窗口大小 block_size 切分行，每个窗口对应一个“伪块”。

2) real_block：
   要求 JSONL 包含 block_number + transaction_index（字段名可配置），
   按真实块号分组、按块内交易序排序后迭代。

默认 block_size=293 来自统计：293744 条记录 / 1001 块 ≈ 293 条/块。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator


DEFAULT_BLOCK_SIZE = 293  # 全量记录数 / 区块数 取整


class DataLoader:
    def __init__(
        self,
        jsonl_path: str,
        block_size: int = DEFAULT_BLOCK_SIZE,
        max_blocks: int | None = None,
        max_txs: int | None = None,
        skip_empty_slots: bool = True,
        mode: str = "pseudo_block",
        block_number_field: str = "block_number",
        tx_index_field: str = "transaction_index",
    ):
        self.path = Path(jsonl_path)
        self.block_size = block_size
        self.max_blocks = max_blocks
        self.max_txs = max_txs
        self.skip_empty_slots = skip_empty_slots
        self.mode = mode
        self.block_number_field = block_number_field
        self.tx_index_field = tx_index_field
        self._total_rows: int | None = None
        self._total_blocks: int | None = None

    def iter_blocks(self) -> Iterator[list[dict]]:
        """
        按模式迭代块。
        - pseudo_block: 固定窗口切块
        - real_block: 按 block_number 分组 + transaction_index 排序
        """
        if self.mode == "pseudo_block":
            yield from self._iter_pseudo_blocks()
            return
        if self.mode == "real_block":
            yield from self._iter_real_blocks()
            return
        raise ValueError(f"未知模式: {self.mode!r}，可选 pseudo_block / real_block")

    def _iter_pseudo_blocks(self) -> Iterator[list[dict]]:
        block_txs: list[dict] = []
        block_idx = 0

        for row in self._raw_rows():
            block_txs.append(row)
            if len(block_txs) >= self.block_size:
                yield block_txs
                block_idx += 1
                block_txs = []
                if self.max_blocks is not None and block_idx >= self.max_blocks:
                    return

        # 最后一个不满块
        if block_txs and (self.max_blocks is None or block_idx < self.max_blocks):
            yield block_txs

    def _iter_real_blocks(self) -> Iterator[list[dict]]:
        """
        按真实块号分组并按 transaction_index 排序。
        假设输入总体上按 block_number 近似有序；若不是，建议上游预排序。
        """
        block_txs: list[dict] = []
        current_block = None
        block_idx = 0

        for row in self._raw_rows():
            if self.block_number_field not in row:
                raise KeyError(
                    f"real_block 模式缺少字段 {self.block_number_field!r}，"
                    "请补采 block_number 或切回 pseudo_block 模式。"
                )
            if self.tx_index_field not in row:
                raise KeyError(
                    f"real_block 模式缺少字段 {self.tx_index_field!r}，"
                    "请补采 transaction_index 或切回 pseudo_block 模式。"
                )

            block_no = self._normalize_numeric(row[self.block_number_field])
            if current_block is None:
                current_block = block_no

            if block_no != current_block:
                yield self._sort_block_txs(block_txs)
                block_idx += 1
                if self.max_blocks is not None and block_idx >= self.max_blocks:
                    return
                block_txs = [row]
                current_block = block_no
            else:
                block_txs.append(row)

        if block_txs and (self.max_blocks is None or block_idx < self.max_blocks):
            yield self._sort_block_txs(block_txs)

    def _sort_block_txs(self, block_txs: list[dict]) -> list[dict]:
        return sorted(
            block_txs,
            key=lambda r: self._normalize_numeric(r.get(self.tx_index_field)),
        )

    @staticmethod
    def _normalize_numeric(v):
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return s
            try:
                return int(s, 16) if s.startswith("0x") else int(s)
            except ValueError:
                return s
        return v

    def count_rows(self) -> int:
        """计算总有效行数（有 accessed_slots 的行），结果缓存。"""
        if self._total_rows is None:
            self._total_rows = sum(1 for _ in self._raw_rows())
        return self._total_rows

    def _raw_rows(self):
        tx_count = 0
        with self.path.open("r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if self.skip_empty_slots and not row.get("accessed_slots"):
                    continue
                yield row
                tx_count += 1
                if self.max_txs is not None and tx_count >= self.max_txs:
                    return

    def get_stats(self) -> dict:
        n = self.count_rows()
        n_blocks = (n + self.block_size - 1) // self.block_size if self.mode == "pseudo_block" else None
        return {
            "total_rows": n,
            "mode": self.mode,
            "block_size": self.block_size,
            "estimated_blocks": n_blocks,
            "max_txs": self.max_txs,
            "block_number_field": self.block_number_field,
            "tx_index_field": self.tx_index_field,
            "jsonl_path": str(self.path),
        }
