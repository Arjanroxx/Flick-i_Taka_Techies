# P3 completion record — Nov 6 to Nov 17

Executed Nov 17, 2026 against merged `main` at `e89498c8898dc321501ec6de15d2cf9571f7c559`.
No commits were made. All generated outputs are under `artifacts/`, which is ignored.

## Scope and evidence standard

P3 owns the sequence model and its evaluation utility. This record separates three
kinds of evidence:

1. **Synthetic fixtures** (`src/p3_synthetic.py`, fixed seeds 0–4). They have known
   state labels and are used for model selection and regression checks.
2. **Unlabelled real data** (BAR-ATH A and B). Used for contract, reproducibility,
   fragmentation and imputation diagnostics. No labels were used to fit anything.
3. **Public five-minute labels**. Inspected for pipeline alignment and fragmentation
   diagnostics. The settings were selected on synthetic fixtures first; the public
   score was measured afterwards as a sanity check, not used to choose the settings.

No external dataset with frame-level possession ground truth is available, so no
external spellF1 or macroF1 is reported. The Metrica Sample Game 1 run is
descriptive only.

## Nov 6 — synthetic possession spell inspection

`src/p3_synthetic.py` generates H/A/D spells on the official 199,319-frame grid,
with half-local occlusions, imputed short gaps, observed nearest-team identity
bursts, set-piece windows, true boundary exits and false boundary bursts. Spells
have a mean near 14.6 s, close to the public five-minute reference mean of 14.2 s
published in the challenge README.

Five seeds, previous settings (temperature 1.0, persistence 0.995, posterior) vs
final settings (temperature 3.0, persistence 0.999, Viterbi):

| Setting | macroF1 | spellF1 | accuracy | predicted spells | mean spell | fragmentation |
| --- | --- | --- | --- | --- | --- | --- |
| Previous | 0.9760 | 0.6871 | 0.9895 | 711 | 8.41 s | 1.99 |
| Final | 0.9792 | 0.8069 | 0.9920 | 573 | 10.45 s | 1.63 |

Smoothing changes 2,747–3,137 in-play frames per seed (about 2% of graded frames).
The X shield emitted **zero** in-play X labels on all five seeds; every X came from
the published outside-play blocks. On real C, 16 in-play frames receive X. The
configured entropy threshold 0.9 is therefore conservative: 18 real in-play frames
reach it.

## Nov 9 — emission feature comparison

Distance evidence uses `softmax(-distance / temperature)` for H and A. Missing or
imputed observations remain neutral at 0.5/0.5. Temperature was the only emission
setting with a measurable effect:

| Temperature | macroF1 | spellF1 | accuracy | predicted spells | mean spell |
| --- | --- | --- | --- | --- | --- |
| 0.5 | 0.9774 | 0.6880 | 0.9895 | 718 | 8.33 s |
| 1.0 | 0.9780 | 0.7365 | 0.9904 | 655 | 9.14 s |
| 2.0 | 0.9789 | 0.7875 | 0.9916 | 595 | 10.06 s |
| 3.0 | 0.9792 | 0.8069 | 0.9920 | 573 | 10.45 s |
| 4.0 | 0.9791 | 0.8115 | 0.9920 | 566 | 10.57 s |
| 6.0 | 0.9785 | 0.8155 | 0.9912 | 554 | 10.80 s |

Temperature 3.0 was retained. It removes most of the per-frame overconfidence while
keeping a 1 m vs 5 m preference clear (0.776 vs 0.224 on a single frame). Temperature
6.0 adds only 0.009 synthetic spellF1 and flattens the evidence further.

`voronoi_control_H` was not added to the emissions. P1 measured 0.81 correlation
with `dA − dH` and 0.84 with the `dH < dA` indicator; the synthetic generator also
constructs it as a monotone function of the same distances. It carries no independent
information for the current decoder.

## Nov 10 — Viterbi path vs forward-backward posterior

Both decoders run on the same emissions and are reset independently at each half
boundary. Five-seed mean:

| Decoder | macroF1 | spellF1 | accuracy | predicted spells |
| --- | --- | --- | --- | --- |
| Posterior MAP | 0.9788 | 0.8027 | 0.9916 | 579 |
| Viterbi | 0.9792 | 0.8069 | 0.9920 | 573 |

Viterbi is retained. It improves synthetic spellF1 by 0.0042 and produces fewer
spells. The difference is small, so the posterior remains the reported probability
and entropy source; only the hard label path changes.

Disputed-window queue exported from final real C
(`artifacts/p3/experiments/disputed_windows.csv`):

| Entropy threshold | Windows | Frames |
| --- | --- | --- |
| 0.9 (configured) | 18 | 18 |
| 0.7 | 28 | 60 |
| 0.5 | 638 | 26,360 |

P4's Nov 17 dry run reviewed eight of these windows and proposed no overrides.

## Nov 11 — transition-prior tuning

The off-diagonal shape is held fixed at the previous relative weights
(H→A 2, H→D 3, A→H 2, A→D 3, D→H 5, D→A 5); only persistence is swept.
Five-seed mean:

