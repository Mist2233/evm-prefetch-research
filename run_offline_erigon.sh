#!/bin/bash

# ================= 配置区 =================
# Erigon 可执行文件路径 (指向软链接，方便切换版本)
# 记得在 workspace 下执行: ln -sfn erigon-research erigon-target
ERIGON_BIN="$HOME/workspace/erigon-target/build/bin/erigon"


# 数据目录路径 (1.7T 数据所在位置)
DATA_DIR="$HOME/blockchain-data/mainnet"

# RPC 端口配置 (默认 8545, 防止端口冲突可以提取出来)
RPC_PORT=8545
# =========================================

echo "🚀 Starting Erigon in OFFLINE mode..."
echo "📂 Binary:  $ERIGON_BIN"
echo "💾 DataDir: $DATA_DIR"
echo "----------------------------------------"

# 检查可执行文件是否存在，防止路径错误
if [ ! -f "$ERIGON_BIN" ]; then
    echo "❌ Error: Erigon binary not found at $ERIGON_BIN"
    echo "   Did you forget to build it? Or is the symlink broken?"
    exit 1
fi

# 启动命令
"$ERIGON_BIN" \
  --datadir "$DATA_DIR" \
  --prune.mode=archive \
  --maxpeers 0 \
  --nodiscover \
  --externalcl \
  --caplin.checkpoint-sync.disable \
  --no-downloader \
  --http \
  --http.api=eth,debug,net,web3,trace \
  --verbosity 3 \
  --http.port $RPC_PORT | tee erigon_output.log