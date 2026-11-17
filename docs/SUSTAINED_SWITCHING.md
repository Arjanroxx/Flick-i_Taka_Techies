# Step 5: evidence-dependent sequence smoothing

Research only; original candidate remains recommended. This experiment changes H/A switching costs, not ownership emissions or D transition probabilities.

Earlier contact-gated switching accepted every original confirmed contact and improved external scores while regressing publicly. The new opt-in duration gate requires an uninterrupted 0.4-second run of original confirmed control before offering the cheaper H/A switch at its first supported frame. The fixed event probability is 0.02. Both settings were fixed before development evaluation; no sweep or post-public adjustment was performed. Offline confirmation backdates the opportunity; this is not causal streaming inference.

Only the proposal sequence is duration-filtered. Original short-contact ownership likelihoods and uncertainty handling remain unchanged. Runs cannot cross missing evidence, a changed team preference, frame gaps or half boundaries. Original D/half reset rules still apply. A long but misleading nearby contact can qualify, and a genuine brief possession may not qualify; sustained proximity is still only a control proxy.

| Metric | Original | Sustained switching |
|---|---:|---:|
| 12 development mean partial spellF1 | 0.459170 | 0.503771 |
| Development H/A macroF1 | 0.785525 | 0.800700 |
| Public spellF1 | 0.542857 | 0.462500 |
| Public H/A/D macroF1 | 0.696450 | 0.6898 (rounded) |
| Public possessions | 11 | 15 |

All twelve development matches improved, clearing the predeclared gate of mean gain >=0.01 and >=8 wins. Source/config fingerprints were then recorded before the public sanity check and verified unchanged afterward. The public result remains below the original; no promotion is justified. These are reused development matches with partial automatic H/A references and no D reference, not independent challenge validation. The eight comparison matches were not evaluated.

All 121 tests passed without skips; three added regressions cover rejection of brief confirmed contacts, long-contact event timing with unchanged emissions, and half-boundary resets. The complete real-data candidate passed the official submission validator. The original CSV checksum is preserved. No inference defaults or submitted output changed.

Reproduce development scoring from the repository root with `python scripts/evaluate_sustained_switching.py`. The opt-in candidate is `configs/sustained_switching_candidate.yaml`; full-pipeline outputs are separate under `artifacts/sustained_switching_candidate/`. Previous Step 2–4 options are not enabled. Aggregate results and fingerprints are in `docs/sustained_switching/`.

This completes a controlled Step 5 experiment, not a solution to all over-merging. It demonstrates external-reference improvement without reliable transfer to the public challenge sample. Further work needs better-supported possession boundaries and genuinely separate compatible validation, rather than repeatedly selecting settings against the public window.
