# Experimental learned-control model

`learned_control.json` contains a 17-feature symmetric logistic ownership classifier, fitted on ten external SkillCorner matches and temperature-calibrated on two separate development matches. Full training code, fixed folds and source provenance are available in the repository. No competition labels were used for fitting.

This is a research candidate, not the default or approved submission model. Its external primary-metric gain is uncertain and the public sanity score is below the original sustained-control candidate. See [the study report](../docs/LEARNED_CONTROL.md).

Source data: [SkillCorner Open Data](https://github.com/SkillCorner/opendata/tree/4340d274572876239c154c90bc507a9b3250a656), credit SkillCorner and PySport. Source licence: [MIT](https://github.com/SkillCorner/opendata/blob/4340d274572876239c154c90bc507a9b3250a656/LICENSE), copyright SkillCorner 2020. Downloaded raw data and reference labels remain outside Git. The weights are transparent derived parameters, not a redistribution of tracking records.

## Segment-utility verifier

`segment_verifier.json` learns positive counterfactual spellF1 utility from twenty segment-relative features. Coefficients/feature scales and duration scale use ten other-match development records; two separate matches select a decision threshold. Its scores are not calibrated possession probabilities. Canonical JSON checksumming binds runtime parameters without depending on whitespace or line endings. This research model failed its held-out development gate and is not enabled by default. See [the Step 9 report](../docs/SEGMENT_VERIFIER.md) for folds, partial-reference limitations and reproduction. The same SkillCorner/PySport attribution above applies.
