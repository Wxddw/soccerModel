# R6.3.6 / HTFT TimeSeg v0.1 (2026-11-20) — prematch six-phase hazard bridge

**Status:** Shadow research only. **Production M79.3.6 fully frozen.**
No official single/core/HTFT selection grant, no change to original Outcome, JC handicap, goals or exact-score Q probabilities.

## Purpose and implementation

Existing \`halftime_bridge_r6313.py\` and \`htft_transition_v2_r636.py\` split frozen fulltime scores by an aggregate first-half fraction or nine-way historical logit. They do not explicitly represent 46–60 minute halftime adjustments, or predicted changes when a team leads or trails.

**New** \`htft_segment_hazard_r636.py\` splits 90 minutes and stoppage time into exactly six periods:

| index | playing minutes |
|---|---|
| 0 | 00–15 |
| 1 | 16–30 |
| 2 | 31–45+ |
| 3 | 46–60 |
| 4 | 61–75 |
| 5 | 76–90+ |

For period \`t\`, home and away have separate frozen prematch expected goals and historical segment weights, \`mu_H,t=lambda_H*w_H,t\`, \`mu_A,t=lambda_A*w_A,t\`. At **period boundaries**, multiply home/away conditional goal intensity by the prior-calibrated leading/trailing team factor. The increment count of each team during that period is independent Poisson *conditional on the current boundary state*. Thus the process is **not** continuous time, no within-period tactical reactions, and does not know future goals or substitutes.

A forward DP propagates (cumulative home goals, cumulative away goals, frozen halftime WDL) and the weighted per-phase goal expectations. At 45 minutes halftime WDL is frozen for each path. For each possible terminal score (H,A) in the full **prematch** Q(H,A), normalize the time paths **only within that terminal score**, and assign its original Q mass. This makes:
- \`sum_HTFT P = 1\`.
- For each FT class, \`sum_HT P(HT,FT)=sum_{(H,A) in FT} Q(H,A)\`.
- Original score / total-goals / exact-margin / JC integer handicap marginals are unchanged.
- Sum six home expected-goal periods equals \`sum_Q H*Q(H,A)\` and likewise away.
- Zero-realization Q (0:0 only) gives halftime/fulltime \`平平\`; a single 1:0 outcome under neutral factors splits first-half goal timing according to home six weights.
- Missing Q, incomplete grid probability, unknown score cells >10, post-cutoff data or not-yet-available training results => **fail closed**.

Output: nine HTFT probabilities, Top1/Top2/Top3, halftime WDL, FT WDL, and expected goal count in each of six periods. **Do not mislabel expected goals as probability of an individual goal or exact scoring minute.**

## Fit only using earlier completed matches

\`fit(history, asof_cutoff)\` requires every historical fixture to contain:
- \`match_id\`, \`kickoff\`, \`observed_at\`, \`cutoff\`, \`result_observed_at\` (all timezone-aware and chronologically ordered).
- Prematch snapshot \`home_xg\` and \`away_xg\`, uniquely sourced and captured before match kickoff.
- \`full_time_score\`, \`half_time_score\`, and \`goal_events: [{"minute": 46, "side": "home"}]\`.
- Minute formats: integer 1..90, or strings \`45+N\` / \`90+N\`; 45+ belongs to first half, 90+ to last period. Count **credited score goals**, not wrongly attributed own-goal scorers, disallowed goals, extra time or penalty shoot-outs.
- Events MUST sum exactly to HT and FT scores, no postmatch events in prediction \`spec\`.
- The historical \`result_observed_at\` must precede the training as-of cutoff; self-declared timestamp provenance is not provider-verification.

The research estimator uses separate smoothed home and away six-period scoring shares, then estimates four rate multipliers from **lead/trail state at the start of each prior period**, and observed goals within those periods, with regularization toward 1. Zero-event strata remain close to 1, not a fabricated strong finding. Initial priors \`segment_prior=10\` and \`hazard_prior=12\`; learned factors are clipped to 0.7..1.3. These values are **engineering research guardrails, not calibrated production constants**.

\`predict(q, spec)\` strictly takes:
\`\`\`json
{
 "source_id":"prematch-q-and-xg-20261120",
 "calibration_id":"fitted-earlier-sample",
 "latest_training_result_observed_at":"2026-11-19T22:00:00+08:00",
 "observed_at":"2026-11-20T17:00:00+08:00",
 "cutoff":"2026-11-20T17:30:00+08:00",
 "kickoff":"2026-11-20T18:30:00+08:00",
 "home_xg":1.5, "away_xg":1.1,
 "home_shares":[0.15,0.16,0.17,0.16,0.17,0.19],
 "away_shares":[0.15,0.16,0.17,0.16,0.17,0.19],
 "state_factors":{"home_leading":0.95,"home_trailing":1.1,"away_leading":0.95,"away_trailing":1.1}
}
\`\`\`
**The JSON values above are illustrative placeholders, not calibrated odds, not a verified historical fit.** Do not use them to generate a formal pick; pass the actual output of \`fit\` with independently timestamped calibration provenance. For Q, pass the entire normalized frozen prematch joint-score matrix as the first argument, never only three score candidates.

## Paired chronological benchmark

\`benchmark_htft_segment_r636.py\` reads authorized JSON:
\`\`\`json
{
  "authorized_for_analysis":true,
  "development":[
   {
    "match_id":"dev1","observed_at":"2026-10-01T16:00:00+08:00",
    "cutoff":"2026-10-01T18:00:00+08:00","kickoff":"2026-10-01T19:00:00+08:00",
    "result_observed_at":"2026-10-01T21:30:00+08:00",
    "home_xg":1.5,"away_xg":1.1,
    "full_time_score":"1:0","half_time_score":"0:0",
    "goal_events":[{"minute":46,"side":"home"}]
   }
  ],
  "holdout":[
   {
    "match_id":"test1","observed_at":"2026-11-01T16:00:00+08:00",
    "cutoff":"2026-11-01T18:00:00+08:00","kickoff":"2026-11-01T19:00:00+08:00",
    "result_observed_at":"2026-11-01T21:30:00+08:00",
    "home_xg":1.5,"away_xg":1.1,
    "full_time_score":"1:0","half_time_score":"0:0",
    "goal_events":[{"minute":46,"side":"home"}],
    "score_matrix":[{"score":"0:0","probability":0.2},{"score":"1:0","probability":0.8}]
   }
  ]
}
\`\`\`
This is a **schema example only, not a valid sample size**. Historical match-level event data must have valid usage permission and input provenance. No real historical dataset is shipped.

\`\`\`bash
cd model
python -m pytest -q test_htft_segment_hazard_r636.py test_benchmark_htft_segment_r636.py
python benchmark_htft_segment_r636.py /path/to/authorized_timestamped.json --output /tmp/htft_timeseg_shadow.json
\`\`\`

Both arms receive the **same** prematch Q and segment shares:
- Baseline = six-period Poisson with all state factors = 1. Its HTFT marginal equals classic independent binomial halftime thinning using the fitted first-half segment-share sum (up to numerical precision).
- Challenger = learned segment-boundary lead/trail hazards; same Q.

Paired metrics = nine-class **Log Loss**, **Brier**, Top1/Top2/Top3, empirical class counts, seeded bootstrap 95% paired loss-difference intervals. A negative challenger-minus-baseline loss is a positive direction, but uncertainty and across-league stability matter. **No promotion even if an in-sample or small holdout improves.**

## Current status and limits

10/10 synthetic/local **unit and benchmark contract tests pass**. A separate 121-cell synthetic full grid run had conserved mass and linked expected-goal segments. **None of these is a genuine match-level out-of-sample performance measurement**. No licensed historical match-level prematch Q+goal-event dataset has been used in the new benchmark. Prior HTFT R6.3.14 380-match EPL benchmark is NOT a result for this new module.

Next research channels (not implemented or proven):
- lineup-based start intensity, goalkeeper/CB/CDM AIC, rest, set-piece xG, tactical changes and substitutions as strictly prematch **scenarios** rather than observed future events;
- probability mass for first/next goal in each period, and credible interval for segment rate;
- red-card event scenario model with independent prematch red-card hazard estimates, not observed cards in pregame inputs;
- cross-league chronological paired holdouts, time-regime calibration, reliable data licenses.

## Research literature

1. Maia et al., *Stochastic modelling of football matches* (2023), https://arxiv.org/abs/2312.04338 — Cox-process scoring hazards depend on score situation and match events. Its reported score-effect values are **not imported as our parameters**.
2. Ayana et al., *Temporal dynamics of goal scoring in soccer* (2025), https://arxiv.org/html/2501.18606v1 — nonuniform goal-time distribution over 3,433 matches; reported timing patterns motivate calibration, not direct fixed weights.

**Flaim Fantasy** covers personal ESPN/Yahoo/Sleeper fantasy leagues, not verified football/soccer match-minute sequences. It is not an eligible source for this task and is not fed into fit.
