# soccerModel — 五大联赛加世界杯模型

当前版本：**M79.3.6 Production（冻结） + Shadow R6.3.13（研究版）**。

- 最新研究说明： [R6.3.13 模块优化](model/README_SHADOW_R6313_20261117.md)
- GitHub技术调研： [七大模块比较及方法审查](model/GITHUB_MODULE_COMPARISON_R6313_20261117.md)
- 上一版统一竞彩让球、比分、总进球接口： [R6.3.12](model/README_SHADOW_R6312_20261117.md)

## 最新研究增强

R6.3.12已经从同一个联合比分概率矩阵派生胜平负、竞彩整数让球、总球0—6/7+和精确比分。R6.3.13在原代码完全保留的基础上新增：

- 泊松、Dixon–Coles、负二项、双变量泊松四种**上游候选**比分概率网格，要求有赛前进球参数与原始来源。
- 由完整Q推导9项半全场概率，保证全场边缘不变；半场进球份额必须来自赛前历史校准，缺数据就封锁。
- 胜平负欧赔乘法/Power去水只读参照，明确市场与模型偏差，不自动反转方向。
- RPS、精确比分与半全场Log Loss以及去水市场Brier作为独立赛后评价。

## 运行

Python 3.10+。直接在`model/`目录执行：

```bash
python -m pytest -q test_selection_efficiency_r633.py test_motivation_squad_r634.py test_shadow_r635.py test_shadow_r636.py test_shadow_r637.py test_shadow_r638.py test_shadow_r639.py test_shadow_r6310.py test_shadow_r6311.py test_shadow_r6312.py test_shadow_r6313.py
python run_r6313.py prematch SYNTHETIC_EXAMPLE_PREMATCH_R6313_NOT_REAL.json /tmp/research_demo.json
```

本地回归：**332/332项通过（继承272项，新增60项）**。这是功能测试，不是332场比赛预测，更不是投注收益保证。

**Production M79.3.6不变。** Shadow研究结果禁止自动改变正式胜平负、比分Top3、进球Top3、竞彩让球、保护或分层。真实进球参数、半全场数据、赔率时间戳仍需独立接入与验证。
