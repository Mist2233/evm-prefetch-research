Figure metric definitions (paper / slides)
==========================================

Fig 1a: Train-split union size ECDF for (to, selector) rules. Unweighted = each rule
counts equally; weighted = CDF over transactions (each tx inherits its rule's union size).
Source: slot_distribution_analysis.py --export-csv

Fig 2*: Label-matrix metrics from train_light_gbm / train (calculate_metrics): Top-K Recall,
Total Recall, Precision, Exact Match. NOT comparable to Hybrid set-based metrics.

Fig 3a: Top-K access-mass coverage = fraction of all slot accesses whose slot identity
lies in the globally K most frequent slots. Source: topk_slot_coverage.py --export-csv

Fig 4a: Hybrid overall Recall/Precision using train_hybrid.calc_metrics (set intersection).
Slow-path LightGBM fixed from a single train; only FAST_PATH_THRESHOLD and fast_path_dict vary.
Source: sweep_hybrid_threshold.py

Fig 5a: Median Python inference time per transaction (offline sklearn). Not Erigon production.
Source: benchmark_inference_latency.py (exports CSV always)

Train/test: random_state=42, test_size=0.2 where applicable.
