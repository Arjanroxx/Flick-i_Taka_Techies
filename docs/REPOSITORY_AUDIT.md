# End-to-end possession audit — Nov 18, 2026

Reviewed merged baseline `0262ebf` and the pipeline, official rules and metric specification. Verified implementation commit: `40fc2caa90f3b48adb761e1aa7a85d6276140083`, on `codex/end-to-end-audit`. The original release candidate and earlier correction outputs remain preserved; this audit produces a separate candidate.

## Prioritized findings

### Critical release-integrity bugs

1. **Nonempty saved overrides were not bound to the current inputs.** `src/p4_arbiter_and_eval.py:168` now requires the local runner's adjacent `response_cache.json` and `summary.json`, checks current A/B/C fingerprints and checks D's own fingerprint. Missing/mismatching provenance fails closed. Empty D remains safe to reuse. `scripts/freeze_p3_candidate.py:56` uses the same checks against its newly generated C, closing a separate bypass.
2. **Confirmed boundary evidence disappeared during tracking outages.** `src/p2_deadball_detector.py:91` now carries an already confirmed exit through consecutive missing/imputed samples within that half; any new observed position ends this carry. `src/p2_deadball_detector.py:113` recognizes a sustained return after an outage rather than requiring the immediately previous frame to be outside. Missing frames retain `is_out_of_bounds=False`: inferred stoppage evidence is distinct from observed geometry.
3. **Broad set-piece tags could restore dead-ball evidence after an established restart.** `src/p2_deadball_detector.py:134` restricts the weak missing-ball tag prior to frames preceding that tag's detected restart. Existing observed-motion limits and half-open tag intervals remain intact.

### spellF1 weaknesses

4. **Optional proximity overrides could carve an opposite-team island inside an uninterrupted possession.** `src/p4_arbiter_and_eval.py:131` now rejects such isolated overrides when both neighboring base labels belong to the same team within the same half. It does not claim to classify control or guarantee that every remaining override improves accuracy. Arbitration remains omitted for this candidate: eight match and eight external windows yielded no accepted overrides.
5. **Proximity is not controlled possession.** `src/p3_sequence_model.py:26` uses relative distances, without an absolute control-distance model. A very distant team preference can be overconfident; contested balls and brief defensive touches are handled only implicitly by HMM context. There is no explicit hysteresis or minimum-duration decoder. This is an unresolved modeling limitation, not a proven HMM indexing defect. Exhaustive-path regression confirms the forward-backward marginals and Viterbi path on a small independently enumerated example.
6. **No justification for deleting every short spell.** Every positive-length H/A spell can count under the official scorer, so a global minimum-duration filter would erase legitimate events and could merge possessions across actual turnovers. No public-score-selected duration filter or extra transition penalty was introduced. The configured Viterbi penalties remain unchanged.
7. **Development evidence is not independent real-match validation.** The legacy generator (`src/p3_synthetic.py:16`) uses a 355-frame geometric scale, matching the published 14.2-second public-window mean. Its documentation explicitly compares the scales, so it cannot support a claim of independent generalization. The historical generator is preserved for reproducibility. The actual-P2 stress fixture now uses explicit lengths spanning one frame to one minute instead, plus long gaps and incomplete synthetic tags. No new parameter was selected from competition labels. Suitable independent labelled matches are still needed to validate control rules and smoothing choices.

### Contract and packaging issues

8. **Relational invariants were missing.** `src/contracts.py:63` now rejects half-missing coordinate pairs and imputation without a positive in-half gap. `src/contracts.py:80` rejects non-X prediction labels outside play. Mock data and the local-runner test fixture now obey those invariants. Spatial float NaNs remain deliberately permitted: unresolved tracking must not become fictitious `(0,0)` observations.
9. **Required installation included unused, unpinned SDK/model packages.** `requirements-team.txt` now contains only pinned runtime dependencies. Unused exploratory packages move to `requirements-development.txt`, which explicitly is not the reproducible release environment. The release code does not import those extras.
10. **Official CSV validator is more permissive than the prose header requirement.** It requires frame/label columns but does not reject every extra column. The pipeline itself writes exactly `frame,label`. The official scorer and validator were left unchanged; their implementation remains the scoring authority.

## Metric semantics verified

