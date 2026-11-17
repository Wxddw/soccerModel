# soccerModel — 足球概率模型研究仓库

**正式版：M79.3.6 Production 冻结；最新研发：Shadow R6.3.14 (2026-11-17)。**

代码位于 [`model/`](model/)，先读 [R6.3.14研发说明](model/README_SHADOW_R6314_20261117.md) 与 [五模块样本外试验指标](model/EXTERNAL_EPL_2023_26_EXPERIMENT_R6314.json)。历史研究版R6.3.12 / R6.3.13源码保留，绝不自动修改正式版权重、方向或授予权限。

## 五模块
- S4：净胜差精确分桶与让平二审，必须使用实际竞彩整数让球盘。
- GS：独立泊松、Dixon–Coles、负二项、双变量泊松候选，赛前参数、同截点、独立测试。
- RC：0–6与7+整数总球校准，从**同一张完整比分概率网格**导出。
- 半全场：九分类条件概率及历史半场进球比例，只用比赛前已完成的样本拟合。
- Outcome：赔率乘法/Power去水基线，强制核验盘口快照的观察时间。

### 测试

```bash
cd model
python -m pytest -q test_selection_efficiency_r633.py test_motivation_squad_r634.py test_shadow_r635.py test_shadow_r636.py test_shadow_r637.py test_shadow_r638.py test_shadow_r639.py test_shadow_r6310.py test_shadow_r6311.py test_shadow_r6312.py test_shadow_r6313.py test_calibration_r6314.py
# 用具有使用权限、赛前冻结的 JSON 样本，离线执行对比
python benchmark_r6314.py /path/to/authorized_prematch.json --output /tmp/benchmark.json
```

本地回归：**367/367通过**，其中35项是本次新增。程序测试不等于真实命中率证明。独立英超三季回顾性研究对照（2024/25开发，2025/26 380场留出）仅验证了**外部简化进球基线**的部分信号，并没有获得完整真实M79正式版的原始赛前联合概率矩阵。项目不会打包或自动抓取来源网站限制AI使用的原始CSV。

**状态**：S4候选校准在留出集变差，禁止晋级；RC和半全场改善幅度很小，仍属观察；赔率去水基线优于简单独立进球基线，不代表应当自动跟随盘口。
