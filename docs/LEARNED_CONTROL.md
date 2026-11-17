# Learned control classifier — mixed transfer results

Completed Nov 18, 2026. A small conditional team-possession classifier was trained exclusively on other-match SkillCorner references. It passed the predeclared development gate and was then frozen for the eight reused comparison matches and public five-minute sanity evaluation. **The results do not establish a reliable ranking-metric improvement over the original sustained-control candidate; keep the original as the recommended candidate for now.** No original/default configuration or submitted file was replaced.

## Results

| Metric | Original sustained control | Learned-control candidate |
|---|---:|---:|
| Development match-held-out partial spellF1 | 0.4592 | **0.4755** |
| Development match-held-out H/A macroF1 | 0.7855 | **0.7960** |
| Eight-match partial spellF1 | 0.4483 | **0.4560** |
| Eight-match H/A macroF1 | 0.7735 | **0.7850** |
| Public five-minute spellF1 | **0.5429** | 0.4242 |
| Public three-class macroF1 | **0.6964** | 0.6902 |
| Public possessions (reference: 17) | 11 | 16 |

Development improvement was +0.01637 partial spellF1, with wins on 11/12 matches and a paired match-bootstrap 90% interval [0.01173, 0.02073]. This is a model-selection CV result and may be optimistic after selecting among four configurations. It passed the gate fixed before evaluation: mean gain at least 0.01, at least eight match wins and positive bootstrap lower bound. Passing that gate authorized final testing, not release promotion.

On the eight comparison matches the partial spellF1 gain shrank to +0.00765, with four wins in eight and interval [-0.00064, +0.01667]. This does not establish a consistent improvement. H/A macroF1 rose by +0.01151, interval [0.00793, 0.01529], with eight wins. Spell recall at IoU 0.5 increased 0.4001 to 0.4227, while precision decreased 0.5226 to 0.5106. The spell-count ratio rose 0.7676 to 0.8303: some missed possessions were recovered, but false ones were also introduced.

The public score fell despite the count becoming closer to 17. The uncertainty intervals overlap broadly (old spellF1 approximately 0.3429–0.7453, new 0.2667–0.5939), and this sample cannot rank full-match performance reliably. No parameter was selected or altered from this result. The eight matches had been evaluated in earlier experiments and are a **reused comparison set**, not a new untouched holdout. Bootstrap intervals do not account for vendor-reference errors, team/league correlations, domain shift or model-selection effects.

[Per-match CV and final results](learned_control/) and [the frozen model](../models/learned_control.json) are included for inspection. Aggregate external scores are partial-reference H/A metrics, not official H/A/D challenge scores. The reference gaps and D limitations described in [the SkillCorner report](SKILLCORNER_VALIDATION.md) remain unchanged.

## What was learned

This is a symmetric logistic classifier with 17 causal geometry features: distance margin, log distance ratio, relative margin, smooth contact difference, rate of advantage change, team-distance stability, moving/decelerating contact interactions, and 0.2/0.6/1.5-second histories. Distance stability while the ball moves is only a co-motion proxy; stable player-relative velocity is not available across both tracking sources.

No frame index, match ID, player identity, absolute pitch location, provider possession field or phase/event label is a model feature. Team membership from the roster is used only to construct team distances. Histories reset at periods/frame gaps, and unavailable geometry remains masked. The feature builder accepts geometry tables only. Tests verify label noninterference, future-feature isolation and exact team-swap symmetry.

The labels are **provider H/A ownership conditional on eligible detected nearby geometry**, not independently annotated controlled receptions. Unknown labels are excluded, never converted to D. Consequently the classifier estimates conditional ownership and cannot establish whether play is live or whether a touch satisfies the challenge's exact control definition.

A no-intercept parameterization enforces team symmetry. Training uses L2-regularized logistic loss and training-only RMS feature scales. Each coefficient-fit match has equal total weight. Probability temperature is fitted on separate calibration matches, also equally weighted. This is empirical provider-domain calibration, not a guarantee that confidence values transfer to the competition tracker.

## Training and selection

The existing twelve development matches form three fixed match-level folds. Each outer validation fold has four matches, with six other matches fitting coefficients and two separate matches calibrating temperature. No outer validation match participates in scaling, fitting or calibration. Four combinations were compared: ridge 0.01/0.1 and confidence threshold 0.75/0.85. Selection maximized mean held-match partial spellF1, then H/A macroF1.

The selected ridge is 0.01 and confidence threshold 0.75. The final model fits coefficients on the first ten development matches and calibrates on the last two, as declared before training. None of the eight comparison matches or competition labels enters fitting, calibration or selection. The full protocol is `configs/learned_control_protocol.json`, and exact fold assignments are in the development report.

The implementation was isolated from the rejected accumulation branch before final evaluation. A clean-base training rerun reproduced the same CV metrics and byte-identical fitted model. The shared input cache can reuse earlier verified geometry, but never earlier model predictions; fresh runs can build it directly from pinned source data. Runtime has no dependency on the rejected experiment.

## How it participates in inference

`hmm.team_evidence: learned_control` is opt-in through `configs/learned_control_candidate.yaml`. Original sustained-control emissions remain the base. The classifier supplies additional H/A likelihoods only where the original lacks confirmed control, the ball and both team distances are observed, the nearest team is within 2 m, geometry is in-bounds, and P2 dead-ball weight is at most 0.2.

Calibrated probability must reach the selected confidence threshold for consecutive same-team observations (three at 25 Hz, two under the predeclared native 10 Hz conversion). Added probabilities are bounded to [0.05, 0.95]. Existing confirmed emissions are not overwritten, although the offline HMM's global context can still change decoded labels elsewhere. HMM transition settings and dead-ball detection are unchanged. Uncertain classifier outputs leave original evidence exactly intact.

The model is plain JSON with coefficients, scales, temperature, feature names and source/training provenance. Its file SHA-256 is bound in the candidate configuration; a changed file fails closed. No pickle, hosted service, optional scikit-learn package or hidden model dependency is needed. Source data are from SkillCorner's pinned open-data snapshot, credited with PySport in the external report; the downloader preserves source licence/README and verifies checksums. No raw tracking, frame labels or competition assets are committed.

## Verification and reproduction

The targeted classifier regressions and full suite passed. Two complete competition runs passed the official 199,319-row validator and matched all A/B/C/D/CSV hashes. Source/config/model fingerprints remained unchanged through both final evaluations. The original candidate CSV checksum was verified and preserved. The candidate is separate at `artifacts/learned_control_candidate/Flick-i_Taka_Techies.csv` and has not been submitted.

```powershell
# Other-match data only; development fitting and match-level validation.
.venv/Scripts/python.exe scripts/download_skillcorner.py
.venv/Scripts/python.exe scripts/train_learned_control.py
# Requires the recorded development gate to pass; publishes/locks the fitted JSON.
.venv/Scripts/python.exe scripts/validate_learned_control.py --freeze
.venv/Scripts/python.exe scripts/validate_learned_control.py
# For direct inference the committed model/config are sufficient; set MTAH_DATA_DIR.
.venv/Scripts/python.exe scripts/run_full_pipeline.py --config configs/learned_control_candidate.yaml --skip-evaluation
```

The existing configurations still generate their original methods. No parameters were changed after final public or eight-match scores. Further research needs better reception/control evidence and a genuinely separate final test set, rather than another round of tuning against the already inspected public sample or eight matches.
