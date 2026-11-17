# Shadow R6.3.14 — Five-module research calibration (2026-11-17)

**Production M79.3.6 frozen. Prior Shadow R6.3.13 source files unchanged.**

## What is actually implemented

- `calibration_r6314.py`: one score-grid margin bucket (-3-/-2/-1/0/+1/+2/+3+) and goal bucket (0..6/7+) utilities, development-only category correction with positive weights, probability conservation, official JC integer-line ±1/±2/±3 audit, 5pp narrow margin warning, precise Brier/RPS/log loss, half-time historical prior, strict timestamped odds baseline.
- `shadow_r6314.py`: optional research-only fitted weights attached to an already valid R6.3.13 prematch packet, proposed candidate grid derived separately without ever replacing original Q or granting formal selections; rejects postmatch input and future training dates.
- `benchmark_r6314.py`: offline paired chronological evaluator for S4, RC, 4 GS candidate families, historical HTFT fractions, market benchmark and JC only with confirmed official signed integer lines. **Never downloads or scrapes data**. Output marks optional channels blocked when requisite source evidence is unavailable.
- `test_calibration_r6314.py`: regression tests including strict train/test separation, output conservation, full grid vs Top3, future halftime training leakage and bookmaker observation timestamps.
- `EXTERNAL_EPL_2023_26_EXPERIMENT_R6314.json`: aggregated research observations from isolated 3-season EPL benchmark; no match-level proprietary dataset included.

## 2023/24–2025/26 external chronology experiment

**380 past games** from 2023/24 were available for prior-team strength; 2024/25 380 used for development; 2025/26 380 used as a future-season held-out test. Team expected goals were a rudimentary independent historical rolling scoring/conceding baseline, *not* M79's Production parameters. Data source: <https://www.football-data.co.uk/data.php>, column specification <https://www.football-data.co.uk/notes.txt>.

| Research channel | Baseline Log Loss | Challenger Log Loss | Decision |
|---|---:|---:|---|
| S4 seven-bin exact margin | 1.776805 | 1.783281 | **Worse; BLOCK promotion** |
| RC 0..6/7+ goals | 1.858861 | 1.857241 | Tiny LL improvement, Brier worsened; WATCH only |
| HTFT nine-way conditional thinning | 1.927642 | 1.925708 | Tiny improvement, 243→246/380 Top3; WATCH only |
| Outcome original independent model vs preclosing de-vig | 1.039079 | 1.015252 | Market multiplicative baseline better; **not an instruction to auto-switch** |
| GS four score-model families | 2.925622 Poisson | 2.925622 DC/BIV (zero dependence fitted) | No measured improvement; no preferred complex family |

GS exact-score Top3: 110/380 (~28.95%); total goals Top3: 248/380 (~65.26%). NB log loss 2.925739. **Do not interpret 380 as 380 certified M79 predictions**.

S4 hypothetical -1/+1 risk warnings: 24 before and 22 after candidate calibration across the 380 matches x2 lines; no actual JC line has been used in this EPL experiment. The earlier 46-match chat recap is a distinct exploratory source, never mixed into these benchmarks.

**Warning:** Football-Data publicly restricts automated AI and data-training uses of its data. No original match-level CSV is redistributed. Future reproduction should use a dataset supplied with authorization or an appropriately licensed source, through the offline benchmark runner. Market quote timestamps must be explicitly preserved for true paired same-cutoff comparisons.

## Offline benchmark with an authorized dataset

Prepare an authorized JSON with development and test arrays, each record having `match_id`, timezone-aware ISO `cutoff` and `kickoff`, a *fully normalized prematch score_matrix* of `{score,probability}`, and `result_score`. Optional: `half_time_score`, complete `candidate_specs` for all four R6.3.13 models, fully timestamped `market_snapshot`, `official_jc_integer_line` (actual official JC signed integer, not Asian line).

```bash
cd model
python -m pytest -q test_selection_efficiency_r633.py test_motivation_squad_r634.py test_shadow_r635.py test_shadow_r636.py test_shadow_r637.py test_shadow_r638.py test_shadow_r639.py test_shadow_r6310.py test_shadow_r6311.py test_shadow_r6312.py test_shadow_r6313.py test_calibration_r6314.py
python benchmark_r6314.py /path/to/licensed_prematch_dataset.json --output /tmp/out.json
```

`benchmark_r6314.py` **does not infer** missing prematch Q from results. Do not feed 11/12–16 user conversation scores as if they were original frozen matrices. A proper independently validated model improvement requires more external seasons/leagues, timestamped bookmaker quotes, full JC lines, and statistical error bars.
