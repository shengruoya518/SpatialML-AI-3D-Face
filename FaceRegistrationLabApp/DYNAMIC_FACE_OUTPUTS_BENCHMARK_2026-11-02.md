# Dynamic face output benchmark — 2026-11-02

All three outputs measured **260.38 ms median submission-to-terminal-readback**, versus **348.55–353.77 ms** for the pooled before/after old full-packet control blocks. The observed median reduction is **25.3–26.4%** in this run.

| Selected outputs | Eligible face frames | Median ms | p95 ms | Completions/s | Final packet bytes |
| --- | --- | --- | --- | --- | --- |
| Pose | 100 | 258.59 | 291.28 | 3.63 | 312 |
| Mesh | 105 | 251.30 | 263.68 | 3.77 | 6124 |
| Blendshapes | 104 | 254.26 | 269.06 | 3.74 | 456 |
| Pose + mesh | 105 | 251.63 | 264.31 | 3.77 | 6124 |
| Pose + blendshapes | 64 | 285.64 | 322.86 | 3.40 | 520 |
| Mesh + blendshapes | 97 | 267.50 | 305.50 | 3.49 | 6332 |
| All three | 99 | 260.38 | 303.98 | 3.58 | 6332 |


| Control block | Eligible face frames | Median ms | p95 ms | Completions/s |
| --- | --- | --- | --- | --- |
| baseline-before | 65 | 348.55 | 386.94 | 3.18 |
| baseline-after | 125 | 353.77 | 390.34 | 2.69 |


Two 15-second tracing-off windows per mode, in forward/reverse order, with three advancing face-present probes before each window. Five initial completions are excluded per window. Face latency requires hasFace, fresh camera frame, no rejection and sensor age in [-0.1, 2] seconds. Cadence includes all consumed work after warmup. Baseline blocks use 25-second off/on/off windows. One readiness timeout occurred when the face left view; completed windows were retained and the same live session resumed. Each control block pools its two trace-off windows. Individual old-build window medians were 308.02, 359.19, 354.70 and 353.40 ms; compared with each separately the all-three median reduction spans 15.5–27.5%. This is a sequential live-scene benchmark, not an identical-image replay. Differences between output subsets include sequential scene/load variation; this run does not isolate the marginal latency cost of each requested output.

## Output validity and switching

All seven runtime combinations returned the requested fields. 41 face-present boundary probes verified pose length, 478 mesh vertices and 52 finite expression scores according to the mask. Maximum measured reconstruction reprojection residual was 0.00015080 px (internal numerical consistency only). All-off check: {'start': 1829, 'end': 1829, 'PASS': True}. Every admitted dynamic journal frame has schema 2, the selected mask, expected byte count, and calibrationEvidence=false. Face loss is retained and excluded from face latency; no NaN/malformed-packet or terminal-completion failure was observed in the measured windows.

Final-result bytes exclude the separate four-byte polling marker and IPC metadata. Compared with the old 11,976-byte packet, pose-only reduces result bytes by 97.4%, blendshapes-only by 96.2%, and all three by 47.1%. This is measured packet size, not a zero-copy or proportional latency claim. Internal detector/ROI/tracker/expression dependencies stay service-side; no readback is uploaded to continue the graph.

## App completion and mesh upload

| Mode | App decode mean ms | App registration mean ms | Submission to app result mean ms | Readback to visible mesh upload median ms | Exposure to visible mesh upload median ms |
| --- | --- | --- | --- | --- | --- |
| Pose | 0.47 | 0.79 | 264.00 | not requested | not requested |
| Mesh | 0.69 | 0.94 | 253.68 | 11.54 | 295.27 |
| Blendshapes | 0.52 | 0.39 | 255.97 | not requested | not requested |
| Pose + mesh | 0.69 | 0.86 | 253.46 | 11.45 | 299.35 |
| Pose + blendshapes | 0.56 | 0.84 | 292.37 | not requested | not requested |
| Mesh + blendshapes | 0.78 | 1.12 | 274.12 | 14.47 | 321.20 |
| All three | 0.69 | 1.00 | 267.29 | 15.38 | 304.68 |


