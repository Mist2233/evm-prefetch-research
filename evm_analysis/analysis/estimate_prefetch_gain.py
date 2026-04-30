"""
Rough latency models: map (recall, precision) to expected speedup on storage access.

Two baselines:

1) IID / all-miss reference (legacy, pessimistic baseline):
       E[T] = recall*t_hit + (1-recall)*t_miss
   vs pure cold t_miss per access.

2) Block-local first-touch (Erigon-style intra_block_state):
   Within a block, state_objects is not cleared: the *first* touch of each distinct
   storage slot in execution order costs t_miss; later touches to the *same* slot
   cost t_hit. Prefetch mainly converts "first touches" from miss to hit if the slot
   was warmed before first use.

   M = total SLOAD/SSTORE (or traced storage accesses) in the block
   U = number of distinct slots that appear (equivalently: count of first-touch events)
   Baseline time  ≈ U * t_miss + (M - U) * t_hit
   With prefetch: recall r applies to *first-touch* events we care about — if r is the
   fraction of first touches correctly prefetched before use:
       Time ≈ r*U*t_hit + (1-r)*U*t_miss + (M-U)*t_hit
   Saved on baseline: U*r*(t_miss - t_hit)

   Align offline ML recall with this: ideally define positives over first-touch
   events per block, not raw duplicate-heavy access lists.

This does NOT substitute for profiling Erigon.

Usage:
  python estimate_prefetch_gain.py
  python estimate_prefetch_gain.py --model iid --recall 0.23
  python estimate_prefetch_gain.py --model block-first-touch --recall 0.23 \\
      --total-accesses 100000 --unique-first-accesses 12000
"""

from __future__ import annotations

import argparse

T_HIT_NS = 30.0
T_MISS_US = 3.0


def ns_to_us(x_ns: float) -> float:
    return x_ns / 1000.0


def expected_time_per_needed_access(
    recall: float,
    t_hit_ns: float,
    t_miss_us: float,
) -> float:
    t_hit_us = ns_to_us(t_hit_ns)
    return recall * t_hit_us + (1.0 - recall) * t_miss_us


def speedup_vs_cold(
    recall: float,
    t_hit_ns: float,
    t_miss_us: float,
) -> float:
    cold = t_miss_us
    warm = expected_time_per_needed_access(recall, t_hit_ns, t_miss_us)
    if warm <= 0:
        return float("inf")
    return cold / warm


def block_first_touch_times(
    recall: float,
    m_total: int,
    u_unique: int,
    t_hit_ns: float,
    t_miss_us: float,
) -> tuple[float, float, float]:
    """
    Returns (baseline_us, with_prefetch_us, speedup_factor).
    u_unique must be <= m_total.
    """
    if u_unique > m_total:
        raise ValueError("unique-first-accesses cannot exceed total-accesses")
    t_hit_us = ns_to_us(t_hit_ns)
    r = recall
    repeat = m_total - u_unique
    baseline = u_unique * t_miss_us + repeat * t_hit_us
    with_pref = r * u_unique * t_hit_us + (1.0 - r) * u_unique * t_miss_us + repeat * t_hit_us
    if with_pref <= 0:
        return baseline, with_pref, float("inf")
    return baseline, with_pref, baseline / with_pref


def run_iid(args):
    r, prec = args.recall, args.precision
    t_hit_ns, t_miss = args.t_hit_ns, args.t_miss_us
    e_per = expected_time_per_needed_access(r, t_hit_ns, t_miss)
    su = speedup_vs_cold(r, t_hit_ns, t_miss)
    wasted = args.wasted_cost_ratio * (1.0 - prec) * t_miss

    print("=== Model: IID vs all-miss baseline (per access) ===")
    print(f"  t_hit = {t_hit_ns} ns  (~{ns_to_us(t_hit_ns):.4f} µs)")
    print(f"  t_miss = {t_miss} µs")
    print(f"  recall = {r:.4f}")
    print()
    print(f"  E[T_access] = recall*t_hit + (1-recall)*t_miss = {e_per:.4f} µs")
    print(f"  vs all-miss baseline ({t_miss} µs): speedup ≈ {su:.2f}x")
    print()
    print(f"  Illustrative tx with {args.n_accesses} accesses (IID):")
    print(f"    baseline wall ≈ {args.n_accesses * t_miss:.2f} µs")
    print(f"    with prefetch model ≈ {args.n_accesses * e_per:.2f} µs")
    if wasted > 0:
        print(f"  + optional wasted-prefetch term ≈ {wasted:.4f} µs per access")
    print()
    print("  Note: pessimistic if real baseline already mixes hit/miss.")


def run_block(args):
    r = args.recall
    t_hit_ns, t_miss = args.t_hit_ns, args.t_miss_us
    m, u = args.total_accesses, args.unique_first_accesses
    t_hit_us = ns_to_us(t_hit_ns)

    baseline, with_pref, speedup = block_first_touch_times(r, m, u, t_hit_ns, t_miss)
    saved = u * r * (t_miss - t_hit_us)

    print("=== Model: block-local first-touch (intra_block_state not cleared) ===")
    print("  Assumption: first touch of each distinct slot in the block = t_miss;")
    print("              later touches to the same slot = t_hit.")
    print()
    print(f"  M = total storage accesses in block:     {m}")
    print(f"  U = distinct slots (first-touch events): {u}")
    print(f"  repeat touches (M - U):                  {m - u}")
    print(f"  t_hit = {t_hit_ns} ns, t_miss = {t_miss} µs, recall (on first touches) = {r:.4f}")
    print()
    print(f"  Baseline time ≈ U*t_miss + (M-U)*t_hit = {baseline:.2f} µs")
    print(f"  With prefetch ≈ r*U*t_hit + (1-r)*U*t_miss + (M-U)*t_hit = {with_pref:.2f} µs")
    print(f"  Time saved (first-touch only) ≈ U*r*(t_miss - t_hit) = {saved:.2f} µs")
    print(f"  Speedup vs baseline ≈ {speedup:.4f}x")
    print()
    print("  Align ML recall: measure on *first-touch* events per block when possible.")
    print("  If prefetch is late, first touch may still miss — r is an upper bound.")


def main():
    p = argparse.ArgumentParser(
        description="Estimate storage-access latency gain from prefetch recall.",
    )
    p.add_argument(
        "--model",
        choices=("iid", "block-first-touch"),
        default="block-first-touch",
        help="iid: vs all-miss per access; block-first-touch: Erigon block baseline (default).",
    )
    p.add_argument("--recall", type=float, default=0.23, help="Recall [0,1]")
    p.add_argument(
        "--precision",
        type=float,
        default=0.68,
        help="Precision (iid model only; optional wasted cost)",
    )
    p.add_argument("--n-accesses", type=int, default=16, help="[iid] accesses per tx")
    p.add_argument("--t-hit-ns", type=float, default=T_HIT_NS)
    p.add_argument("--t-miss-us", type=float, default=T_MISS_US)
    p.add_argument(
        "--wasted-cost-ratio",
        type=float,
        default=0.0,
        help="[iid] optional penalty using precision",
    )
    p.add_argument(
        "--total-accesses",
        type=int,
        default=100_000,
        help="[block] M: total traced storage accesses in one block",
    )
    p.add_argument(
        "--unique-first-accesses",
        type=int,
        default=12_000,
        help="[block] U: distinct slots (first appearance count)",
    )
    args = p.parse_args()

    if args.model == "iid":
        run_iid(args)
    else:
        run_block(args)


if __name__ == "__main__":
    main()
