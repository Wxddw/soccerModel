# M79.3.6 正式版冻结 + Shadow R6.3.12 联合矩阵跨层一致性修复

**状态：实现并通过程序回归测试；尚无独立样本证实预测准确率提高。**

继承 Shadow R6.3.11 既有99个文件，逐个SHA256验证未改。此研究包不包含完整可重建的正式版 M79.3.6 模型权重，也不改变任何正式版的单挑、复选、进球Top3、比分Top3或核心授予。研究层新增 `joint_bridge_r6312.py`、`shadow_r6312.py`、`forward_validation_r6312.py`、`run_r6312.py` 和测试/复盘资料。不能把研究审计里的方向当成已正式授权投注。

## 1. 跨层唯一事实来源：完整赛前联合比分矩阵 Q(h,a)

需要完整、**归一化总概率为1**、有赛前截点的 `score_matrix`。每行 `{'score':'2:1','probability':0.1}`，不接受在缺失尾部时静默归一化；原GS容差较宽时，本模块会严格拒绝总质量不为1的网格。有限网格仅覆盖单队0—10球，不能声称高于10球的真尾部已经建模。

所有研究市场共用同一 Q：

- `P(主胜)=Σ[H>A] Q(H,A)`，平局及客胜类推。
- `P(T=k)=Σ[H+A=k] Q(H,A)`，对 k=0…6 逐一求和；`7+` 为独立聚合桶，不能写作“7球精确预测”。
- 竞彩带符号整数让球线 L：`D=H+L-A`，D>0 为让胜、D=0 为让平、D<0 为让负；**让平要求主客原始净胜差 `H-A=-L`**。
- `Score Top3` 是 Q 最大的三个比分点；`Goal Top3` 是 P(T=k) 最大的三个桶。**这两种Top3原理上不必一一对应**，缺少对应比分时提示候选覆盖缺口，不强制修改概率或替换Top3。
- 对落在Goal Top3但没有比分Top3代表的桶，列出该桶最高概率精确比分，组成只读挑战版；明确输出取代第三比分点后的概率质量损失。

## 2. S4让球风险门：仅允许研究，绝不自动反转

必须提供带时间戳的 `official_handicap_line` 和 `official_handicap_line_source`，线必须为中国竞彩整数 `-3..+3`；不能替换为亚洲让球 -0.75、-1.25 或欧赔推测值。

针对完整净胜差聚合后：

1. 输出 `让胜/让平/让负` 独立概率、最高与次高研究方向、研究复选方向、差距，精确让平目标净胜差。
2. 前两名相差≤5个百分点，**暂停让球单挑授权、建议二审**；让平距离首选≤5个百分点，同样触发专项提醒。这个5pp是继承的审查宽度，未经历史样本调参认证。
3. 已冻结让球首选与矩阵聚合首选不一致，提示方向冲突，保留原冻结首选，不自动切换。
4. 比分Top3里有两项或更多映射让平且冻结首选不是让平，单独提示**但不自动改选让平**；比分单点众数与聚合让球众数不相同不属于数学错误。
5. 最大单一让球概率<40%给予弱候选提示；正式授权始终为空。
6. 缺少官方整数让球线，竞彩让球状态`BLOCK`，仍能单独从矩阵计算胜平负/整数总球/比分。

## 3. RC/GS链接门与校验

旧模型容许联合矩阵概率与单独提供的胜平负、总球桶之间有1.5个百分点容差。新模块不修改旧数据，而是额外提供更严格的 `FROZEN_*_NOT_EXACTLY_DERIVED_FROM_SAME_GRID` 风险标记；差距大于 `1e-6` 将**封锁跨层结果发布**。不能“微调一个输出”使冲突消失，必须找回正确的原始联合比分矩阵重新计算。

`goal_top3_to_score_top3_coverage` 显示每个进球桶完整概率、被全球比分Top3覆盖的概率及最高概率对应比分。`goal_anchor_challengers` 是研究挑战候选，不允许删除已按概率排序的原始Top3。这样修复的是链接、来源和提示，而不是为追逐某一轮比分人工增加候选。

## 4. 用11月16日8场对话方案做开发诊断，不使用赛果训练

