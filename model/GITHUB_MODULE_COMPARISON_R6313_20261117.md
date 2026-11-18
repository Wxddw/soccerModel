# GitHub模块调研与R6.3.12差距审查（2026-11-17）

> 研究性质：比较方法和接口，**未直接复制第三方项目源码、未安装训练成熟包、未计算真实比赛上的效果提升**。

| 范畴 | GitHub代码或项目 | 已核实的实现 | R6.3.12原有机制 | R6.3.13处理与边界 |
| --- | --- | --- | --- | --- |
| 胜平负 / 综合市场 | [penaltyblog](https://github.com/martineastwood/penaltyblog) `models/football_probability_grid.py` | 概率矩阵派生1X2、BTTS、总球和让球 | `joint_bridge_r6312` 已统一胜平负、JC整数让球、总球、比分Top3 | 保留原桥；增加独立分布候选，不改变正式方向 |
| 精确比分 / 极端球 | [goalmodel](https://github.com/opisthokonta/goalmodel) `R/goalmodel_predict.R`; [sports-outcome-models](https://github.com/Gardner81/sports-outcome-models) `soccer_models.py` | 泊松、Dixon–Coles、负二项、双变量泊松构造及进球相关性 | 只要求输入有效Q，本身不生成Q | `candidate_models_r6313.py` 独立生成4种研究网格；仅接受赛前有来源参数，测量0—10尾部截断并封锁过大遗漏 |
| 半全场 | [Shushmath/Full-time-scores-prediction](https://github.com/Shushmath/Full-time-scores-prediction) | 根据已知半场射门等数据预测全场，属于临场特征 | 半全场仅观察或手工选项，缺少来自Q的一致性 | 不直接移植临场信息防泄漏；独立提出条件二项稀释基线 `halftime_bridge_r6313.py`，给定赛前历史半场进球占比，9项半全场概率总和为1，全场边缘严格等于原Q；非已训练的比赛状态模型 |
| 赔率 / 去水 | [penaltyblog implied](https://github.com/martineastwood/penaltyblog/blob/master/penaltyblog/implied/implied.py)、[shin-devig](https://github.com/neeljshah/shin-devig) | 原始倒数赔率去水：乘法归一、Power、Shin等 | 记录市场，但未提供独立去水的概率比较层 | `market_audit_r6313.py` 实现乘法法、Power法、差值与方法间不一致度；要求赛前同场时间戳，禁止跨用亚洲走水或竞彩让球SP |
| 历史数据接入 | [soccerdata](https://github.com/probberechts/soccerdata) | FBref、Club Elo、Understat、Football-Data.co.uk等跨平台命名和数据缓存 | 目前没有内置可审计的大规模历史赛前数据源 | 列为**待接入**，不宣称本次已经拉取完整一年样本，后续须核实法律条款及字段时间戳 |
| 概率评分 / 回测 | [penaltyblog metrics](https://github.com/martineastwood/penaltyblog/blob/master/penaltyblog/metrics/rps.py)、[goalmodel](https://github.com/opisthokonta/goalmodel) `score_predictions` | RPS、Brier、Log Loss及时间权重 | `forward_validation_r6312` 记录WDL/总球/JC Brier与Log Loss | `forward_validation_r6313.py` 增加RPS、精确比分对数损失、半全场损失、两种市场去水基线同场评分；仍要求同截点赛前冻结 |
| 过时实现风险 | [RyanSCodes/Dixon-Coles-Football-Predictor](https://github.com/RyanSCodes/Dixon-Coles-Football-Predictor) | README声明Python 2.7，含指数时间衰减 | 无仓库代码依赖 | 仅参考时间衰减思路，**不移植旧版运行时代码** |

## 直接实现与尚未实现

已实现：

1. 4种研究用上游 Q 生成器。要比较的是**同样赛前λ与参数**下不同分布的WDL、RC、GS、S4边缘变化，暂不授权调权。
2. 半全场9分类从冻结Q推导，要求预先给定并标注赛前来源的主客半场进球份额；无参数则 `BLOCK`，绝不默认0.45冒充历史事实。
3. 三项欧赔的两种去水参考分布、市场-研究模型偏差及分歧；无报价或报价过期、盘口类型不对时拒绝生成伪概率。
4. 独立数据层前向快照记录，结果单独评价WDL/总球RPS、比分与半全场Log Loss、市场Brier，不经过预测入口。

未完成（不能宣称）：

- 真实球队xG、双变量相关、Dixon–Coles rho、负二项dispersion或各队半场进球率的**拟合/历史校准**。
- 当天赛前赔率和成交流动性的全量拉取；市场去水不是必发交易量。
- CMP、Shin的训练/方法选择、动态红牌状态转换、自动学习融合权重；都需要独立数据和样本外验证。
- 模型真实命中率、对市场优势、竞彩回报率任何改善认证。

## 防止常见设计错误

- *赔率本身不是训练标签*：去水得到的是特定市场隐含的可比基准，不是赛果真实概率。
- *Q数据来源决定准确性*：所有模块同矩阵计算，只解决算术一致性，不自动意味着Q预测准确。
- *半全场≠对全场比分再次抽样*：条件于全场比分分配半场进球，可以保证FT边缘概率不变；真实足球事件相关性仍需历史数据验证。
- *GoalTop3≠ScoreTop3逐项映射*：比分前三按单点概率排序，进球前三按桶概率排序，二者没有一一覆盖的数学必要；记录诊断但不强行改概率。
- *公平比较*：必须相同比赛、相同赛前截点、同一套标签与合格的验证样本，按球队、联赛、赛事阶段分层；开发集和合成集不计成绩。