Submission-to-app-result ends after decoding and registration. It excludes StateFlow/UI presentation. Mesh columns use only matching visible scene-upload acknowledgements; omitted outputs do not receive fabricated render timings.

## What computation remains

| Component, tracing-on mean ms | Old full packet | Pose only | Blendshapes only | All three |
| --- | --- | --- | --- | --- |
| RGB camera | 16.28 | 13.72 | 17.61 | 16.42 |
| Camera values | 3.35 | 3.63 | 3.85 | 3.23 |
| Camera pose | 0.17 | 0.14 | 0.17 | 0.30 |
| Detector preprocessing | 61.33 | 58.32 | 62.55 | 60.07 |
| Detector inference | 2.68 | 2.62 | 3.19 | 2.28 |
| Detection decode and ROI | 30.34 | 28.34 | 31.17 | 28.68 |
| Producer snapshot | 2.81 | 2.26 | 2.53 | 2.25 |
| Landmark preprocessing | 85.61 | 81.61 | 89.09 | 83.05 |
| Landmark inference | 2.62 | 2.61 | 2.84 | 2.54 |
| Sparse landmark preparation | 16.04 | 14.71 | 17.18 | 15.71 |
| Geometry fitting | 32.81 | 30.29 | 35.31 | 31.61 |
| Face pose and quality | 13.16 | 12.31 | 12.77 | 11.73 |
| Fit snapshot | 9.47 | 9.65 | 10.46 | 9.67 |
| Full mesh reconstruction | 34.83 | omitted | omitted | omitted |
| Blendshape input model | omitted | omitted | 0.30 | 0.34 |
| Blendshape inference | 2.81 | omitted | 2.95 | 2.55 |
| Legacy result packing | 43.10 | omitted | omitted | omitted |
| Mesh snapshot | 35.19 | omitted | omitted | omitted |
| Final output model | omitted | 0.21 | 0.64 | 0.34 |
| Terminal marker | 2.04 | 2.30 | 3.20 | 2.51 |


Old-build component column: baseline-after-operators. The full per-mode operator mean/median/p95/counts are in `performance-data/all-operator-face-timings.csv`; `analysis.json` contains all grouped timings and per-window distributions. Omitted means that the selected graph does not execute that operation, not a measured zero-duration call.

| All-three remaining component | Mean ms | Median ms | p95 ms |
| --- | --- | --- | --- |
| Landmark preprocessing | 83.05 | 82.89 | 90.76 |
| Detector preprocessing | 60.07 | 60.27 | 66.87 |
| Geometry fitting | 31.61 | 31.20 | 38.58 |
| Detection decode and ROI | 28.68 | 28.86 | 31.74 |
| RGB camera | 16.42 | 16.14 | 22.26 |
| Sparse landmark preparation | 15.71 | 15.31 | 19.74 |
| Face pose and quality | 11.73 | 10.92 | 16.51 |
| Fit snapshot | 9.67 | 9.25 | 13.25 |
| Camera values | 3.23 | 2.86 | 5.79 |
| Blendshape inference | 2.55 | 2.21 | 4.40 |
| Landmark inference | 2.54 | 2.22 | 4.17 |
| Terminal marker | 2.51 | 2.04 | 5.51 |
| Detector inference | 2.28 | 2.03 | 3.32 |
| Producer snapshot | 2.25 | 2.06 | 3.52 |
| Blendshape input model | 0.34 | 0.14 | 1.18 |
| Final output model | 0.34 | 0.14 | 1.30 |
| Camera pose | 0.30 | 0.11 | 1.13 |


| Tracing-on budget, same eligible face chains | Old full packet mean ms | All three mean ms |
| --- | --- | --- |
| operatorMs | 394.67 | 273.28 |
| withinTaskOverheadMs | 7.13 | 5.96 |
| interTaskGapMs | 1.32 | 2.00 |
| outsideServiceSpanMs | 9.69 | 9.92 |
| submitToReadbackMs | 412.80 | 291.16 |


