# 参考文献清单

> 用途：NAS 会议论文 Related Work 文献参考
> 日期：2026-06-17

---

## A. EVM 存储访问优化（10 篇）——最直接相关

这些工作与本文的方法**正交**，可以相互补充，但均未从"混合预取"的角度解决 EVM 存储访问问题。

| # | 标题 | 作者 | 发表 | 链接 |
|---|---|---|---|---|
| 1 | **Storage Replica: Accelerating the Storage Access of the Ethereum Virtual Machine** | Kamil Jezek, Seongho Jeong, Yeonsoo Kim, Bernhard Scholz, Bernd Burgstaller | *Applied Sciences*, Vol. 16, No. 1, 2026 | https://doi.org/10.3390/app16010486 |
| 2 | **EVMTracer: Dynamic Analysis of the Parallelization and Redundancy Potential in the Ethereum Virtual Machine** | Xiaowen Hu, Bernd Burgstaller, Bernhard Scholz | *IEEE Access*, 2023 | https://ieeexplore.ieee.org/document/10102454 |
| 3 | **EIP-2930: Optional Access Lists** | Vitalik Buterin, Martin Holst Swende | Ethereum Berlin Hard Fork, 2021 | https://eips.ethereum.org/EIPS/eip-2930 |
| 4 | **EIP-7650: Programmable Access Lists** | Qi Zhou, Zhiqiang Xu | Ethereum Magicians, 2024 | https://eips.ethereum.org/EIPS/eip-7650 |
| 5 | **EIP-7863: Block-level Warming** | Toni Wahrstätter, Jochem Brouwer, Alex Stokes, Ansgar Dietrichs, Yoav Weiss, Alex Forshtat | Ethereum Improvement Proposal, 2025 | https://eips.ethereum.org/EIPS/eip-7863 |
| 6 | **Reddio: Parallel EVM Execution with Asynchronous Storage** | Xiaodong Qi, Xinran Chen, Asiy, Neil Han | *arXiv:2503.04595*, 2025 | https://arxiv.org/abs/2503.04595 |
| 7 | **Efficient Concurrent Execution of Smart Contracts in Blockchains using Object-based Transactional Memory** | Parwat Singh Anjana, Hagit Attiya, Sweta Kumari, Sathya Peri, Archit Somani | *NETYS*, 2019 | https://arxiv.org/abs/1904.00358 |
| 8 | **Inferring Needless Write Memory Accesses on Ethereum Bytecode** | Elvira Albert, Jesús Correas, Pablo Gordillo, Guillermo Román-Díez, Albert Rubio | *TACAS*, 2023 (LNCS) | https://arxiv.org/pdf/2301.04757 |
| 9 | **EVM-Shield: In-Contract State Access Control for Fast Vulnerability Detection and Prevention** | Xiaoli Zhang, Wenxiang Sun, Zhicheng Xu, Hongbing Cheng, Chengjun Cai, Helei Cui, Qi Li | *IEEE TIFS*, Vol. 19, pp. 2517–2532, 2024 | https://doi.org/10.1109/TIFS.2024.3349852 |
| 10 | **Efficient Parallel Execution of Blockchain Transactions Leveraging Conflict Specifications** | Parwat Singh Anjana, Matin Amini, Rohit Kapoor, Rahul Parmar, Raghavendra Ramesh, Srivatsan Ravi, Joshua Tobkin | *AFT 2025* (LIPIcs, Vol. 354) | https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.AFT.2025.29 |

---

## B. 机器学习辅助预取（6 篇）——技术路线相关

这些工作展示了 ML 在预取领域的应用趋势，但均运行在**在线路径**上，未采用 offline-compilation 方式。

