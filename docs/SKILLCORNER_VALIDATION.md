# SkillCorner frozen-model validation

Completed Nov 18, 2026. SkillCorner and PySport are credited for providing the open data. Source revision: `4340d274572876239c154c90bc507a9b3250a656`; [repository and data description](https://github.com/SkillCorner/opendata/tree/4340d274572876239c154c90bc507a9b3250a656). The snapshot contains 20 tracking objects although the README says ten matches. All 20 complete matches were downloaded and verified, yielding 40 frozen-model evaluations.

## Main result

| Split | Matches | Distance partial spellF1 | Control partial spellF1 | Distance H/A macroF1 | Control H/A macroF1 |
|---|---:|---:|---:|---:|---:|
| Development | 12 | 0.3495 | 0.4592 | 0.7682 | 0.7855 |
| Test | 8 | 0.3457 | 0.4483 | 0.7552 | 0.7735 |

These are unweighted means across complete matches, measured only where a provider H/A label exists. They are **partial-reference metrics, not challenge scores** and cannot be directly compared with the competition public-window 0.5429. Control improves partial spellF1 on all 20 matches; on the test split it also improves H/A macroF1 on all eight.

On the eight test matches, the mean paired control-minus-distance difference is **+0.1026** partial spellF1. A 10,000-draw paired bootstrap over whole matches gives an approximate 90% interval **[+0.0969, +0.1092]**. The H/A macroF1 difference is **+0.0183**, interval **[+0.0149, +0.0221]**. These intervals describe variability across this sample of matches; they do not account for systematic vendor-label errors, shared-team/league correlations, or quantify competition qualification chances.

Control reduces test fragmentation from 1.6084 to 0.8987. Its predicted/reference spell-count ratio is 0.7676 versus distance-only 1.4803. It fixes much of the over-fragmentation in this benchmark, but now tends to merge or miss some reference possessions. Mean predicted spell duration rises from 6.34 to 12.22 seconds over labelled runs.

[Per-match metrics](skillcorner_validation/per_match.csv), [split summaries](skillcorner_validation/summary.csv), and [paired comparisons with source fingerprints](skillcorner_validation/report.json) are committed aggregate reports. No tracking or frame-level references are committed.

## Protocol and split

`configs/skillcorner_protocol.json` was locked before model evaluation. Match IDs were ranked by SHA256(source revision + ':' + match ID), first 12 assigned to development and last eight to test. All matches were included; no match was dropped based on performance. Both methods used frozen 25 Hz settings from the existing pipeline, with only predeclared rate conversion. No threshold fitting, model training, competition-label reads, or parameter selection was performed in this benchmark. The test split was evaluated under predeclared frozen settings; partial results from the failed metadata-loader attempt were discarded and recomputed under the final source fingerprints. No model settings were changed between attempts. The test results have now been observed and should not become an iterative tuning set.

The reference schema and a short source sample were inspected before the protocol was locked, to establish usability. An initial execution hit a Windows UTF-8 metadata decoding failure; after fixing the loader, all matches were evaluated under the same final source fingerprints. This was an input-handling correction, not a model change based on scores.

## Reference semantics and limitations

- Tracking `possession.group` supplies H/A targets. Null possession stays X/unknown; **it is never automatically relabelled D**. `possession.player_id`, group, dynamic events and phase labels are never inference features.
- H/A labels cover a mean 52.9% of test-match period frames (including stoppages in the denominator). Across all matches, coverage ranges from 45.8% to 63.3%. Unknown spans are excluded, not assumed wrong or correct.
- Temporal metrics use the official IoU thresholds and one-to-one matching, but scored runs end at unknown-reference spans and period boundaries. Predicted X is filled only within each labelled run. This can hide errors spanning an excluded interval, especially false bridges across unknown or dead-ball stretches. Partial spellF1 cannot certify full stoppage boundaries or complete-match possession recovery.
- H/A macroF1 averages H and A only. Predicted D/X on known H/A frames still count as misses. We do not report the official three-class macroF1, because D references are absent and an always-absent D class would make that metric misleading.
- Phase files are used only for consistency diagnostics, not input features or invented D labels. End-frame inclusivity is unresolved, so diagnostics compare conservative strict interiors and closed coverage. Across all matches, 18,340 strict-interior phase frames have null group labels and 25,869 known-group frames lie outside closed phase coverage. The two reference products are not perfectly interchangeable; using phase gaps as unquestioned D truth would be unjustified.
- References and positions are provider-generated, potentially sharing underlying estimation errors. This is external reference agreement, not independently human-validated ground truth or proof that SkillCorner and Metrica define controlled possession identically.
- Inputs use only coordinates marked detected; off-screen extrapolations are discarded. Only roster IDs/team membership, pitch dimensions, period and detected geometry feed inference. No possession labels select nearest players or determine dead-ball evidence.

## Native-rate and coordinate adaptation

The adapter validates contiguous frame IDs, period identifiers, and within-period 0.1-second timestamp increments. Coordinates are in metres centred on the pitch; translation by half the actual pitch dimensions converts them to the pipeline convention. Team distances remain in physical metres with no unnecessary pitch rescaling. The adapter derives the geometry and motion needed by P2/P3 without forcing these matches into the competition-only 199,319-row contract. P2 receives no SkillCorner phase/event labels: this validates the geometry/P3 comparison, not competition Smart Tagging or full H/A/D detection. Period boundaries reset derivatives and inference. Missing samples remain NaN, not zero or repeated synthetic observations.

Evaluation stays at native 10 Hz; data is not duplicated to 25 Hz. The frozen 25 Hz transition matrix is converted to `T25**2.5` (matrix power). Emission weights are raised to 2.5 and normalized to approximate the same per-second evidence exposure. This is an explicit temporal approximation, since observation updates and transitions do not commute exactly. Control and boundary confirmation use two independent native observations, short-gap timing uses five native frames, and metre/speed/acceleration thresholds retain their units. Native 100 ms resolution cannot validate competition boundaries to 40 ms precision.

Actual P2 boundary/motion logic is reused with the external frame rate and pitch, but without SkillCorner event/phase labels as inputs. Therefore, this evaluates the geometry/P2/P3 combination and the relative benefit of control-aware team evidence; it does not validate the competition Smart Tagging subsystem.

## Executed checks and reproduction

All **87 tests passed without skips**, including seven native-adapter/schema tests and the emission-time-conversion test. Tests verify target-label noninterference, UTF-8 metadata, centred coordinates, unknown-reference handling, match split, native P2 indexing and time conversion. The existing 25 Hz control candidate was regenerated separately and **all A/B/C/D/CSV hashes were unchanged**. No competition public scoring was run during this benchmark.

The downloader verifies every tracking LFS object against its pinned SHA-256 and size. The evaluator verifies Git blob hashes for metadata, phases and pointers against `configs/skillcorner_source_blobs.json`. It records source/protocol fingerprints and rejects changes during a run. Source licence and README are retained locally; the public repository includes the MIT licence and asks for SkillCorner attribution.

```powershell
.venv/Scripts/python.exe scripts/download_skillcorner.py
.venv/Scripts/python.exe scripts/validate_skillcorner.py
```

Downloads stay in `artifacts/external/skillcorner/`; detailed checkpoints, protocol, aggregate reports and compatibility logs are under `artifacts/skillcorner_validation/`. Correctly fingerprinted checkpoints allow interrupted runs to resume. The required runtime dependencies remain those pinned in `requirements-team.txt`.

## Decision

The control-aware candidate has substantially stronger support than the public five-minute result alone: its improvement is consistent across these external matches under a frozen protocol. That supports continuing with it as the stronger research candidate. It does **not** establish a full H/A/D score, guarantee generalization to BAR-ATH, or justify automatic submission replacement. No competition CSV, default configuration, submission form or receipt was changed. Future development must use development matches and keep any new final evaluation genuinely separate.
