# Control-aware spatial evidence candidate

**External validation completed:** [20-match SkillCorner report](SKILLCORNER_VALIDATION.md). The frozen control-aware method improved partial-reference spellF1 on all eight test matches, but provider labels and unknown D intervals limit what this establishes. This remains a separate candidate; no competition submission was changed.

Pitch boundaries inform whether the ball is dead. Possession boundaries require a different question: did the opponent gain control, or merely become momentarily closer? This experimental option addresses the latter without changing raw tracking or inventing new coordinates.

## Implemented behavior

`src/control_evidence.py` derives a view of Contract A using Contract B's stoppage evidence. An observed contact candidate must satisfy all of:

- Ball and both team distances are available; the ball is not imputed and has no missing-gap claim.
- The frame is inside a half, B does not flag out-of-bounds, and dead-ball weight is at most 0.2.
- The nearest team is within 2 metres and has a 2-metre advantage over the other team.
- The same team satisfies these requirements for at least three consecutive frames. A gap, ambiguous frame, period change or noncontiguous frame index breaks confirmation.

These are transparent physical priors reused from the existing local proximity arbiter, not fitted or calibrated control probabilities. There are no player IDs, manual corrections or match-frame-specific rules.

In offline inference, a confirmed run supplies team evidence from its first contact frame, avoiding a fixed two-frame confirmation delay. A shorter touch supplies neutral H/A evidence; distant or contested frames also supply neutral evidence. The existing HMM, its selected transition settings and its uncertainty shield handle temporal continuity. The algorithm does not force a new label simply because a contact exists, hold an owner indefinitely, or delete every short output segment. Strong D remains under P2/P3 control and each half resets independently.

## Activation and compatibility

The existing `configs/config.yaml` retains distance-only evidence. Its inference behavior is unchanged. The candidate enables `hmm.team_evidence: sustained_control`, with an explicit `control` settings block:

```powershell
# Set MTAH_DATA_DIR to the authorised tactical bundle location first.
.venv/Scripts/python.exe scripts/run_full_pipeline.py --config configs/control_candidate.yaml --skip-evaluation
.venv/Scripts/python.exe evaluation/validate_submission.py artifacts/control_candidate/Flick-i_Taka_Techies.csv
```

Outputs use `artifacts/control_candidate/`, keeping prior releases and saved overrides separate. The A/B/C/D schemas are unchanged. A separate mode prevents an unvalidated hypothesis silently replacing the audited submission.

## Verification and limits

Targeted regressions cover a two-frame defensive touch, a sustained turnover with a boundary at first supported contact, far/contested/missing/imputed/stopped evidence, confirmation across gaps/halves, invalid settings, and explicit compatibility with distance-only mode. The full suite and two real-data pipeline runs are logged under `artifacts/control_candidate/`.

This is a control proxy, not proof of controlled possession. Three nearby observations can still be a rebound; genuine short receptions may fail confirmation. A pass may travel far from every player while possession continues. Neutral evidence lets the HMM infer those stretches, but can still misplace a turnover or become too uncertain. Tracking teleports, long outages and incomplete D coverage remain limitations. Rejecting spatial evidence may increase X and harm macroF1. No public-window score is used to select or tune this candidate, and no full-match accuracy improvement is claimed. Independent labelled other-match data is needed before calling it a stronger submission method.

Executed verification: all **79 tests passed with no skips**. Both real-data runs passed the official 199,319-row validator and reproduced identical A/B/C/D/CSV hashes. Evidence and diagnostics remain local. No public scoring or model selection was performed.
