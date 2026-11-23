# R6.3.6 — 2026-11-18 postmatch repair research (Shadow only)

**Created 2026-11-19.** Research *track name* R6.3.6-postmatch; do not confuse with pre-existing `shadow_r636.py` (dated 2026-11-08). Based on `import/r6.3.12-unified-score-matrix-20261117`, which already contains R6.3.14 research materials. It is **not** a downgrade to older R6.3.6 logic.

## Hard freeze
- M79.3.6 Production: no edits to weights, decision rights, WDL Top1, protection, JC, Goal, Score or CORE.
- All challenger outputs are Shadow; no automatic selection or release.
- Never use match results to reconstruct missing prematch `Q(h,a)`, line, odds, availability, substitutions, or injury reports.
- Source independence: odds, Asian lines, exchange prices derived from the same market are one evidence family unless independence can be demonstrated.
- Prematch timestamps must precede the actual kickoff. Postmatch evidence is reserved for scoring, not features.
- Do not merge research candidates into Production until blinded chronological holdout meets pre-registered gates.

## Priority 1 — Score × exact margin joint matrix (first)
Use a **single complete normalized prematch Q(h,a)**, all cells >=0 and sum=1 (tolerance 1e-8). Reject incomplete/Top3-only/renormalized-tail input.
Derive all WDL, exact margin buckets, official JC handicap triad, goals 0..6/7+ and Score Top3 from Q *only*, preserving one source of truth. For signed official line L, adjusted difference `h+L-a`; equal zero => **让平**, positive => 让胜, negative => 让负. Do NOT use an Asian line as JC line.
Required checks:
1. Mass conservation across WDL, JC, goal bins and margin groups, independent of Score Top3.
2. Goal Top3 to Score Top3 coverage report with missing-bucket candidate, but no forced overwrite of original Score Top3.
3. Exact margin = 1/2/3+ for -1/-2/-3 official JC lines; monitor away big-win tails separately.
4. Near-tie (< = 5 percentage points) and 1-goal-margin risk are *review flags only*, not automatic grants.
5. Score family top candidate may differ from aggregated WDL/JC top candidate without creating mathematical inconsistency.
Existing basis: `joint_bridge_r6312.py`, `calibration_r6314.py`, associated tests. Implement additive audit rather than duplicate probability engines.

## Priority 2 — RC dual tail and integer goal buckets (second)
Compute `P(T=t)` from the same Q for t=0..6, plus 7+; preserve central peak (normally 2/3). Study 0/1 low tail AND 5/6/7+ high tail as separate buckets, including 4-goal edge.
- One tail slot maximum under the existing two-independent-evidence-family rule; contradictory high/low evidence => flag conflict and keep baseline ranking.
- Never mechanically add 0, 4 or 5+ following a known match outcome; only compare candidates by chronological holdout metrics.
- Report exact-bucket multiclass Brier, log loss, Top3, zero-goal recall, 4-goal recall, 5/6/7+ recall, false-tail activation and central-peak preservation.

## Priority 3 — AIC replacement roles + match tempo (third)
Prematch features only: key position, expected minutes, substitution quality, role fit, lineup uncertainty, depth, rotation, schedule rest, opponent tactical matchup.
Separate **pre-match predicted state transition** (ahead/level/behind, 0–30/31–60/61–90 minute bands) from **in-match observed events**. Never leak eventual goals, red cards, substitutions or injuries into prematch AIC.
Three rival models: absence-only baseline, role/quality replacement correction, and replacement+tempo state-transition model. Test incremental gain; if none, keep baseline.
Prevent role duplication and family double counting; report both favorable and adverse counterexamples.

## Priority 4 — Outcome market reversal constraint (fourth)
Retain frozen original outcome and track each subsequent recommendation as an explicit candidate with timestamp and source provenance.
- Market-only swings cannot flip WDL selection.
- Require at least two independent adverse evidence families plus a directional margin threshold that was registered before the holdout.
- HRI/WFC may demote CORE, not reverse direction by themselves.
- Audit reversal-benefit and reversal-harm separately: original-correct-but-flipped-wrong, original-wrong-flipped-correct, both wrong, and no-flip.
- Do not optimize using the 2026-11-18 four results.