| # | 标题 | 作者 | 发表 | 链接 |
|---|---|---|---|---|
| 11 | **A Hierarchical Neural Model of Data Prefetching** | Zhan Shi, Akanksha Jain, Kevin Swersky, Milad Hashemi, Parthasarathy Ranganathan, Calvin Lin | *ASPLOS*, 2021 | https://dl.acm.org/doi/10.1145/3445814.3446752 |
| 12 | **Building Efficient Neural Prefetcher** | Yuchen Liu, Georgios Tziantzioulis, David Wentzlaff | *MEMSYS*, 2023 | https://dl.acm.org/doi/10.1145/3631882.3631903 |
| 13 | **Pythia: A Customizable Hardware Prefetching Framework Using Online Reinforcement Learning** | Rahul Bera, Konstantinos Kanellopoulos, Anant V. Nori, Taha Shahroodi, Sreenivas Subramoney, Onur Mutlu | *MICRO*, 2021 | https://dl.acm.org/doi/10.1145/3466752.3480114 |
| 14 | **RL-CoPref: A Reinforcement Learning-Based Coordinated Prefetching Controller for Multiple Prefetchers** | Huijing Yang, Juan Fang, Xing Su, Zhi Cai, Yuening Wang | *J. Supercomputing*, Vol. 80, pp. 13001–13026, 2024 | https://doi.org/10.1007/s11227-024-05938-9 |
| 15 | **Learning Semantics, Not Addresses: Runtime Neural Prefetching for Far Memory** | Yutong Huang, Zhiyuan Guo, Yiying Zhang | *arXiv:2506.00384*, 2025 | https://arxiv.org/abs/2506.00384 |
| 16 | **A²P: Accelerating Graph Analytics Using Attention-Based Data Prefetcher** | Pengmiao Zhang, Rajgopal Kannan, Anant V. Nori, Viktor K. Prasanna | *SN Computer Science*, Vol. 5, No. 5, 2024 | https://doi.org/10.1007/s42979-024-02989-w |

---

## C. 经典预取技术 & 综述（3 篇）——基础参考

提供预取领域的理论框架和分类法，用于定位本文方法在学术版图中的位置。

| # | 标题 | 作者 | 发表 | 链接 |
|---|---|---|---|---|
| 17 | **A Primer on Hardware Prefetching** | Babak Falsafi, Thomas F. Wenisch | *Morgan & Claypool*, 2014 | https://doi.org/10.1007/978-3-031-01730-8 |
| 18 | **Toward Intelligent Prefetching: A Survey on Complex Memory Access Prediction Techniques** | Sheel Sindhu Manohar | *arXiv:2606.09955*, 2026 | https://arxiv.org/abs/2606.09955 |
| 19 | **Prefetching Using Markov Predictors** | Doug Joseph, Dirk Grunwald | *ISCA*, 1997 | https://dl.acm.org/doi/10.1145/264107.264207 |

---

## D. Learned Index / 哈希表增强（4 篇）——概念关联

这些工作将 ML 用于增强传统数据结构（B-tree、哈希表），与本文"用 ML 增强哈希表"思路类似，但面向数据库索引而非 EVM 预取。

| # | 标题 | 作者 | 发表 | 链接 |
|---|---|---|---|---|
| 20 | **ALEX: An Updatable Adaptive Learned Index** | Jialin Ding, Umar Farooq Minhas, Jia Yu, et al. | *SIGMOD*, 2020 | https://dl.acm.org/doi/10.1145/3318464.3389711 |
| 21 | **PGM-index: A Fully-Dynamic Compressed Learned Index with Provable Worst-Case Bounds** | Paolo Ferragina, Giorgio Vinciguerra | *PVLDB*, Vol. 13, 2020 | https://dl.acm.org/doi/10.14778/3389133.3389135 |
| 22 | **RadixSpline: A Single-Pass Learned Index** | Andreas Kipf, Ryan Marcus, Alexander van Renen, et al. | *aiDM@SIGMOD*, 2020 | https://dl.acm.org/doi/10.1145/3401071.3401659 |
| 23 | **Shift-Table: A Low-latency Learned Index for Range Queries using Model Correction** | Ali Hadian, Thomas Heinis | *EDBT*, 2021 | https://arxiv.org/abs/2101.10457 |

---

---

## 概览

| 分类 | 数量 | 在 Related Work 中的角色 |
|---|---|---|
| A. EVM 存储优化 | 10 篇 | 正交关系——可互补，非竞争 |
| B. ML 预取技术 | 6 篇 | 技术思想来源——但均为在线运行 |
| C. 经典预取综述 | 3 篇 | 理论框架——定位本文位置 |
| D. Learned Index | 4 篇 | 概念类比——ML 增强传统数据结构 |
| **合计** | **23 篇** | |
