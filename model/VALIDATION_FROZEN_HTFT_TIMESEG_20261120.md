# HTFT TimeSeg v0.1: audit of actual archived prematch snapshots — 2026-11-20

**Decision: NO EVIDENCE TO PROMOTE. Keep Shadow; M79.3.6 Production frozen.**

## Exactly what was verified

Three actual Library ZIPs existed BEFORE their fixtures started, with an independently visible Library creation time, a saved internally dated cutoff, SHA256 of original \`frozen_forecasts.json\`, and 31×31 normalized score probability grids.

| JC sale date | ZIP | Complete archive Q | Library upload before first kickoff | Model provenance |
| --- | --- | ---: | --- | --- |
| 2026-10-17 | \`M79_20261017_统一赛前冻结与净阵容观察_1821.zip\` | 24 | yes | market/IPF uncalibrated, NOT fully reconstructed M79 |
| 2026-10-19 | \`M79_20261019_统一赛前冻结_2036.zip\` | 8 | yes | market/IPF uncalibrated |
| 2026-10-20 | \`M79_20261020_统一分析与赛前冻结_1849.zip\` | 9 | yes | market/IPF uncalibrated |
| Total | | **41** | **41** | **0 formally certified M79 Production** |

Original SHA256 checksums (frozen forecast files):
- Oct 17: \`10cc511738d60fc201643ead77cf3c1bd0b59c0da7117b41e7d78d7312d1e04b\`.
- Oct 19: \`daa5b0a135b726182ab614737e9437dd4c18315483a6f079e67bf7a90b22f50e\`.
- Oct 20: \`18a9c5653673886e75eb63307e4f6e6b45edd85a236d434e4f51abba9fe664f5\`.

Each archived score grid is 31×31, with **small but positive** mass where home or away score >10, so the unmodified TimeSeg v0.1 0..10 engine is **incompatible with every original archived grid**. Do not silently clip, renormalize, or claim a complete model fit.

## Full-mass compatibility regression

Additive \`htft_segment_archive_bridge_r636.py\` treats each 0..10 score cell via the v0.1 temporal engine, with a **neutral analytic conditional-binomial fallback** for score cells outside the supported domain. This does not drop any frozen Q mass. Require out-of-range Q tail <=0.001 per game; fail closed for higher tails, report explicit bound for any uncertain state-dependent correction to the missing tail.

For **all 41 archived games**, baseline neutral state factors=1 and original archive 45% first-half goal rate reproduced the original nine-way HTFT probability records: maximum absolute difference **2.731148640577885e-14** over all nine paths and all games. Largest unsupported-score probability tail was **0.0008241126495478941** (0.0824%). This proves compatibility/reconciliation, **not** improved prediction.

## REAL frozen-input retrospective sensitivity: nine matched Oct 20 fixtures

Held constant: each original Oct 20 full 31×31 Q, actual archived pregame odds/score source, all nine actual half/full results. Both variants' probability grids were read-only and never generated using results.

- **Original frozen neutral 45% halves:** Top1 3/9, Top2 5/9, Top3 6/9; nine-class Log Loss **1.8074126965662098**, Brier **0.7816798985607607**.
- **Neutral six-period, prior first-half share 52/(52+58)=47.2727%:** Top1 3/9, Top2 5/9, Top3 6/9; LL **1.8158852552569222**, Brier **0.7864184172137023**.
- **Same 47.2727% half fraction + trailing-side hazard x1.10:** Top1 3/9, Top2 5/9, Top3 6/9; LL **1.809330756491228**, Brier **0.7843973085959558**.
- Paired state-challenger minus **original frozen** LL mean **+0.0019180599250**, deterministic resampling 95% **[-0.0136586470, +0.0191825264]**.
- Paired Brier mean **+0.0027174100**, 95% **[-0.0050309294, +0.0110733516]**. Both confidence intervals cross zero.

The **47.2727% historical fraction** comes from the previous separately archived StatsBomb 48-match event research (52 first-half goals, 58 second-half). The **1.10** trailing hazard was chosen for sensitivity illustration motivated by independent published literature, **not** a fitted weight from the ten/forty-one fixtures. This analysis is a **retrospective sensitivity test of actual pregame-frozen inputs**, **NOT a time-frozen version of the six-phase challenger**: v0.1 was invented AFTER all Oct fixtures. Do NOT publish these nine as a certified independent holdout, claim historical six-segment accuracy, or train new weights using their test outcomes.

Actual matched Oct 20 normal-time HT/FT results (JC codes 001,002,003,004,005,007,008,009,010) were cross-checked against original club/league match results where accessible. Goal-event minute data matched to these 41 games are absent from the frozen input; therefore the six-segment empirical *fit()* cannot be run on an independently certified development period.

## Separate earlier research: R6.3.18 (not pooled)

Prior real historical series, **1450** chronologically held-out 2026 fixtures with halftime/fulltime results:
- In-play *already known halftime score* and trailing-margin binary, n=865, LL **0.5733546→0.5344968**, Brier **0.1925245→0.1794835**.
- **Pregame nine-way**, 1450 fixtures, LL **1.8844992→1.8844988** (virtually no gain), Top1 **458→460** before fulltime marginal re-lock.
- With fulltime locked, five-state nine-way LL **1.8844992→1.8845838** (worse), Top1 **458→458**.
Those were **different** three-/five-state challenger models and separately sourced full/half score archives, NOT a backtest of the new six-period v0.1 engine. The 48 minute-level events are international tournaments not these 1450 club fixtures. Never combine cohorts as if common Q/xG/goal-event records.

## Eligibility conclusion

| Requirement | 41 original Q archive | Real nine-score subset | Genuine six-period historical fit & frozen test |
|---|---: |---:|---:|
| Actual prematch timestamped Q | 41 | 9 | 41 potential |
| Correct normal-time HT + FT | incomplete | 9 | 9 for this exploratory comparison |
| Matched goal minutes + prematch, source-verifiable xG | unavailable | unavailable | **0** |
| Six-period weights fitted entirely before each test's freeze | no | no | **0** |
| Two linked independent chronological samples, full rights/provenance | no | no | **0** |
| Certified paired challenger > baseline | n/a | **no** | **not assessable** |

**No positive improvement claim can be justified.** Do not change the 1.10 hazard or 47.27% fraction to maximize the observed nine games. Only ingest lawful source-specific goal minutes, prematch team xG and frozen Q at the *same* match granularity, fit on earlier available results, lock weights before each future test kickoff, then perform paired nine-class LL/Brier/Top1/Top2/Top3 on untouched fixtures.

## Original source and reproducibility notes

Library original archives are preserved and unmodified. Local audit outputs:
- \`ARCHIVE_ELIGIBILITY_20261120.json\`: 41 match archive provenance and all-ineligible reasons.
- \`ARCHIVE_MASS_BRIDGE_41_20261120.json\`: 41/41 nine-path baseline compatibility check.
- \`RETROSPECTIVE_9_SENSITIVITY_20261120.json\`: 9 match paired numeric audit with uncertainty and individual result records.

The repository does **not** redistribute the user Library ZIPs or external licensed event records. Research status only; **no model weight, formal selection or Production file changes**.