- `evaluation/possession_metrics.py:60` defines same-team temporal IoU matching averaged over 0.3, 0.4, 0.5, 0.6 and 0.7. Intervals are half-open. Matching is greedy in descending IoU, deterministic, and one-to-one. There is no minimum spell duration or extra boundary tolerance in spell matching.
- `evaluation/possession_metrics.py:259` derives scored runs from non-X ground truth, then fills predicted X forward and leading X backward within each run. A wholly abstained run remains X. Frame macroF1 sees raw X as misses. Scored runs need not equal complete halves when only a public slice has labels.
- `evaluation/possession_metrics.py:464` extracts maximal H/A runs. D is excluded as an object but splits H–D–H into two possessions. A one-frame D or opposite-team island can therefore affect matching. H–X–H is merged by the temporal fill; X over a turnover instead delays the boundary.
- Transition diagnostics use ±12/25 frames, independently of spellF1's IoU thresholds. The documented one-frame-free example is not a universal boundary exemption: tiny spells remain sensitive.
- Ranking is spellF1, then macroF1; no unofficial metric or scorer behavior was changed.

## Tracking, timing and rule checks

P1 parses every contiguous tactical ATD frame, maps `frame_id - 1`, scales to 105.3×68 m and preserves out-of-bounds positions. Short interpolation uses observed endpoints inside a single half and rejects implausible endpoint displacement; missing pairs become NaN, not zero. Derivatives do not bridge missing/imputed observations or half boundaries. Player identity changes and observed source teleports remain; relative velocities and density/control proxies are not used by the current P3 emissions. The raw A fingerprint still matches the frozen P1 candidate.

Smart Tagging uses rounded seconds×25 with exclusive ends. The published second-half scored block starts before its actual kickoff; neither is an offset error. Broadcast tracking is not merged into the tactical timeline. Video and homography are not required inputs to the released possession method; optional homography callers must honor validity/alignment checks.

No hosted model invocation or match-data upload was found in `src/` or `scripts/`. Network code only downloads pinned external sample files. `google-genai` was an unused dependency, not evidence of an upload. Public-label reads occur in scoring paths, not P1/P2/P3/P4 inference; experiment scoring uses synthetic truth. This is a source audit, not proof about every past manual experiment or external account action. Historical reports show repeated public sanity measurements, so those scores must not be used to choose among submitted versions.

Tracked-file checks found no competition XML, ATD text, video, Parquet handoffs or `.env` files in the current index. Private assets, detailed caches and generated outputs stay ignored. Source checks cannot certify remote history or the organiser's enrolment terms; no redistribution or upload is introduced by these fixes.

## Executed verification

- Mock pipeline and official validator: pass, 199,319 rows.
- Full suite: **74 tests, no skips, pass**, including actual tactical integration. New regressions cover contracts, stale D, missing-boundary continuity, post-restart tag behavior, arbitration islands, HMM enumeration and X/D scoring semantics.
- Two full real-data pipeline runs: both validate; every A/B/C/D/CSV hash matches between runs.
- Local arbitration: eight windows, zero overrides, zero changed frames.
- External Metrica: 145,006 frames, two periods, eight windows, zero overrides. No external possession accuracy is measured.
- Final frozen-code public sanity: spellF1 **0.229630**, macroF1 **0.655278**, 37 predicted possessions. No thresholds were changed after this score. The small difference from the prior correction (0.2222 spellF1) is not evidence of generalization; the public smooth125 reference remains 0.4242. We cannot claim zero prediction errors or full-match score regressions from these checks.
- After broadening only the synthetic stress durations, the seven missing-evidence/stress tests passed again. That change does not affect the real-data inference code or its verified outputs.

Logs, fingerprints and generated CSV: `artifacts/repository_audit/`. The reproducible runtime is Python 3.12 with pinned `requirements-team.txt`. Current inference uses no optional development packages. Earlier submission packages and root CSV are not silently replaced.

For nonempty overrides, retain the local runner's D, `response_cache.json` and `summary.json` together and use matching A/B/C. Do not copy only D into another input version. Normal generation with no overrides file writes a validated empty D.

## Audited output fingerprints

The standalone freeze utility also reproduced the full pipeline C and CSV hashes. NaN/out-of-range entropy and override thresholds now fail rather than silently disabling their guards.

| Output | SHA-256 |
|---|---|
| spatial | `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB` |
| deadball | `E4D3437CC21BCD0CC89890EA4C2921F9EA21E481D46242230EC3DA0EB681481B` |
| predictions | `117E932A7FC2D1FA6BDC2A6663D8A007415FC5DD530B90BC28120073B8C98E16` |
| overrides | `6003E21FC6478FC506A5DA9A11569F5A4CBD99141C2D63C076EDE3659FA41177` |
| submission | `75C89431B452D7727938A1C2B6127B58630EF80E89C7A7FEEF669D9FF52165E8` |
