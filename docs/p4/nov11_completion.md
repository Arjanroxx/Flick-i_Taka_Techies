# P4 — Nov 11 override checks and external assessment

Owner: Arjan (P4). Completed Nov 12, 2026.

## Result

Completed the confidence, overlap and period-boundary checks and ran the local arbiter on public Metrica Sample Game 1 tracking. The run processed 145,006 frames across two periods and reviewed eight high-entropy windows. It produced zero proposals, zero accepted overrides and zero changed frames. A repeated run produced byte-identical feature tables, predictions, response cache, override table and CSVs.

The provisional confidence threshold remains 0.8. The run establishes that the adapter and arbitration workflow process another match reproducibly. Possession accuracy and confidence calibration require independent labels and remain unmeasured here.

## Source and usage statement

Metrica Sports publishes the anonymised sample for football analytics use and requests acknowledgement for public use. The pinned README describes a 105 × 68 metre pitch, normalized coordinates, and synchronized event/tracking data. This assessment credits Metrica Sports. The source has a usage statement rather than a separate formal licence file in the inspected revision. The downloaded files and source statement remain in ignored local storage. [Metrica Sports source and usage statement](https://github.com/metrica-sports/sample-data/blob/e706dd506b360d69d9d123d5b8026e7294b13996/README.md)

The input revision is `e706dd506b360d69d9d123d5b8026e7294b13996`. Inputs are `Sample_Game_1_RawTrackingData_Home_Team.csv` and `Sample_Game_1_RawTrackingData_Away_Team.csv`. Each input URL and SHA-256 fingerprint is recorded in the local response cache. The event CSV supplies no continuous possession-label sequence for this assessment, so it was excluded from label construction.

## Adapter

`src/p4_external_sample.py` reads the three-row tracking header and preserves the delivered frame identifiers. It checks ordered contiguous integer frames, period order, 25 fps time steps, and agreement between Home and Away frame/time/ball records.

The adapter scales coordinates using the sample's 105 × 68 metre pitch, calculates nearest-team distances, and records missing-ball gaps separately in each period. Missing coordinates and absent-player distances remain NaN. Ball positions remain observed or missing, with no interpolation.

The external dead-ball input uses weak boundary evidence. Observed out-of-bounds positions receive 0.98, observed in-bounds positions 0.05, and missing ball observations 0.5. These provisional weights provide a processing baseline. In-bounds stoppages may be missed, so this proxy still needs independent evaluation.

The existing P3 sequence model generates the external baseline from those features. P4 uses the Nov 10 observed-proximity rule, the existing 0.9 entropy threshold, at most eight windows, and requests capped at 125 frames. It records each window's evidence, proposals and accepted responses. Every real request retained the baseline.

## Timeline handling

P4's parser, window selector and local arbiter now accept an explicit external period map. External interval checks use that map. Calls using the competition defaults continue to enforce the published Barcelona–Athletic frame domain and halves. Shared competition contracts remain as defined in `src/contracts.py`.

Override application now addresses the frame labels in the DataFrame index, supporting the sample's one-based frame identifiers. External outputs are named `external_*` and use their source timeline. The external CSVs contain 145,006 rows indexed to that sample.

## Confidence and overlap checks

- Scores below 0.8 are filtered out, and scores at the threshold are accepted.
- Higher-confidence rows win overlapping frames regardless of their original row order.
- Equal-confidence overlaps resolve in favour of the later input row, preserving the existing stable-sort behaviour.
- Override endpoints are inclusive, and neighbouring frames retain their original labels.
- Cross-period and out-of-domain responses are rejected.
- Synthetic observed runs produce accepted external overrides, while competition-default validation rejects those fixtures' deliberately different frame domain.

These checks exercise acceptance as well as retention. They verify the rule's mechanics, without selecting or calibrating the threshold against the competition labels.

## Reproduce

From the repository root with team dependencies installed:

```powershell
.venv/Scripts/python.exe scripts/assess_external_arbiter.py --download
.venv/Scripts/python.exe scripts/assess_external_arbiter.py --out artifacts/p4/nov11/repeat_run
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

The first command downloads missing pinned public inputs and the source README. Further offline runs can omit `--download`. `--data-dir` selects another local sample folder, and `--config` selects the sequence and threshold settings.

Evidence is saved under `artifacts/p4/nov11/external_run/`.

| File | Evidence |
|---|---|
| `external_spatial.parquet` | Sample-specific ball and team features |
| `external_deadball.parquet` | Weak boundary/missingness evidence |
| `external_predictions.parquet` | P3 baseline probabilities and labels |
| `external_overrides.parquet` | Valid empty external override table from this run |
| `response_cache.json` | Input/source hashes, settings, requests and decisions |
| `baseline.csv`, `with_overrides.csv` | Before/after sequences on the sample timeline |
| `summary.json` | Outcome and output fingerprints |

## Verification and next handoff

All 43 tests passed, including nine new external-adapter and integration tests. The competition mock pipeline also passed its official 199,319-row CSV validator. Two real external runs produced identical output fingerprints. The Windows test run used `artifacts/tmp` for temporary files because its default temporary directory was inaccessible.

Nov 11 is complete for override mechanics and external processing. When P3 shares its reviewed competition C candidate, regenerate the Nov 10 window queue and D using the matching A/B/C versions. Keep 0.8 explicitly provisional until an eligible independent label source supports calibration.
