# P4 — Nov 16 clean-source reproduction evidence

## Completed checks

Cloned merged main at commit `0e6fe9122dca0a20b922791dfc0f61e331720108` into an isolated ignored directory. Ran the regular full pipeline twice against the authorised local tactical bundle, with public scoring skipped.

- Both runs passed the official 199,319-row CSV validator.
- A, B, C, D and CSV SHA-256 fingerprints were identical across both runs.
- All five outputs matched the previously recorded provisional Nov 14 candidate.
- All 45 tests passed from the cloned source tree.
- The cloned source tree remained clean after generation and tests.

This run reused the existing Python 3.12 team environment. Dependency installation into a newly created environment was outside this check. The input configuration was created privately in the clone, using the authorised bundle location and the repository's model settings.

## Local evidence

The clean source and generated files are under `artifacts/p4/nov16/checkout/`. Logs, the run script and `reproduction.json` are under `artifacts/p4/nov16/`. The manifest records the source commit, interpreter, output fingerprints, repeat comparison and prior-candidate comparison. Competition assets, private paths and generated predictions remain ignored.

## Remaining release work

The compared C was regenerated from the merged baseline. P3's reviewed/frozen C handoff remains outstanding in the visible repository reports. When that handoff arrives, record its matching A/B versions and settings, refresh the D decision and run the release export and reproduction checks against those exact inputs.

P4's final public-window sanity report and technical-document release fields still depend on that reviewed release candidate. This check used no public ground-truth scoring or threshold selection. Nov 12–13 and Nov 15 final handoff sign-offs remain pending.
