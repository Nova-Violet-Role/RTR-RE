<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RE:Symbiose compression calibration (generated, do not edit)

Background compression never pauses the caller: submit latency is the
caller-visible pause; elapsed time completes on the worker thread.

| Context | Reps ready | Submit median | Queue median | Plan median | Sink median | Complete median | Complete p95 | Tokens/s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 80000 | 4/4 | 0.2 ms | 0.2 ms | 4.1 ms | 0.5 ms | 4.8 ms | 5.0 ms | 16546018.6 |

Profile: trigger=40000, target=20000, sink=file.
Workloads use deterministic varied synthetic text. Tokens/s is a
pipeline upper bound, not a model or retrieval-quality claim.
ONNX indexing is intentionally excluded; this tool times planning,
background eviction and the verbatim span sink only.
