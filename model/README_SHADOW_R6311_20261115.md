# M79.3.6 Production 冻结 + Shadow R6.3.11（2026-11-15）

## 定位：正向优化 ≠ 赛后反推权重

继承 R6.3.10 的完整85个文件，原文件逐个 SHA256 保持一致。**M79.3.6 正式版完全冻结**，本包并不含可重建全部正式模型权重的代码；新能力是实装的**赛前研究审计、比分候选挑战方案及前向配对计分**，不宣称训练出新的概率参数或提高实际预测命中率。

开发诊断：11月14日周六003—016 纯足球口径14场，基于历史对话方案与赛果，复算唯一8/14、精确比分Top1 0/14、比分Top3 5/14、Goal Top3 8/14。此记录仅为**对话级开发集**，没有原始独立冻结生产矩阵/完整原始消息时间凭证，不是前向验证，不用于拟合参数、选择阈值或认证提升。

## 1. 新增 ESR/Form v0.3：足球因素来源质量门

可选 `football_evidence_v311`，每条要求：`event_id`, `source_id`, `observed_at`, `family`, `side`, `signal`, `certainty`。全部必须早于冻结 `cutoff`；未来新闻拒绝。

- `form` 近期战绩必须明确 `opponent_adjusted: true/false`。未对对手强度修正时，触发人工复核，不得用裸近5场自动反向或放行核心。此前瓦尔韦克/登博思的对手强弱与征召名单就是这一类。
- `squad` 和 `replacement` 同属**一个 roster 证据家族**；同一个 `event_id` 多次出现不得重复计票。回归、征召不等于确认首发，更不等于提升战力；`replacement_quality` 仅允许 `verified_equal`, `verified_better`, `verified_worse`, `unknown`，后续必须有符合时间截点的证据支持。本包**不为这些主观标签赋分**。
- `tactics`, `motivation`, `schedule`, `matchup`, `xg` 可独立存档，但新增风险家族票数一直为0，不绕开继承的双独立证据与授权限制。
- 缺少来源或上下文，状态为 `UNKNOWN`，不是一票通过。

示例：

```json
"football_evidence_v311": [
  {"event_id":"away-winger-absence", "family":"squad", "side":"away", "signal":"home", "certainty":"confirmed", "source_id":"official-squad-doc", "observed_at":"2026-11-15T11:00:00+08:00", "replacement_quality":"unknown"},
  {"event_id":"opponent-adjusted-recent-form", "family":"form", "side":"home", "signal":"home", "certainty":"reported", "source_id":"precutoff-form-dataset", "observed_at":"2026-11-15T10:50:00+08:00", "opponent_adjusted":true}
]
```

## 2. GS1.8：不伪造比分集中度的备选Top3

必须有**经继承GS1.3一致性验算的同一赛前联合比分矩阵**才会创建挑战组：

- 基准 `raw_global_top3`：按精确比分单点概率选择全球前三，**该组在这张冻结矩阵内部的理论Top3覆盖质量最大**。
- 挑战A `wdl_family_diversity_candidate`：若前三全部来自同一胜平负家族，则用最高概率的其他家族比分替换第三；若已覆盖多家族则保持原样。
- 挑战B `btts_diversity_candidate`：若前三都是双方进球或都是未双方进球，则用最高概率的另一类型比分替换第三。
- 挑战C `jc_margin_family_diversity_candidate`：仅在官方竞彩整数让球**有赛前来源与冻结可检验**时创建，若前三全部落在同一让球结果家族，则用不同结果家族最高比分替换第三。

每个挑战组输出比分、总概率质量及相对基准的损失；**不自动替换正式Top3**。若联合矩阵校准准确，分散的Top3理论上不会胜过原始Top3；只有独立未来数据证实某挑战组实际覆盖更好，才继续研发。若没有矩阵则返回 `UNKNOWN`，不得编造比分概率。

