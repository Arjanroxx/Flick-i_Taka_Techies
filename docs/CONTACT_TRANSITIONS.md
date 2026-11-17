# Contact-gated transitions: consistent external gains, public regression

Completed November 18, 2026. **Keep the original sustained-control candidate recommended.** The new opt-in model improves partial-reference spellF1 on all twenty available external matches, but regresses on the official public sample. It is a research candidate, not a demonstrated improvement for the competition. Defaults, original outputs and the submitted file were preserved.

## Results

| Evaluation | Original spellF1 | Contact transitions | Original macroF1 | Contact transitions |
|---|---:|---:|---:|---:|
| 12 development matches | 0.4592 | **0.5010** | 0.7855 | **0.8031** |
| 8 reused comparison matches | 0.4483 | **0.5014** | 0.7735 | **0.7941** |
| Official public five minutes | **0.5429** | 0.4000 | **0.6964** | 0.6916 |

External scores are partial provider-reference H/A scores; public macroF1 includes H/A/D. They are not interchangeable. Development spellF1 improved on 12/12 matches, mean difference +0.04181, paired match-bootstrap 90% interval [0.03292, 0.05115]. Eight-match spellF1 improved on 8/8, mean difference +0.05307, interval [0.04182, 0.06384]. H/A macroF1 improved on all eight, difference +0.02054, interval [0.01604, 0.02482].

On the eight matches, spell precision at IoU 0.5 rose 0.5226 to 0.5513 and recall rose 0.4001 to 0.4753. The spell-count ratio rose 0.7676 to 0.8655, while fragmentation rose 0.8987 to 0.9966. These are improvements in recovered reference spells, not merely a count closer to the reference.

Public possessions rose from 11 to 18 against 17 reference possessions, **without recovering additional matches at IoU 0.5**: both methods matched eight. More plausible counts therefore do not establish correctness. Public spellF1 bootstrap 90% intervals are approximately [0.3429, 0.7453] for the original and [0.2514, 0.5371] for the new model. They overlap, but the observed regression remains a warning; neither small-sample uncertainty nor external gains justify ignoring it. D frame F1 stayed 0.4851; this experiment did not improve dead-ball evidence.

The eight comparison matches have been inspected in previous experiments. They are **reused comparisons, not a fresh holdout**. The source provider's automatic ownership references, masked unknown spans, missing D labels, team/league correlation and native 10 Hz tracking limit transfer conclusions. Bootstrap intervals do not cover these errors or repeated model selection. See [the external-data limitations](SKILLCORNER_VALIDATION.md). No parameters were changed after final scoring, and none were selected using public or eight-match results.

## Why this experiment

The original model's development spell audit at IoU 0.5 found:

| Diagnostic category | Reference spells | Median duration | Fraction with original same-team confirmed control |
|---|---:|---:|---:|
| Matched | 1,677 | 11.20 s | 92.0% |
| No same-team overlap | 1,081 | 1.90 s | 17.6% |
| Shared long prediction | 696 | 6.00 s | 91.8% |
| Boundary/duration mismatch | 528 | 4.50 s | 90.3% |
| Multiple prediction fragments | 68 | 18.55 s | 100.0% |

These are descriptive, ordered overlap categories, not definitive causal labels. In particular, a long prediction overlapping multiple same-team reference spells suggests merging, but reference gaps can also limit what is observable. The contrast between weakly supported missed spells and strongly supported merged spells motivated changing transition cost rather than adding more ownership emissions.

## Implementation and frozen selection

`src/contact_transitions.py` uses the **original** sustained-control detector. When it confirms a team different from the last confirmed team, the HMM gets one switching opportunity at that contact's first supported frame. Existing offline confirmation backdates the opportunity to the first frame of the confirmed run. This is an offline model, not a causal streaming claim.

Only the opposite team's transition row changes: probability mass moves from staying with that team to switching to the newly confirmed team. All transitions into D, out of D and within D remain unchanged, as do ownership emissions, missing-data rules and P2. History resets on a half change, nonconsecutive frame index, outside-period frame or D weight at least 0.5. Missing/contested/imputed frames cannot propose a switch; neutral gaps can carry the last confirmed team, without creating evidence. A short unsupported touch does not qualify. A sufficiently long but misleading nearby contact still can qualify, which is a material failure mode.

Both forward-backward probabilities and Viterbi decoding use the same time-varying transition matrices. Existing uncertainty/abstention handling then applies to those posteriors. The feature is absent from existing configurations, so the default path retains its original results.

Before evaluation, `configs/contact_transition_protocol.json` declared only two event probabilities: 0.02 and 0.1. The gentler 0.02 setting won by mean development partial spellF1 and passed the declared development gate (gain >= 0.01, >= 8 match wins, positive paired-bootstrap lower bound). The 0.1 setting reached only 0.4812 spellF1 and reduced precision despite better frame macroF1. Both configurations are reported, not hidden. Selection makes development confidence intervals optimistic.

The event probability applies once per confirmed turnover at both frame rates. All existing 10 Hz transition/emission scaling and confirmation adaptation remain unchanged. This is an explicit event-level modelling assumption, not exact continuous-time equivalence. The selected configuration and inference/evaluation sources were fingerprinted before final comparisons. No weights are trained, no labels enter inference, and there is no dependency on the learned classifier model or the rejected accumulation experiment.

## Verification and reproduction

All **103 tests passed without skips**, including eight new regressions. Targeted tests cover unsupported touches, missing/imputed coordinates, half/frame-gap/D resets, H/A symmetry, row probabilities, unchanged D entries and emissions, and recovery of an evidence-supported short possession. Time-varying forward-backward and Viterbi are checked against exhaustive enumeration of every path in a small example; constant schedules reproduce constant-matrix inference exactly.

Two full real-data pipeline runs passed the official 199,319-row validator and matched every A/B/C/D/CSV hash. The original C was regenerated byte-identically; all original artifact hashes were verified. Candidate output is separate at `artifacts/contact_transition_candidate/Flick-i_Taka_Techies.csv`. It has not been submitted. Source fingerprints remained unchanged throughout final scoring.

```powershell
# Development diagnosis and the two predeclared candidates, other-match data only.
.venv/Scripts/python.exe scripts/diagnose_development_spells.py
.venv/Scripts/python.exe scripts/evaluate_contact_transitions.py
.venv/Scripts/python.exe scripts/validate_contact_transitions.py --freeze
# Frozen reused comparison; no tuning or release promotion.
.venv/Scripts/python.exe scripts/validate_contact_transitions.py
# Local private-data integration/repeat checks and public sanity scoring.
.venv/Scripts/python.exe scripts/validate_contact_transitions.py --competition
# Direct inference: set MTAH_DATA_DIR, retain validation without public scoring.
.venv/Scripts/python.exe scripts/run_full_pipeline.py --config configs/contact_transition_candidate.yaml --skip-evaluation
```

Aggregate protocols, per-match scores and verification records are in [contact_transitions/](contact_transitions/). Raw tracking, labels and prediction traces remain local. The next validation need is genuinely separate match data with compatible possession boundaries and D annotations, plus a label-independent examination of the tracker/control differences between providers. Further tuning against the same public sample would make the reported result less trustworthy.