## Development-only casebook (NOT independent validation)
2026-11-18 JC001 Coritiba 0–1 Santos: originally discussed away; last frozen discussion home; *latest* prediction misses WDL/protection, actual +1 JC draw.
JC002 Flamengo 2–1 Athletico-PR: WDL win, official -2 => 让负 (not 让平); 2–1 score Top3 hit.
JC003 Corinthians 4–0 Botafogo: WDL win, official -1 => 让胜; 4 goals and 4–0 outside frozen goal/score Top3.
JC004 Gremio 0–0 Bahia: WDL draw, official -1 => 让负; 0 goals and 0–0 absent frozen Top3.
Casebook may guide failure taxonomy, but cannot fit weights or claim efficacy.

## Evaluation contract / exit gates
0. Establish original frozen packets, provenance of real JC integer lines and 90-min outcomes. If absent, mark NOT_EVALUABLE; NEVER infer original `Q` from published picks.
1. Run all inherited regression tests and add audit unit tests (normalization, incomplete grid refusal, JC -2 boundary 2–0/2–1/3–0, 0 and 7+ bins, no-leak AIC, two-family reversals).
2. Development set and **chronologically later, untouched** holdout. Pair Production / existing R6.3.14 / new challenger with identical prematch cutoffs and identical match population. Use independently sourced licensed records.
3. Compare WDL/JC/RC/Score/HTFT: multiclass log loss, Brier, ranked probability score where appropriate, Top1/Top3, calibration by bucket, paired confidence intervals, exclusions and coverage.
4. Require non-degradation in upstream WDL and both log loss and Brier (not only hit rate) for claimed downstream improvements; no one-match hotfixes.
5. Stage-gate in the exact order above. A failed priority does NOT authorize skipping it to promote later items. Document adverse evidence and remain Shadow.
6. Keep initial 2026-11-18 four-match results in diagnostic-only file; they must never be included in independent test denominator.

## Current status
Branch created; this file registers the research sequence and acceptance criteria. **No new calibrated parameters, accuracy improvements, or real-case backtest certification have been established by this document.** No edits to Production.


