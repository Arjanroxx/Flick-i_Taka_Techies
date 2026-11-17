# P1 — A candidate 1: frozen spatial candidate (Nov 12 deliverable)

Owner: P1. Nov 12 deliverable: freeze the next spatial candidate and document remaining
limitations; A candidate 1 must be validated and reproducible from code. This is the file P2
rebuilds B against today (Nov 12 handoff order: P1 → P2 → P3 → P4).

## Handoff A candidate 1

| | |
|---|---|
| File | `artifacts/spatial_features.parquet` |
| SHA-256 | `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB` |
| Reproducibility | Two clean regenerations produced identical hashes; run logged below |
| Spatial code | `src/p1_spatial_features.py` at commit `5ae09e3` (branch `p1/nov05-08-preparation`) |
| Regenerate | `.venv/Scripts/python.exe scripts/check_p1_loader.py --write-a` |
| Config | `configs/config.yaml` — `short_gap: 12` (unchanged) |
| Contract | `validate("spatial", table)` passes; `python -m unittest discover -s tests -v` → 27 tests OK; mock pipeline validator `OK` + 199,319 rows |
| Input version | Tactical bundle delivered Nov 6, unpacked 2026-11-12 into `data/tactical/` (not committed) |

**To the team:** A candidate 1 is frozen at the above commit. Share the parquet and config
privately (not via the repository). Record this document, the commit and the hash with your
handoff log. P2: the summary of A changes from A v0 is in
[nov09_a_v1.md](nov09_a_v1.md) — derivatives are now NaN wherever a filled position participates,
and 32 teleport-spanning fills were removed; your stoppage mask should be rebuilt against this.

## Content summary

199,319 rows; official halves (play blocks 11185–90651 and 110808–190197; `half=0` elsewhere);
coordinates in metres on 105.3 × 68 m (out-of-bounds values preserved for P2); ball observed
59.32%, imputed 19 frames, otherwise missing. Gap policy: only gaps ≤ `short_gap` (12 frames)
inside a half, with endpoint implied speed ≤ 40 m/s, are linearly interpolated.

## Remaining limitations

1. **Ball missing on 40.7% of play frames.** Short-gap fill can only help with 4 holes; the
   ~11 s median outages remain unresolved by design. Any consumer must handle NaN distances.
2. **Tracker teleports persist in observed data** (e.g. y sweeping from −5.98 m to 64 m in
   ~1 s, reaching a 109.6 m/s reading). These are source defects, faithfully propagated; P2
   rejects derivatives that touch unobserved frames, P3 demotes imputed evidence to neutral.
3. **224 observed→observed frames exceed 40 m/s** and 7 frames exceed 100 m/s. Left as measured.
4. **Incomplete H visibility near half 1's end** (frames 90038–90221): no H track slot observed;
   distances report NaN. Correct behaviour, surfaced here because P3 neutralises it rather than
   mislabelling it.
5. **Broadcast feed unused.** Not aligned to the tactical timeline (one frame count
   discrepancy in video; no homography) and not required for the spatial contract. Excluded
   until synchronisation is verified — do not extrapolate broadcast geometry into A.
6. **`voronoi_control_H` remains the distance proxy** (~0.81 correlation with `dA − dH`).
   Assessment in [nov10_11_feature_quality.md](nov10_11_feature_quality.md): no added value for
   P3's current emissions; revisit only with external validation.
7. **No external validation yet.** All checks here are fixture-based or internal; Metrica's
   sample carries no frame-level possession labels, so selection evidence must come from
   fixtures or eligible other-match data.
8. **Track slots are tracklets, not people** (46 slots; identity can switch within structured
   play). `rel_vel` spikes from slot changes are retained, not filtered.

## Reproduce from clean state

```powershell
python -m venv .venv                                        # Python 3.13 confirmed working
.venv/Scripts/python.exe -m pip install -r requirements-team.txt
.venv/Scripts/python.exe scripts/check_p1_loader.py --write-a
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Set `MTAH_DATA_DIR` or pass `--data-dir` to `scripts/run_full_pipeline.py` if the bundle lives
outside `./data`.
