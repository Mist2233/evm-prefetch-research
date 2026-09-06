----------------------- REVIEW 1 ---------------------

SUBMISSION: 3322
TITLE: Split-Path ML-Augmented Prefetching: Low-Latency Storage Architecture for EVM State

----------- Overall merit -----------
SCORE: 3 (Weak accept)
----------- Reviewer's confidence -----------
SCORE: 3 (Knowledgeable)
----------- Paper summary -----------
The paper shows that online ML inference (~28 ms) exceeds cold storage writes (~3 µs) by around 100x in Ethereum Virtual Machine (EVM) and becomes infeasible. SPML-PF addresses this issue through a split-path prefetching framework, which consists of an online path that has O(1) hash table lookups indexed by (to, selector) pattern keys and an offline path that trains a LightGBM model. Trace-driven simulations show that the prefetch recall improves and delivers a speedup of 12.7% in storage operations.
----------- Strengths -----------
- Motivation is clear and supported by quantitative analysis.
- The split-path design looks novel.
----------- Weaknesses -----------
- Only trace-driven simulations are presented. The implementation details of the simulator are not clearly described. Real-world performance remains questionable.

- The evaluation window (1001 blocks) looks short. The storage speedup (12.7%) looks marginal.
----------- Comments for authors -----------
Thank you for your work. The split-path design looks new, but its performance improvements look marginal.

The evaluation is entirely based on trace-driven simulation. Additionally, the paper gives limited details about how the simulator is implemented and shows whether it faithfully reproduces the Ethereum operations. It’s unclear whether real-world I/O factors such as asynchronous I/O or memory contention are correctly captured. Furthermore, the integration with the real EVM client is not clearly shown, even though the experimental configuration (Sec. V-A2) mentions the Erigon client version.

The ML accuracy improvements look small. Even though the recall increases from 22.23% to 31.17%, the 31.17% recall remains low. There will be many false negatives. How do they affect performance in practice? The paper doesn’t provide a clear answer to this.  

The speedup is 12.7%. The speedup looks too small and may disappear due to workload fluctuations.

The evaluation window contains only 1001 blocks, which translates to only a few hours of transactions. It may not reflect the dynamic nature of workloads.

The evaluation configuration assumes 30ns for hot-data access and 3us for cold-data access. These numbers highly depend on hardware configurations. How will your solution be affected in other settings?


----------------------- REVIEW 2 ---------------------

SUBMISSION: 3322
TITLE: Split-Path ML-Augmented Prefetching: Low-Latency Storage Architecture for EVM State

