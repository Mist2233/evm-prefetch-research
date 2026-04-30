#!/usr/bin/env python3
"""Collect opcode statistics for router contracts using Erigon."""
import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from web3 import Web3

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    tqdm = None

TARGET_CONTRACTS = {
    "0x881d40237659c251811cec9c364ef91dc08d300c": "Metamask Swap Router",
    "0x66a9893cc07d91d95644aedd05d03f95e1dba8af": "Uniswap V4 Universal Router",
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2 Router 2",
    "0x111111125421ca6dc452d289314280a0f8842a65": "1inch Aggregation Router V6",
    "0x2e1dee213ba8d7af0934c49a23187babeaca8764": "OKX DEX Router",
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Aggregation Router V5",
}

LOWER_TARGETS = {addr.lower(): label for addr, label in TARGET_CONTRACTS.items()}

# Erigon-compatible tracer (simplified)
OPCODE_TRACER_SCRIPT = """
{
    data: {counts: {}},
    step: function(log) {
        var op = log.op.toString();
        this.data.counts[op] = (this.data.counts[op] || 0) + 1;
    },
    fault: function(log) {},
    result: function() {
        return this.data;
    }
}
""".strip()


@dataclass
class TraceResult:
    tx_hash: str
    block_number: int
    timestamp: int
    target: str
    opcode_counts: Dict[str, int]
    gas_used: Optional[int]
    from_address: str
    to_address: str

    def to_json(self) -> Dict[str, Any]:
        return {
            "txHash": self.tx_hash,
            "blockNumber": self.block_number,
            "timestamp": self.timestamp,
            "target": self.target,
            "opcodeCounts": self.opcode_counts,
            "gasUsed": self.gas_used,
            "from": self.from_address,
            "to": self.to_address,
        }


def configure_logging(log_path: Path, enable_logging: bool = False, verbose: bool = False) -> None:
    """Configure logging to file only, with optional console output."""
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    if enable_logging:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # File handler - always detailed
        file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(file_handler)
    else:
        # Add NullHandler to prevent warnings/errors from going to stderr (lastResort)
        # when no other handlers are present.
        logger.addHandler(logging.NullHandler())
    
    # Console handler - only for errors or if verbose
    if verbose:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(console_handler)


def build_web3(rpc_url: str) -> Web3:
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 300}))
    if not w3.is_connected():
        raise RuntimeError(f"Cannot connect to {rpc_url}")
    return w3


def debug_trace_transaction(w3: Web3, tx_hash: str) -> Dict[str, Any]:
    params = {"tracer": OPCODE_TRACER_SCRIPT, "timeout": "180s"}
    return w3.manager.request_blocking("debug_traceTransaction", [tx_hash, params])


def scan_blocks(
    w3: Web3,
    start_block: int,
    end_block: int,
    max_traces: Optional[int] = None,
    show_progress: bool = True,
    block_interval: int = 1,
) -> Iterable[TraceResult]:
    logging.info("Scanning blocks %s -> %s", start_block, end_block)
    traces_collected = 0
    total_blocks = len(range(start_block, end_block + 1, block_interval))
    
    # Progress bar setup
    if show_progress and HAS_TQDM:
        pbar = tqdm(
            total=max_traces if max_traces else None,
            desc="📊 Collecting traces",
            unit="tx",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            position=0,
            leave=True,
        )
        block_pbar = tqdm(
            total=total_blocks,
            desc="🔍 Scanning blocks",
            unit="blk",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}",
            position=1,
            leave=True,
        )
    else:
        pbar = None
        block_pbar = None
        if show_progress:
            print(f"📊 Collecting traces (target: {max_traces if max_traces else 'unlimited'})...")

    for block_idx, block_num in enumerate(range(start_block, end_block + 1, block_interval)):
        try:
            block = w3.eth.get_block(block_num, full_transactions=True)
        except Exception as e:
            logging.warning("Failed to fetch block %s: %s", block_num, e)
            if block_pbar is not None:
                block_pbar.update(1)
            continue

        block_ts = block["timestamp"]
        for tx in block["transactions"]:
            # 实现无差别攻击，而不是回放某些特定交易
            # 如果想要回到特定交易部分，取消下面的注释即可。
            to_address = (tx.get("to") or "").lower()
            # if to_address not in LOWER_TARGETS:
            #     continue

            # target_name = LOWER_TARGETS[to_address]
            target_name = LOWER_TARGETS.get(to_address, "Other Contract")
            tx_hash = Web3.to_hex(tx["hash"])

            try:
                trace = debug_trace_transaction(w3, tx_hash)
                counts = trace.get("counts", {})
                gas_used = tx.get("gas")
            except Exception as e:
                logging.warning("Failed to trace %s: %s", tx_hash, e)
                continue

            traces_collected += 1
            logging.info(
                "✓ Trace #%s: %s (block %s, contract=%s, opcodes=%s)",
                traces_collected,
                tx_hash[:10],
                block_num,
                target_name,
                len(counts),
            )
            
            if pbar is not None:
                pbar.update(1)
                pbar.set_postfix_str(f"{target_name[:20]}")

            yield TraceResult(
                tx_hash=tx_hash,
                block_number=block_num,
                timestamp=block_ts,
                target=target_name,
                opcode_counts={op: int(val) for op, val in counts.items()},
                gas_used=int(gas_used) if gas_used else None,
                from_address=tx["from"],
                to_address=tx["to"],
            )

            if max_traces and traces_collected >= max_traces:
                logging.info("Reached max_traces=%s, stopping", max_traces)
                if pbar is not None:
                    pbar.close()
                if block_pbar is not None:
                    block_pbar.close()
                return
        
        if block_pbar is not None:
            block_pbar.update(1)
    
    if pbar is not None:
        pbar.close()
    if block_pbar is not None:
        block_pbar.close()