对于0球、5—6球、7+球，另保存矩阵中最高分值场景供尾部审查。7+属于聚合桶，不能把7+当作一个具体整数进球。仍维持RC2.7与S4 v2.0机制，不按11月14日赛果统一加大尾部/让平权重。

## 3. 来源分离：纯足球 vs 市场

可选 `matrix_provenance_v311` 包含 `source_id`, `observed_at`, `channel`, `model_id`；`channel` 可为 `football_only`, `market_only`, `hybrid`, `unknown`。若声明 `football_only` 却有 `market_price` 证据，立即拒绝。来源声明不是独立认证；未取得实际纯足球进球模型与历史训练快照，就不能把市场反推的矩阵叫作纯足球预测。

**正确实验**应在每一未来比赛的同一截止时间保存两份不同输入的纯足球/市场矩阵，并将两个独立快照与官方比分配对。来源不可确认者保持UNKNOWN，不得为了得到更好结果直接融合。

## 4. 真正的前向配对记录

`forward_validation_r6311.py` 严格分成赛前与赛后两个入口：

- `freeze(packet)`：**只有真实执行时间在开赛前，且不早于声明截点时**才能冻结。调用基线R6.3.10与新研究R6.3.11的相同输入，分别留存比分Top3，记录完整输入SHA256和快照SHA256。
- `evaluate(snapshot, actual)`：必须验证完整快照Hash、身份、赛果来源、观测时间晚于开球90分钟及`final_90min`，赛后分数绝不进入赛前inspect。允许基准/挑战按同一真实结果计分。
- `evaluate-batch`：拒绝重复赛事，报告样本数、基准与各挑战命中、样本差异；**不足50场不允许任何晋级讨论**，推荐100场以上。即使达到数量门槛，还需分组、覆盖率及Brier/Log Loss等其他门槛，不因单一Top3多中几场自动晋级。

纯SHA256是**文件完整性校验，不是外部可信时间戳或不可伪造证据**。正式前向验证仍需独立写入不可回改归档（具备审计日志的库/第三方时间戳）保存原数据和冻结结果。测试中的人工合成未来比赛**不等于真实比赛验证**。

## 5. 启动

Python 3.10+，安装pytest：

```bash
python -m pytest -q test_selection_efficiency_r633.py test_motivation_squad_r634.py test_shadow_r635.py test_shadow_r636.py test_shadow_r637.py test_shadow_r638.py test_shadow_r639.py test_shadow_r6310.py test_shadow_r6311.py
python run_r6311.py prematch SYNTHETIC_EXAMPLE_PREMATCH_NOT_REAL.json SYNTHETIC_R6311_OUT.json
python run_r6311.py recap-dev14 RECAP_20261114_14_MATCHES_CONVERSATION_ONLY_DEV.json DEV14_RECAP_AUDIT.json
# 仅当真实时刻在官方开赛前：
python run_r6311.py freeze REAL_PREMATCH_PACKET.json FREEZE_R6311.json
# 完赛后在独立文件中组织 {"snapshot": <之前保存的冻结对象>, "actual": {"match_id":"...","score":"1:0","status":"final_90min","observed_at":"...","source_id":"official-report"}}
python run_r6311.py evaluate FINAL_PAIR.json SCORE_PAIR.json
# 多场：[{"snapshot":...,"actual":...},...] 
python run_r6311.py evaluate-batch FINAL_PAIRS.json BATCH_REPORT.json
```

## 6. 版本和测试

- 已确认代码契约本地回归：**215/215通过 = R6.3.10继承185 + 新增30**，不代表215场比赛命中。
- 与所有原R6.3.10文件SHA256一致，不更改Production权重/同一输入概率；所有正式授权仍为`null`。
- 11月14日复盘文件独立封装，赛前入口明确拒绝`actual_score`、`final_score`、`recap`、`red_card`、赛中事件等字段。
- 目前无匹配的50+场完全独立的未来真实赛前快照，因此**尚无经验证的命中率提升，不能宣称模型预测准确率提高**。
