# soccerModel — 五大联赛加世界杯模型

当前版本：**M79.3.6 Production（冻结） + Shadow R6.3.12（研究版）**。

这份仓库收录用户项目的最新研究版源码、测试、配置及历史复盘诊断资料。代码位于 [model/](model/)；主版本说明请阅读 [R6.3.12 README](model/README_SHADOW_R6312_20261117.md)。

## 最新修复

- 统一完整赛前联合比分概率矩阵 Q(主队进球, 客队进球)，派生胜平负、竞彩足球整数让球三项、总进球0—6与7+、精确比分。
- 让平预警、盘口窄差复核及强制跨层一致性审计。
- 比分Top3与总球Top3共享概率来源，但**不要求一一对应**；若缺少某个总球桶对应比分，提供覆盖提示与只读挑战组。
- 记录同截点赛前快照，赛后验证不得反向污染预测。

## 快速运行

环境：Python 3.10+，测试需要 `pytest`。

```bash
cd model
python -m pytest -q test_selection_efficiency_r633.py test_motivation_squad_r634.py test_shadow_r635.py test_shadow_r636.py test_shadow_r637.py test_shadow_r638.py test_shadow_r639.py test_shadow_r6310.py test_shadow_r6311.py test_shadow_r6312.py
python run_r6312.py prematch SYNTHETIC_EXAMPLE_PREMATCH_R6312_NOT_REAL.json /tmp/r6312_output.json
python replay_dev16_r6312.py
```

本地原包回归测试：**272/272通过**。测试证明程序功能和回归约束，而非真实赛事实战命中率。具体示例和历史诊断文件带 `SYNTHETIC` / `DEV` / `NOT_REAL` 标记，不能当作真实赛前验证。

**重要边界**：本研究包不包含完整可重建的正式版M79.3.6权重与所有实时数据源。Shadow模块不得自动改变Production的方向或授权状态。未经过独立前向测试，不能宣称模型预测准确率提高。

## 技术参考

- [penaltyblog](https://github.com/martineastwood/penaltyblog)：联合比分概率与多个市场聚合
- [goalmodel](https://github.com/opisthokonta/goalmodel)：比分概率、进球模型和概率评分

本仓库内容为研究用途；请勿将单次回测成绩解释成保证结果。
