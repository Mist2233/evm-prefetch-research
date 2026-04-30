import json
import os
from collections import Counter

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MultiLabelBinarizer
from sklearn.tree import DecisionTreeClassifier

TOP_K_SLOTS_LIST = [1000, 5000, 10000]
TOP_N_PREFETCH_LIST = [5, 10, 20]
DATA_PATH = '/home/tianyumao/workspace/transaction-replay/erigon_tx_trace.jsonl'
MODEL_DIR = '/home/tianyumao/workspace/transaction-replay/evm_analysis/models'
RANDOM_STATE = 42


def load_data(file_path):
    data = []
    print(f"Loading data from {file_path}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return pd.DataFrame(data)


def build_prob_matrix(model, X_input):
    proba_outputs = model.predict_proba(X_input)
    n_samples = X_input.shape[0]
    n_labels = len(proba_outputs)
    prob_matrix = np.zeros((n_samples, n_labels), dtype=float)
    model_classes = model.classes_
    for i, probs in enumerate(proba_outputs):
        classes_i = model_classes[i]
        if probs.shape[1] == 1:
            prob_matrix[:, i] = 1.0 if classes_i[0] == 1 else 0.0
        else:
            class1_idx = np.where(classes_i == 1)[0][0]
            prob_matrix[:, i] = probs[:, class1_idx]
    return prob_matrix


def predict_top_n(prob_matrix, top_n):
    n_samples, n_labels = prob_matrix.shape
    y_pred_top_n = np.zeros((n_samples, n_labels), dtype=int)
    top_n = min(top_n, n_labels)
    if top_n > 0:
        top_indices = np.argpartition(prob_matrix, -top_n, axis=1)[:, -top_n:]
        row_indices = np.arange(n_samples)[:, None]
        y_pred_top_n[row_indices, top_indices] = 1
    return y_pred_top_n


def predict_max_default_top_n(y_pred_default, prob_matrix, top_n):
    y_pred_hybrid = y_pred_default.copy().astype(int)
    if top_n <= 0:
        return y_pred_hybrid
    n_samples, n_labels = prob_matrix.shape
    top_n = min(top_n, n_labels)
    sorted_indices = np.argsort(-prob_matrix, axis=1)
    for i in range(n_samples):
        current_count = int(y_pred_hybrid[i].sum())
        if current_count >= top_n:
            continue
        needed = top_n - current_count
        candidates = sorted_indices[i]
        added = 0
        for idx in candidates:
            if y_pred_hybrid[i, idx] == 0:
                y_pred_hybrid[i, idx] = 1
                added += 1
                if added >= needed:
                    break
    return y_pred_hybrid


def calculate_metrics(y_true, y_pred, total_slots_test):
    exact_match = np.all(y_true == y_pred, axis=1).mean()
    true_positives = np.logical_and(y_true, y_pred).sum()
    predicted_positives = y_pred.sum()
    actual_positives_topk = y_true.sum()
    actual_positives_total = total_slots_test.sum()
    precision = true_positives / predicted_positives if predicted_positives > 0 else 0
    recall_topk = true_positives / actual_positives_topk if actual_positives_topk > 0 else 0
    recall_total = true_positives / actual_positives_total if actual_positives_total > 0 else 0
    return recall_topk, recall_total, precision, exact_match


def main():
    print("Loading Transactions In...")
    df = load_data(DATA_PATH)
    
    # Fill NA and default values
    for col in ['to', 'code_hash', 'selector', 'input_param_1', 'input_param_2', 'input_param_3', 'from', 'value']:
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].fillna('').astype(str)

    print(f"Original data size: {len(df)}")
    df = df[df['selector'] != '0x'].copy()
    print(f"Data size after filtering '0x' selector: {len(df)}")
    df['accessed_slots'] = df['accessed_slots'].apply(lambda x: x if isinstance(x, list) else [])

    le_to = LabelEncoder()
    le_code_hash = LabelEncoder()
    le_sel = LabelEncoder()
    le_param = LabelEncoder()
    le_param2 = LabelEncoder()
    le_param3 = LabelEncoder()
    le_from = LabelEncoder()
    le_value = LabelEncoder()

    df['f_to'] = le_to.fit_transform(df['to'])
    df['f_code_hash'] = le_code_hash.fit_transform(df['code_hash'])
    df['f_sel'] = le_sel.fit_transform(df['selector'])
    df['f_param'] = le_param.fit_transform(df['input_param_1'])
    df['f_param2'] = le_param2.fit_transform(df['input_param_2'])
    df['f_param3'] = le_param3.fit_transform(df['input_param_3'])
    df['f_from'] = le_from.fit_transform(df['from'])
    df['f_value'] = le_value.fit_transform(df['value'])
    
    X = df[['f_to', 'f_code_hash', 'f_sel', 'f_param', 'f_param2', 'f_param3', 'f_from', 'f_value']]
    total_slots_count = df['accessed_slots'].apply(len).values

    all_slots = [slot for slots in df['accessed_slots'] for slot in slots]
    slot_counts = Counter(all_slots)
    print(f"Total unique slots: {len(slot_counts)}")

    rows = []
    for top_k in TOP_K_SLOTS_LIST:
        print(f"\nTraining with TOP_K_SLOTS={top_k}")
        top_slots = set(slot for slot, _ in slot_counts.most_common(top_k))
        filtered_slots = df['accessed_slots'].apply(lambda slots: [s for s in slots if s in top_slots])
        mlb = MultiLabelBinarizer()
        y = mlb.fit_transform(filtered_slots)
        print(f"Shape of y: {y.shape}")

        FEATURE_CONFIGS = [
            {'name': 'to+selector+param1+codehash', 'features': ['f_to', 'f_sel', 'f_param', 'f_code_hash']},
            {'name': 'to+sel+params+codehash+from+value', 'features': ['f_to', 'f_sel', 'f_param', 'f_param2', 'f_param3', 'f_code_hash', 'f_from', 'f_value']}
        ]

        for fc in FEATURE_CONFIGS:
            f_name = fc['name']
            f_cols = fc['features']
            print(f"  Training with features: {f_name}")
            
            X_curr = df[f_cols]
            X_train, X_test, y_train, y_test, _, total_slots_test = train_test_split(
                X_curr, y, total_slots_count, test_size=0.2, random_state=RANDOM_STATE
            )

            model = DecisionTreeClassifier(max_depth=10, random_state=RANDOM_STATE)
            model.fit(X_train, y_train)

            model_path = os.path.join(MODEL_DIR, f'evm_model_k{top_k}_{f_name.replace("+", "_")}.pkl')
            save_data = {
                'model': model,
                'le_to': le_to,
                'le_code_hash': le_code_hash,
                'le_sel': le_sel,
                'le_param': le_param,
                'le_param2': le_param2,
                'le_param3': le_param3,
                'le_from': le_from,
                'le_value': le_value,
                'mlb': mlb,
                'top_slots': top_slots,
                'features_used': f_cols
            }
            joblib.dump(save_data, model_path)
            # Only save the most complete model as evm_model_v1.pkl
            if top_k == 1000 and f_name == 'to+sel+params+codehash+from+value':
                joblib.dump(save_data, os.path.join(MODEL_DIR, 'evm_model_v1.pkl'))

            y_pred = model.predict(X_test)
            prob_matrix = build_prob_matrix(model, X_test)
            rec_topk, rec_total, prec, em = calculate_metrics(y_test, y_pred, total_slots_test)
            rows.append((top_k, f_name, 'default', '-', rec_topk, rec_total, prec, em))

            for top_n in TOP_N_PREFETCH_LIST:
                y_pred_top_n = predict_top_n(prob_matrix, top_n)
                rec_topk_n, rec_total_n, prec_n, em_n = calculate_metrics(y_test, y_pred_top_n, total_slots_test)
                rows.append((top_k, f_name, 'top_n', str(top_n), rec_topk_n, rec_total_n, prec_n, em_n))
                y_pred_hybrid = predict_max_default_top_n(y_pred, prob_matrix, top_n)
                rec_topk_h, rec_total_h, prec_h, em_h = calculate_metrics(y_test, y_pred_hybrid, total_slots_test)
                rows.append((top_k, f_name, 'max(default,top_n)', str(top_n), rec_topk_h, rec_total_h, prec_h, em_h))

    print("\n| K | Features | Strategy | N | Top-K Recall | Total Recall | Precision | Exact Match |")
    print("|---:|:---|:---|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | "
            f"{row[4]:.2%} | {row[5]:.2%} | {row[6]:.2%} | {row[7]:.2%} |"
        )


if __name__ == "__main__":
    main()
