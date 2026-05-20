"""
离线增量管道：hybrid slow-path 离线补充 fast-path 规则。

管线：
  1. 按 block_number 切分 Window A/B
  2. Window A：识别 rule_miss 交易，用 hybrid 预测，累积正确 slot 计数
  3. 按 min_support / max_new_slots_per_key 过滤
  4. 合并 delta 到 fast_path_dict
  5. Window B：rule_base vs rule_plus_delta 仿真对比

用法：
  python -m simulation.run --offline-delta \
    --model models/evm_model_hybrid_v1.pkl \
    --delta-split-ratio 0.8 --delta-min-support 2
"""

from __future__ import annotations

import csv
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from simulation.prefetch_api import HybridPrefetcher, RuleBasePrefetcher, make_prefetcher
from simulation.run import run_simulation


def split_by_block(
    jsonl_path: str,
    split_ratio: float = 0.8,
    max_txs: int | None = None,
) -> tuple[list[dict], list[dict], dict]:
    """
    按 block_number 分组，前 split_ratio 的块归 Window A，其余归 Window B。

    Returns:
        (window_a_txs, window_b_txs, stats dict)
    """
    # 读取并按块分组
    blocks: dict[int, list[dict]] = {}
    tx_count = 0
    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not row.get("accessed_slots"):
                continue
            bn = _normalize_block_number(row.get("block_number"))
            if bn is None:
                continue
            blocks.setdefault(bn, []).append(row)
            tx_count += 1
            if max_txs is not None and tx_count >= max_txs:
                break

    sorted_blocks = sorted(blocks.items())
    split_idx = max(1, int(len(sorted_blocks) * split_ratio))

    window_a: list[dict] = []
    for _, txs in sorted_blocks[:split_idx]:
        window_a.extend(txs)

    window_b: list[dict] = []
    for _, txs in sorted_blocks[split_idx:]:
        window_b.extend(txs)

    stats = {
        "total_txs": tx_count,
        "total_blocks": len(sorted_blocks),
        "window_a_blocks": split_idx,
        "window_b_blocks": len(sorted_blocks) - split_idx,
        "window_a_txs": len(window_a),
        "window_b_txs": len(window_b),
        "split_ratio": split_ratio,
    }
    return window_a, window_b, stats


def generate_candidates(
    txs: list[dict],
    hybrid_prefetcher: HybridPrefetcher,
    fast_path_dict: dict,
    verbose: bool = True,
) -> dict[tuple, dict[str, int]]:
    """
    在 Window A 上为 rule_miss 交易生成候选增量。

    对每笔 (to, selector) 不在 fast_path_dict 中的交易：
      - 调用 hybrid 预测
      - 取 predicted ∩ accessed_slots
      - 按 (to, selector) 键累加各 slot 的正确次数

    Returns:
        {(to, selector): {slot: correct_count}}
    """
    # 分离 rule_hit 和 rule_miss
    rule_miss_indices: list[int] = []
    rule_miss_txs: list[dict] = []
    for idx, tx in enumerate(txs):
        key = (tx.get("to", ""), tx.get("selector", ""))
        if key not in fast_path_dict:
            rule_miss_indices.append(idx)
            rule_miss_txs.append(tx)

    if verbose:
        print(f"  Window A 总交易: {len(txs)}, rule_miss: {len(rule_miss_txs)} "
              f"({len(rule_miss_txs)/max(len(txs),1)*100:.1f}%)")

    if not rule_miss_txs:
        return {}

    # 逐批预测（复用 HybridPrefetcher.predict_batch 的批处理）
    candidates: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    batch_size = hybrid_prefetcher.slow_batch_size
    total = len(rule_miss_txs)

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_txs = rule_miss_txs[start:end]
        predictions = hybrid_prefetcher.predict_batch(batch_txs)

        for tx, preds in zip(batch_txs, predictions):
            key = (tx.get("to", ""), tx.get("selector", ""))
            true_set = set(tx.get("accessed_slots", []))
            correct = true_set.intersection(preds)
            for slot in correct:
                candidates[key][slot] += 1

        if verbose and (end % (batch_size * 10) == 0 or end == total):
            n_keys = len(candidates)
            print(f"    进度: {end}/{total} txs, 累计 {n_keys} 个候选键")

    if verbose:
        total_slots = sum(sum(s.values()) for s in candidates.values())
        print(f"  候选生成完成: {len(candidates)} 个键, {total_slots} 个 slot 实例")

    return dict(candidates)


