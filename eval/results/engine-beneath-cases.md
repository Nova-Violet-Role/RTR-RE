# Engine Beneath — case scoreboard (RE edition)

- Run: 2026-11-06T12:15:40
- Cases: 7 — passed 7, failed 0
- Verdict: **PASS**

| Case | Verdict | Required checks |
|---|---|---|
| corrupted-sink-reports-failed | pass | worker_reports_failed, error_recorded |
| duplicate-submission-deterministic | pass | same_keep, same_evict, same_total_tokens |
| live-engine-sink-roundtrip | pass | verdict_pass, sink_exists, sink_has_marker |
| preset-axis-all-six | pass | standard_resolves, calibrated_resolves, wide_resolves, fusion-ah_resolves, symbiose-ah_resolves, re-symbiose_resolves |
| production-scale-bounds | pass | all_accounted, keep_within_max, compress_triggered |
| protected-tool-todowrite-retained | pass | todowrite_retained |
| tool-pair-fixpoint | pass | call_retained, result_retained |

