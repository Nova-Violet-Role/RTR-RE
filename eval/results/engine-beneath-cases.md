# Engine Beneath — case scoreboard (RE edition)

- Run: 2026-11-06T12:45:01
- Cases: 10 — passed 10, failed 0
- Verdict: **PASS**

| Case | Verdict | Required checks |
|---|---|---|
| corrupted-sink-mid-batch | pass | worker_reports_failed, error_recorded, sink_attempted_write |
| corrupted-sink-reports-failed | pass | worker_reports_failed, error_recorded |
| duplicate-submission-deterministic | pass | same_keep, same_evict, same_total_tokens |
| live-engine-sink-roundtrip | pass | verdict_pass, sink_exists, sink_has_marker |
| preset-axis-all-six | pass | standard_resolves, calibrated_resolves, wide_resolves, fusion-ah_resolves, symbiose-ah_resolves, re-symbiose_resolves |
| production-scale-bounds | pass | all_accounted, keep_within_max, compress_triggered |
| production-scale-extreme-protection-warning | pass | old_todo_evicted_past_threshold, recent_todo_retained, all_accounted |
| protected-tool-todowrite-retained | pass | todowrite_retained |
| tool-pair-fixpoint | pass | call_retained, result_retained |
| worker-cache-deduplicates | pass | second_is_cached, same_digest, first_ready |

