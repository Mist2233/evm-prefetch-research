"""Load and merge Figure-2 metrics from evm-decision-tree-data.xlsx (per plan)."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_XLSX = BASE_DIR / 'evm-decision-tree-data.xlsx'

RENAME = {
    'K': 'k',
    'Features': 'features',
    'Strategy': 'strategy',
    'N': 'n',
    'Top-K Recall': 'recall_topk',
    'Total Recall': 'recall_total',
    'Precision': 'precision',
    'Exact Match': 'exact_match',
}


def _parse_pct(x):
    if pd.isna(x):
        return float('nan')
    if isinstance(x, (int, float)):
        v = float(x)
        return v / 100.0 if v > 1.0 else v
    s = str(x).strip().replace('%', '')
    try:
        v = float(s)
        return v / 100.0 if v > 1.0 else v
    except ValueError:
        return float('nan')


def _normalize_sheet(df: pd.DataFrame, model: str, sheet: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={k: v for k, v in RENAME.items() if k in df.columns})
    df['model'] = model
    df['sheet'] = sheet
    for col in ['recall_topk', 'recall_total', 'precision', 'exact_match']:
        if col in df.columns:
            df[col] = df[col].map(_parse_pct)
    return df


def load_figure2_from_xlsx(
    xlsx_path: os.PathLike | None = None,
) -> pd.DataFrame:
    path = Path(xlsx_path or DEFAULT_XLSX)
    if not path.is_file():
        raise FileNotFoundError(f"Missing xlsx: {path}")

    xl = pd.ExcelFile(path)
    parts = []
    # Sheet1, Sheet2: DT (different feature grids); Sheet3: LightGBM
    mapping = [
        ('Sheet1', 'DT', 'Sheet1'),
        ('Sheet2', 'DT', 'Sheet2'),
        ('Sheet3', 'LightGBM', 'Sheet3'),
    ]
    for sheet_name, model, tag in mapping:
        if sheet_name not in xl.sheet_names:
            continue
        df = pd.read_excel(path, sheet_name=sheet_name, engine='openpyxl')
        parts.append(_normalize_sheet(df, model, tag))

    if not parts:
        raise ValueError('No sheets loaded from xlsx')
    return pd.concat(parts, ignore_index=True)


def export_merged_csv(
    out_path: os.PathLike | None = None,
    xlsx_path: os.PathLike | None = None,
) -> Path:
    out_path = Path(out_path or BASE_DIR / 'figures' / 'data' / 'metrics_figure2_merged.csv')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = load_figure2_from_xlsx(xlsx_path)
    df.to_csv(out_path, index=False)
    return out_path


if __name__ == '__main__':
    p = export_merged_csv()
    print(f"Wrote {p}")
