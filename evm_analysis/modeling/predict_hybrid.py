import os
import json
import joblib
import pandas as pd

DATA_PATH = '/home/tianyumao/workspace/transaction-replay/erigon_tx_trace.jsonl'
MODEL_PATH = '/home/tianyumao/workspace/transaction-replay/evm_analysis/models/evm_model_hybrid_v1.pkl'

def main():
    print("Loading Hybrid Model...")
    save_data = joblib.load(MODEL_PATH)
    fast_path_dict = save_data['fast_path_dict']
    model = save_data['model']
    mlb = save_data['mlb']
    encoders = save_data['encoders']
    feature_cols = save_data['feature_cols']

    print(f"Loaded {len(fast_path_dict)} Fast Path rules.")
    
    print("Loading First 1000 Transactions for Inference Test...")
    data = []
    with open(DATA_PATH, 'r') as f:
        for i, line in enumerate(f):
            if not line.strip(): continue
            data.append(json.loads(line))
            if i >= 1000: break
            
    df = pd.DataFrame(data)
    
    # Fill NAs and safe transform
    for col in encoders.keys():
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].fillna('').astype(str)
        
        le = encoders[col]
        known = set(le.classes_)
        fallback = le.classes_[0] if len(le.classes_) > 0 else 0
        df[f'f_{col}'] = df[col].apply(lambda x: le.transform([x])[0] if x in known else le.transform([fallback])[0])

    predictions = []
    fast_hits = 0
    slow_hits = 0
    
    for _, row in df.iterrows():
        key = (row['to'], row['selector'])
        if key in fast_path_dict:
            predictions.append(fast_path_dict[key])
            fast_hits += 1
        else:
            X_pred = pd.DataFrame([row[feature_cols]])
            pred_sparse = model.predict(X_pred)
            predictions.append(list(mlb.inverse_transform(pred_sparse)[0]))
            slow_hits += 1
            
    print(f"\nInference Complete!")
    print(f"Total Predictions: {len(predictions)}")
    print(f"Routed to Fast Path (Hash Map): {fast_hits} ({(fast_hits/len(predictions)):.2%})")
    print(f"Routed to Slow Path (LightGBM): {slow_hits} ({(slow_hits/len(predictions)):.2%})")
    
    print(f"\nSample Prediction 1 (slots): {predictions[0][:5]}")

if __name__ == "__main__":
    main()