| Persistence | macroF1 | spellF1 | accuracy | predicted spells |
| --- | --- | --- | --- | --- |
| 0.990 | 0.9773 | 0.7592 | 0.9911 | 620 |
| 0.995 | 0.9774 | 0.7663 | 0.9913 | 612 |
| 0.997 | 0.9784 | 0.7865 | 0.9916 | 591 |
| 0.998 | 0.9791 | 0.8036 | 0.9919 | 576 |
| 0.999 | 0.9792 | 0.8069 | 0.9920 | 573 |

Persistence 0.999 is retained. This is **fixture tuning only**. External
transition-prior tuning is blocked because no suitable other-match labels exist.

## Nov 12 — real A/B replay and initial C

The full pipeline ran against the authorised tactical bundle. A was regenerated
from merged P1 and matches P1's published candidate hash. B reproduced byte for
byte through P2's handoff command.

| Artifact | SHA-256 | Notes |
| --- | --- | --- |
| A `artifacts/spatial_features.parquet` | `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB` | matches P1's frozen candidate |
| B `artifacts/deadball_mask.parquet` | `13A2E7D25083CF615FDE65F296511497ACAE784BD33B1E2817C833DAE4DBA624` | `reproduced_byte_for_byte=true` |
| C `artifacts/base_predictions.parquet` | `5A2E686896DAEDF858019FE01D21A6A50BB00B5F6D5E31F7504743F36FB61872` | 199,319 rows, 679 label segments |
| D `artifacts/llm_overrides.parquet` | `6003E21FC6478FC506A5DA9A11569F5A4CBD99141C2D63C076EDE3659FA41177` | explicit empty D, 0 rows |

Final real diagnostics: 679 segments (659 in play), entropy mean 0.1311,
p95 0.6700, max 0.9570. The previous settings produced 1,284 segments
(1,246 in play), entropy mean 0.1854. 16,385 frames changed (8.22% of the match).

## Nov 13 — imputation discontinuity checks

Real A contains 19 imputed frames in four runs, all at most 12 frames:

| Check | Result |
| --- | --- |
| Imputed runs within `short_gap` | pass (max 12) |
| Imputed runs inside one half | pass |
| Imputed frame without coordinates | 0 |
| Gap-length mismatch inside a run | 0 |
| Imputed frame with finite speed | 0 |
| Cross-half gap claims | 0 |
| Imputed team evidence neutral (0.5/0.5) | pass |
| Short-gap X shield can apply | pass |

Long and edge gaps remain missing: 105,086 frames are missing without imputation,
including halftime and the long tracking gaps. Missing positions cannot produce a
finite nearest-team distance or a derivative.

## Nov 14 — external spellF1 and macroF1

**Blocked.** Metrica Sports Sample Game 1 provides tracking for two teams and an
event table, but no frame-level possession ground truth. The event columns are
`Team, Type, Subtype, Period, Start Frame, Start Time, End Frame, End Time, From,
To, Start X, Start Y, End X, End Y`; there is no possession column. The public
BAR-ATH five-minute labels are competition data, not an external match, and were
not substituted.

The external tracking was still adapted through P4's loader and run through P3:
145,006 frames, two periods, 678 label segments. P4's external assessment records
`possession_accuracy_measured: false`. No external metric claim is made.

## Nov 15 — freeze C candidate

`scripts/freeze_p3_candidate.py` reads validated A and B, decodes C, applies the
configured D, writes the CSV, runs the official validator and records hashes in a
manifest. A second freeze produced identical C and CSV hashes.

Release candidate:

- CSV `Flick-i_Taka_Techies.csv`
- SHA-256 `D51E19A05ACAEA0A36DA065AD37C42DCFCB4B45E9FDD3CF8668FF96BA4E90FAA`
- 199,319 rows, 679 label segments
- Label counts: H 83,770; A 70,909; D 4,162; X 40,478
- `artifacts/p3/release/freeze/manifest.json`
- `artifacts/p3/release/validator.log`

## Commands

```powershell
.venv/Scripts/python.exe scripts/run_p3_experiments.py
.venv/Scripts/python.exe scripts/run_full_pipeline.py --skip-evaluation
.venv/Scripts/python.exe scripts/freeze_p3_candidate.py --out artifacts/p3/release/freeze --submission Flick-i_Taka_Techies.csv
.venv/Scripts/python.exe evaluation/validate_submission.py Flick-i_Taka_Techies.csv
.venv/Scripts/python.exe evaluation/run_evaluation.py --gt public --results artifacts/p3/release/evaluation_input --out artifacts/p3/release/evaluation --no-detail
```

## Limits

- Synthetic metrics measure behaviour under the generator's assumptions, not real
  possession accuracy.
- No external frame-level possession labels exist, so external spellF1, macroF1 and
  transition-prior generalisation remain unmeasured.
- P2 does not flag many in-bounds stoppages. Real C labels only 2.1% of frames D, and
  the public window shows poor D timing. P3 did not reinterpret P2's diagnostic
  `active_set_piece_type` column; doing so needs P2 coordination.
- The public five-minute sanity score is 0.5188 macroF1 and 0.1926 spellF1 (37
  predicted spells, 8.0 s mean), below `baseline_smooth125` at 0.5812/0.4242.
  It is reported as a sanity check, not as an external validation result.
