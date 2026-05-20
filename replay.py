import sys
import json
import urllib.request
import time
import os
from tqdm import tqdm

# 配置 Erigon RPC 地址
RPC_URL = "http://localhost:8545"
# 使用 callTracer 因为它比默认的 struct logger 更轻量且足以触发执行
DEFAULT_TRACER = "callTracer"
# 输出文件路径 (Erigon 工作目录下的文件)
OUTPUT_FILE = "erigon_tx_trace.jsonl"

def rpc_call(method, params, id=1):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": id
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(RPC_URL, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {"error": str(e)}

def get_block_tx_count(block_num):
    """
    Returns the transaction count for a block.
    """
    res = rpc_call("eth_getBlockTransactionCountByNumber", [hex(block_num)])
    if 'result' in res and res['result']:
        return int(res['result'], 16)
    return 0

def get_block_transactions(block_num):
    # 获取区块内的所有交易哈希
    res = rpc_call("eth_getBlockByNumber", [hex(block_num), False])
    if 'result' in res and res['result']:
        return res['result']['transactions']
    return []

def replay_transaction(tx_hash, pbar=None):
    # 调用 debug_traceTransaction 触发 Erigon 端的 TraceTx 函数
    # 我们的数据捕获逻辑（Hook）就埋点在 TraceTx 中
    params = [tx_hash, {"tracer": DEFAULT_TRACER}]
    start_time = time.time()
    res = rpc_call("debug_traceTransaction", params)
    duration = time.time() - start_time
    
    if 'error' in res:
        msg = f"[-] Error replaying {tx_hash}: {res['error']}"
        if pbar:
            pbar.write(msg)
        else:
            print(msg)
        return False
    elif 'result' in res:
        # Success - suppress output to avoid spamming, rely on progress bar
        # We can write a debug message here if needed
        # pbar.write(f"Success {tx_hash}")
        return True
    else:
        msg = f"[-] Unknown response for {tx_hash}: {res}"
        if pbar:
            pbar.write(msg)
        else:
            print(msg)
        return False

def check_captured_data():
    """
    检查生成的 jsonl 文件，验证新特征 input_param_1 是否存在
    """
    if not os.path.exists(OUTPUT_FILE):
        return

    print("\n--- Verifying Captured Data ---")
    try:
        with open(OUTPUT_FILE, 'r') as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1]
                data = json.loads(last_line)
                print(f"Last captured entry:")
                print(f"  From: {data.get('from')} (New Feature)")
                print(f"  To: {data.get('to')}")
                print(f"  Value: {data.get('value')} (New Feature)")
                print(f"  CodeHash: {data.get('code_hash')}")
                print(f"  Selector: {data.get('selector')}")
                print(f"  Input Param 1: {data.get('input_param_1')}")
                print(f"  Input Param 2: {data.get('input_param_2')} (New Feature)")
                print(f"  Input Param 3: {data.get('input_param_3')} (New Feature)")
                print(f"  Accessed Slots Count: {len(data.get('accessed_slots', []))}")
    except Exception as e:
        print(f"Error reading output file: {e}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 replay.py <start_block> <end_block>")
        sys.exit(1)
        
    start_block = int(sys.argv[1])
    end_block = int(sys.argv[2])
    
    print(f"Starting replay from block {start_block} to {end_block}...")
    print(f"Target Feature Set: (from, to, value, code_hash, selector, input_param_1, input_param_2, input_param_3)")
    
    # Pre-calculate total transactions for progress bar
    print("Calculating total transactions...")
    total_txs = 0
    block_tx_counts = {}
    
    # Use tqdm for the counting phase as well if range is large, but usually fast enough
    for block_num in range(start_block, end_block + 1):
        count = get_block_tx_count(block_num)
        block_tx_counts[block_num] = count
        total_txs += count
        
    print(f"Total transactions to replay: {total_txs}")
    
    # Main replay loop with progress bar
    with tqdm(total=total_txs, unit="tx") as pbar:
        for block_num in range(start_block, end_block + 1):
            pbar.set_description(f"Block {block_num}")
            
            # Skip if no txs known from pre-calc
            if block_tx_counts.get(block_num, 0) == 0:
                continue
                
            tx_hashes = get_block_transactions(block_num)
            
            for tx_hash in tx_hashes:
                replay_transaction(tx_hash, pbar)
                pbar.update(1)
                
    print(f"\nReplay completed.")
    check_captured_data()
    print(f"Full data saved to '{OUTPUT_FILE}' in Erigon's working directory.")

if __name__ == "__main__":
    main()