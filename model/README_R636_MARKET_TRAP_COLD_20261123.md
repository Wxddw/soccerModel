# R6.3.6-MTC v0.1 盘口诱导疑点 / 冷盘价格异动（影子研究）

**2026-11-23；仅Shadow；M79.3.6 Production、既有单挑/复选/让球/比分/进球数/半全场概率及核心等级均不变。** 本功能只标记“疑似诱盘信号”“冷门赔率异动”，**无法确定博彩公司的主观意图，更不能据此断言操盘、异常比赛或冷门必出**。

## 研究现状

- 前两轮 (2026-11-21, 11-22) 复盘指出强热门失手、让球净胜差不准、进球尾部遗漏。但**比赛最终冷门不意味着其赛前盘口一定是诱盘**，这些开发样本不得用来调参再评分。
- 2026-11-22 13:52+08:00 冻结16场的研究快照里只有当时的竞彩赔率/整数让球和市场/IPF概率矩阵，**缺少同公司、经来源及时间校验的开盘—赛前两点欧赔/亚盘轨迹**。`DEV_20261122_ODDS_16_FAIL_CLOSED.json` 逐场列出“证据不足”，不是说那些比赛无盘口风险。
- 赔率变化数据入口： [ZGZCW 欧亚指数](https://plzx.zgzcw.com/)、[500 欧指](https://odds.500.com/fenxi/ouzhi-1362868.shtml)、[500 亚指](https://odds.500.com/fenxi/yazhi-1362868.shtml)、[买量比](https://www.vipc.cn/jczq/buys)。页面可以显示初始/即时数据，**但网页的“初始价”不等于具有可独立追溯的原始采集时间戳**，买量赛后回查页面更不能被当成已冻结的赛前买量。
- 完整数据应有同一家公司的 `bookmaker、market、observed_at、source_url、opening/current odds、Asian home handicap、欧赔返还率`；买量另需 `observed_at`；赛前阵容/赛程/战术也各需要不晚于冻结点的时间戳。

## 本次程序

- `market_trap_cold_watch_r636.py`: 输入 `match_id/cutoff/kickoff/official_jc_signed_line/quotes/crowd/independent_evidence`。每个赔率记录要求公司、市场、完整小数赔率、独立时间与URL。欧赔和亚洲盘、大小球分市场去水、同公司按时间先后比较；亚洲盘接收0.25球步长；**竞彩整数让球和亚洲盘口永不互换**。
- 市场层仅可触发 `FAVORITE_PROBABILITY_DRIFT`、`UNDERDOG_PRICE_SHORTENING_COLD_WATCH`、`EURO_ASIAN_OPPOSITE_MOVES`、`STRONG_FAVORITE_SHALLOW_ASIAN_LINE`、`CROWD_HEAT_VS_MARKET_DRIFT`，全部只进入人工二审。
- 其中受众买量与百家欧赔即便来自不同网站仍属同一 **market** 证据家族；若要对冷门方向提高复审优先级，需再有两个非市场证据族且来源不同。即使满足也不自动反转。
- 初始**研究阈值**：单公司起始/最近报价至少相隔10分钟；至少2家有完整欧赔时间序列的公司；市场热门隐含胜率回落至少3个百分点，或冷门隐含胜率上升至少3个百分点，多家公司同向；欧亚背离要求欧赔热门概率提升2.5pp、亚盘让球负担反向变浅至少0.25球，双公司同时满足。以上都**未经独立历史验证，不是实际胜率或庄家动机判定标准**。
- 港赔/亚洲水位如 `0.91` 必须按该报价源的明确赔率格式正确转换成欧洲小数赔率 `1.91` 后传入，**不可把水位0.91当作十进制返还赔率**。还需核查该盘口是主盘还是次盘、是否发生主盘切换。
- 对初盘时间戳缺失、结算后公布买量、两市场不同步、只有一家报价或缺少真实亚洲让球时，返回 `INSUFFICIENT_BOOKMAKER_TIME_SERIES`，不做诱盘/冷盘结论；严禁使用赛果、红牌、比赛后的伤停/盘口。
- `market_trap_integration_r636.py`: 只读接在旧版 `prematch_exposure_review` 上，严格比对比赛ID、统一截点、开球时间与竞彩整数线；市场层不得取得反向选取或核心授权。
- `test_market_trap_cold_watch_r636.py`, `test_market_trap_integration_r636.py`: 覆盖同公司轨迹、2家公司确认、逆向买量、亚洲盘四分之一球、JC隔离、独立证据族、防止赛后泄漏以及代码不改输入。

### 运行

```bash
cd model
pytest -q test_matchday_publish_gate_r636.py test_r636_exposure_guards_20261122.py \
  test_replay_nov21_exposure_diagnostics_r636.py \
  test_market_trap_cold_watch_r636.py test_market_trap_integration_r636.py
```

本地包含既有审查层的测试 **57/57 passed**。仅测试流程守恒、规则与输入验证，**不代表诱盘与冷盘分类有预测能力**。

## 以后批次的正式验证门槛

按比赛前真实时间冻结：同盘口多公司初价、定时快照、赛前收盘、盘口/水位、去水欧赔、大小球、赔率返还率、凯利（防止重复证据）、买量/必发成交及独立阵容证据；合规记录开盘后新增伤停。随后用赛果和结算数据**单独**计算异常信号对冷门识别的增量AUC/PR、Log Loss、Brier、报警率、误报率、选中场次与未选中场次相比较的风险倍率。开发与时间顺序留出严格隔离，按联赛和盘口深度分组。

缺少赛前真开盘时不以赛后复盘补造任何时间序列。即使客队意外大胜也不能据此说“庄家提前放出冷盘信号”。

**Flaim Fantasy** 只处理用户的美式梦幻联赛数据（ESPN/Yahoo/Sleeper），不提供竞彩足球欧亚盘口或资金成交；因此不参与本模块统计，避免无关数据污染。