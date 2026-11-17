# Step 9: train a verifier for segment-level metric utility

Research only; development gate failed. The protected Step 6 duration candidate remains unchanged, with its recorded public spellF1 of 0.557143. This Step 9 model was not scored on the public window or eight reused comparison matches, and was not submitted or promoted.

## What was learned

Earlier classifiers predicted frame ownership and Step 8 used hand-written split verification. This model instead learns whether a proposed possession split **improves the official segment metric**. For each eligible other-match proposal, its target is positive only when inserting that split improves exact global mean spellF1 over IoU 0.3–0.7. This is segment-utility supervision with a logistic surrogate, **not direct differentiable optimization of spellF1** and not a controlled-reception annotation.

The proposal generator is broader than Step 8: observed opponent proximity within 3 m with a 0.5 m advantage for the original confirmation length, inside a long decoded H/A spell. Original-owner confirmed contact must bracket it within three seconds. Strong D/out-of-bounds conflicts veto proposals, but short missing spans can be represented as features. No coordinates are invented. Existing X and D labels cannot be overwritten. Greedy score-ranked acceptance prevents overlapping splits.

Twenty segment-relative features describe duration, parent duration, distances/advantage, observed contact and control fractions, movement/stationarity/speed statistics, distance stability, base probabilities/entropy, abstentions, missing coverage and bracket delays. Features contain no reference labels, match identities, absolute frame/time or pitch location. They are symmetric under an H/A swap. Distance stability remains a nearest-team proxy, not tracked-player identity or independent evidence.

Reference gaps and censored proposal intervals are excluded from utility labelling, rather than becoming negative examples. Global utility is computed exactly using the change in the affected scored run, including the global spell-count denominator and official one-to-one matching. Regression tests compare this calculation with a full counterfactual rescore.

## Fitting, threshold selection and held-out evaluation

Three fixed match folds each use six matches for coefficients, two separate matches for decision-threshold calibration and four for evaluation. Duration scale and long-spell search trigger are also fitted on the six coefficient-fit matches only. No scored match influences scaling, fitting, duration estimation or threshold selection.

The classifier uses equal total weight per nonempty coefficient-fit match, training-only feature centering/scaling and fixed L2 strength 0.1. The intercept is unpenalized. Decision thresholds are calibration-score quantiles fixed in the protocol; the disabled baseline is always an option. Selection maximizes mean calibration-match spellF1, then H/A macroF1, then prefers the higher threshold. These are **uncalibrated decision scores**, not probabilities that a split is correct. Threshold calibration here does not mean probability calibration.

The primary predeclared gate required mean held-out spellF1 gain >=0.01, at least eight match wins and a positive paired match-bootstrap lower bound. No hyperparameters or thresholds were changed after held-out evaluation.

| Same-fold held-out comparison | Duration baseline | Learned verifier |
|---|---:|---:|
| Mean partial-reference spellF1 | 0.509491 | **0.511721** |
| Mean H/A macroF1 | **0.792520** | 0.792309 |
| Spell precision at IoU 0.5 | **0.615279** | 0.606400 |
| Spell recall at IoU 0.5 | 0.448118 | **0.457582** |

Mean spellF1 gain was +0.002230, with seven wins, five losses and paired match-bootstrap 90% interval [-0.000799, +0.005292]. This is not a consistent, established improvement. The baseline differs slightly from Step 6's 0.509190 because Step 6 used leave-one-match-out duration estimation from eleven matches; this study fits duration on six coefficient-fit matches to keep threshold calibration fully separate. Raw scores across those protocols must not be treated as an apples-to-apples ranking.

## Frozen proposal-only ablation

After fitting, the same saved outer-fold weights and thresholds were reproduced without retraining or selection. Accepting every proposal scored only **0.386826** mean spellF1; the learned verifier recovered **0.511721**, versus the no-split baseline **0.509491**. Thus learning rejects many harmful proposals, but its remaining net improvement over leaving the duration model alone is small and uncertain. Proposal-only precision/recall at IoU 0.5 were 0.312823/0.516446, illustrating the fragmentation cost of accepting all contacts. This ablation did not alter model settings or authorize promotion.

## Export and integration

The final research model fits coefficients and duration scale on the first ten development matches and selects its decision threshold on the last two. It uses 1,761 utility-labelled coefficient-fit proposals, including 472 positive-utility examples. Final duration/search scale is 9.368214 seconds; final decision-score threshold is 0.408030 (a score, **not seconds**). The two calibration matches are not used for coefficients or duration scale.

`models/segment_verifier.json` contains plain JSON coefficients, scales, threshold and source/training provenance. Canonical JSON checksumming binds model parameters while tolerating harmless whitespace/line-ending changes. The feature names/version and numerical parameters are validated. No pickle, external service or new dependency is required.

The real-data exported candidate passed the official 199,319-row validator. Relative to its own ten-match-fitted duration baseline, it changed 403 labels and added 24 full-play segments; posteriors, entropy, D and X masks stayed unchanged. Those probabilities remain the base decoder's probabilities, not recalibrated confidence for overridden splits. Because this candidate's duration scale is fitted on ten matches, attributing all differences versus the protected all-twelve Step 6 output to the verifier would be incorrect.

The full **146-test suite passed without skips**, including seven new targeted regressions. They cover exact global utility, reference-gap exclusion, H/A feature symmetry, overlap resolution, D/X preservation, train-only scaling, empty/single-class fallback, disjoint folds, canonical hashing and tamper rejection. Protected original artifacts were verified; Step 6's CSV matches its saved comparison copy and its C regenerated byte-identically. No default or protected output changed.

```powershell
.venv/Scripts/python.exe scripts/train_segment_verifier.py
# Optional post-fit frozen ablation, no training or threshold selection.
.venv/Scripts/python.exe scripts/assess_segment_proposals.py
# MTAH_DATA_DIR supplies the private tracking bundle; validation without public scoring.
.venv/Scripts/python.exe scripts/run_full_pipeline.py --config configs/segment_verifier_candidate.yaml --skip-evaluation
```

Aggregates, fold assignments and verification are in [segment_verifier/](segment_verifier/). Candidate output is separate under `artifacts/segment_verifier_candidate/`. Prior Steps 2–5 and 7–8 options are not enabled in this candidate.

## Remaining data limitation

This implements the segment-targeted training experiment possible with the available data; it does **not** supply better-matched external ground truth. The same partial automatic SkillCorner H/A references have been inspected repeatedly and have no D labels. Unknown/censored intervals, provider errors and differences in possession semantics remain. Individual positive counterfactuals also need not remain beneficial when several are combined; joint calibration and held-out scoring measure that effect.

A stronger final claim needs genuinely separate matches with compatible controlled-possession boundaries and D annotations. Public five-minute labels remain sanity data, not training or threshold-selection data. More tuning on this repeatedly inspected window cannot establish reliable generalization. No manual labels or corrections on the challenge match were created.
