<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RE:Symbiose compression calibration (generated, do not edit)

Background compression never pauses the caller: submit latency is the
caller-visible pause; elapsed time completes on the worker thread.

| Context | Reps ready | Submit median | Queue median | Plan median | Sink median | Complete median | Complete p95 | Tokens/s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 320000 | 4/4 | 3.1 ms | 3.1 ms | 0.0 ms | 0.0 ms | 3.2 ms | 3.4 ms | 100628930.8 |
| 400000 | 4/4 | 3.9 ms | 3.9 ms | 18.5 ms | 1.1 ms | 23.5 ms | 23.7 ms | 17006802.7 |
| 640000 | 4/4 | 5.9 ms | 5.9 ms | 33.7 ms | 1.3 ms | 40.9 ms | 40.9 ms | 15662857.0 |

Profile: trigger=320000, target=128000, sink=file.
Workloads use deterministic varied synthetic text. Tokens/s is a
pipeline upper bound, not a model or retrieval-quality claim.
ONNX indexing is intentionally excluded; this tool times planning,
background eviction and the verbatim span sink only.