def filter_candidates(
    candidates: dict[tuple, dict[str, int]],
    min_support: int = 2,
    max_new_slots_per_key: int | None = None,
) -> dict[tuple, list[str]]:
    """
    按 min_support 和 max_new_slots_per_key 过滤候选增量。

    Returns:
        {(to, selector): [slot, ...]}
    """
    filtered: dict[tuple, list[str]] = {}
    total_kept = 0
    total_discarded = 0

    for key, slot_counts in candidates.items():
        kept = [
            slot for slot, count in slot_counts.items()
            if count >= min_support
        ]
        # 按正确次数降序，优先保留高频 slot
        kept.sort(key=lambda s: slot_counts[s], reverse=True)
        if max_new_slots_per_key is not None:
            kept = kept[:max_new_slots_per_key]

        discarded = len(slot_counts) - len(kept)
        total_kept += len(kept)
        total_discarded += discarded

        if kept:
            filtered[key] = kept

    print(f"  过滤结果: min_support={min_support}, "
          f"max_new_slots_per_key={max_new_slots_per_key or '∞'} → "
          f"保留 {total_kept} slots ({len(filtered)} 键), "
          f"丢弃 {total_discarded} slots")

    return filtered


def merge_delta(
    fast_path_dict: dict[tuple, list[str]],
    delta: dict[tuple, list[str]],
) -> dict[tuple, list[str]]:
    """合并 delta 到 fast_path_dict，返回新 dict（不修改原 dict）。"""
    merged = {k: list(v) for k, v in fast_path_dict.items()}
    new_keys = 0
    new_slots = 0
    existing_added = 0

    for key, slots in delta.items():
        if key in merged:
            existing = set(merged[key])
            before = len(existing)
            existing.update(slots)
            after = len(existing)
            merged[key] = list(existing)
            existing_added += (after - before)
        else:
            merged[key] = list(set(slots))
            new_keys += 1
            new_slots += len(merged[key])

    print(f"  合并完成: 新增 {new_keys} 个键, {new_slots} slots; "
          f"已有键补充 {existing_added} slots; "
          f"dict {len(fast_path_dict)} → {len(merged)} 键")
    return merged


def compute_delta_stats(
    original: dict,
    augmented: dict,
    filtered_delta: dict,
) -> dict:
    """统计 delta 的关键指标。"""
    new_keys = [k for k in filtered_delta if k not in original]
    existing_keys = [k for k in filtered_delta if k in original]
    total_new_slots = sum(len(v) for k, v in filtered_delta.items() if k not in original)
    total_existing_new_slots = sum(len(v) for k, v in filtered_delta.items() if k in original)
    all_delta_slots = sum(len(v) for v in filtered_delta.values())

    return {
        "original_keys": len(original),
        "augmented_keys": len(augmented),
        "delta_keys_total": len(filtered_delta),
        "delta_keys_new": len(new_keys),
        "delta_keys_existing": len(existing_keys),
        "delta_slots_total": all_delta_slots,
        "delta_slots_new_keys": total_new_slots,
        "delta_slots_existing_keys": total_existing_new_slots,
        "avg_slots_per_new_key": round(total_new_slots / max(len(new_keys), 1), 2),
    }


def _normalize_block_number(v: Any) -> int | None:
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return int(s, 16) if s.startswith("0x") else int(s)
        except ValueError:
            return None
    return None


def _write_temp_jsonl(txs: list[dict]) -> str:
    """将交易列表写入临时 JSONL 文件，返回路径。"""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    )
    for tx in txs:
        tmp.write(json.dumps(tx, ensure_ascii=False) + "\n")
    tmp.close()
    return tmp.name