The budget reconciles on the same matched eligible face frames. The outside-service span combines submission, completion polling and result readback around the service run span; it does not isolate IPC. Enqueue wait includes dependency work and is never added twice. Optional expression preparation/publication replaces JS with small weightless models. Full-mesh reconstruction and legacy result packing move to compiled app work at the final handoff; the large mesh snapshot is absent outside calibration.

## Trace validation

| Operator window | Eligible complete face chains | Clock anchors | Anchor spread ms |
| --- | --- | --- | --- |
| dynamic-trace-mask1 | 47 | 14 | 3.684 |
| dynamic-trace-mask4 | 39 | 14 | 3.684 |
| dynamic-trace-mask7 | 45 | 14 | 3.684 |
| dynamic-trace-mask2 | 46 | 14 | 3.684 |
| dynamic-trace-mask5 | 39 | 14 | 3.684 |
| dynamic-trace-mask3 | 45 | 14 | 3.684 |
| dynamic-trace-mask6 | 41 | 14 | 3.684 |
| baseline-before-operators | 9 | 3 | 4.131 |
| baseline-after-operators | 50 | 3 | 7.627 |


Every task requires complete successful ordered operator events, the expected type signature, matching service/client ownership and exact dependency task IDs. Decimal wait_for references are joined to hexadecimal task IDs. App capture+age log anchors associate wall-clock service events with monotonic journal submit/readback intervals within a 10 ms tolerance; ambiguous associations and boundary/warmup/no-face/unfresh/rejected frames are excluded. Expression and publication pipelines both contain two operations, so mapping uses complete type signatures and the active selected output pipeline.

## Per-window populations

| Window | Completions | Eligible after warmup | Face latency median ms | p95 ms | No face after warmup | Rejected after warmup |
| --- | --- | --- | --- | --- | --- | --- |
| dynamic-a-mask7 | 53 | 48 | 262.71 | 308.03 | 0 | 0 |
| dynamic-a-mask1 | 55 | 50 | 254.97 | 285.06 | 0 | 0 |
| dynamic-a-mask4 | 57 | 52 | 254.51 | 270.94 | 0 | 0 |
| dynamic-a-mask2 | 58 | 53 | 253.36 | 264.50 | 0 | 0 |
| dynamic-a-mask5 | 53 | 18 | 292.05 | 329.53 | 30 | 0 |
| dynamic-a-mask3 | 58 | 52 | 252.35 | 264.21 | 1 | 1 |
| dynamic-a-mask6 | 51 | 46 | 283.88 | 309.70 | 0 | 0 |
| dynamic-b-mask6 | 56 | 51 | 258.34 | 274.30 | 0 | 0 |
| dynamic-b-mask3 | 58 | 53 | 251.08 | 264.37 | 0 | 0 |
| dynamic-b-mask5 | 52 | 46 | 283.94 | 317.47 | 1 | 0 |
| dynamic-b-mask2 | 58 | 52 | 250.66 | 261.62 | 1 | 1 |
| dynamic-b-mask4 | 57 | 52 | 254.13 | 266.23 | 0 | 0 |
| dynamic-b-mask1 | 55 | 50 | 266.36 | 295.65 | 0 | 0 |
| dynamic-b-mask7 | 56 | 51 | 257.73 | 268.71 | 0 | 0 |
| dynamic-trace-mask1 | 53 | 48 | 276.70 | 293.99 | 0 | 0 |
| dynamic-trace-mask4 | 47 | 42 | 314.59 | 365.52 | 0 | 0 |
| dynamic-trace-mask7 | 50 | 45 | 291.53 | 304.71 | 0 | 0 |
| dynamic-trace-mask2 | 51 | 46 | 286.84 | 303.71 | 0 | 0 |
| dynamic-trace-mask5 | 48 | 42 | 295.98 | 358.91 | 1 | 0 |
| dynamic-trace-mask3 | 52 | 47 | 281.62 | 299.58 | 0 | 0 |
| dynamic-trace-mask6 | 51 | 44 | 285.36 | 301.24 | 2 | 2 |
| baseline-before-baseline_before | 85 | 35 | 308.02 | 399.23 | 45 | 1 |
| baseline-before-operators | 60 | 10 | 452.58 | 476.70 | 45 | 0 |
| baseline-before-baseline_after | 72 | 30 | 359.19 | 380.52 | 37 | 0 |
| baseline-after-baseline_before | 68 | 63 | 354.70 | 390.27 | 0 | 0 |
| baseline-after-operators | 60 | 55 | 406.09 | 468.57 | 0 | 0 |
| baseline-after-baseline_after | 67 | 62 | 353.40 | 390.07 | 0 | 0 |