## Additional requested parallel research: HTFT v2 (2026-11-20)
Nine-category HTFT conditional state transition has been implemented as a **research-only independent output**:
- \`htft_transition_v2_r636.py\`: full Q(H,A) + historical home/away halftime goal fractions + regularized nine-path transition weights; each FT score cell is normalized separately, guaranteeing exact original FT marginals.
- \`benchmark_htft_transition_v2_r636.py\`: authorized JSON development/holdout paired evaluation; multiclass Log Loss, Brier, Top1/2/3 and seeded bootstrap CI. Historical *result-observation* time must precede holdout source observation.
- Unit tests \`test_htft_transition_v2_r636.py\` and \`test_benchmark_htft_transition_v2_r636.py\` (8/8 passed in standalone local test run; not a real predictive backtest).
- See \`README_HTFT_V2_R636_20261120.md\` for input/output contract and literature.

This is **parallel research** requested by the user; it does not skip or re-order the four existing R6.3.6 gates, modify Production or claim new real-world predictive accuracy.


## New optional HTFT TimeSeg v0.1 research channel — 2026-11-20

The user requested an additional **prematch-predictive time-segment model**. This does not change the frozen 4-stage R6.3.6 priorities or the official M79.3.6 Production weights and grants.

- \`htft_segment_hazard_r636.py\`: new six-period conditional Poisson hazard DP; transitions depend on leading/trailing team state **at period start** and on source-checked historical parameters. Reanchors all temporal paths to the **unchanged** prematch full score Q(H,A); emits period expected-goals and nine HTFT class probabilities.
- \`benchmark_htft_segment_r636.py\`: authorized offline historical event train / chronological holdout, neutral-vs-state-dependent paired match comparison (HTFT Top1/Top2/Top3, Brier, Log Loss, bootstrap CI); timestamps must demonstrate that training results preceded every holdout prematch observation.
- \`test_htft_segment_hazard_r636.py\` and \`test_benchmark_htft_segment_r636.py\`: **10 local synthetic/contract tests passed**. This number is not a real-match predictive validation.
- \`README_HTFT_TIMESEG_R636_20261120.md\` documents strict input contracts, side/goal-timing, provenance and academic research.

This model requires licensed historical **goal event times**, prematch frozen team xG and Q, and independent input provenance. It has **not** been run on a historical real-match test sample with verifiably frozen predictions; it is **SHADOW / not certified**. Do not use completed fixture events as features for a prediction of that same fixture.


## Frozen-prematch historical eligibility / HTFT TimeSeg audit (2026-11-20)

See \`model/VALIDATION_FROZEN_HTFT_TIMESEG_20261120.md\`, plus \`model/htft_segment_archive_bridge_r636.py\` and \`model/test_htft_segment_archive_bridge_r636.py\`. Three user-owned archive ZIPs (Oct17/19/20) expose **41 legitimate pre-kickoff complete 31x31 Q** from market/IPF reference models, not full Production M79. Under neutral 45% temporal split, all **41/41** archived nine-class distributions reproduced (max absolute discrepancy 2.7311e-14). A nine-match Oct20 score-aligned **retrospective sensitivity** yielded original LL 1.807413/Brier .781680 versus candidate 47.27%-first-half + 1.10 trailing-hazard LL 1.809331/Brier .784397 (**both worse**; confidence intervals span zero). The six-phase challenger was **not frozen before those historical kickoffs**, and matched historical goal-event minutes/eligible train-test records are unavailable: certified independent new-model n=**0**. Keep Shadow. Neither synthetic unit tests nor older R6.3.18 known-halftime live improvement proves prematch improvement.


## Nov23 research amendment — joint score tails + HTFT two-goal margin regimes (Shadow only)

Following the 2026-11-22 16-match frozen market/IPF retrospective, new conditional joint-score calibration and HTFT 2-goal-segment research modules were added without changing any Production parameters or released picks:
- `joint_tail_calibration_shadow_r636.py` with `benchmark_joint_tail_shadow_r636.py`: six non-overlapping-score features, pregame expected-goal regimes, chronological fit and paired out-of-sample scoring. Tilts Q strictly within fulltime WDL classes, leaving Outcome frozen but requiring **every** dependent Score/Goal/JC (and any future HTFT) candidate to be recomputed from the same changed research Q. No training until enough authorized earlier match-level frozen Q and results are available; missing learned regime => fail closed.
- `htft_margin2_timeseg_shadow_r636.py`: add separate 1-goal vs 2+-goal lead and trail phase-boundary intensities, conditioned on the **original** Q(H,A). Requires 80+ earlier timestamped licensed goal-minute matches; no actual in-play events as pregame features.
- `htft_regime_watch_r636.py`: nine-class state-risk probability/Top2 review, exact FT marginal verification, explicit five-decimal display rounding tolerance.
- `replay_nov22_development_r636.py` + `DEV_20261122_FROZEN_REPLAY.json`: verify immutable 16-match original market/IPF Q SHA-256, contrast expected Score Top3 **4.51398** vs actual **1**, HTFT Top2 **9.24728** vs actual **10**, and 5+goals **4.33298** vs actual **6**. These are **postmatch diagnostic facts, not new candidate predictive results**.
- See `README_R636_NOV23_JOINT_TAIL_HTFT.md` for detailed contracts and restrictions. Selected local test suite with the Nov21/22 audit modules passed **62/62**; this is functional regression only, not full-repository or historic predictive certification.

**Freeze:** M79.3.6 Production unchanged; independent eligible holdout for new modules not yet performed; no formal grant.


## 2026-11-23 Market trap / cold-price signals (Shadow)

Added `market_trap_cold_watch_r636.py`, `market_trap_integration_r636.py`, their tests and `README_R636_MARKET_TRAP_COLD_20261123.md`.
The read-only market layer distinguishes 1X2 price drift, underdog shortening, euro/Asian line divergence, shallow lines for high-probability favorites, and prematch crowd/price divergence. Bookmaker identity + timezone-aware observation times + frozen cutoff are compulsory; at least two companies with genuine pregame time-series quotes for any cross-book signal. Asian quarter lines MUST NOT be confused with official three-way JC integer handicaps, and bookmaker water formats must be converted explicitly.
No bookmaker intention, fix, or manipulation inferred. Multiple market outlets and purchase shares constitute **one** correlated evidence family. Independent nonmarket evidence remains a prerequisite for a cold-direction escalation. **No automated reversal or core grant**.
The 2026-11-22 16-game archived market/IPF snapshot lacks full timestamped opening/latest per-book odds, so `DEV_20261122_ODDS_16_FAIL_CLOSED.json` correctly returns insufficient evidence in all cases without inventing historical movement or explaining known upsets post hoc.
**57/57** selected local combined Nov21/22 + new-market tests passed, functional only; independent predictive accuracy certification is **not yet available**. Production unchanged.
