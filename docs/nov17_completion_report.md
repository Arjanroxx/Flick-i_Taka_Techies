# Nov 17 completion report — Flick-i_Taka_Techies

Executed Nov 17, 2026 on merged `main` at
`e89498c8898dc321501ec6de15d2cf9571f7c559`. No commit, push, merge or pull
request was made.

## 1. Timeline

| Date | Deliverable | Status | Evidence |
| --- | --- | --- | --- |
| Nov 5 | P3 baseline | **COMPLETE** | `src/p3_sequence_model.py` runs; mock pipeline exported a valid 199,319-row CSV; 57 tests pass. |
| Nov 6 | Synthetic possession spell inspection | **COMPLETE** | `src/p3_synthetic.py`; five fixed seeds; behaviour report in `docs/p3/p3_completion.md`. |
| Nov 8 | External baseline | **BLOCKED** | Metrica Sample Game 1 tracking loads and P3 runs descriptively (145,006 frames, 678 segments). No frame-level possession ground truth, so no external baseline metric. Real A/B/C frame counts align at 199,319. |
| Nov 9 | Emission feature comparison | **COMPLETE** | Temperature sweep on five synthetic seeds: spellF1 0.688 → 0.807. `voronoi_control_H` rejected as redundant with nearest-distance evidence. |
| Nov 10 | Viterbi path vs posterior comparison | **COMPLETE** | Five-seed mean: posterior spellF1 0.8027, Viterbi 0.8069. Disputed windows exported (`artifacts/p3/experiments/disputed_windows.csv`). |
| Nov 11 | External transition-prior tuning | **PARTIAL** | Persistence grid 0.990–0.999 tuned on synthetic fixtures; 0.999 retained. No external labels, so external tuning is blocked. |
| Nov 12 | Real A/B replay and initial C export | **COMPLETE** | A, B, C generated on BAR-ATH; A matches P1's hash; B reproduces byte for byte; CSV validator passed. |
| Nov 13 | Imputation discontinuity checks | **COMPLETE** | 19 imputed frames in 4 runs, all ≤12 frames; no coordinates violation, no finite derivative, no cross-half gap, neutral P3 evidence. |
| Nov 14 | External spellF1 and macroF1 comparison | **BLOCKED** | Metrica events have no possession column; BAR-ATH public labels are not external data and were not substituted. |
| Nov 15 | Freeze C candidate | **COMPLETE** | `scripts/freeze_p3_candidate.py`; manifest with A/B/C/D/CSV hashes; second freeze identical. |
| Nov 16 | Full integration | **COMPLETE** | P1→A→P2→B→P3→C→P4→D→CSV ran end to end; 57 tests pass. Caveat: P4's provisional fingerprints are superseded by final C; P4 refresh/sign-off pending. |
| Nov 17 | Final CSV, P1/P2 sign-off, official validation/scoring | **PARTIAL** | Final CSV generated and officially validated; public five-minute sanity scored. P1/P2 sign-offs and private full-match scoring unavailable. |

## 2. Implementation changes

P3-owned work only. No P1, P2 or P4 implementation was rewritten.

| File | Change |
| --- | --- |
| `src/p3_sequence_model.py` | Exposed `team_evidence`, `build_emissions`, `forward_backward`, `viterbi` and `decode`; `run(config, spatial, deadball)` interface unchanged. Defaults preserve the old posterior path. |
| `src/p3_synthetic.py` | New fixed-seed synthetic A/B generator with known H/A/D/X truth, occlusions, imputation, identity bursts, set pieces and false boundary exits. |
| `scripts/run_p3_experiments.py` | New reproducible utility for synthetic sweeps, real diagnostics, imputation checks, disputed-window export and descriptive external run. |
| `scripts/freeze_p3_candidate.py` | New freeze/release utility; validates A/B, decodes C, applies D, writes CSV, runs the official validator and records hashes. |
| `configs/config.yaml` | HMM transition persistence changed to 0.999; added `emission_temperature: 3.0` and `decoder: viterbi`. |
| `tests/test_sequence_model.py` | Sharpness assertion updated from >0.9 to >0.7 with a >0.3 margin, reflecting the calibrated emission rather than the old overconfident one. |
| `tests/test_p3_decoders.py` | New tests: Viterbi determinism, half independence, invalid decoder rejection, temperature monotonicity, X outside play. |
| `tests/test_p3_synthetic.py` | New tests: synthetic A/B contracts, X-only-outside-play truth, imputed short-gap invariants. |
| `docs/p3/p3_completion.md` | New P3 experiment and completion record. |
| `Flick-i_Taka_Techies_technical.md` | Factual P3 method, validation, limitation and release updates. |
| `TEAM_ROADMAP.md` | Updated the P3 technical-convention line. |

