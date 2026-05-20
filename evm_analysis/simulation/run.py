"""
仿真平台 CLI 入口。

使用方式：
  # 单次运行（E0 无预取基线）
  python -m simulation.run --prefetcher none

  # 四组对照实验一次性输出
  python -m simulation.run --all --model models/evm_model_hybrid_v1.pkl

  # 敏感性分析（扫描 t_miss 参数）
  python -m simulation.run --sensitivity --model models/evm_model_hybrid_v1.pkl

  # 快速测试（只跑前 20 个伪块）
  python -m simulation.run --all --model models/evm_model_hybrid_v1.pkl --max-blocks 20
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from simulation.cache_sim import CacheSim
from simulation.data_loader import DataLoader, DEFAULT_BLOCK_SIZE
from simulation.metric_log import MetricLog, RunSummary
from simulation.prefetch_api import BasePrefetcher, make_prefetcher

# ── 默认路径（相对于项目根目录） ───────────────────────────────────────────────
DEFAULT_DATA = str(Path(__file__).resolve().parents[2] / "erigon_tx_trace.jsonl")
DEFAULT_MODEL = "models/evm_model_hybrid_v1.pkl"
DEFAULT_OUTPUT_DIR = "figures/data"


# ── 核心重放函数 ───────────────────────────────────────────────────────────────

def run_simulation(
    prefetcher: BasePrefetcher,
    data_path: str,
    data_mode: str,
    block_size: int,
    max_blocks: int | None,
    max_txs: int | None,
    block_number_field: str,
    tx_index_field: str,
    t_hit_ns: float,
    t_miss_us: float,
    prefetch_timing: str = "ideal",
    t_prefetch_us: float = 0.0,
    prefetch_concurrency: int = 1,
    queue_delay_us: float = 0.0,
    tx_exec_us_per_slot: float = 0.0,
    tx_exec_us_base: float = 0.0,
    progress_every_txs: int = 500,
    verbose: bool = True,
) -> RunSummary:
    loader = DataLoader(
        data_path,
        block_size=block_size,
        max_blocks=max_blocks,
        max_txs=max_txs,
        mode=data_mode,
        block_number_field=block_number_field,
        tx_index_field=tx_index_field,
    )
    sim = CacheSim(
        t_hit_ns=t_hit_ns,
        t_miss_us=t_miss_us,
        prefetch_timing=prefetch_timing,
        t_prefetch_us=t_prefetch_us,
        prefetch_concurrency=prefetch_concurrency,
        queue_delay_us=queue_delay_us,
        tx_exec_us_per_slot=tx_exec_us_per_slot,
        tx_exec_us_base=tx_exec_us_base,
    )
    log = MetricLog(
        prefetcher_name=prefetcher.name,
        data_mode=data_mode,
        prefetch_timing=prefetch_timing,
        t_hit_ns=t_hit_ns,
        t_miss_us=t_miss_us,
        block_size=block_size,
    )

    t0 = time.time()
    for block_idx, block_txs in enumerate(loader.iter_blocks()):
        sim.reset_block()
        log.new_block()

        pred_t0 = time.perf_counter()
        batch_predictions = prefetcher.predict_batch(block_txs)
        pred_elapsed_us = (time.perf_counter() - pred_t0) * 1e6
        log.add_predict_overhead_us(pred_elapsed_us)
        if len(batch_predictions) != len(block_txs):
            raise RuntimeError(
                f"{prefetcher.name}.predict_batch 返回长度不匹配："
                f"{len(batch_predictions)} != {len(block_txs)}"
            )
        for tx, predicted in zip(block_txs, batch_predictions):
            result = sim.process_tx(tx, predicted)
            log.record(result)
            if verbose and progress_every_txs > 0 and (log.summary().n_tx % progress_every_txs == 0):
                s = log.summary()
                elapsed = time.time() - t0
                print(
                    f"  [{prefetcher.name}] tx={s.n_tx} blocks={s.n_blocks} "
                    f"cost={s.total_cost_us/1e6:.3f}s "
                    f"pred={s.predict_overhead_us/1e6:.3f}s "
                    f"elapsed={elapsed:.1f}s"
                )

        if verbose and (block_idx + 1) % 100 == 0:
            s = log.summary()
            elapsed = time.time() - t0
            print(
                f"  [{prefetcher.name}] 块 {block_idx+1} | "
                f"累计交易 {s.n_tx} | "
                f"代价 {s.total_cost_us/1e6:.3f} s | "
                f"预测开销 {s.predict_overhead_us/1e6:.3f} s | "
                f"耗时 {elapsed:.1f}s"
            )

    log.set_elapsed_s(time.time() - t0)
    return log.summary()


# ── 打印与保存 ─────────────────────────────────────────────────────────────────

def print_summary(s: RunSummary, baseline: RunSummary | None = None) -> None:
    print(f"\n{'='*55}")
    print(f"  预取器: {s.prefetcher_name.upper():<10}  "
          f"mode={s.data_mode}  timing={s.prefetch_timing}  "
          f"t_hit={s.t_hit_ns}ns  t_miss={s.t_miss_us}µs")
    print(f"{'='*55}")
    print(f"  伪块数          : {s.n_blocks}")
    print(f"  交易数          : {s.n_tx}")
    print(f"  真实访问次数    : {s.n_true_accesses}")
    print(f"  应产生 miss 数  : {s.n_would_be_miss}  (块级 first-touch 基准)")
    print(f"  预取防止 miss 数: {s.n_miss_prevented}")
    print(f"  预测 slot 数    : {s.n_predicted}")
    print(f"  召回率 Recall   : {s.recall:.4f}  (防止miss / 应有miss)")
    print(f"  精确率 Precision: {s.precision:.4f}  (防止miss / 预测数)")
    print(f"  缓存命中次数    : {s.cache_hits_total}")
    print(f"  缓存缺失次数    : {s.cache_misses_total}  (实际剩余 miss)")
    print(f"  缺失率          : {s.miss_rate:.4f}")
    print(f"  预取发起数      : {s.prefetch_issued_total}")
    print(f"  预取相关槽位数  : {s.prefetch_relevant_total}")
    print(f"  预取及时命中率  : {s.prefetch_timely_rate:.4f}")
    print(f"  预取排队等待    : {s.prefetch_queue_wait_us_total:.2f} µs")
    print(f"  总仿真代价      : {s.total_cost_us/1e6:.4f} s  ({s.total_cost_us:.0f} µs)")
    print(f"  预测器开销      : {s.predict_overhead_us/1e6:.4f} s  ({s.predict_overhead_us:.0f} µs)")
    print(f"  端到端近似代价  : {s.e2e_cost_proxy_us/1e6:.4f} s  ({s.e2e_cost_proxy_us:.0f} µs)")
    print(f"  程序真实耗时    : {s.e2e_elapsed_s:.4f} s")
    print(f"  平均每笔交易    : {s.avg_cost_per_tx_us:.4f} µs")
    print(f"  平均每次访问    : {s.avg_cost_per_access_us:.6f} µs")
    print(f"  平均每笔预测开销: {s.avg_predict_overhead_per_tx_us:.4f} µs")
    if baseline is not None and baseline is not s:
        speedup = s.speedup_vs(baseline)
        net_speedup = s.net_speedup_vs(baseline)
        saved_us = baseline.total_cost_us - s.total_cost_us
        net_gain_us = saved_us - s.predict_overhead_us
        print(f"  相对基线加速比  : {speedup:.4f}x")
        print(f"  节省代价        : {saved_us:.0f} µs  ({saved_us/baseline.total_cost_us*100:.2f}%)")
        print(f"  净收益(net)     : {net_gain_us:.0f} µs")
        print(f"  净口径加速比    : {net_speedup:.4f}x")


def save_results(summaries: list[RunSummary], output_path: str, baseline: RunSummary) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in summaries:
        d = s.as_dict()
        d["speedup_vs_baseline"] = round(s.speedup_vs(baseline), 6)
        d["speedup_net_vs_baseline"] = round(s.net_speedup_vs(baseline), 6)
        d["saved_cost_us"] = round(baseline.total_cost_us - s.total_cost_us, 4)
        d["storage_gain_us"] = d["saved_cost_us"]
        d["net_gain_us"] = round(d["saved_cost_us"] - s.predict_overhead_us, 4)
        rows.append(d)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n结果已保存至: {output_path}")


# ── 自检：E1 应与理论公式一致 ────────────────────────────────────────────────

def sanity_check(baseline: RunSummary, oracle: RunSummary) -> None:
    """
    验证仿真实现正确性：
    E0：实际 cache_misses == n_would_be_miss（无预取时两者应完全一致）
    E1：oracle recall == 1.0（预测所有真实 slots，miss 全部被防止）
    E1：代价 <= E0 代价
    """
    print("\n" + "="*55)
    print("  自检（Sanity Check）")
    print("="*55)

    # E0：无预取时，「应有 miss」== 「实际 miss」（两个字段应完全相同）
    expected = baseline.n_would_be_miss
    actual = baseline.cache_misses_total
    diff_pct = abs(actual - expected) / max(expected, 1) * 100
    print(f"  E0 miss 一致性：应有={expected}  实际={actual}  "
          f"偏差={diff_pct:.2f}%  {'✓' if diff_pct < 0.01 else '✗ 异常'}")

    # E1：oracle recall 应为 1.0
    print(f"  E1 Recall     ：{oracle.recall:.4f}  "
          f"{'✓' if oracle.recall > 0.999 else '✗ 异常（OraclePrefetcher 实现有误）'}")

    # E1 代价应 <= E0
    ok = oracle.total_cost_us <= baseline.total_cost_us
    print(f"  E1 代价 ≤ E0  ：{'✓' if ok else '✗ 异常（预取反而变慢？）'}")


# ── 敏感性分析 ────────────────────────────────────────────────────────────────

SENSITIVITY_PARAMS = [
    ("基准",       30.0, 3.0),
    ("t_miss-20%", 30.0, 2.4),
    ("t_miss+20%", 30.0, 3.6),
    ("t_hit-20%",  24.0, 3.0),
    ("t_hit+20%",  36.0, 3.0),
]

PARALLEL_PREFETCH_LATENCIES_US = [0.0, 0.5, 1.0, 2.0, 4.0]
PARALLEL_PREFETCH_CONCURRENCIES = [1, 4, 16]


def inspect_data_schema(
    data_path: str,
    block_number_field: str,
    tx_index_field: str,
    head_rows: int = 1000,
) -> None:
    required_common = ["to", "selector", "accessed_slots"]
    required_real = [block_number_field, tx_index_field]

    first_keys = set()
    counters = {k: 0 for k in required_common + required_real}
    row_count = 0

    with open(data_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row_count == 0:
                first_keys = set(row.keys())
            row_count += 1
            for k in counters:
                if k in row:
                    counters[k] += 1
            if row_count >= head_rows:
                break

    print("\n数据字段检查（抽样）")
    print(f"  文件: {data_path}")
    print(f"  抽样行数: {row_count}")
    for k in required_common:
        print(f"  {k:<20} {'✓' if counters[k] > 0 else '✗'} ({counters[k]}/{row_count})")
    for k in required_real:
        print(f"  {k:<20} {'✓' if counters[k] > 0 else '✗'} ({counters[k]}/{row_count})")
    print(f"  首行字段数: {len(first_keys)}")


def run_sensitivity(
    data_path: str,
    model_path: str,
    data_mode: str,
    block_size: int,
    max_blocks: int | None,
    max_txs: int | None,
    block_number_field: str,
    tx_index_field: str,
    output_path: str,
    max_param_cases: int | None = None,
    hybrid_gate_rate: float = 0.1,
    use_gpu: bool = False,
    gpu_device_id: int = 0,
    slow_batch_size: int = 1024,
    tx_exec_us_per_slot: float = 0.0,
    tx_exec_us_base: float = 0.0,
) -> None:
    print("\n开始敏感性分析（固定 prefetcher=hybrid，扫描 t_hit/t_miss）...")
    rows = []
    params = SENSITIVITY_PARAMS[:max_param_cases] if max_param_cases is not None else SENSITIVITY_PARAMS
    for label, t_hit_ns, t_miss_us in params:
        print(f"\n  参数组合: {label}  t_hit={t_hit_ns}ns  t_miss={t_miss_us}µs")
        baseline = run_simulation(
            make_prefetcher(
                "none",
                hybrid_gate_rate=hybrid_gate_rate,
                use_gpu=use_gpu,
                gpu_device_id=gpu_device_id,
                slow_batch_size=slow_batch_size,
            ),
            data_path, data_mode, block_size, max_blocks, max_txs,
            block_number_field, tx_index_field,
            t_hit_ns, t_miss_us, verbose=False,
            tx_exec_us_per_slot=tx_exec_us_per_slot,
            tx_exec_us_base=tx_exec_us_base,
        )
        hybrid = run_simulation(
            make_prefetcher(
                "hybrid",
                model_path,
                hybrid_gate_rate,
                use_gpu,
                gpu_device_id,
                slow_batch_size,
            ),
            data_path, data_mode, block_size, max_blocks, max_txs,
            block_number_field, tx_index_field,
            t_hit_ns, t_miss_us, verbose=False,
            tx_exec_us_per_slot=tx_exec_us_per_slot,
            tx_exec_us_base=tx_exec_us_base,
        )
        row = {
            "param_label": label,
            "t_hit_ns": t_hit_ns,
            "t_miss_us": t_miss_us,
            "baseline_cost_us": round(baseline.total_cost_us, 2),
            "hybrid_cost_us": round(hybrid.total_cost_us, 2),
            "speedup": round(hybrid.speedup_vs(baseline), 4),
            "saved_pct": round(
                (baseline.total_cost_us - hybrid.total_cost_us) / baseline.total_cost_us * 100, 2
            ),
            "recall": round(hybrid.recall, 4),
            "precision": round(hybrid.precision, 4),
        }
        rows.append(row)
        print(f"    加速比={row['speedup']}x  节省={row['saved_pct']}%  "
              f"recall={row['recall']}  prec={row['precision']}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n敏感性分析结果已保存至: {output_path}")


def run_parallel_sensitivity(
    data_path: str,
    model_path: str,
    data_mode: str,
    block_size: int,
    max_blocks: int | None,
    max_txs: int | None,
    block_number_field: str,
    tx_index_field: str,
    t_hit_ns: float,
    t_miss_us: float,
    latencies_us: list[float],
    concurrencies: list[int],
    output_path: str,
    hybrid_gate_rate: float = 0.1,
    use_gpu: bool = False,
    gpu_device_id: int = 0,
    slow_batch_size: int = 1024,
    tx_exec_us_per_slot: float = 0.0,
    tx_exec_us_base: float = 0.0,
) -> None:
    print("\n开始并行预取敏感性分析（fixed prefetcher=hybrid）...")
    baseline = run_simulation(
        make_prefetcher(
            "none",
            hybrid_gate_rate=hybrid_gate_rate,
            use_gpu=use_gpu,
            gpu_device_id=gpu_device_id,
            slow_batch_size=slow_batch_size,
        ),
        data_path, data_mode, block_size, max_blocks, max_txs,
        block_number_field, tx_index_field,
        t_hit_ns, t_miss_us, verbose=False,
        tx_exec_us_per_slot=tx_exec_us_per_slot,
        tx_exec_us_base=tx_exec_us_base,
    )
    rows = []
    for latency_us in latencies_us:
        for concurrency in concurrencies:
            s = run_simulation(
                make_prefetcher(
                    "hybrid",
                    model_path,
                    hybrid_gate_rate,
                    use_gpu,
                    gpu_device_id,
                    slow_batch_size,
                ),
                data_path, data_mode, block_size, max_blocks, max_txs,
                block_number_field, tx_index_field,
                t_hit_ns, t_miss_us,
                prefetch_timing="timed",
                t_prefetch_us=latency_us,
                prefetch_concurrency=concurrency,
                queue_delay_us=0.0,
                verbose=False,
                tx_exec_us_per_slot=tx_exec_us_per_slot,
                tx_exec_us_base=tx_exec_us_base,
            )
            rows.append(
                {
                    "t_prefetch_us": latency_us,
                    "prefetch_concurrency": concurrency,
                    "total_cost_us": round(s.total_cost_us, 2),
                    "speedup_vs_baseline": round(s.speedup_vs(baseline), 4),
                    "recall": round(s.recall, 4),
                    "precision": round(s.precision, 4),
                    "prefetch_timely_rate": round(s.prefetch_timely_rate, 4),
                    "prefetch_queue_wait_us_total": round(s.prefetch_queue_wait_us_total, 2),
                }
            )
            print(
                f"  latency={latency_us}us, concurrency={concurrency} -> "
                f"speedup={rows[-1]['speedup_vs_baseline']}x, "
                f"timely_rate={rows[-1]['prefetch_timely_rate']}"
            )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n并行预取敏感性结果已保存至: {output_path}")


def run_alpha_sweep(
    data_path: str,
    model_path: str,
    data_mode: str,
    block_size: int,
    max_blocks: int | None,
    max_txs: int | None,
    block_number_field: str,
    tx_index_field: str,
    t_hit_ns: float,
    t_miss_us: float,
    prefetch_timing: str,
    t_prefetch_us: float,
    prefetch_concurrency: int,
    queue_delay_us: float,
    tx_exec_us_per_slot: float,
    tx_exec_us_base: float,
    alphas: list[float],
    output_path: str,
    hybrid_gate_rate: float = 0.1,
    use_gpu: bool = False,
    gpu_device_id: int = 0,
    slow_batch_size: int = 1024,
    progress_every_txs: int = 500,
    verbose: bool = True,
) -> None:
    print("\n开始 Alpha 执行时间覆盖敏感性分析...")
    print(f"  tx_exec_us_per_slot={tx_exec_us_per_slot}  tx_exec_us_base={tx_exec_us_base}")
    print(f"  alphas={alphas}")

    baseline = run_simulation(
        make_prefetcher(
            "none",
            hybrid_gate_rate=hybrid_gate_rate,
            use_gpu=use_gpu,
            gpu_device_id=gpu_device_id,
            slow_batch_size=slow_batch_size,
        ),
        data_path, data_mode, block_size, max_blocks, max_txs,
        block_number_field, tx_index_field,
        t_hit_ns, t_miss_us,
        prefetch_timing=prefetch_timing,
        t_prefetch_us=t_prefetch_us,
        prefetch_concurrency=prefetch_concurrency,
        queue_delay_us=queue_delay_us,
        tx_exec_us_per_slot=tx_exec_us_per_slot,
        tx_exec_us_base=tx_exec_us_base,
        progress_every_txs=progress_every_txs,
        verbose=verbose,
    )
    hybrid = run_simulation(
        make_prefetcher(
            "hybrid",
            model_path,
            hybrid_gate_rate,
            use_gpu,
            gpu_device_id,
            slow_batch_size,
        ),
        data_path, data_mode, block_size, max_blocks, max_txs,
        block_number_field, tx_index_field,
        t_hit_ns, t_miss_us,
        prefetch_timing=prefetch_timing,
        t_prefetch_us=t_prefetch_us,
        prefetch_concurrency=prefetch_concurrency,
        queue_delay_us=queue_delay_us,
        tx_exec_us_per_slot=tx_exec_us_per_slot,
        tx_exec_us_base=tx_exec_us_base,
        progress_every_txs=progress_every_txs,
        verbose=verbose,
    )

    storage_gain_us = hybrid.storage_gain_vs(baseline)
    tx_exec_us_total = hybrid.tx_exec_us_total
    raw_pred_overhead = hybrid.predict_overhead_us

    rows = []
    for alpha in alphas:
        effective_overhead = hybrid.effective_pred_overhead_us(alpha)
        net_gain = hybrid.net_gain_with_overlap_us(baseline, alpha)
        speedup = hybrid.speedup_overlap_vs(baseline, alpha)
        rows.append({
            "alpha": alpha,
            "tx_exec_us_total": round(tx_exec_us_total, 2),
            "raw_pred_overhead_us": round(raw_pred_overhead, 2),
            "effective_pred_overhead_us": round(effective_overhead, 2),
            "storage_gain_us": round(storage_gain_us, 2),
            "net_gain_us": round(net_gain, 2),
            "speedup_overlap_vs_baseline": round(speedup, 6),
            "net_positive": "Y" if net_gain > 0 else "N",
            "baseline_cost_us": round(baseline.total_cost_us, 2),
            "hybrid_cost_us": round(hybrid.total_cost_us, 2),
            "recall": round(hybrid.recall, 4),
            "precision": round(hybrid.precision, 4),
        })
        print(
            f"  alpha={alpha:.2f}  eff_overhead={effective_overhead/1e6:.3f}s  "
            f"net_gain={net_gain/1e6:.3f}s  "
            f"speedup={speedup:.4f}x  {'✓' if net_gain > 0 else '✗'}"
        )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nAlpha 覆盖敏感性结果已保存至: {output_path}")


# ── CLI 参数解析 ──────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="EVM 存储预取仿真平台",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data", default=DEFAULT_DATA, help="JSONL 数据文件路径")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Hybrid 模型 pkl 路径（rule/hybrid 必须）")
    p.add_argument(
        "--prefetcher",
        choices=["none", "oracle", "rule", "hybrid", "hybrid_gated"],
        default="none",
        help="单次运行时使用的预取器（--all 时忽略此参数）",
    )
    p.add_argument(
        "--hybrid-gate-rate",
        type=float,
        default=0.1,
        help="hybrid_gated 的 slow-path 触发比例（0~1）",
    )
    p.add_argument("--use-gpu", action="store_true", help="对 hybrid/hybrid_gated 尝试启用 GPU 推理")
    p.add_argument("--gpu-device-id", type=int, default=0, help="GPU 设备 ID（--use-gpu 时生效）")
    p.add_argument("--slow-batch-size", type=int, default=1024, help="hybrid 慢路径分片批大小")
    p.add_argument("--all", action="store_true", help="依次运行 E0/E1/E2/E3 四组实验并输出对比")
    p.add_argument("--sensitivity", action="store_true", help="运行敏感性分析（扫描 t_hit/t_miss）")
    p.add_argument("--parallel-sensitivity", action="store_true", help="运行并行预取敏感性分析")
    p.add_argument("--alpha-sweep", action="store_true", help="运行 alpha 执行时间覆盖敏感性分析")
    p.add_argument("--offline-delta", action="store_true", help="运行离线增量管道（hybrid → fast-path 补充）")
    p.add_argument("--delta-split-ratio", type=float, default=0.8, help="Window A/B 切分比例")
    p.add_argument("--delta-min-support", type=int, default=2, help="候选 slot 最小支持次数")
    p.add_argument("--delta-max-slots-per-key", type=int, default=None, help="每键最多新增 slot 数")
    p.add_argument("--sensitivity-cases", type=int, default=None, help="敏感性参数组合上限（快速抽样）")
    p.add_argument(
        "--parallel-latencies",
        type=float,
        nargs="*",
        default=PARALLEL_PREFETCH_LATENCIES_US,
        help="并行敏感性扫描的预取延迟列表(µs)",
    )
    p.add_argument(
        "--parallel-concurrencies",
        type=int,
        nargs="*",
        default=PARALLEL_PREFETCH_CONCURRENCIES,
        help="并行敏感性扫描的并发度列表",
    )
    p.add_argument("--inspect-data", action="store_true", help="打印数据字段可用性检查")
    p.add_argument("--compare-modes", action="store_true", help="对比 pseudo_block 与 real_block 两种模式")
    p.add_argument(
        "--data-mode",
        choices=["pseudo_block", "real_block"],
        default="pseudo_block",
        help="块划分模式",
    )
    p.add_argument("--block-number-field", default="block_number", help="real_block 模式块号字段名")
    p.add_argument("--tx-index-field", default="transaction_index", help="real_block 模式块内序字段名")
    p.add_argument("--block-size", type=int, default=DEFAULT_BLOCK_SIZE, help="伪块大小（交易数/块）")
    p.add_argument("--max-blocks", type=int, default=None, help="最多处理的伪块数，不填则全量")
    p.add_argument("--max-txs", type=int, default=None, help="最多处理的交易条数（用于快速抽样）")
    p.add_argument("--t-hit-ns", type=float, default=30.0, help="缓存命中代价（ns）")
    p.add_argument("--t-miss-us", type=float, default=3.0, help="缓存缺失代价（µs）")
    p.add_argument(
        "--prefetch-timing",
        choices=["ideal", "timed"],
        default="ideal",
        help="预取完成模型：ideal=立即就绪, timed=按延迟/并发模拟",
    )
    p.add_argument("--t-prefetch-us", type=float, default=0.0, help="单槽预取服务时间（µs）")
    p.add_argument("--prefetch-concurrency", type=int, default=1, help="预取并发 worker 数")
    p.add_argument("--queue-delay-us", type=float, default=0.0, help="预取入队固定延迟（µs）")
    p.add_argument("--tx-exec-us-base", type=float, default=0.0, help="每笔交易执行时间代理基础值（µs）")
    p.add_argument("--tx-exec-us-per-slot", type=float, default=0.0, help="每 slot 访问执行时间代理增量（µs）")
    p.add_argument(
        "--alphas",
        type=float,
        nargs="*",
        default=[0.0, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0],
        help="alpha 覆盖比例列表（alpha sweep 用）",
    )
    p.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT_DIR, help="CSV 输出目录"
    )
    p.add_argument("--quiet", action="store_true", help="减少进度输出")
    p.add_argument("--progress-every-txs", type=int, default=500, help="每处理多少交易打印一次进度")
    return p


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = build_parser().parse_args()
    verbose = not args.quiet

    if args.inspect_data:
        inspect_data_schema(
            data_path=args.data,
            block_number_field=args.block_number_field,
            tx_index_field=args.tx_index_field,
        )
        return

    # ── 敏感性分析模式 ─────────────────────────────────────────────────────
    if args.sensitivity:
        run_sensitivity(
            data_path=args.data,
            model_path=args.model,
            data_mode=args.data_mode,
            block_size=args.block_size,
            max_blocks=args.max_blocks,
            max_txs=args.max_txs,
            block_number_field=args.block_number_field,
            tx_index_field=args.tx_index_field,
            output_path=str(Path(args.output_dir) / "sensitivity_table.csv"),
            max_param_cases=args.sensitivity_cases,
            hybrid_gate_rate=args.hybrid_gate_rate,
            use_gpu=args.use_gpu,
            gpu_device_id=args.gpu_device_id,
            slow_batch_size=args.slow_batch_size,
            tx_exec_us_per_slot=args.tx_exec_us_per_slot,
            tx_exec_us_base=args.tx_exec_us_base,
        )
        return

    if args.parallel_sensitivity:
        run_parallel_sensitivity(
            data_path=args.data,
            model_path=args.model,
            data_mode=args.data_mode,
            block_size=args.block_size,
            max_blocks=args.max_blocks,
            max_txs=args.max_txs,
            block_number_field=args.block_number_field,
            tx_index_field=args.tx_index_field,
            t_hit_ns=args.t_hit_ns,
            t_miss_us=args.t_miss_us,
            latencies_us=args.parallel_latencies,
            concurrencies=args.parallel_concurrencies,
            output_path=str(Path(args.output_dir) / "parallel_prefetch_sensitivity.csv"),
            hybrid_gate_rate=args.hybrid_gate_rate,
            use_gpu=args.use_gpu,
            gpu_device_id=args.gpu_device_id,
            slow_batch_size=args.slow_batch_size,
            tx_exec_us_per_slot=args.tx_exec_us_per_slot,
            tx_exec_us_base=args.tx_exec_us_base,
        )
        return

    if args.alpha_sweep:
        run_alpha_sweep(
            data_path=args.data,
            model_path=args.model,
            data_mode=args.data_mode,
            block_size=args.block_size,
            max_blocks=args.max_blocks,
            max_txs=args.max_txs,
            block_number_field=args.block_number_field,
            tx_index_field=args.tx_index_field,
            t_hit_ns=args.t_hit_ns,
            t_miss_us=args.t_miss_us,
            prefetch_timing=args.prefetch_timing,
            t_prefetch_us=args.t_prefetch_us,
            prefetch_concurrency=args.prefetch_concurrency,
            queue_delay_us=args.queue_delay_us,
            tx_exec_us_per_slot=args.tx_exec_us_per_slot,
            tx_exec_us_base=args.tx_exec_us_base,
            alphas=args.alphas,
            output_path=str(Path(args.output_dir) / "alpha_sweep_overlap.csv"),
            hybrid_gate_rate=args.hybrid_gate_rate,
            use_gpu=args.use_gpu,
            gpu_device_id=args.gpu_device_id,
            slow_batch_size=args.slow_batch_size,
            progress_every_txs=args.progress_every_txs,
            verbose=verbose,
        )
        return

    if args.offline_delta:
        from simulation.offline_delta import run_offline_delta_pipeline
        run_offline_delta_pipeline(
            data_path=args.data,
            model_path=args.model,
            data_mode=args.data_mode,
            block_size=args.block_size,
            max_txs=args.max_txs,
            max_blocks=args.max_blocks,
            block_number_field=args.block_number_field,
            tx_index_field=args.tx_index_field,
            t_hit_ns=args.t_hit_ns,
            t_miss_us=args.t_miss_us,
            split_ratio=args.delta_split_ratio,
            min_support=args.delta_min_support,
            max_new_slots_per_key=args.delta_max_slots_per_key,
            output_dir=args.output_dir,
            use_gpu=args.use_gpu,
            gpu_device_id=args.gpu_device_id,
            slow_batch_size=args.slow_batch_size,
            quiet=args.quiet,
        )
        return

    if args.compare_modes:
        rows = []
        for mode in ("pseudo_block", "real_block"):
            baseline = run_simulation(
                make_prefetcher(
                    "none",
                    hybrid_gate_rate=args.hybrid_gate_rate,
                    use_gpu=args.use_gpu,
                    gpu_device_id=args.gpu_device_id,
                    slow_batch_size=args.slow_batch_size,
                ),
                args.data, mode, args.block_size, args.max_blocks, args.max_txs,
                args.block_number_field, args.tx_index_field,
                args.t_hit_ns, args.t_miss_us,
                prefetch_timing=args.prefetch_timing,
                t_prefetch_us=args.t_prefetch_us,
                prefetch_concurrency=args.prefetch_concurrency,
                queue_delay_us=args.queue_delay_us,
                tx_exec_us_per_slot=args.tx_exec_us_per_slot,
                tx_exec_us_base=args.tx_exec_us_base,
                progress_every_txs=args.progress_every_txs,
                verbose=verbose,
            )
            hybrid = run_simulation(
                make_prefetcher(
                    "hybrid",
                    args.model,
                    args.hybrid_gate_rate,
                    args.use_gpu,
                    args.gpu_device_id,
                    args.slow_batch_size,
                ),
                args.data, mode, args.block_size, args.max_blocks, args.max_txs,
                args.block_number_field, args.tx_index_field,
                args.t_hit_ns, args.t_miss_us,
                prefetch_timing=args.prefetch_timing,
                t_prefetch_us=args.t_prefetch_us,
                prefetch_concurrency=args.prefetch_concurrency,
                queue_delay_us=args.queue_delay_us,
                tx_exec_us_per_slot=args.tx_exec_us_per_slot,
                tx_exec_us_base=args.tx_exec_us_base,
                progress_every_txs=args.progress_every_txs,
                verbose=verbose,
            )
            rows.append(
                {
                    "mode": mode,
                    "baseline_cost_us": round(baseline.total_cost_us, 2),
                    "hybrid_cost_us": round(hybrid.total_cost_us, 2),
                    "speedup": round(hybrid.speedup_vs(baseline), 4),
                    "recall": round(hybrid.recall, 4),
                    "precision": round(hybrid.precision, 4),
                    "prefetch_timely_rate": round(hybrid.prefetch_timely_rate, 4),
                }
            )
        output_path = str(Path(args.output_dir) / "mode_compare.csv")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n模式对比结果已保存至: {output_path}")
        return

    # ── 全量四组对比 ───────────────────────────────────────────────────────
    if args.all:
        experiments = [
            ("none",   None),
            ("oracle", None),
            ("rule",   args.model),
            ("hybrid", args.model),
            ("hybrid_gated", args.model),
        ]
        summaries: list[RunSummary] = []
        for pname, mpath in experiments:
            print(f"\n{'─'*55}")
            print(f"  运行 {pname.upper()} ...")
            pf = make_prefetcher(
                pname,
                mpath,
                args.hybrid_gate_rate,
                args.use_gpu,
                args.gpu_device_id,
                args.slow_batch_size,
            )
            s = run_simulation(
                pf, args.data, args.data_mode, args.block_size, args.max_blocks,
                args.max_txs,
                args.block_number_field, args.tx_index_field,
                args.t_hit_ns, args.t_miss_us,
                prefetch_timing=args.prefetch_timing,
                t_prefetch_us=args.t_prefetch_us,
                prefetch_concurrency=args.prefetch_concurrency,
                queue_delay_us=args.queue_delay_us,
                tx_exec_us_per_slot=args.tx_exec_us_per_slot,
                tx_exec_us_base=args.tx_exec_us_base,
                progress_every_txs=args.progress_every_txs,
                verbose=verbose,
            )
            summaries.append(s)

        baseline = summaries[0]  # E0 NoPrefetcher

        # 自检（timed 模式下 Oracle 也可能“来不及”，不再要求 Recall=1）
        if args.prefetch_timing == "ideal":
            sanity_check(summaries[0], summaries[1])
        else:
            print("\n已跳过 strict sanity_check（prefetch_timing=timed）")

        # 打印所有结果
        for s in summaries:
            print_summary(s, baseline)

        # 打印对比表
        print(f"\n\n{'─'*55}")
        print(f"  {'预取器':<10} {'召回率':>8} {'精确率':>8} {'代价(µs)':>14} {'加速比':>8} {'节省%':>8}")
        print(f"{'─'*55}")
        for s in summaries:
            spd = s.speedup_vs(baseline)
            saved_pct = (baseline.total_cost_us - s.total_cost_us) / baseline.total_cost_us * 100
            print(
                f"  {s.prefetcher_name:<10} "
                f"{s.recall:>8.4f} "
                f"{s.precision:>8.4f} "
                f"{s.total_cost_us:>14,.0f} "
                f"{spd:>8.4f}x "
                f"{saved_pct:>7.2f}%"
            )

        output_path = str(Path(args.output_dir) / "simulation_results.csv")
        save_results(summaries, output_path, baseline)
        return

    # ── 单次运行 ───────────────────────────────────────────────────────────
    print(f"运行单次仿真：prefetcher={args.prefetcher}")
    pf = make_prefetcher(
        args.prefetcher,
        args.model,
        args.hybrid_gate_rate,
        args.use_gpu,
        args.gpu_device_id,
        args.slow_batch_size,
    )
    s = run_simulation(
        pf, args.data, args.data_mode, args.block_size, args.max_blocks, args.max_txs,
        args.block_number_field, args.tx_index_field,
        args.t_hit_ns, args.t_miss_us,
        prefetch_timing=args.prefetch_timing,
        t_prefetch_us=args.t_prefetch_us,
        prefetch_concurrency=args.prefetch_concurrency,
        queue_delay_us=args.queue_delay_us,
        tx_exec_us_per_slot=args.tx_exec_us_per_slot,
        tx_exec_us_base=args.tx_exec_us_base,
        progress_every_txs=args.progress_every_txs,
        verbose=verbose,
    )
    print_summary(s)

    output_path = str(Path(args.output_dir) / f"sim_{args.prefetcher}.csv")
    save_results([s], output_path, s)


if __name__ == "__main__":
    main()
