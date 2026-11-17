# Step 8: propose possession splits and verify them separately

Research only; not promoted. Step 6 remains protected with its recorded public spellF1 of 0.557143. This Step 8 experiment was not scored on the public window or eight reused comparison matches because its development gate failed.

## Proposal and verification

The opt-in second stage examines long decoded H/A spells, rather than making switching easier everywhere. A spell is considered long when its length exceeds the equal-match average complete reference-spell duration estimated from the other eleven development matches. Final competition inference uses the all-development estimate, 9.512913 seconds; this is a search trigger, not a maximum permitted possession length.

The proposal stage finds observed opponent proximity within 2 m, with at least 0.5 m distance advantage. This is intentionally broader than original confirmed control, so a proposal alone cannot change a label.

The verifier requires at least 0.4 seconds of consecutive moving contact: ball speed between 1 and 12 m/s and opponent nearest-distance change at most 2 m/s. Original confirmed control by the original owner must bracket it within one second on each side. The entire bracket must be observed, non-imputed, live according to B, inside the pitch and within one continuous half/frame block. Brief touches, stationary balls, unstable contact, missing tracking and D conflicts are rejected. Multiple accepted proposals cannot overlap.

On acceptance, the opponent label starts at the first verified moving-contact frame and lasts until the original owner's first subsequent confirmed return. The surrounding original-owner labels remain. This can recover only an internal owner/opponent/owner sequence; it cannot recover a completely unobserved takeover, a stoppage or a takeover continuing beyond the original spell.

The thresholds are fixed heuristic modelling choices reused from earlier contact experiments, **not learned optima**. All checks derive from the same tracking source: movement verification is complementary evidence, not an independent sensor or calibrated proof of control. Nearest-team distance stability is not actual player-relative co-motion and can be misleading during defensive challenges or tracking switches. Genuine stationary/slow receptions or longer unbracketed opponent possessions can also be rejected.

## Development results

The primary predeclared comparison was Step 6 duration + splitting versus duration alone. The original-model pair was a standalone ablation, not an alternative promotion target. Duration parameters and long-spell trigger were estimated leave-one-match-out; no scored match fitted its own scale.

| Model | Mean partial spellF1 | Mean H/A macroF1 | Spell precision at IoU 0.5 | Spell recall at IoU 0.5 |
|---|---:|---:|---:|---:|
| Original | 0.459170 | 0.785525 | 0.540548 | 0.415127 |
| Original + verified splits | 0.457674 | 0.785417 | 0.536881 | 0.415381 |
| Duration | **0.509190** | **0.793171** | **0.615409** | 0.447175 |
| Duration + verified splits | 0.507475 | 0.793065 | 0.611035 | **0.447430** |

For the duration model, eight matches worsened, four were unchanged and none improved. Mean difference was -0.001715, with paired match-bootstrap 90% interval [-0.002512, -0.000971]. For the original, seven worsened, five were unchanged and none improved; mean difference -0.001496, interval [-0.002316, -0.000752]. Both failed the predeclared gate of mean gain >=0.01, at least eight wins and positive paired-bootstrap lower bound.

Each model family gained 22 full-play segments across twelve matches (an internal owner/opponent/owner insertion adds two net segments). Average changed frames per match were 14.25 for the original and 13.17 for duration. Recall barely improved while precision decreased. Additional splits therefore failed to improve recovery under these references, despite passing the tracking-based verifier. No thresholds were changed after seeing those results.

These are repeatedly inspected partial automatic H/A references without D targets, not fresh independent validation. Unknown reference gaps can alter partial-reference counts; full-play counts were measured independently of those gaps. Bootstrap intervals do not capture vendor-reference error, domain shift or repeated development. The results reject this verifier formulation, not every possible split-verification method.

## Integration and verification

The full 137-test suite passed without skips. After two final edge cases were added, all seven targeted tests passed. Regressions cover valid insertion, long-spell restriction, brief/stationary/unstable contacts, missing/imputed coordinates, D conflicts, period/frame discontinuities, missing owner brackets, H/A symmetry, multiple proposals and input preservation.

The separate real-data duration-plus-splitting output passed the official 199,319-row submission validator. It changed 59 labels and added four full-play segments, without public scoring. All posteriors, entropy values, D and X masks remained identical to the Step 6 output. Probabilities remain those of the base decoder; they are not recalibrated confidence for verified splits. Original artifacts were checked against their manifest; the protected duration CSV matches its saved comparison copy, and disabled-splitting duration C regenerated byte-identically.

```powershell
.venv/Scripts/python.exe scripts/evaluate_selective_splits.py
# Private data directory supplied through MTAH_DATA_DIR; validation without public scoring.
.venv/Scripts/python.exe scripts/run_full_pipeline.py --config configs/selective_splits_candidate.yaml --skip-evaluation
```

The opt-in configuration uses the duration decoder and selective splitting only; earlier Steps 2–5 and Step 7 options are not enabled. Outputs are separate under `artifacts/selective_splits_candidate/`. Aggregates, protocol and verification records are in [selective_splits/](selective_splits/). No default, protected candidate, submitted CSV or form response was changed.