The `run` output is byte-identical to the previous baseline when the old settings
(temperature 1.0, persistence 0.995, posterior) are supplied. This was checked
against the saved real C before changing the configuration.

## 3. Experiments

All experiments are reproducible from the repository root with fixed seeds.
Full tables are in `docs/p3/p3_completion.md`; raw results are in
`artifacts/p3/experiments/results.json` and `synthetic_summary.csv`.

Command:

```powershell
.venv/Scripts/python.exe scripts/run_p3_experiments.py
```

Dataset: five synthetic matches (seeds 0–4) on the official 199,319-frame grid,
plus the unlabelled BAR-ATH A/B artifacts and Metrica Sample Game 1 tracking.
No training labels from BAR-ATH were used. No external possession labels exist.

Five-seed means:

| Configuration | macroF1 | spellF1 | accuracy | predicted spells |
| --- | --- | --- | --- | --- |
| Previous (T=1, p=0.995, posterior) | 0.9760 | 0.6871 | 0.9895 | 711 |
| Final (T=3, p=0.999, Viterbi) | 0.9792 | 0.8069 | 0.9920 | 573 |
| T=6, p=0.999, Viterbi | 0.9785 | 0.8155 | 0.9912 | 554 |

The final setting was chosen as the conservative point where the temperature and
persistence gains flatten. T=6 adds only 0.009 fixture spellF1 and flattens the
evidence further.

Real-data effect (no labels): predicted segments 1,284 → 679; live segments
1,246 → 659; 16,385 frames changed (8.22%). Entropy mean 0.1854 → 0.1311.

Imputation checks on real A: all pass. The full check table is in
`docs/p3/p3_completion.md` under Nov 13.

External run: descriptive only, `possession_accuracy_measured: false`. It cannot
support a spellF1 or macroF1 comparison.

## 4. Integration

Pipeline executed end to end:

`P1 → A → P2 → B → P3 → C → P4 → D → Final CSV`

| Stage | Artifact | SHA-256 / result |
| --- | --- | --- |
| P1 A | `artifacts/spatial_features.parquet` | `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB`; matches P1's published candidate |
| P2 B | `artifacts/deadball_mask.parquet` | `13A2E7D25083CF615FDE65F296511497ACAE784BD33B1E2817C833DAE4DBA624`; `reproduced_byte_for_byte=true`; kickoff alignment agrees |
| P3 C | `artifacts/base_predictions.parquet` | `5A2E686896DAEDF858019FE01D21A6A50BB00B5F6D5E31F7504743F36FB61872` |
| P4 D | `artifacts/llm_overrides.parquet` | `6003E21FC6478FC506A5DA9A11569F5A4CBD99141C2D63C076EDE3659FA41177`; explicit empty D |
| Final CSV | `Flick-i_Taka_Techies.csv` | `D51E19A05ACAEA0A36DA065AD37C42DCFCB4B45E9FDD3CF8668FF96BA4E90FAA` |

P1/P2 contract checks: 199,319 rows, half alignment, metre coordinates,
missing-value handling, short-gap imputation, B restart/flag schema all pass.

Before regeneration, the pre-change A/B/C/D and CSV were copied to
`artifacts/p3/experiments/before_final/`; their hashes are preserved there.

P4 verification on the final C:

- Local dry run reviewed 8 windows, accepted 0 overrides and changed 0 frames.
- Baseline and override CSVs are identical and both pass the official validator.
- External Metrica assessment reviewed 8 windows, proposed 0 overrides, changed
  0 frames, and records no possession accuracy.
- The empty D is applied without changing the base CSV.

Tests: `python -m unittest discover -s tests -v` → **57 tests, OK**.

## 5. Final output

