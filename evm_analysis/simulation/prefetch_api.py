"""
预取策略接口层。

提供四种预取器，对应计划书中的 E0–E3 实验组：
  NoPrefetcher    (E0) 无预取基线
  OraclePrefetcher(E1) 理想上界（知道真实 accessed_slots）
  RuleBasePrefetcher(E2) 仅 fast_path_dict 查表
  HybridPrefetcher  (E3) 完整混合模型（查表 + LightGBM 慢路径）

所有 Prefetcher 只暴露一个方法：predict(tx: dict) -> list[str]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

_MODEL_CACHE: dict[str, dict] = {}


class BasePrefetcher(ABC):
    name: str = "base"

    @abstractmethod
    def predict(self, tx: dict) -> list[str]:
        """给定一条交易记录，返回预测的 slot 列表（去重顺序不保证）。"""
        ...


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


# ── E2：规则查表（fast_path_dict 单独贡献） ─────────────────────────────────

class RuleBasePrefetcher(BasePrefetcher):
    """仅使用 fast_path_dict，不调用 ML 模型。"""
    name = "rule"

    def __init__(self, fast_path_dict: dict[tuple, list[str]]):
        self.fast_path_dict = fast_path_dict

    def predict(self, tx: dict) -> list[str]:
        key = (tx.get("to", ""), tx.get("selector", ""))
        return self.fast_path_dict.get(key, [])


# ── E3：混合预取器（fast_path_dict + LightGBM 慢路径） ──────────────────────

class HybridPrefetcher(BasePrefetcher):
    """
    复用 evm_model_hybrid_v1.pkl 中保存的 fast_path_dict + LightGBM 模型。
    推理逻辑与 modeling/predict_hybrid.py 保持一致，但为仿真场景做了适配：
      - 对 JSONL 中缺失的字段（input_param_2/3、from、value）自动填充空串
      - 未知 label 值使用 encoder 第 0 类作为 fallback
    """
    name = "hybrid"

    def __init__(self, saved: dict):
        self.fast_path_dict: dict = saved["fast_path_dict"]
        self.model = saved["model"]
        self.mlb = saved["mlb"]
        self.encoders: dict = saved["encoders"]
        self.feature_cols: list[str] = saved["feature_cols"]

        # 预先计算每个编码器的 fallback（第 0 类的编码值，始终为 0）
        self._fallback: dict[str, int] = {col: 0 for col in self.encoders}
        # 预先构建 known-classes 集合，避免每次推理重建
        self._known: dict[str, set] = {
            col: set(le.classes_) for col, le in self.encoders.items()
        }

    @classmethod
    def from_model_path(cls, model_path: str) -> "HybridPrefetcher":
        import joblib
        saved = joblib.load(model_path)
        return cls(saved)

    def _encode_row(self, tx: dict) -> dict:
        """将一条交易记录编码为模型所需的特征字典。"""
        encoded = {}
        field_map = {
            "f_to": "to",
            "f_code_hash": "code_hash",
            "f_selector": "selector",
            "f_input_param_1": "input_param_1",
            "f_input_param_2": "input_param_2",
            "f_input_param_3": "input_param_3",
            "f_from": "from",
            "f_value": "value",
        }
        for feat_col, raw_col in field_map.items():
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
        key = (tx.get("to", ""), tx.get("selector", ""))

        # 快路径：O(1) 查表
        if key in self.fast_path_dict:
            return self.fast_path_dict[key]

        # 慢路径：LightGBM 推理
        import pandas as pd
        encoded = self._encode_row(tx)
        X = pd.DataFrame([{col: encoded.get(col, 0) for col in self.feature_cols}])
        pred_sparse = self.model.predict(X)
        result = self.mlb.inverse_transform(pred_sparse)
        return list(result[0]) if result else []


# ── 工厂函数 ─────────────────────────────────────────────────────────────────

def make_prefetcher(name: str, model_path: str | None = None) -> BasePrefetcher:
    """
    按名称构建预取器。name 对应 CLI --prefetcher 参数：
      none / oracle / rule / hybrid
    rule 和 hybrid 都需要 model_path 指向 evm_model_hybrid_v1.pkl。
    """
    if name == "none":
        return NoPrefetcher()
    if name == "oracle":
        return OraclePrefetcher()
    if name in ("rule", "hybrid"):
        if not model_path or not Path(model_path).exists():
            raise FileNotFoundError(
                f"--model 路径不存在或未指定（当前值：{model_path!r}），"
                "rule/hybrid 预取器需要 evm_model_hybrid_v1.pkl"
            )
        saved = _MODEL_CACHE.get(model_path)
        if saved is None:
            import joblib
            saved = joblib.load(model_path)
            _MODEL_CACHE[model_path] = saved
        if name == "rule":
            return RuleBasePrefetcher(saved["fast_path_dict"])
        return HybridPrefetcher(saved)
    raise ValueError(f"未知 prefetcher 名称：{name!r}，可选：none/oracle/rule/hybrid")
