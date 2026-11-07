# Wiki Inbox
## Ingest 2026-11-06 09:01

Standing product-boundary rule (operator, 2026-11-06):
- RTR (C:\RTR) = retrieval-only, built to annihilate RAG. Every structural update — better DTD typing, better ONNX retrieval, RRF/ballot improvements — lands in the RTR repo directly.
- RTR-RE (C:\RTR-RE) = RTR retrieval + Compressor + Keeper + everything else. Every major incremental performance update to Compressor and Keeper lands only in RTR-RE.
- Presets are shared: rtr_presets.json registry exists in both, keeper bounds (trigger/target/max) and CPU/modality profiles stay in sync across both trees.
- Versus (VS) tests exist on BOTH repos but differ per product: RTR's benches prove retrieval vs RAG; RTR-RE's benches prove the full engine (keeper/compressor/manager) plus retrieval. Never assume one product's bench is the other's.
- Both repos are independent git histories; no sync tooling. Updates flow by deliberate copy per the rule above, not by sync.
