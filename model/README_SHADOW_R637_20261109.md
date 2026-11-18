# M79.3.6 Production冻结 + Shadow R6.3.7

**Date:** 2026-11-09  
**Purpose:** 25-match recap-driven research adjustment: symmetric direction risk, effective-squad role functionality, core authorization separation, score-family runners-up and official JC handicap data contract.

## 1. Version and permission

- Production M79.3.6 remains fully frozen.
- R6.3.7 is a research-only overlay on R6.3.6/R6.3.5/R6.3.4/R6.3.3.
- No fitted weights, WDL probability changes, automatic direction flips, or formal single/core/protection/handicap grants.
- The 25-match conversation recap is descriptive development evidence only, not an official frozen prematch archive, training set, threshold-fit set, or independent holdout.

## 2. Corrected recap arithmetic

The 25 published prematch predictions for matches 006–030 were re-entered row-by-row and checked against actual FT/HT scores:

| Metric | Hits |
|---|---:|
| WDL unique direction | 16/25 (64%) |
| WDL double protection | 22/25 (88%) |
| Goal Top3 | 20/25 (80%) |
| Exact Score Top3 | 17/25 (68%) |
| HT/FT Top2 | 16/25 (64%) |

The previous narrative stated HT/FT 17/25; exact row-level recomputation corrects this to **16/25**. No official JC integer handicap pick was frozen for all 25 matches, so handicap accuracy is deliberately not calculated. Matches 001–005 had no prematch model output in the reviewed conversation and are excluded.

Miss groups:
- WDL single: 006, 009, 011, 018, 020, 021, 025, 028, 029.
- Protection: 011, 018, 029.
- Goal Top3: 018, 019, 021, 025, 028.
- Score Top3: 007, 011, 018, 019, 021, 023, 025, 028.
- HT/FT Top2: 006, 009, 011, 015, 018, 020, 023, 025, 029.

The 018 (AIK 3–2 Häcken) core-candidate failure, 011 and 029 protection failures, and 019/021 high-tail misses are diagnostic examples, not fitted targets.

## 3. DVRG v0.1 — Direction Vulnerability Review Gate

R6.3.5 HFRG only reviewed home favorites. R6.3.7 extends risk review symmetrically to a selected home or away Top1 when Top1 >= 40% and direction is not draw.

Input options (use one, not both):
- `favorite_risk_evidence`: families `roster`, `schedule`, `tactical`, `opponent_strength`, `market`; state is `adverse_to_favorite`, `neutral`, or `favorable_to_favorite`.
- Existing `risk_evidence`: home-relative records are safely inverted when raw direction is away.

Evidence families are deduplicated by cause. Two adverse independent families or a severe critical-spine roster warning produce HIGH_RISK; one adverse family produces WATCH; fewer than two audited families produce UNKNOWN. A clear review requires at least two families and no adverse family.

Unknown/high risk affects core review only. It does **not** delete the unique raw Top1, change probabilities, flip direction, or issue a formal single grant. This is intended to address 011/018/029 without making the model stop selecting a unique direction.

## 4. ESR Functionality v0.1 and MSI handling

ESR exposes:
- goalkeeper replacement quality shift;
- center-back + defensive-midfield central spine shift;
- attacking-midfielder + winger + striker attacking-unit shift;
- effective XI strength gap and change relative to baseline.

These role components remain one roster family and cannot be counted as independent votes. MSI remains objective context only. Opponent must-win or higher stakes is a review flag, not a direct probability boost and not an independent risk family.

## 5. Selection Efficiency v0.5

- Preserve raw WDL Top1 as the unique research direction.
- Separate direction coverage from core readiness.
- A core candidate requires structural probability, complete confirmed ESR, verified MSI, prior R6.3.4 evidence pass, and DVRG clear review.
- High risk, missing risk evidence, projected-only XI, or MSI/context conflict can hold **core status**, not erase the raw direction.
- Avoidance recovery thresholds remain unchanged (Top1 >= 35%, Top1-second gap <= 8pp); recovery is review-only, never automatic restoration.

## 6. GS1.5 score-family runners-up

- Original probability-ranked Score Top3 remains unchanged.
- Add Top2 score candidates within each WDL result family, including the draw family (to expose 2:2/3:3 candidates when relevant).
- Add the best scoreline in each exact total-goal bucket, with explicit 5/6/7+ high-tail watch candidates.
- No score candidate replaces the Top3; no probabilities change.
- 019 (4:3) and 021 (4:4) do not justify globally raising 7+ probability. Tail evidence remains timestamped, independent and pre-cutoff.

## 7. S4 v1.7 official handicap contract

Required prematch fields:
- `official_handicap_line`: integer from -3 to +3, with negative = home gives goals, positive = home receives goals.
- `official_handicap_line_source`: `source_id`, `observed_at`, `basis="official_jc_handicap"`.
- `frozen_handicap_pick`: exactly one of `让胜`, `让平`, `让负`.

Missing any required field returns UNKNOWN and no accuracy score. Asian handicap cannot substitute for the official Chinese lottery integer line. Handicap probabilities still come from the same coherent score matrix.

## 8. Unchanged modules

- RC2.5 exact 0/5/7+ routing remains unchanged.
- HT-State v0.3 remains unchanged; full 9-state joint distribution is still required.
- WDL probabilities remain unchanged; proper probability scores cannot improve from a selection-only overlay.

## 9. Known R6.3.6 package defect repaired in this copy

The inherited GS1.4 exact-tail cross-check referenced `top_total_buckets` before it was defined. R6.3.7's bundled copy defines the set from the frozen Score Top3 before checking the tail. The original R6.3.6 archive in Library is left untouched.

## 10. Test execution

Command:

```bash
python -m pytest -q test_selection_efficiency_r633.py test_motivation_squad_r634.py test_shadow_r635.py test_shadow_r636.py test_shadow_r637.py
```

Result: **112 passed, 0 failed** (23 R6.3.3 + 28 R6.3.4 + 21 R6.3.5 + 23 R6.3.6 + 17 R6.3.7). The R6.4 base200 suite was not included in this run and is not claimed as re-executed.

## 11. Promotion gate

- Minimum 50 independent forward matches; recommend 100+.
- R6.3.6 and R6.3.7 must use identical prematch snapshots and identical cutoffs.
- Report single hit rate, single coverage, correct raw Top1 missed by prior avoidance, incorrect recovery singles, protection misses, core false grants, conditional accuracy, Brier/LogLoss (only if actual fitted probabilities are changed), Goal bucket calibration, Score Top3, HT/FT Top2, and S4 actual JC handicap pick performance.
- Stratify home/away favorites, weak edges, squad changes, schedule pressure, and market disagreement.
- No automatic promotion and no tuning on this 25-match recap.

## 12. Run

```bash
python run_r637.py prematch PREMATCH_PACKET.json shadow_output.json
python run_r637.py replay-recap25 RECAP_25_INPUT_CONVERSATION_ONLY.json RECAP_25_AUDIT_R637.json
```