def aggregate_counts(traces: Iterable[TraceResult]) -> Dict[str, Dict[str, int]]:
    per_target: Dict[str, Counter[str]] = defaultdict(Counter)
    for trace in traces:
        per_target[trace.target].update(trace.opcode_counts)
    return {target: dict(counter) for target, counter in per_target.items()}


def parse_block_number(value: str) -> int:
    """Parse block number from decimal or hexadecimal string."""
    if value.startswith("0x") or value.startswith("0X"):
        return int(value, 16)
    return int(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc", required=True)
    parser.add_argument("--start-block", type=parse_block_number, required=True,
                        help="Starting block number (decimal or 0x-prefixed hex)")
    parser.add_argument("--end-block", type=parse_block_number, required=True,
                        help="Ending block number (decimal or 0x-prefixed hex)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output JSON file (will be saved in results/ directory)")
    parser.add_argument("--max-traces", type=int, default=None)
    parser.add_argument("--log-file", type=Path, default=Path("logs/trace.log"))
    parser.add_argument("--enable-logging", action="store_true", help="Enable logging to file")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed logs in console (slower)")
    parser.add_argument("--no-progress", action="store_true",
                        help="Disable progress bar")
    parser.add_argument("--block-interval", type=int, default=1,
                        help="Interval for sampling blocks (e.g., 100 means trace 1 block every 100).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(args.log_file, enable_logging=args.enable_logging, verbose=args.verbose)

    # Ensure output is in results/ directory
    output_path = args.output
    if output_path:
        if not output_path.is_absolute():
            # If relative path, put it in results/ directory
            if output_path.parts[0] != "results":
                output_path = Path("results") / output_path
    
    # Console output (not logged to file)
    print(f"🔗 Connecting to {args.rpc}...")
    w3 = build_web3(args.rpc)
    print(f"✅ Connected to chain_id={w3.eth.chain_id}")
    print(f"📍 Blocks: {args.start_block:,} -> {args.end_block:,} ({args.end_block - args.start_block + 1:,} blocks)")
    print(f"🎯 Target: {args.max_traces if args.max_traces else 'unlimited'} traces")
    print(f"📝 Logs: {args.log_file if args.enable_logging else 'Disabled'}")
    print(f"💾 Output: {output_path if output_path else 'Disabled'}")
    print()
    
    if not HAS_TQDM and not args.no_progress:
        print("💡 Tip: Install tqdm for progress bar: pip install tqdm")
        print()
    
    logging.info("Connected to chain_id=%s", w3.eth.chain_id)
    
    results = list(scan_blocks(
        w3, 
        args.start_block, 
        args.end_block, 
        args.max_traces,
        show_progress=not args.no_progress,
        block_interval=args.block_interval
    ))

    if not results:
        print("⚠️  No matching transactions found")
        logging.warning("No matching transactions found")
        return 0

    print(f"\n✅ Collected {len(results)} traces")
    logging.info("Collected %s traces", len(results))
    aggregate = aggregate_counts(results)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "range": {"startBlock": args.start_block, "endBlock": args.end_block},
                    "contracts": TARGET_CONTRACTS,
                    "transactions": [t.to_json() for t in results],
                    "aggregate": aggregate,
                },
                f,
                indent=2,
            )
        print(f"💾 Report written to {output_path}")
        logging.info("Report written to %s", output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