Generated and validated:

- Path: `C:\Hackathons_2026\Barca\Flick-i_Taka_Techies\Flick-i_Taka_Techies.csv`
- SHA-256: `D51E19A05ACAEA0A36DA065AD37C42DCFCB4B45E9FDD3CF8668FF96BA4E90FAA`
- Rows: 199,319, frames 0–199,318 in order
- Labels: H 83,770; A 70,909; D 4,162; X 40,478
- Validator: `OK`, 199,319 rows, frames 0–199,318; log at
  `artifacts/p3/release/validator.log`
- Freeze manifest: `artifacts/p3/release/freeze/manifest.json`
- A second freeze reproduced the same C and CSV hashes.

Public five-minute sanity check (not external validation, not model selection). The
scorer's possession count fills X abstentions inside each half; the validator's
590-possession report counts every X as a gap.

| Metric | Final candidate | `baseline_smooth125` |
| --- | --- | --- |
| macroF1 | 0.5188 | 0.5812 |
| spellF1 | 0.1926 | 0.4242 |
| predicted possessions | 37 | 16 |
| mean duration | 8.0 s | 18.5 s |
| fragmentation | 1.86 | not reported |

The previous P3 baseline scored macroF1 0.5149 / spellF1 0.0851 with 77
possessions. The final candidate is a substantial improvement over that baseline
but remains below the best provided baseline. **No official full-match score was
computed**; the private ground truth is not available locally.

## 6. Outstanding blockers

1. **No private full-match ground truth.** Official scoring cannot be executed or
   claimed. Only the public five-minute sanity score is available.
2. **No external frame-level possession ground truth.** External spellF1, macroF1
   and transition-prior generalisation are unmeasured. The Metrica sample has
   tracking and events only.
3. **P1 and P2 sign-offs are missing.** Their artifacts pass contracts and B
   reproduces byte for byte, but the owners have not signed the release in this
   session.
4. **P4 refresh/sign-off against final C is pending.** P4's Nov 14/16 fingerprints
   describe the previous C. The empty-D decision and local/external checks were
   re-run against final C with zero overrides, but P4's documentation and owner
   sign-off still need updating.
5. **P2 dead-ball coverage limits D.** Real C labels 2.1% of frames D. Many
   in-bounds stoppages are not flagged by B, and public-window D timing is poor.
   Fixing this needs P2 coordination, not a P3-only change.
6. **Tactical video is absent from the bundle copy.** The pipeline does not need
   it, but video-frame extraction checks cannot be re-run.
7. **Python version.** The available environment is Python 3.14, not the documented
   3.12. All 57 tests pass, but a 3.12 clean-environment install was not repeated.

## 7. Git summary

Branch: `main`, tracking `origin/main`, no commits made.

Modified:

- `configs/config.yaml`
- `src/p3_sequence_model.py`
- `tests/test_sequence_model.py`
- `Flick-i_Taka_Techies_technical.md`
- `TEAM_ROADMAP.md`

New:

- `src/p3_synthetic.py`
- `scripts/run_p3_experiments.py`
- `scripts/freeze_p3_candidate.py`
- `tests/test_p3_decoders.py`
- `tests/test_p3_synthetic.py`
- `docs/p3/p3_completion.md`
- `docs/nov17_completion_report.md`

Generated artifacts are ignored under `artifacts/` and the final CSV is ignored by
the repository's existing `.gitignore`. No P1/P2/P4 source file was modified.

## 8. Final submission readiness

**READY WITH DOCUMENTED LIMITATIONS.**

The submission file exists, has the exact required schema, passes the official
validator, is reproducible from validated A/B artifacts, and the full pipeline and
test suite run cleanly. The P3 deliverables that were technically possible without
external labels are implemented and measured.

The limitations are material and must be stated in the submission:

- No external frame-level possession labels, so external spellF1/macroF1 and
  transition generalisation are unmeasured.
- No private full-match ground truth, so no official score is claimed.
- The public sanity score is below the provided `baseline_smooth125`.
- P1/P2 sign-offs and P4's final refresh/sign-off are still outstanding.

This is not "READY" because official scoring and owner sign-offs are incomplete.
It is not "NOT READY" because the required CSV is valid, reproducible and
available tonight.