def run_offline_delta_pipeline(
    data_path: str,
    model_path: str,
    data_mode: str = "real_block",
    block_size: int = 293,
    max_txs: int | None = None,
    max_blocks: int | None = None,
    block_number_field: str = "block_number",
    tx_index_field: str = "transaction_index",
    t_hit_ns: float = 30.0,
    t_miss_us: float = 3.0,
    split_ratio: float = 0.8,
    min_support: int = 2,
    max_new_slots_per_key: int | None = None,
    output_dir: str = "figures/data",
    use_gpu: bool = False,
    gpu_device_id: int = 0,
    slow_batch_size: int = 1024,
    quiet: bool = False,
) -> None:
    """
    离线增量管道主流程。
    """
    verbose = not quiet
    print("\n" + "=" * 55)
    print("  离线增量管道 (Offline Delta Pipeline)")
    print("=" * 55)
    print(f"  split_ratio={split_ratio}  min_support={min_support}  "
          f"max_new_slots_per_key={max_new_slots_per_key or '∞'}")

    # 1. 加载模型
    if verbose:
        print("\n[1/5] 加载模型...")
    saved = __import__("joblib").load(model_path)
    fast_path_dict: dict = saved["fast_path_dict"]

    # 2. 切分 Window A / B
    if verbose:
        print("[2/5] 切分 Window A / B...")
    window_a, window_b, split_stats = split_by_block(
        data_path, split_ratio=split_ratio, max_txs=max_txs,
    )
    print(f"  Window A: {split_stats['window_a_blocks']} 块, "
          f"{split_stats['window_a_txs']} 笔交易")
    print(f"  Window B: {split_stats['window_b_blocks']} 块, "
          f"{split_stats['window_b_txs']} 笔交易")

    if not window_a or not window_b:
        print("  错误: Window A 或 B 为空，请调整 split_ratio 或增加 max_txs")
        return

    # 3. 生成候选增量
    if verbose:
        print("[3/5] Window A 生成候选增量...")
    hybrid = HybridPrefetcher(
        saved, use_gpu=use_gpu, gpu_device_id=gpu_device_id,
        slow_batch_size=slow_batch_size,
    )
    candidates = generate_candidates(window_a, hybrid, fast_path_dict, verbose=verbose)

    # 4. 过滤并合并
    if verbose:
        print("[4/5] 过滤并合并 delta...")
    filtered = filter_candidates(candidates, min_support=min_support,
                                 max_new_slots_per_key=max_new_slots_per_key)
    augmented_dict = merge_delta(fast_path_dict, filtered)
    delta_stats = compute_delta_stats(fast_path_dict, augmented_dict, filtered)

    # 保存 delta stats
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    stats_path = str(Path(output_dir) / "offline_delta_stats.csv")
    stats_row = {**split_stats, **delta_stats}
    with open(stats_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(stats_row.keys()))
        writer.writeheader()
        writer.writerow(stats_row)
    print(f"  Delta stats 已保存至: {stats_path}")

    # 5. Window B 评估
    if verbose:
        print("[5/5] Window B 评估 (rule_base vs rule_plus_delta)...")

    tmp_path = _write_temp_jsonl(window_b)
    try:
        # 覆盖 max_txs/max_blocks 避免二次限制（已在 split 阶段控制）
        common = dict(
            data_path=tmp_path,
            data_mode=data_mode,
            block_size=block_size,
            max_blocks=None,
            max_txs=None,
            block_number_field=block_number_field,
            tx_index_field=tx_index_field,
            t_hit_ns=t_hit_ns,
            t_miss_us=t_miss_us,
        )

        rule_base = run_simulation(
            RuleBasePrefetcher(fast_path_dict),
            verbose=False, **common,
        )
        rule_delta = run_simulation(
            RuleBasePrefetcher(augmented_dict),
            verbose=False, **common,
        )

        # 构建评估行
        eval_row = {
            "prefetcher": "rule_base",
            "n_tx": rule_base.n_tx,
            "n_blocks": rule_base.n_blocks,
            "recall": round(rule_base.recall, 4),
            "precision": round(rule_base.precision, 4),
            "total_cost_us": round(rule_base.total_cost_us, 2),
            "n_miss_prevented": rule_base.n_miss_prevented,
            "n_would_be_miss": rule_base.n_would_be_miss,
            "predict_overhead_us": round(rule_base.predict_overhead_us, 2),
        }
        eval_row2 = {
            "prefetcher": "rule_plus_delta",
            "n_tx": rule_delta.n_tx,
            "n_blocks": rule_delta.n_blocks,
            "recall": round(rule_delta.recall, 4),
            "precision": round(rule_delta.precision, 4),
            "total_cost_us": round(rule_delta.total_cost_us, 2),
            "n_miss_prevented": rule_delta.n_miss_prevented,
            "n_would_be_miss": rule_delta.n_would_be_miss,
            "predict_overhead_us": round(rule_delta.predict_overhead_us, 2),
        }

        # 计算 delta 带来的变化
        recall_delta = rule_delta.recall - rule_base.recall
        cost_delta_us = rule_base.total_cost_us - rule_delta.total_cost_us
        eval_row["recall_delta"] = round(recall_delta, 4)
        eval_row["cost_delta_us"] = round(cost_delta_us, 2)
        eval_row2["recall_delta"] = ""
        eval_row2["cost_delta_us"] = ""

        eval_path = str(Path(output_dir) / "rule_delta_eval.csv")
        with open(eval_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(eval_row.keys()))
            writer.writeheader()
            writer.writerow(eval_row)
            writer.writerow(eval_row2)
        print(f"  Eval 结果已保存至: {eval_path}")

        # 打印对比
        print(f"\n  {'':<18} {'rule_base':>12} {'rule_delta':>12} {'变化':>12}")
        print(f"  {'Recall':<18} {rule_base.recall:>12.4f} {rule_delta.recall:>12.4f} "
              f"{recall_delta:>+12.4f}")
        print(f"  {'Precision':<18} {rule_base.precision:>12.4f} {rule_delta.precision:>12.4f}")
        print(f"  {'Total Cost (µs)':<18} {rule_base.total_cost_us:>12.0f} {rule_delta.total_cost_us:>12.0f} "
              f"{-cost_delta_us:>+12.0f}")
        print(f"  {'Miss Prevented':<18} {rule_base.n_miss_prevented:>12} {rule_delta.n_miss_prevented:>12}")

        if recall_delta > 0 or cost_delta_us > 0:
            print(f"\n  ✓ delta 带来正向收益")
        else:
            print(f"\n  ✗ delta 未带来可测量提升（可尝试调整 min_support 或 split_ratio）")

    finally:
        import os
        os.unlink(tmp_path)