## Conditions and limits

Device PB311XHGKC220141G; package com.pico.spatial.ml.sample.facelandmarker.registrationlab; branch dev/facelandmarker; Kotlin SDK 6.1.9. ROM and process details are retained in baseline metadata. Thermal snapshots: [{"file": "dynamic-after-a.json", "thermal": ["Thermal Status: 2"]}, {"file": "dynamic-after-b.json", "thermal": ["Thermal Status: 2"]}, {"file": "dynamic-after-trace.json", "thermal": ["Thermal Status: 2"]}, {"file": "dynamic-before.json", "thermal": ["Thermal Status: 2"]}, {"file": "baseline-before/before.json", "thermal": ["Thermal Status: 2"]}, {"file": "baseline-before/after.json", "thermal": ["Thermal Status: 2"]}, {"file": "baseline-after/before.json", "thermal": ["Thermal Status: 2"]}, {"file": "baseline-after/after.json", "thermal": ["Thermal Status: 2"]}]. Thermal status is a condition snapshot, not evidence of the cause of timing changes.

- Native preprocessing in both old and new builds; this isolates output changes and does not measure the GPU preprocessing experiment.
- Registration Lab forces per-frame detection and still runs producer/fit snapshots and diagnostic preprocessing copies; the normal app may have different costs.
- Operator means include tracing/service wrappers and cannot be subtracted from untraced median latency to infer transport.
- Readback timing includes terminal polling and IPC; individual buffer-copy, kernel and Binder costs are not isolated.
- App decode includes validation and capture-pose lookup; registration includes freshness checks and Stage conversion. Mesh upload acknowledgement is not compositor presentation.
- Native switch interaction, rapid switching and a new One check or Full trial were not exercised; calibration export/optical acceptance and wearer interaction with the switches remain pending.
- Small model calls completed on device. Their requested backend is CPU LiteRT; these traces do not independently identify the installed delegate partition.
- No Perfetto scheduler, CPU/GPU counters or compositor capture; hardware bottleneck attribution remains undetermined.

## Final state and artifacts

New dynamic APK restored/hash-verified: True; final debug value: ''; lease released: True; original external files checked: 268; missing: []; shrunk: []; camera calibration hash preserved: True. Other private file hash changes: ['files/profileInstalled'] (AndroidX ProfileVerifier compilation cache; packaged class evidence retained separately).

The newly implemented dynamic build is left installed with all three outputs selected. Camera parameters and recordings were preserved. No service restart, service/SDK replacement, calibration capture/profile change, data clear, uninstall, commit or push occurred during this measurement. Both apps pass assembleDebug, lintDebug and spotlessCheck after the diagnostic-control changes; 168 host model/decoder/selection cases pass. The final host APK differs from the measured APK only in classes3.dex: method-level disassembly isolates executable differences to diagnostic remoteStatus (a formatting/debug spacer); pipeline/runner/decoder/render instructions and every other packaged entry match. Exact hashes and comparison are in final-build-apk-comparison.json. The measured APK is the one restored.

Artifacts: `artifacts/facelandmarker/dynamic-outputs/session-output-20261102-141408/`. `dynamic-manifest.json` preserves window boundaries/status probes; `performance-data/analysis.json` has filtered raw statistics; CSV and chain files preserve operator detail; `analyze_dynamic.py` and `write_dynamic_report.py` reproduce the report. `apks/` contains the exact old and dynamic APKs. HTML: `report.html`.

Next optimization targets should follow the measured shared preprocessing, sparse geometry and remaining lab snapshot costs. Preserve the internal dependency chain and final-output-only readback rule. Measure the GPU preprocessing combination separately after its numerical/export acceptance; these timings do not justify promoting its experimental flag.
