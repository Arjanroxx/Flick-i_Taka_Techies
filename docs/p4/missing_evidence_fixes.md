# Missing-evidence corrections

These corrections use synthetic behavior requirements. No competition ground-truth labels were used to select settings, and no improvement in real-match spellF1 is claimed.

## Changes

- P2 uses neutral weight 1/3 when ball tracking is missing or imputed without stronger evidence. With neutral team preferences, H/A/D emissions are equal. Observed live defaults remain 0.05.
- A recognized set-piece tag during missing/imputed tracking supplies weak D weight 0.5. This uncalibrated prior does not label all tags as dead or replace observed live-motion evidence. Existing boundary, stationary and restart logic remains.
- P3 retains three-state entropy in nats and also checks conditional H/A entropy divided by log(2). A separate `team_uncertainty: 0.9` threshold catches near-even team preferences that the old 0.9-nat threshold missed when D was unlikely. The shield remains restricted to unavailable/short-gap evidence and preserves decoded D.
- P3 restores exact neutral 1/3 after float32 serialization to avoid rounding-driven tie breaking.
- P1 returns on failed loader diagnostics before writing A.
- Existing idealized decoder experiments remain for comparison. A separate `detector_pipeline_stress` evaluation runs synthetic tracking with long outages and incomplete synthetic tags through actual P2, then P3. It is diagnostic, not external accuracy validation or a full model of real tracking.

## Verification and release handling

Regression tests cover missing and tagged occlusions, conditional H/A ambiguity under both decoders, preservation of strong D evidence, observed live motion, actual-detector stress fixtures and failure-safe handoff writing. The existing boundary-jitter test distinguishes neutral missing observations from observed live evidence.

The previous release candidate and public score describe implementation `783d20d`, not these corrections. That CSV remains preserved at the repository root and in the private submission package. Corrected outputs are generated separately under `artifacts/evidence_fixes/`; never combine an old manifest with revised B/C/D/CSV.

Use the normal pipeline commands with the current configuration to reproduce the corrected method. Local verification logs and its manifest remain private under `artifacts/evidence_fixes/`. No submission form is changed or submitted by this work. A revised submission needs its own validated CSV and matching document.

## Executed checks

All 64 tests passed with no skips, including the real tactical integration class. Two full revised real-data runs passed the official CSV validator and produced identical A/B/C/D/CSV hashes. The refreshed local arbiter reviewed eight windows, proposed zero overrides and changed zero frames. One fixed-seed detector-pipeline stress run completed; its metrics are diagnostics only, not real-match validation. No public scoring was run for this revision.

| Revised output | SHA-256 |
|---|---|
| spatial | `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB` |
| deadball | `1AA50EDB6757127A4BD42711E7155EA8A8572A5A757A562E61A0AD55F8396E10` |
| predictions | `FC052C29CFC0387B829CD90BD6B608CA4E2E249F1ED6C274939C6393E59C5819` |
| overrides | `6003E21FC6478FC506A5DA9A11569F5A4CBD99141C2D63C076EDE3659FA41177` |
| submission | `0E90CE5537FC72B2D785551D1B2898F67E9B3A20CDB95055C89C528EA9621159` |