`RECAP_DEV_20261116_CONVERSATION_ONLY_NOT_FORWARD_R6312.json` 是已发布选项和之后记录的赛果。它不具有赛前完整概率矩阵、可信第三方时间戳或完整Production原始数据，**不能被作为独立前向验证**。

`python replay_dev16_r6312.py` 只输出聊天记录层的冲突：8场中实际让平3场、让球首选2/8、3场已发布Goal Top3含未被比分Top3覆盖的桶、3场有多个比分Top3映射让平却未选让平。复盘文件**不会进入 `inspect()` 或模型概率运算**。不要据此直接添加让平/5球权重。

## 5. 冻结、赛后评分与禁止篡改

`forward_validation_r6312.py` 新增赛前快照、双方旧版与桥接研究版记录、双层SHA256与赛后单独评价。后者可检验实际赛果下的胜平负和整数球Brier/Log Loss及让球研究首选，但概率为0的实际事件保留异常标记，不通过人为加平滑修补。

只有**真实执行时间早于比赛开球且晚于声明截点**才能冻结；赛后核验必须是有来源的90分钟完赛比分。SHA256提供完整性检测，不等于不可伪造的外部时间戳。必须使用不可回改的外部记录作为正式前向验证。

建议独立新比赛≥50场才启动晋级讨论，≥100场检查稳定性、让球准确度、比分Top3覆盖、RC整数总球Brier与Log Loss；**单元测试数量不等于预测比赛数量**。

## 6. 使用方法

Python 3.10+，`pytest` 用于测试。

```bash
python -m pytest -q test_selection_efficiency_r633.py test_motivation_squad_r634.py test_shadow_r635.py test_shadow_r636.py test_shadow_r637.py test_shadow_r638.py test_shadow_r639.py test_shadow_r6310.py test_shadow_r6311.py test_shadow_r6312.py
python run_r6312.py prematch SYNTHETIC_EXAMPLE_PREMATCH_R6312_NOT_REAL.json SYNTHETIC_EXAMPLE_OUTPUT_R6312_NOT_REAL.json
python replay_dev16_r6312.py
# 只能对尚未开赛的真实比赛执行：
python run_r6312.py freeze REAL_PREMATCH_INPUT.json IMMUTABLE_PREMATCH_SNAPSHOT.json
# 比赛完赛且有独立来源时：
python run_r6312.py evaluate FINAL_PAIR_INPUT.json EVALUATED_PAIR.json
python run_r6312.py evaluate-batch FINAL_PAIRS_INPUT.json EVALUATION_BATCH.json
```

- prematch输出重点字段：`S4_GS_RC_unified_probability_bridge_v312`、`S4_GS_RC_cross_layer_hardlock_v312`、`audit_flags_r6312`。
- 测试全部通过：**272/272 = 继承215 + 新增57**；其中新增包含不同λ的合成泊松网格守恒性测试，以及冻结后独立赛果评分。不宣称2026-11-16预测被新版“重新命中”。
- 不自动接入网络、也不包含真实完整赔率历史或球队进球参数；用户提供真实赛前联合矩阵后才能进行可核验的概率桥接。

## 7. 外部技术参考与适用边界

- [penaltyblog — FootballProbabilityGrid官方文档](https://penaltyblog.readthedocs.io/en/latest/models/football_prob_grid.html)：多市场由同一完整比分网格导出、有限尾部截断与归一化纪律。
- [penaltyblog GitHub](https://github.com/martineastwood/penaltyblog)：泊松、双变量泊松、Dixon-Coles等可作未来**上游生成Q矩阵**的参考，不是本研究补丁实际安装/拟合结果。
- [goalmodel GitHub](https://github.com/opisthokonta/goalmodel)：进球分布、比分概率和概率评分方法参考。未将R包作为此Python补丁依赖。

**注意区分**：中国竞彩让平是让球后的三项离散投注结果；penaltyblog文档里Asian handicap整数线中的`push`只是**推赢走水**概念，对比净胜差可以参考，但结算与竞彩让平并不相同。

Flaim Fantasy 仅连接用户的 ESPN/Yahoo/Sleeper 美式幻想体育联赛，无法产生本项目欧国联、足球竞彩的正式比分或中国竞彩整数盘口输入，不予混入模型。

GitHub连接到的用户代码仓库目前没有识别到本足球模型对应的项目仓库，因此不会把源文件擅自提交到其他用途的仓库。本地ZIP可独立执行。
