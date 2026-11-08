# P4 technical outline and arbitration experiment

Nov 7 and 8 deliverables completed on Nov 8, 2026.

## Response contract

The local arbiter returns one JSON object with exactly four fields. This example uses synthetic evidence and illustrative frame numbers.

```json
{"start_frame": 12000, "end_frame": 12005, "override_label": "A", "confidence": 0.92}
```

Frame bounds are inclusive integers inside the requested window and one playable half. The label is H, A, D, or X. Confidence is a finite number from zero to one. The parser checks types and bounds before converting the response into a Contract D row. A rejected response or a decision to retain P3's prediction yields no override. X is an explicit override label.

Run the synthetic rejection checks with `.venv/Scripts/python.exe -m unittest discover -s tests -v`. Coverage includes malformed JSON, bad labels, invalid confidence, noninteger frames, reversed intervals, and windows that cross halftime or exceed the request.

## Inputs and method

Use the tactical timeline and the uncertainty queue generated from P3's current predictions. Refresh the queue for each new C version. Pair each window with P1 ball and team proximity, P2 stoppage evidence, and a few local tactical video reads when needed. The [Nov 6 asset report](nov06_completion.md) records successful sample reads from both videos, the one-frame broadcast count discrepancy, and the missing broadcast homography.

Start with a deterministic local rule. On a synthetic window, propose H or A only when several consecutive observed ball positions support the same team and the stoppage evidence is low. Keep the baseline when observations are missing, the teams are close, or the evidence conflicts. Compare candidate output against the unchanged P3 baseline on labeled synthetic cases covering true turnovers, occlusions, and stoppages. Check spell fragmentation, wrong overrides, and the share of windows overridden. Treat confidence as a rule score until calibrated against independent labels. Use the configured confidence threshold for the first integration check.

## External data and evaluation

Metrica Sample Game 1 can exercise event ingestion and timing. It lacks continuous possession labels, so use synthetic labels for the initial experiment and document any suitable independent labeled source before supervised tuning. Keep competition footage, tracking and extracts local. Use the public competition window for pipeline sanity checks.

## Reproduction

Record the code commit, input artifact versions, window-selection settings, arbitration settings and accepted override file. Regenerate D when C changes. Preserve the output CSV checksum and official validator result for the final technical document. Run the baseline without arbitration first, then compare the experiment using the same inputs and the validated D rows.

The response parser and synthetic checks are complete. The experiment is designed for the upcoming implementation and dry run.
