"""
预取策略接口层。

提供四种预取器，对应论文中的实验组：
  NoPrefetcher      (E0) 无预取基线
  OraclePrefetcher  (E1) 理想上界（知道真实 accessed_slots）
  TablePrefetcher   (E2) 仅 pattern_table 查表
  MLPrefetcher      (离线增量生成) pattern_table + LightGBM 离线路径

所有 Prefetcher 只暴露一个方法：predict(tx: dict) -> list[str]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd

_MODEL_CACHE: dict[str, dict] = {}


class BasePrefetcher(ABC):
    name: str = "base"

    @abstractmethod
    def predict(self, tx: dict) -> list[str]:
        """给定一条交易记录，返回预测的 slot 列表（去重顺序不保证）。"""
        ...

    def predict_batch(self, txs: list[dict]) -> list[list[str]]:
        """批量预测默认退化为逐条预测，子类可重写以做向量化推理。"""
        return [self.predict(tx) for tx in txs]


# ── E0：无预取基线 ──────────────────────────────────────────────────────────

class NoPrefetcher(BasePrefetcher):
    name = "none"

    def predict(self, tx: dict) -> list[str]:
        return []


# ── E1：理想上界 ────────────────────────────────────────────────────────────

class OraclePrefetcher(BasePrefetcher):
    """直接返回真实 accessed_slots，代表预取完全正确的理论上界。"""
    name = "oracle"

    def predict(self, tx: dict) -> list[str]:
        return list(set(tx.get("accessed_slots", [])))


# ── E2：Hash Table 查表 ─────────────────────────────────────────────────────

class TablePrefetcher(BasePrefetcher):
    """仅使用 pattern_table 查表，不调用 ML 模型。"""
    name = "table"

    def __init__(self, pattern_table: dict[tuple, list[str]]):
        self.pattern_table = pattern_table

    def predict(self, tx: dict) -> list[str]:
        key = (tx.get("to", ""), tx.get("selector", ""))
        return self.pattern_table.get(key, [])


# ── ML 预取器（pattern_table + LightGBM 离线路径） ─────────────────────────

class MLPrefetcher(BasePrefetcher):
    """
    复用 evm_model_hybrid_v1.pkl 中保存的 pattern_table + LightGBM 模型。
    推理逻辑与 modeling/predict_hybrid.py 保持一致，但为仿真场景做了适配：
      - 对 JSONL 中缺失的字段（input_param_2/3、from、value）自动填充空串
      - 未知 label 值使用 encoder 第 0 类作为 fallback
    """
    name = "ml"
    _FIELD_MAP = (
        ("f_to", "to"),
        ("f_code_hash", "code_hash"),
        ("f_selector", "selector"),
        ("f_input_param_1", "input_param_1"),
        ("f_input_param_2", "input_param_2"),
        ("f_input_param_3", "input_param_3"),
        ("f_from", "from"),
        ("f_value", "value"),
    )

    def __init__(
        self,
        saved: dict,
        use_gpu: bool = False,
        gpu_device_id: int = 0,
        offline_batch_size: int = 1024,
    ):
        self.pattern_table: dict = saved["fast_path_dict"]  # pickle 中 key 暂时保留原名
        self.model = saved["model"]
        self.mlb = saved["mlb"]
        self.encoders: dict = saved["encoders"]
        self.feature_cols: list[str] = saved["feature_cols"]
        self.use_gpu = use_gpu
        self.gpu_device_id = gpu_device_id
        self.offline_batch_size = max(1, int(offline_batch_size))
        self._class_labels = np.asarray(self.mlb.classes_, dtype=object)

        # 预先计算每个编码器的 fallback（第 0 类的编码值，始终为 0）
        self._fallback: dict[str, int] = {col: 0 for col in self.encoders}
        # 预先构建 known-classes 集合，避免每次推理重建
        self._known: dict[str, set] = {
            col: set(le.classes_) for col, le in self.encoders.items()
        }
        self._configure_inference_device()

    @classmethod
    def from_model_path(cls, model_path: str) -> "MLPrefetcher":
        import joblib
        saved = joblib.load(model_path)
        return cls(saved)

    def _configure_inference_device(self) -> None:
        """
        为 LightGBM 子模型设置推理设备。
        默认 CPU；开启 use_gpu 时尝试切到 GPU。
        """
        target = "gpu" if self.use_gpu else "cpu"
        estimators = getattr(self.model, "estimators_", None)
        if not estimators:
            return
        for est in estimators:
            if hasattr(est, "set_params"):
                try:
                    est.set_params(device=target, gpu_device_id=self.gpu_device_id)
                except Exception:
                    # 某些构建环境不支持 GPU 参数，忽略并回退默认设备。
                    pass

    def _encode_row(self, tx: dict) -> dict:
        """将一条交易记录编码为模型所需的特征字典。"""
        encoded = {}
        for feat_col, raw_col in self._FIELD_MAP:
            col_name = raw_col  # encoder key
            if col_name not in self.encoders:
                encoded[feat_col] = 0
                continue
            le = self.encoders[col_name]
            val = str(tx.get(raw_col, "") or "")
            if val in self._known[col_name]:
                encoded[feat_col] = int(le.transform([val])[0])
            else:
                encoded[feat_col] = self._fallback[col_name]
        return encoded

    def predict(self, tx: dict) -> list[str]:
        return self.predict_batch([tx])[0]

    def _decode_sparse_predictions(self, pred_sparse) -> list[list[str]]:
        if hasattr(pred_sparse, "toarray"):
            arr = pred_sparse.toarray()
        else:
            arr = np.asarray(pred_sparse)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        out: list[list[str]] = []
        for row in arr:
            idx = np.flatnonzero(row)
            if idx.size == 0:
                out.append([])
                continue
            out.append(self._class_labels[idx].tolist())
        return out

    def predict_batch(self, txs: list[dict]) -> list[list[str]]:
        if not txs:
            return []

        predictions: list[list[str]] = [[] for _ in txs]
        offline_indices: list[int] = []
        offline_rows: list[list[int]] = []

        for idx, tx in enumerate(txs):
            key = (tx.get("to", ""), tx.get("selector", ""))
            cached = self.pattern_table.get(key)
            if cached is not None:
                predictions[idx] = cached
                continue
            offline_indices.append(idx)
            encoded = self._encode_row(tx)
            offline_rows.append([encoded.get(col, 0) for col in self.feature_cols])

        if offline_rows:
            for start in range(0, len(offline_rows), self.offline_batch_size):
                end = min(start + self.offline_batch_size, len(offline_rows))
                X = pd.DataFrame(offline_rows[start:end], columns=self.feature_cols)
                pred_sparse = self.model.predict(X)
                offline_preds = self._decode_sparse_predictions(pred_sparse)
                for idx, pred in zip(offline_indices[start:end], offline_preds):
                    predictions[idx] = pred

        return predictions


class MLGatedPrefetcher(MLPrefetcher):
    """
    MLPrefetcher 的低风险变体：
    - pattern_table 始终保留；
    - 离线路径仅按 gate_rate 触发，降低模型推理开销。
    """
    name = "ml_gated"

    def __init__(
        self,
        saved: dict,
        gate_rate: float = 0.1,
        use_gpu: bool = False,
        gpu_device_id: int = 0,
        offline_batch_size: int = 1024,
    ):
        super().__init__(
            saved,
            use_gpu=use_gpu,
            gpu_device_id=gpu_device_id,
            offline_batch_size=offline_batch_size,
        )
        if gate_rate < 0.0 or gate_rate > 1.0:
            raise ValueError(f"gate_rate 必须在 [0, 1]，当前值: {gate_rate}")
        self.gate_rate = float(gate_rate)

    def _should_run_offline_path(self, tx: dict) -> bool:
        """
        使用稳定哈希做采样门控，保证同一交易特征在多次实验中决策一致。
        """
        if self.gate_rate >= 1.0:
            return True
        if self.gate_rate <= 0.0:
            return False
        seed = "|".join(
            [
                str(tx.get("to", "")),
                str(tx.get("selector", "")),
                str(tx.get("input_param_1", "")),
                str(tx.get("input_param_2", "")),
                str(tx.get("input_param_3", "")),
                str(tx.get("value", "")),
            ]
        )
        h = hashlib.md5(seed.encode("utf-8")).hexdigest()
        sample = int(h[:8], 16) / 0xFFFFFFFF
        return sample < self.gate_rate

    def predict_batch(self, txs: list[dict]) -> list[list[str]]:
        if not txs:
            return []

        predictions: list[list[str]] = [[] for _ in txs]
        offline_indices: list[int] = []
        offline_rows: list[list[int]] = []

        for idx, tx in enumerate(txs):
            key = (tx.get("to", ""), tx.get("selector", ""))
            cached = self.pattern_table.get(key)
            if cached is not None:
                predictions[idx] = cached
                continue
            if not self._should_run_offline_path(tx):
                continue
            offline_indices.append(idx)
            encoded = self._encode_row(tx)
            offline_rows.append([encoded.get(col, 0) for col in self.feature_cols])

        if offline_rows:
            for start in range(0, len(offline_rows), self.offline_batch_size):
                end = min(start + self.offline_batch_size, len(offline_rows))
                X = pd.DataFrame(offline_rows[start:end], columns=self.feature_cols)
                pred_sparse = self.model.predict(X)
                offline_preds = self._decode_sparse_predictions(pred_sparse)
                for idx, pred in zip(offline_indices[start:end], offline_preds):
                    predictions[idx] = pred

        return predictions


# ── 工厂函数 ─────────────────────────────────────────────────────────────────

def make_prefetcher(
    name: str,
    model_path: str | None = None,
    ml_gate_rate: float = 0.1,
    use_gpu: bool = False,
    gpu_device_id: int = 0,
    offline_batch_size: int = 1024,
) -> BasePrefetcher:
    """
    按名称构建预取器。name 对应 CLI --prefetcher 参数：
      none / oracle / table / ml / ml_gated
    table/ml/ml_gated 都需要 model_path 指向 evm_model_hybrid_v1.pkl。
    """
    if name == "none":
        return NoPrefetcher()
    if name == "oracle":
        return OraclePrefetcher()
    if name in ("table", "ml", "ml_gated"):
        if not model_path or not Path(model_path).exists():
            raise FileNotFoundError(
                f"--model 路径不存在或未指定（当前值：{model_path!r}），"
                "table/ml/ml_gated 预取器需要 evm_model_hybrid_v1.pkl"
            )
        saved = _MODEL_CACHE.get(model_path)
        if saved is None:
            import joblib
            saved = joblib.load(model_path)
            _MODEL_CACHE[model_path] = saved
        if name == "table":
            return TablePrefetcher(saved["fast_path_dict"])
        if name == "ml_gated":
            return MLGatedPrefetcher(
                saved,
                gate_rate=ml_gate_rate,
                use_gpu=use_gpu,
                gpu_device_id=gpu_device_id,
                offline_batch_size=offline_batch_size,
            )
        return MLPrefetcher(
            saved,
            use_gpu=use_gpu,
            gpu_device_id=gpu_device_id,
            offline_batch_size=offline_batch_size,
        )
    raise ValueError(f"未知 prefetcher 名称：{name!r}，可选：none/oracle/table/ml/ml_gated")
