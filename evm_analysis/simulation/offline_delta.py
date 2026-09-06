"""
离线增量管道：ML 离线路径补充 pattern_table。

管线：
  1. 按 block_number 切分 training_window / eval_window
  2. training_window：识别 table_miss 交易，用 MLPrefetcher 预测，累积正确 slot 计数
  3. 按 min_support / max_new_slots_per_key 过滤
  4. 合并 delta 到 pattern_table
  5. eval_window：original vs augmented 仿真对比

用法：
  python -m simulation.run --offline-delta \
    --model models/evm_model_hybrid_v1.pkl \
    --delta-split-ratio 0.7 --delta-min-support 2
"""

from __future__ import annotations

import csv
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from simulation.prefetch_api import MLPrefetcher, TablePrefetcher, make_prefetcher
from simulation.run import run_simulation


def split_by_block(
    jsonl_path: str,
    split_ratio: float = 0.7,
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
    ml_prefetcher: MLPrefetcher,
    pattern_table: dict,
    verbose: bool = True,
) -> dict[tuple, dict[str, int]]:
    """
    在 training_window 上为 table_miss 交易生成候选增量。

    对每笔 (to, selector) 不在 pattern_table 中的交易：
      - 调用 MLPrefetcher 预测
      - 取 predicted ∩ accessed_slots
      - 按 (to, selector) 键累加各 slot 的正确次数

    Returns:
        {(to, selector): {slot: correct_count}}
    """
    # 分离 table_hit 和 table_miss
    table_miss_indices: list[int] = []
    table_miss_txs: list[dict] = []
    for idx, tx in enumerate(txs):
        key = (tx.get("to", ""), tx.get("selector", ""))
        if key not in pattern_table:
            table_miss_indices.append(idx)
            table_miss_txs.append(tx)

    if verbose:
        print(f"  训练窗口总交易: {len(txs)}, table_miss: {len(table_miss_txs)} "
              f"({len(table_miss_txs)/max(len(txs),1)*100:.1f}%)")

    if not table_miss_txs:
        return {}

    # 逐批预测（复用 MLPrefetcher.predict_batch 的批处理）
    candidates: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    batch_size = ml_prefetcher.offline_batch_size
    total = len(table_miss_txs)

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_txs = table_miss_txs[start:end]
        predictions = ml_prefetcher.predict_batch(batch_txs)

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
    pattern_table: dict[tuple, list[str]],
    delta: dict[tuple, list[str]],
) -> dict[tuple, list[str]]:
    """合并 delta 到 pattern_table，返回新 dict（不修改原 dict）。"""
    merged = {k: list(v) for k, v in pattern_table.items()}
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
          f"dict {len(pattern_table)} → {len(merged)} 键")
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
    split_ratio: float = 0.7,
    min_support: int = 2,
    max_new_slots_per_key: int | None = None,
    output_dir: str = "figures/data",
    use_gpu: bool = False,
    gpu_device_id: int = 0,
    offline_batch_size: int = 1024,
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
    pattern_table: dict = saved["fast_path_dict"]

    # 2. 切分训练/评估窗口
    if verbose:
        print("[2/5] 切分训练/评估窗口...")
    training_window, eval_window, split_stats = split_by_block(
        data_path, split_ratio=split_ratio, max_txs=max_txs,
    )
    print(f"  训练窗口: {split_stats['window_a_blocks']} 块, "
          f"{split_stats['window_a_txs']} 笔交易")
    print(f"  评估窗口: {split_stats['window_b_blocks']} 块, "
          f"{split_stats['window_b_txs']} 笔交易")

    if not training_window or not eval_window:
        print("  错误: 训练或评估窗口为空，请调整 split_ratio 或增加 max_txs")
        return

    # 3. 生成候选增量
    if verbose:
        print("[3/5] 训练窗口生成候选增量...")
    ml_prefetcher = MLPrefetcher(
        saved, use_gpu=use_gpu, gpu_device_id=gpu_device_id,
        offline_batch_size=offline_batch_size,
    )
    candidates = generate_candidates(training_window, ml_prefetcher, pattern_table, verbose=verbose)

    # 4. 过滤并合并
    if verbose:
        print("[4/5] 过滤并合并 delta...")
    filtered = filter_candidates(candidates, min_support=min_support,
                                 max_new_slots_per_key=max_new_slots_per_key)
    augmented_dict = merge_delta(pattern_table, filtered)
    delta_stats = compute_delta_stats(pattern_table, augmented_dict, filtered)

    # 保存 delta stats
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    stats_path = str(Path(output_dir) / "offline_delta_stats.csv")
    stats_row = {**split_stats, **delta_stats}
    with open(stats_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(stats_row.keys()))
        writer.writeheader()
        writer.writerow(stats_row)
    print(f"  Delta stats 已保存至: {stats_path}")

    # 5. 评估窗口对比
    if verbose:
        print("[5/5] 评估窗口对比 (original vs augmented)...")

    tmp_path = _write_temp_jsonl(eval_window)
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

        original_result = run_simulation(
            TablePrefetcher(pattern_table),
            verbose=False, **common,
        )
        augmented_result = run_simulation(
            TablePrefetcher(augmented_dict),
            verbose=False, **common,
        )

        # 构建评估行
        eval_row = {
            "prefetcher": "original_table",
            "n_tx": original_result.n_tx,
            "n_blocks": original_result.n_blocks,
            "recall": round(original_result.recall, 4),
            "precision": round(original_result.precision, 4),
            "total_cost_us": round(original_result.total_cost_us, 2),
            "n_miss_prevented": original_result.n_miss_prevented,
            "n_would_be_miss": original_result.n_would_be_miss,
            "predict_overhead_us": round(original_result.predict_overhead_us, 2),
        }
        eval_row2 = {
            "prefetcher": "augmented_table",
            "n_tx": augmented_result.n_tx,
            "n_blocks": augmented_result.n_blocks,
            "recall": round(augmented_result.recall, 4),
            "precision": round(augmented_result.precision, 4),
            "total_cost_us": round(augmented_result.total_cost_us, 2),
            "n_miss_prevented": augmented_result.n_miss_prevented,
            "n_would_be_miss": augmented_result.n_would_be_miss,
            "predict_overhead_us": round(augmented_result.predict_overhead_us, 2),
        }

        # 计算 delta 带来的变化
        recall_delta = augmented_result.recall - original_result.recall
        cost_delta_us = original_result.total_cost_us - augmented_result.total_cost_us
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
        print(f"\n  {'':<18} {'original_table':>14} {'augmented_table':>16} {'变化':>12}")
        print(f"  {'Recall':<18} {original_result.recall:>14.4f} {augmented_result.recall:>16.4f} "
              f"{recall_delta:>+12.4f}")
        print(f"  {'Precision':<18} {original_result.precision:>14.4f} {augmented_result.precision:>16.4f}")
        print(f"  {'Total Cost (µs)':<18} {original_result.total_cost_us:>14.0f} {augmented_result.total_cost_us:>16.0f} "
              f"{-cost_delta_us:>+12.0f}")
        print(f"  {'Miss Prevented':<18} {original_result.n_miss_prevented:>14} {augmented_result.n_miss_prevented:>16}")

        if recall_delta > 0 or cost_delta_us > 0:
            print(f"\n  ✓ delta 带来正向收益")
        else:
            print(f"\n  ✗ delta 未带来可测量提升（可尝试调整 min_support 或 split_ratio）")

    finally:
        import os
        os.unlink(tmp_path)
