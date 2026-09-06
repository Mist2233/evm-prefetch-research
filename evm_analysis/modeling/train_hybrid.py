import os
import json
import joblib
import numpy as np
import pandas as pd
from collections import defaultdict
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MultiLabelBinarizer
from lightgbm import LGBMClassifier
from sklearn.multioutput import MultiOutputClassifier

DATA_PATH = '/home/tianyumao/workspace/transaction-replay/erigon_tx_trace.jsonl'
MODEL_DIR = '/home/tianyumao/workspace/transaction-replay/evm_analysis/models'
RANDOM_STATE = 42
UNION_SIZE_THRESHOLD = 152  # 95% of (to, selector) fall under this
TOP_K_SLOTS = 1000

def load_data(path):
    data = []
    with open(path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            data.append(json.loads(line))
    return pd.DataFrame(data)

def calc_metrics(y_t, y_p):
    total_true = sum(len(set(t)) for t in y_t)
    total_pred = sum(len(set(p)) for p in y_p)
    total_hit = sum(len(set(t).intersection(set(p))) for t, p in zip(y_t, y_p))
    exact_matches = sum(1 for t, p in zip(y_t, y_p) if set(t) == set(p))

    recall = total_hit / total_true if total_true > 0 else 0
    precision = total_hit / total_pred if total_pred > 0 else 0
    em = exact_matches / len(y_t) if len(y_t) > 0 else 0
    return recall, precision, em

def main():
    print("Loading Transactions In...")
    df = load_data(DATA_PATH)

    for col in ['to', 'code_hash', 'selector', 'input_param_1', 'input_param_2', 'input_param_3', 'from', 'value']:
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].fillna('').astype(str)

    df = df[df['selector'] != '0x'].copy()
    df['accessed_slots'] = df['accessed_slots'].apply(lambda x: x if isinstance(x, list) else [])
    print(f"Data size after filtering: {len(df)}")

    # 1. Label Encoders
    print("Encoding features...")
    encoders = {}
    for col in ['to', 'code_hash', 'selector', 'input_param_1', 'input_param_2', 'input_param_3', 'from', 'value']:
        le = LabelEncoder()
        df[f'f_{col}'] = le.fit_transform(df[col])
        encoders[col] = le

    feature_cols = ['f_to', 'f_selector', 'f_input_param_1', 'f_input_param_2', 'f_input_param_3', 'f_code_hash', 'f_from', 'f_value']

    # 2. Train/Test Split
    df_train, df_test = train_test_split(df, test_size=0.2, random_state=RANDOM_STATE)
    print(f"Train size: {len(df_train)}, Test size: {len(df_test)}")

    # 3. Build Pattern Table (Hash Map)
    print("\nBuilding Pattern Table (Hash Map)...")
    to_sel_slots = defaultdict(set)
    for _, row in df_train.iterrows():
        to_sel_slots[(row['to'], row['selector'])].update(row['accessed_slots'])

    pattern_table = {}
    offline_keys = set()
    for k, v in to_sel_slots.items():
        if len(v) <= UNION_SIZE_THRESHOLD:
            pattern_table[k] = list(v)
        else:
            offline_keys.add(k)

    print(f"Pattern table entries: {len(pattern_table)} (simple pattern keys)")
    print(f"Offline-route keys: {len(offline_keys)} (complex pattern keys)")

    # 4. Prepare Offline Path Data for LightGBM
    df_train_offline = df_train[df_train.apply(lambda x: (x['to'], x['selector']) in offline_keys, axis=1)]
    print(f"\nOffline Path Training Samples: {len(df_train_offline)}")

    # Extract Top K slots strictly from the offline path training data
    slot_counts = defaultdict(int)
    for slots in df_train_offline['accessed_slots']:
        for s in slots:
            slot_counts[s] += 1
    top_slots = set([s for s, _ in sorted(slot_counts.items(), key=lambda x: x[1], reverse=True)[:TOP_K_SLOTS]])

    # Filter targets to only top K slots for the ML model
    df_train_offline_y = df_train_offline['accessed_slots'].apply(lambda slots: [s for s in slots if s in top_slots])

    mlb = MultiLabelBinarizer(classes=list(top_slots))
    y_train_offline = mlb.fit_transform(df_train_offline_y)
    X_train_offline = df_train_offline[feature_cols]

    # 5. Train Classification Model (LightGBM)
    print("Training Classification Model (LightGBM)...")
    base_lgbm = LGBMClassifier(
        n_estimators=30,
        learning_rate=0.1,
        max_depth=10,
        random_state=RANDOM_STATE,
        n_jobs=4,
        verbose=-1
    )
    model = MultiOutputClassifier(base_lgbm, n_jobs=4)
    model.fit(X_train_offline, y_train_offline)

    # Save Model
    save_data = {
        'fast_path_dict': pattern_table,  # pickle key kept for backward compatibility
        'model': model,
        'mlb': mlb,
        'encoders': encoders,
        'feature_cols': feature_cols
    }
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(save_data, os.path.join(MODEL_DIR, 'evm_model_hybrid_v1.pkl'))
    print("\nModel saved successfully!")

    # 6. Evaluate on Test Set
    print("\nEvaluating on Test Set...")
    is_table_hit = df_test.apply(lambda x: (x['to'], x['selector']) in pattern_table, axis=1)

    df_test_hit = df_test[is_table_hit].copy()
    df_test_miss = df_test[~is_table_hit].copy()

    # Online Path (Hash Table Lookup)
    table_preds = df_test_hit.apply(lambda x: pattern_table[(x['to'], x['selector'])], axis=1).tolist()

    # Offline Path (LightGBM Prediction)
    if len(df_test_miss) > 0:
        X_test_offline = df_test_miss[feature_cols]
        ml_preds_sparse = model.predict(X_test_offline)
        offline_preds = list(mlb.inverse_transform(ml_preds_sparse))
    else:
        offline_preds = []

    y_true_hit = df_test_hit['accessed_slots'].tolist()
    y_true_miss = df_test_miss['accessed_slots'].tolist()

    rec_hit, prec_hit, em_hit = calc_metrics(y_true_hit, table_preds)
    rec_miss, prec_miss, em_miss = calc_metrics(y_true_miss, offline_preds)
    rec_all, prec_all, em_all = calc_metrics(y_true_hit + y_true_miss, table_preds + offline_preds)

    print("\n" + "="*40)
    print("=== Model Evaluation ===")
    print("="*40)
    print(f"Test Set Data Routed to Online Path: {len(y_true_hit) / len(df_test):.2%}")
    print("-" * 40)
    print(f"1. Online Path (Hash Map) - {len(y_true_hit)} txs")
    print(f"   Recall:    {rec_hit:.2%}")
    print(f"   Precision: {prec_hit:.2%}")
    print(f"   Exact M:   {em_hit:.2%}")
    print("-" * 40)
    print(f"2. Offline Path (LightGBM) - {len(y_true_miss)} txs")
    print(f"   Recall:    {rec_miss:.2%}")
    print(f"   Precision: {prec_miss:.2%}")
    print(f"   Exact M:   {em_miss:.2%}")
    print("-" * 40)
    print(f"3. Overall Unified System - {len(df_test)} txs")
    print(f"   Recall:    {rec_all:.2%}")
    print(f"   Precision: {prec_all:.2%}")
    print(f"   Exact M:   {em_all:.2%}")
    print("========================================")

if __name__ == "__main__":
    main()
