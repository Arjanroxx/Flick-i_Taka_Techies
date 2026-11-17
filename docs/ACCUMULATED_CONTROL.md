# Accumulated-control experiment — not recommended for promotion

Completed Nov 18, 2026. This experiment implements the requested over-merging revision and evaluates the frozen result on the public five minutes and the same eight SkillCorner comparison matches. **It does not demonstrate an improvement in the primary metric. Retain the original sustained-control candidate.** No default method, prior candidate, submitted CSV or form response was replaced.

## Results

| Evaluation | Original sustained control | Accumulated control |
|---|---:|---:|
| Public five-minute spellF1 | **0.5429** | 0.3771 |
| Public three-class macroF1 | **0.6964** | 0.6736 |
| Public predicted possessions (reference: 17) | 11 | 18 |
| Eight-match partial-reference spellF1 | **0.4483** | 0.4414 |
| Eight-match H/A macroF1 | 0.7735 | **0.7838** |
| Eight-match predicted/reference spell-count ratio | 0.7676 | 0.9289 |
| Eight-match spell precision at IoU 0.5 | **0.5226** | 0.4661 |
| Eight-match spell recall at IoU 0.5 | 0.4001 | **0.4291** |

The count becomes more plausible, but extra possessions are not reliably correct. On the eight matches, missed reference spells at IoU 0.5 fall from a mean 197.5 to 187.9 per match while spurious spells rise from 120.8 to 164.0. More recovered spells do not offset the new false ones.

The eight-match mean partial spellF1 difference is -0.00693, paired whole-match bootstrap 90% interval [-0.01819, +0.00428], with three wins in eight. This is not evidence of an improvement, nor proof of worse full-match performance. The H/A macroF1 difference is +0.01027, interval [+0.00448, +0.01607], with seven wins. The ranking objective remains spellF1, not frame-level accuracy or possession-count matching.

Public bootstrap intervals are broad: original spellF1 approximately [0.3429, 0.7453], revision [0.2171, 0.5371]. The public result is a final sanity measurement, not a selection criterion or a basis for another tuning round. No settings were changed after either final evaluation.

## Implemented model

The mode `hmm.team_evidence: accumulated_control` is opt-in in `configs/accumulated_control_candidate.yaml`. Neither the default distance configuration nor the original sustained-control configuration is changed.

Observed nearby evidence has strength `min(team_distance_advantage / 2 m, 1)`. Same-team evidence accumulates in seconds rather than imposing a hard two-metre margin. Observed neutral frames decay the accumulator; missing/imputed/stopped evidence, frame gaps and half boundaries reset it. A challenger starts fresh rather than having to undo unlimited incumbent history.

The selected configuration requires 0.24 seconds of full-strength support: e.g. a consistent 0.5 m advantage contributes one quarter strength and needs approximately 0.96 seconds. Offline confirmation backdates support to the first supported contact. This can recover crowded receptions that the original hard gate rejects.

Confirmed H/A likelihoods are bounded between 2/3 and 0.9, not treated as calibrated control probabilities. The lower bound supplies useful evidence for sustained moderate contact; the upper bound stops an extreme distance ratio overwhelming the HMM. Geometry limits and the existing HMM transition matrix remain fixed. This changes evidence supplied to the HMM; it does not introduce a learned control classifier or force a last-owner label indefinitely.

The synthetic regressions recover a sustained crowded turnover, suppress a short extreme tracker touch, preserve D, and reject unsupported accumulation through gaps. They establish intended mechanics, not football accuracy. The external experiment shows that prolonged proximity can still be mistaken for controlled possession.

## Development and freeze protocol

Only the twelve development matches were used to choose parameters. The first trial (0.12 s, minimum likelihood 0.8) increased recall but added many false spells: development partial spellF1 0.4042 versus original 0.4592. A conservative trial (0.24 s, 0.7) recovered to 0.4562.

A declared nine-point grid then compared confirmation times 0.16/0.20/0.24 s and minimum likelihoods 2/3, 0.70 and 0.75. Selection used mean development partial spellF1, then H/A macroF1; it did not target a possession count. The selected 0.24 s / 2/3 setting scored 0.4596 versus original 0.4592 on development, effectively unchanged, while H/A macroF1 rose from 0.7855 to 0.7989. Defaults were aligned with this explicitly configured selection, then a final development rerun reproduced the selected grid score exactly.

The selected source/config fingerprints were locked before public and eight-match evaluation. Both stages verified the lock. The original sustained-control method reproduced its prior external results exactly, preventing an unnoticed baseline change. The eight matches had already been used in the earlier benchmark: this is a **reused comparison set**, not a new untouched holdout. No parameters were changed after observing the final eight-match/public scores.

The source protocol and results are in [the study directory](accumulated_control/): development selection, per-match metrics, test report, freeze fingerprints and public scoreboard. Detailed input caches remain private under `artifacts/accumulated_validation/`.

## Verification and reproduction

All **93 tests passed without skips**. Two full competition-data runs passed the official 199,319-row validator and reproduced identical A/B/C/D/CSV hashes. The new CSV is generated separately at `artifacts/accumulated_control/Flick-i_Taka_Techies.csv`; it is not recommended as a replacement based on this study.

```powershell
# Optional: reproduce the bounded search, using development matches only.
.venv/Scripts/python.exe scripts/tune_accumulated_control.py
.venv/Scripts/python.exe scripts/validate_accumulated_control.py --stage development
.venv/Scripts/python.exe scripts/validate_accumulated_control.py --freeze
.venv/Scripts/python.exe scripts/validate_accumulated_control.py --stage test
# Generate the separate competition candidate; set MTAH_DATA_DIR first.
.venv/Scripts/python.exe scripts/run_full_pipeline.py --config configs/accumulated_control_candidate.yaml --skip-evaluation
```

The SkillCorner source, native-rate adaptation, unknown/D reference limitations and attribution are documented in [the external validation report](SKILLCORNER_VALIDATION.md). Partial external spellF1 and H/A macroF1 are not official H/A/D challenge scores and are not numerically comparable to the public-window score.

## Next research direction

The hypothesis helped recover some missed possessions but did not reliably distinguish true control from prolonged proximity. Further work should diagnose development false transitions and add discriminating reception/pass-continuity or robust team-level co-motion evidence, rather than loosening proximity gates or tuning to public counts. It needs a genuinely separate final comparison set if development continues. This failed primary-metric experiment should remain visible rather than being presented as a stronger submission.
