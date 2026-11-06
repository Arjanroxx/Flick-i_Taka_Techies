# P4 — Nov 6 completion and early data-arrival checks

Owner: Arjan (P4). Completed Nov 6, 2026.

**Today's deliverable is complete.** Added a working loader for Metrica Sports Sample Game 1 events and assessed the source. Early match-data access also enabled a real tactical baseline run, asset checks and local video extraction checks.

## External development sample

Source: Metrica Sports, Sample Game 1, revision `e706dd506b360d69d9d123d5b8026e7294b13996`. The loader reads 1,745 event records. It checks required fields, numeric values, team names and frame references. A reversed kickoff interval in the public source is preserved and flagged for assessment.

The public repository describes anonymized matches, normalized coordinates, synchronized tracking/events and a 105 × 68 metre pitch. Its README invites analytics use and requests attribution. A separate formal LICENSE file was not found in the inspected revision. Credit Metrica Sports and retain the source terms. Further uses requiring broader rights need clarification. The downloaded data stays in ignored local storage. [Source and usage statement](https://github.com/metrica-sports/sample-data/blob/e706dd506b360d69d9d123d5b8026e7294b13996/README.md)

**Supervised possession tuning is not established by this sample.** The loaded CSV contains event observations. It does not supply a complete H/A/D possession label for every frame, nor does the source inspection establish how every annotation was produced. It supports loader, timestamp and event-processing development. A verified label definition and permitted training use are still needed before using it as a possession tuning set. Filling each event team's label across gaps would invent labels.

Run from the repository root:

```powershell
.venv/Scripts/python.exe scripts/check_external_sample.py --download
# Subsequent offline checks:
.venv/Scripts/python.exe scripts/check_external_sample.py
```

The pinned source URL, local file checksum, event counts and anomaly assessment are recorded under `artifacts/external/metrica/`.

## Checks brought forward after match access arrived

| Check | Outcome | Implication |
|---|---|---|
| Tactical tracking alignment | Passed official raw alignment check | Delivered ATD can use the official frame mapping |
| Broadcast tracking alignment | Passed official raw alignment check | Its own tracking timeline is readable |
| Tactical homography | Alignment and usable-value checks passed | Geometry is available for local development |
| Smart Tagging time base | Published kickoff-containment checks passed | Existing timestamp conversion is usable |
| Tactical baseline | Real A, B, C and D pass contracts; CSV passes official validation | Teammates can begin real feature-quality work |
| Tactical video | Expected frame count and FPS; local extraction and end-of-file decoding passed | P4 frame-extraction preparation is working |
| Broadcast video | Opens and decodes; its count is one frame shorter than the published tracking count | Investigate before aligning video to broadcast tracking |
| Broadcast homography | Absent from the supplied data folder | Optional dual-feed geometry remains incomplete |
| Uncertainty windows | Generated locally from the current baseline | A starting queue for P4; regenerate after model changes |
| Public sample evaluation | One sanity run completed with settings unchanged | Evidence is kept locally; model selection still uses external evidence |

The video-frame discrepancy identifies a metadata/length issue. It establishes neither the missing frame's position nor a correction offset. Broadcast-to-tactical synchronization remains separate work.

These are baseline processing checks performed by P4. P1 and P2 still own spatial-feature and stoppage quality, and P3 still owns sequence-model choices. Empty D means local arbitration has not been implemented yet. The final submission candidate has not been selected.

## Local outputs

- `artifacts/spatial_features.parquet`, `deadball_mask.parquet`, `base_predictions.parquet` and `llm_overrides.parquet`.
- `Flick-i_Taka_Techies.csv`, the current validated real-data baseline.
- `artifacts/local_config.yaml`, private configuration pointing to this machine's downloaded bundle.
- `artifacts/p4/nov06/asset_checks.json`, video metadata, local read-check images, contested windows and run logs.
- `artifacts/p4/nov06/public_sanity/`, the single public sanity evaluation.
- `artifacts/external/metrica/`, the external event file and its source assessment.

Competition data, extracts, private paths and prediction outputs stay in ignored local folders. Public changes contain code and this status report.

To replay the local real pipeline:

```powershell
.venv/Scripts/python.exe scripts/run_full_pipeline.py --config artifacts/local_config.yaml --skip-evaluation
```

For another machine, use its own authorised bundle path through `--data-dir` or `MTAH_DATA_DIR`. The inspection command accepts explicit tactical and broadcast video paths, accommodating download suffixes:

```powershell
.venv/Scripts/python.exe scripts/inspect_match_assets.py --data-dir 'D:/match-data' --tactical-video 'D:/videos/tactical.mp4' --broadcast-video 'D:/videos/broadcast.mp4'
```

## Next work

P4 can finish the local arbiter response schema and rejection checks on Nov 7. Use the saved window queue for designing a local approach, then regenerate it when P3 changes C. Training-label suitability remains an explicit open item.

P1 can inspect real ball gaps and identity-switch effects immediately. P2 can review real tag categories and restart evidence immediately. P3 can inspect the real baseline's possession fragmentation and missing-observation behavior, using synthetic or other-match evidence for model selection.