----------- Overall merit -----------
SCORE: 2 (Weak reject)
----------- Reviewer's confidence -----------
SCORE: 3 (Knowledgeable)
----------- Paper summary -----------
The paper introduces Split-Path ML-Augmented Prefetching (SPML-PF), a low-latency prefetching architecture designed to mitigate the I/O overhead of cold EVM state-slot accesses. SPML-PF removes ML inference from the latency-sensitive execution path through an online/offline split design. The online path performs constant-time lookups in a hash table indexed by the transaction’s target contract address and function selector. The offline path trains a multi-label classification model on historical transaction traces, accumulates and filters correctly predicted (pattern key, storage slot) associations, and merges the resulting incremental patterns into the online hash table. In trace-driven evaluation, the augmented design increases prefetch recall from 22.23% to 31.17%, reduces total storage-access cost by 11.3%, and provides a 12.7% speedup, although with a corresponding decrease in precision.
----------- Strengths -----------
The following is the strength of the paper:
+ Split-path architecture that removes ML inference from the latency-critical online path.
+ A rigorous quantitative demonstration that conventional online ML prefetching is infeasible for EVM storage.
+ An EVM-specific hybrid prefetching design that combines direct hash-table prediction for stable contract-access patterns with offline ML-assisted discovery and filtering of more complex storage-slot patterns.
+ A controlled empirical evaluation showing that offline ML augmentation improves recall and reduces simulated storage-access cost.
----------- Weaknesses -----------
The following is the weakness of the paper:
- The simulator does not clearly include database-read cost, cache pollution, bandwidth contention, and the impact of 83.5% false-positive prefetches; therefore, the reported speedup may be an artifact of optimistic assumptions.
- SPML-PF is evaluated only through trace replay, without integration into Erigon or measurement of end-to-end block latency and transaction throughput.
- The paper omits non-ML baselines such as top-k slot frequency, recency-weighted tables, and association-rule mining; the gains may result simply from enlarging the hash table.
- Results come from one contiguous mainnet interval of roughly 1,000 blocks, one client, and one machine, with no evaluation of workload drift, contract upgrades, unseen contracts, or repeated retraining cycles.
----------- Comments for authors -----------
This more detailed description for the weaknesses addressed.
* The paper explicitly states that "cold access latency is 3 µs and hot access latency is 30 ns" and that "prefetched slots are injected before execution begins." It claims a "cost reduction" and "speedup." However, the high false-positive rate (as derived from the reported recall of 31.17% and precision of 16.48% for E3) means a large number of unnecessary database reads are being performed. The paper does not provide a detailed cost model that explicitly accounts for these false-positive reads, potential cache pollution from incorrectly prefetched data, or bandwidth contention. Without such a model, the reported gains are indeed susceptible to being artifacts of optimistic assumptions where the cost of false positives is underestimated or ignored.
* The "Implementation and Experimental Setup" section clearly states: "To evaluate the prefetching strategy, we built a trace-driven offline replay simulator, avoiding the need to modify Erigon’s codebase." It explicitly mentions that the blockchain node is a "modified Erigon client version 2.59" for collecting traces, but the evaluation is done via a simulator. The paper also doesn't present any end-to-end block execution times or transaction throughput figures for an integrated system.
* The paper's "Experiment Groups" section (Table I and description of E2 vs. E3) shows that E2 is "SPML-PF (w/o offline) Original pattern-key table (baseline)" and E3 is "SPML-PF Original + offline increments (proposed)." The gain is attributed to the "offline increments" generated by the ML model. However, the paper does not include experimental groups for alternative non-ML methods like frequency counting, top-K slots, or association rule mining to generate these "offline increments." It also notes that the ML model's transaction-specific predictions are "merged into the online hash table" which uses a static (to, selector) -> slot set format, meaning the fine-grained ML predictions (based on calldata, sender, etc.) are collapsed into a static mapping. This suggests that the observed improvements may come primarily from adding more entries to the hash table, which simpler non-ML methods might achieve equally well.
* The "Dataset" section explicitly states, "Transaction execution traces are collected via the debug trace transaction interface for 1,001 consecutive Ethereum mainnet blocks from block height 20,000,000 to 20,001,000." This confirms the limited temporal and volumetric scope. The "Scaling Consistency" experiment uses different transaction volumes from the same general dataset, not different datasets or time periods. The paper also does not mention any experiments testing for workload drift, contract upgrades, unseen contracts, different client versions, or repeated retraining cycles over extended periods. It uses "one machine" for evaluation, reinforcing the lack of diverse testing environments.


----------------------- REVIEW 3 ---------------------

SUBMISSION: 3322
TITLE: Split-Path ML-Augmented Prefetching: Low-Latency Storage Architecture for EVM State

----------- Overall merit -----------
SCORE: 3 (Weak accept)
----------- Reviewer's confidence -----------
SCORE: 1 (No familiarity)
----------- Paper summary -----------
This paper studies the cold storage access bottleneck in Ethereum Virtual Machine (EVM) execution. The authors observe that cold storage accesses are substantially more expensive than intra-block cache hits, while directly placing an ML predictor on the online execution path introduces inference overhead much larger than the potential storage-access savings. To address this issue, the paper proposes SPML-PF, a split-path ML-augmented prefetching architecture. The online path uses a lightweight hash table indexed by (to, selector) for constant-time prefetch lookup, while the offline path periodically trains a multi-label classifier on historical transaction traces and uses the learned predictions to augment the online hash table. Experiments on Ethereum mainnet traces show that the offline augmentation improves recall from 22.23% to 31.17% and reduces the modeled storage access cost by 11.3%.
----------- Strengths -----------
1.The paper targets an important storage bottleneck in EVM execution.
2.The overall architecture is simple and practical.
3.The paper is generally well organized and easy to follow. T
----------- Weaknesses -----------
1.The evaluation is simulation-based rather than an end-to-end implementation in Erigon.
2.The baseline comparison could be further strengthened.
----------- Comments for authors -----------
Overall, the paper addresses an interesting problem and presents a clean observation: directly placing an ML predictor on the EVM storage-access critical path is impractical because inference overhead can substantially exceed the latency savings from prefetching. The proposed split-path architecture is intuitive and avoids this issue by using ML only offline while retaining lightweight O(1) hash-table lookups online. The paper is clearly written, and the trace-based results show promising improvements.

However, I have two major concerns. First, the current evaluation is based on a trace-driven simulator rather than an end-to-end implementation in Erigon, making it difficult to assess whether the reported storage-access improvements translate into actual transaction or block execution speedups. Second, the evaluation does not establish whether ML is actually necessary: since the final result of offline inference is converted into (pattern key, storage slot) entries in a hash table, simple frequency- or history-based offline pattern mining could potentially achieve similar benefits. Comparing SPML-PF against such baselines, together with a real-system implementation and evaluation under temporally changing workloads, would substantially strengthen the paper.