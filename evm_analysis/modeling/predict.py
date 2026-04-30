import json
import joblib
import pandas as pd
import numpy as np
import os

# Configuration
MODEL_PATH = '/home/tianyumao/workspace/transaction-replay/evm_analysis/models/evm_model_v1.pkl'
DATA_PATH = '/home/tianyumao/workspace/transaction-replay/erigon_tx_trace.jsonl'

def load_data(file_path, limit=100):
    data = []
    print(f"Loading first {limit} transactions from {file_path} for prediction demo...")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    with open(file_path, 'r') as f:
        count = 0
        for line in f:
            if line.strip():
                try:
                    data.append(json.loads(line))
                    count += 1
                    if count >= limit:
                        break
                except json.JSONDecodeError:
                    continue
    return pd.DataFrame(data)

# Load Model
print(f"Loading model from {MODEL_PATH}...")
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model file not found. Please run train.py first.")

save_data = joblib.load(MODEL_PATH)
model = save_data['model']
le_to = save_data['le_to']
le_code_hash = save_data.get('le_code_hash') # handle backward compatibility if possible
le_sel = save_data['le_sel']
le_param = save_data['le_param']
mlb = save_data['mlb']
# top_slots = save_data.get('top_slots', set()) # Optional: useful if we want to filter ground truth

# Load Data
df = load_data(DATA_PATH, limit=100)

# Preprocess Features (Handle unseen labels)
print("Preprocessing features...")
for col in ['to', 'code_hash', 'selector', 'input_param_1', 'input_param_2', 'input_param_3', 'from', 'value']:
    if col not in df.columns:
        df[col] = ''
    df[col] = df[col].fillna('').astype(str)

le_param2 = save_data.get('le_param2')
le_param3 = save_data.get('le_param3')
le_from = save_data.get('le_from')
le_value = save_data.get('le_value')

# Transform
def safe_encode(df_col, encoder):
    if encoder is None:
        return [0] * len(df_col)
    known = set(encoder.classes_)
    fallback = encoder.classes_[0] if len(encoder.classes_) > 0 else 0
    return df_col.apply(lambda x: encoder.transform([x])[0] if x in known else encoder.transform([fallback])[0])

df['f_to'] = safe_encode(df['to'], le_to)
df['f_code_hash'] = safe_encode(df['code_hash'], le_code_hash)
df['f_sel'] = safe_encode(df['selector'], le_sel)
df['f_param'] = safe_encode(df['input_param_1'], le_param)
df['f_param2'] = safe_encode(df['input_param_2'], le_param2)
df['f_param3'] = safe_encode(df['input_param_3'], le_param3)
df['f_from'] = safe_encode(df['from'], le_from)
df['f_value'] = safe_encode(df['value'], le_value)

features_used = save_data.get('features_used', ['f_to', 'f_code_hash', 'f_sel', 'f_param'])
X_pred = df[features_used]

# Predict
print("Predicting...")
y_pred_sparse = model.predict(X_pred)

# Convert predictions back to slot strings
predicted_slots = mlb.inverse_transform(y_pred_sparse)

# Display results
print("\n--- Prediction Results (First 5 samples) ---")
for i in range(5):
    print(f"\nTransaction {i+1}:")
    print(f"To: {df.iloc[i]['to']}")
    print(f"Selector: {df.iloc[i]['selector']}")
    print(f"Predicted Slots: {len(predicted_slots[i])} slots")
    # print(f"Slots: {predicted_slots[i]}") # Uncomment to see actual slots
    
    actual = set(df.iloc[i]['accessed_slots']) if isinstance(df.iloc[i]['accessed_slots'], list) else set()
    predicted = set(predicted_slots[i])
    
    intersection = actual.intersection(predicted)
    print(f"Actual Slots: {len(actual)}")
    print(f"Correctly Predicted: {len(intersection)}")
