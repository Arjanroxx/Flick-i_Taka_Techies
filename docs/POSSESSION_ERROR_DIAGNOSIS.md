# Step 1: identify which possession errors the original model makes

November 18, 2026. This step adds a read-only error diagnostic. **No model settings, predictions, overrides or submission files changed.** The protected original still scores **0.542857 spellF1** on the public five minutes. The diagnostic reproduces that score using the official spell implementation.

## Public sample: what is actually wrong

The reference contains 17 possession spells; the original predicts 11. At the official headline IoU of 0.5, **8 spells match, 9 reference spells are missed and 3 predicted spells are unmatched**. The count deficit of six therefore does not mean that inserting six boundaries would solve the errors.

The following categories partition the 17 reference possessions:

| Diagnostic category | Reference possessions | Interpretation |
|---|---:|---|
| Matched at IoU 0.5 | 8 | Recovered sufficiently well at this threshold; timing can still be imperfect |
| Missed team possession | 4 | No overlapping prediction for the correct team; the filled prediction includes the opponent |
| Boundary/duration mismatch | 3 | A same-team prediction exists but its overlap is insufficient; no detected same-team bridge or fragmentation explains it |
| Merged prediction overlap | 2 | Insufficient overlap with a prediction that bridges distinct same-team reference possessions |

Separately, the tool identifies **two concrete predicted spells bridging an opponent possession**. No predicted same-team spell bridges a D-only separator in this sample. These bridge events overlap the spell categories above: **do not add them to the nine missed spells**.

The sample has **four reference stoppages**. Two have no predicted D coverage; the other two are only partly covered. A missed D interval need not merge two same-team spells: it may instead extend one team until the next team or another predicted boundary. This is why D coverage is reported independently of same-team bridges.

All four missed team possessions have observed, non-imputed ball coordinates throughout, but **zero confirmed same-team control frames under the original detector**. This establishes that missing coordinates alone do not explain those four misses. It does not establish whether tracker geometry, the proximity/confirmation filter or the possession definition caused the absent control evidence.

Across the eight matched spells, internal endpoint observations have mean absolute error **4.16 seconds**, median **2.96 seconds**, and maximum **11.92 seconds**. These are matched-spell endpoint errors, not transition-detection latency across all possessions. A shared transition can count as two spell endpoints. Endpoints at the reference window's edges are excluded from this summary because the full spell is not observed there. Per-spell signed errors are retained locally: positive means late, negative means early.

## Twelve external development matches

Only the predeclared twelve development matches were processed. The eight reused comparison matches were not re-evaluated in this step.

| Reference-spell category | Count |
|---|---:|
| Matched | 1,677 |
| Missed team possession | 1,007 |
| Merged prediction overlap | 725 |
| Boundary/duration mismatch | 515 |
| Predicted dead instead of possession | 53 |
| Fragmented or boundary mismatch | 52 |
| Entire reference run unanswered | 21 |
| **Total** | **4,050** |

There are 3,118 predicted spells and **561 opponent-possession bridge events**. Mean per-match partial-reference spellF1 remains **0.459170**, exactly the original development result. Of the 2,373 unmatched reference spells, 1,374 contain original same-team confirmed control evidence. The tool therefore supports separating absent control evidence from evidence that exists but does not lead to a sufficiently aligned recovered spell. Neither category alone proves a physical cause.

These are partial automatic H/A references, with unknown spans excluded. **They cannot measure missed stoppages**: no D ground truth is available. The tool marks D assessment unavailable, rather than reporting zero dead-ball errors. Reference gaps and half boundaries prevent both matching and bridge detection across them.

## Implementation and outputs

`src/spell_diagnostics.py` validates aligned consecutive frame indices, follows the official X filling within scored runs and descending-IoU one-to-one matching, and reports the official counts at all five IoU thresholds. The detailed categories use IoU 0.5 only; they are interval descriptions, not a replacement metric or a claim of proven causation.

The diagnostic reports four complementary tables per match:

- `reference_spells.csv`: match status, category, candidate signed boundary errors, abstention/opponent/D fractions, original control support and observed-ball coverage.
- `merge_bridges.csv`: one predicted spell crossing a D-only, opponent-only or mixed separator between same-team reference spells.
- `stoppages.csv`: completely missed, partly covered or fully covered D intervals. Full coverage does not establish that the predicted D interval has correct outer boundaries.
- `predicted_spells.csv`: matching status and the number of overlapping same-team reference spells, including unmatched predictions.

```powershell
.venv/Scripts/python.exe scripts/diagnose_possession_errors.py
# Alternatively, diagnose just one source:
.venv/Scripts/python.exe scripts/diagnose_possession_errors.py --scope public
.venv/Scripts/python.exe scripts/diagnose_possession_errors.py --scope development
```

Outputs are under `artifacts/possession_diagnosis/`; the combined file is `report_all.json`. The aggregate [record](possession_diagnosis/report_all.json) is committed; per-frame/interval traces remain local. The runner verifies original A/B/C/D/CSV hashes before and after the public diagnostic and fingerprints its source/configuration files. No inference code changed. Public results are sanity diagnostics, not training targets or a tuning set; there are no manual labels or frame-specific corrections.

Tests cover missed opponent possessions versus stoppages, shifted boundaries, false D, fragmentation and false predictions, mixed separators, period/reference gaps, X filling and all-X runs, observed/control masks, strict alignment, official metric agreement and input preservation.

Verification: the full 112-test suite passed without skips; after adding two final edge cases, all 11 diagnostic regressions passed. The combined real-data run completed for the public sample and all twelve development matches, with every protected original artifact unchanged.

## What this enables next

We now have separate, measurable error buckets. The next step can investigate D evidence and absent takeover evidence independently on development data. This step deliberately does not select new thresholds or implement either fix; it establishes the breakdown needed to judge them.
