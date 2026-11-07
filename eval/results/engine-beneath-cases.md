# Engine Beneath — case scoreboard (RE edition)

- Run: 2026-11-07T19:23:18
- Cases: 27 — passed 27, failed 0
- Verdict: **PASS**

| Case | Verdict | Required checks |
|---|---|---|
| compressor-double-duty-after-keeper-trim | pass | fires_over_trigger, kept_within_keeper_cap, kept_tokens_reduced, evict_nonempty |
| compressor-evicted-retrievable-via-memory-search | pass | compressed, sink_wrote_file, memory_search_finds_evicted |
| compressor-fires-only-past-trigger | pass | no_compress_below_trigger, compress_above_trigger |
| compressor-incremental-ten-plus-fires | pass | all_twelve_cycles_fired, all_partitions_exact, all_token_reports_exact, all_payloads_verbatim, all_ndata_masked, all_within_budget_slack |
| compressor-lexikon-interplay | pass | compressed, lexikon_expands_to_evicted_term, alias_query_retrieves_evicted |
| compressor-never-compresses-protected | pass | protected_never_compressed_below, old_protected_evictable_above, recent_protected_retained_above |
| compressor-reduces-live-window | pass | window_measurably_smaller, evict_payload_carries_all_evicted |
| compressor-session-resume-cumulative | pass | session1_compressed, cumulative_persisted_session1, session2_resumed_compressed, cumulative_grew_across_resume, atomic_write_no_tmp_leftovers |
| content-model-feature-in-header | pass | header_has_content_models, fragments_listed, fragment_query_resolves |
| corrupted-sink-mid-batch | pass | worker_reports_failed, error_recorded, sink_attempted_write |
| corrupted-sink-reports-failed | pass | worker_reports_failed, error_recorded |
| duplicate-submission-deterministic | pass | same_keep, same_evict, same_total_tokens |
| live-engine-sink-roundtrip | pass | verdict_pass, sink_exists, sink_has_marker |
| optimizer-cpu-profile-applies-threads | pass | local_system_applies_8, public_default_applies_4, legacy_performance_still_works |
| optimizer-expansion-gated | pass | expansion_on_uses_lexikon, expansion_off_gates_lexikon |
| optimizer-mjs-plan-context-aligned | pass | registry_preset_symbiose_ah, plan_trigger_250k, plan_target_100k, plan_maxkeep_40 |
| optimizer-modality-controls-hybrid | pass | rag_dense_hybrid_false, rag_dense_expansion_false, rtr_full_hybrid_true, rtr_full_expansion_true |
| optimizer-parking-applies | pass | parking20_caps_to_3, parking80_keeps_4 |
| optimizer-profile-consumed-by-engine | pass | models_match_profile, threads_match_profile, profile_hybrid_flag, profile_expansion_flag |
| parameter-entity-injection-blocked | pass | root_is_safe, no_injected_attributes, no_injected_elements, param_entities_reported_as_data |
| preset-axis-all-six | pass | standard_resolves, calibrated_resolves, wide_resolves, fusion-ah_resolves, symbiose-ah_resolves, re-symbiose_resolves |
| preset-axis-full | pass | standard_bounds_exact, calibrated_bounds_exact, wide_bounds_exact, fusion-ah_bounds_exact, symbiose-ah_bounds_exact, re-symbiose_bounds_exact, re-symbiose-mugen_bounds_exact, parking_arithmetic_all_cells, public_default_profile, local_system_profile |
| production-scale-bounds | pass | all_accounted, keep_within_max, compress_triggered |
| production-scale-extreme-protection-warning | pass | old_todo_evicted_past_threshold, recent_todo_retained, all_accounted |
| protected-tool-todowrite-retained | pass | todowrite_retained |
| tool-pair-fixpoint | pass | call_retained, result_retained |
| worker-cache-deduplicates | pass | second_is_cached, same_digest, first_ready |

