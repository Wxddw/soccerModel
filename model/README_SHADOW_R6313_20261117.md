# M79.3.6 Production冻结 + Shadow R6.3.13 GitHub参考优化研究版

**状态：研究代码已实现，并通过新增单元测试；尚无独立真实比赛验证证明预测更准。**

从R6.3.12完整继承文件；**继承文件不修改**。本版本研究参考（不是复制或已安装的训练结果）见 [`GITHUB_MODULE_COMPARISON_R6313_20261117.md`](GITHUB_MODULE_COMPARISON_R6313_20261117.md)。

## 1. 模块

- `candidate_models_r6313.py`：提供泊松 / Dixon–Coles / 负二项 / 双变量泊松独立上游网格。需要已知主客进球期望、相关/离散参数（依据模型选择）和赛前来源ID+时间戳。最多单队10球；截断质量超过0.002则拒绝使用，容许时明确标注截断及被归一化部分。**只供候选比较，不能覆盖R6.3.12冻结矩阵。**
- `halftime_bridge_r6313.py`：在完整Q(H,A)上按源自赛前历史资料的主客半场进球份额，对每个终场比分条件分解半场进球；导出9项半全场概率与前半场胜平负概率。完整FT边缘必须精确等于同一个Q。该二项稀释是尚待历史校准的基准模型，不是已训练的分钟级足球状态模型。
- `market_audit_r6313.py`：三项十进制胜平负欧赔的乘法与Power去水，显式展示overround、不同方法分歧及与联合比分矩阵的差值；只读、不回填赔率到Production胜平负、比分、盘口或进球数。
- `shadow_r6313.py`：把三个可选研究通道接入当前R6.3.12的只读输出。候选模型、半场份额、盘口必须有赛前时间戳，且早于模型截止时间及同场开球。缺输入即标记BLOCK，不猜数据。中文竞彩让球仍按R6.3.12符号整数口径，不混用亚洲走水。
- `forward_validation_r6313.py`：新快照嵌套R6.3.12冻结记录，新增WDL/总球RPS、精确比分对数损失、半全场Log Loss和市场Brier。实际赛果、半场比分只能进入赛后评价，绝不进入赛前概率生成。缺失的前向证据不补造。

## 2. 本地运行

Python 3.10+，pytest用于测试。第三方数学或外部数据包均为**可选的研究参考，不作为现有代码运行依赖**。

```bash
cd model
python -m pytest -q test_selection_efficiency_r633.py test_motivation_squad_r634.py \
  test_shadow_r635.py test_shadow_r636.py test_shadow_r637.py test_shadow_r638.py \
  test_shadow_r639.py test_shadow_r6310.py test_shadow_r6311.py test_shadow_r6312.py \
  test_shadow_r6313.py

# 演示模拟的赛前数据；不会生成正式投注授权
python run_r6313.py prematch SYNTHETIC_EXAMPLE_PREMATCH_R6313_NOT_REAL.json /tmp/r6313_result.json

# 独立的上游候选矩阵
python run_r6313.py candidate-grid SYNTHETIC_CANDIDATE_R6313_NOT_REAL.json /tmp/r6313_candidate.json

# 真实比赛须在赛前合法冻结并取得可复核的官方结果后再做下面两步：
python run_r6313.py freeze REAL_PREMATCH_INPUT.json REAL_FROZEN_SNAPSHOT.json
python run_r6313.py evaluate REAL_FINAL_RECORD.json REAL_EVALUATION.json
```

评价模式的输入为 `{"snapshot": <冻结JSON>, "actual": {"match_id", "score", "observed_at", "source_id", "status":"final_90min"}}`。可选的独立来源半场字段是`half_time_score`、`half_time_source_id`。**不得自建回溯时间戳冒充前向样本**。

## 3. 晋级要求与限制

- 程序单元/性质测试≠赛事实盘验证；合成测试不计真实命中率。
- 需要独立样本≥50场才考虑研究晋级评审，建议≥100场并按赛制、时间与联赛分组。必须比较完整Brier、Log Loss、RPS和Top1/Top3覆盖，避免只看一轮命中率。
- 每场需提供完整Q、双方预期进球、可能相关/分散参数、历史半场比例、赛前可获取赔率与时间戳。若缺，单一通道BLOCK，不把空缺伪装成成功。
- `M79.3.6 Production`仍冻结。研究候选无权自动反转胜平负、改变比分Top3、总球路由、JC让球或核心等级。
- 未设置网络抓取、没有导入第三方项目源文件，也没有计算任何实战利润/收益率。
