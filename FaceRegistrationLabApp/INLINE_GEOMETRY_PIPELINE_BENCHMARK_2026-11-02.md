# Inline geometry: measured pipeline and implementation — 2026-11-02

The single-model fit runs successfully on headset. Fitting averages **34.71 ms originally, 1.77 ms with split models and 1.76 ms inline**. Both candidates remove about 95% of measured fitting time. Inline has fewer model boundaries but shows **no meaningful further fitting improvement** over split models in this run.

| Variant | Fit mean ms (traced) | Full pipeline median ms (untraced) | p95 ms | Completions/s | Eligible untraced faces |
| --- | --- | --- | --- | --- | --- |
| original | 34.71 | 256.73 | 270.73 | 3.69 | 139 |
| split | 1.77 | 230.34 | 244.07 | 4.07 | 155 |
| inline | 1.76 | 237.78 | 270.30 | 3.92 | 149 |


With tracing off, the original before/after controls have medians **254.62 / 259.57 ms**; split windows **231.04 / 230.18 ms**; inline windows **247.60 / 232.90 ms**. Pooled medians are **256.73 / 230.34 / 237.78 ms** respectively. Inline is 7.4% below the pooled original and 3.2% above split; split is 10.3% below original. This sequential live-scene run does not demonstrate an end-to-end win from inlining SVD-equivalent rotation. The two inline windows vary by 14.69 ms, so do not treat the pooled split/inline difference as an isolated solver cost.

## Inline SpatialML operations in execution order

All rows below use the same **67 complete, fresh, valid face chains**, with tracing enabled. Rows 1–11 are detector/acquisition, 12–21 landmark/fitting, 22–23 expression processing and 24–25 final publication. Values are wall durations in milliseconds. CPU/NPU labels are requested placements unless otherwise stated.

| Order | Operation / work | Implementation | Mean ms | p95 ms |
| --- | --- | --- | --- | --- |
| 1 | Acquire 3248×2464 RGB, source K and exposure timestamp; installed internal copy phases not separately timed | Native VST operator | 17.02 | 22.22 |
| 2 | Select effective virtual camera intrinsics for the lab | JavaScript | 3.89 | 7.44 |
| 3 | Look up camera pose at the exposure timestamp | Native pose operator | 0.24 | 0.71 |
| 4 | Compose crop affine with the lab image transform | JavaScript | 2.86 | 6.73 |
| 5 | Affine sample/crop/resize RGB bytes to 256×256 | Native image operator | 46.76 | 54.09 |
| 6 | Convert the cropped RGB bytes to FP32 | Native conversion | 6.36 | 8.93 |
| 7 | Normalize the cropped float pixels by 255 | Native arithmetic | 3.70 | 5.49 |
| 8 | Infer detector boxes and confidence scores | Trained LiteRT model; NPU requested | 2.94 | 6.66 |
| 9 | Decode detector tensors, select face and construct ROI | JavaScript | 26.11 | 33.02 |
| 10 | Prepare current crop/ROI and update frame/tracking state | JavaScript | 3.07 | 4.93 |
| 11 | Copy producer state into a calibration diagnostic snapshot | JavaScript | 2.29 | 4.29 |
| 12 | Compose crop affine with the lab image transform | JavaScript | 2.61 | 5.31 |
| 13 | Affine sample/crop/resize RGB bytes to 256×256 | Native image operator | 70.18 | 76.37 |
| 14 | Convert the cropped RGB bytes to FP32 | Native conversion | 6.41 | 9.06 |
| 15 | Normalize the cropped float pixels by 255 | Native arithmetic | 3.65 | 5.68 |
| 16 | Infer 478 landmark triplets and presence outputs | Trained LiteRT model; NPU requested | 2.56 | 4.13 |
| 17 | Validate landmarks, update tracking ROI, compute depth mean and prepare the 33 fit points | JavaScript | 15.50 | 21.25 |
| 18 | Three sparse fits, inline quaternion/Jacobi rotations, two unprojections, scales and pose | Weightless LiteRT model; CPU requested | 1.76 | 3.44 |
| 19 | Camera-to-world transform, pose checks/filtering and tracker validity feedback | JavaScript | 6.39 | 8.99 |
| 20 | Fit/reprojection/quality diagnostics and invalidity feedback to tracker | JavaScript | 5.96 | 8.48 |
| 21 | Copy sparse fit intermediates into a calibration diagnostic snapshot | JavaScript | 9.54 | 12.55 |
| 22 | Gather 146 XY pairs, undo ROI crop and normalize for expression model | Weightless LiteRT model; CPU requested | 0.40 | 1.77 |
| 23 | Infer 52 expression scores | Trained LiteRT model; NPU requested | 2.78 | 4.67 |
| 24 | Concatenate selected final fields into the 6,332-byte packet | Weightless LiteRT model; CPU requested | 0.21 | 0.70 |
| 25 | Publish terminal completion sequence after the output is ready | JavaScript | 2.48 | 4.76 |


The inline solver at row 18 performs all three sparse fits and both scale-dependent unprojections. Covariance, quaternion diagonalization and rotations remain inside LiteRT. The following pose/quality operations still update service-side tracking state before final output publication. Only final app results cross to the app; no intermediates are read back and uploaded to resume SpatialML.

The two native crop operators alone total **116.94 ms**; detector and landmark preprocessing including affine preparation, byte→float conversion and normalization total **142.53 ms**, about 58% of the inline operator budget. Detection decode/ROI is **29.18 ms**, sparse landmark preparation **15.50 ms**, face pose/quality **12.35 ms** and fit snapshot **9.54 ms**. These are the remaining measured priorities. The current run deliberately holds the native preprocessing configuration fixed.

## Component comparison

| Component, mean ms | Original | Split | Inline |
| --- | --- | --- | --- |
| Final output model | 0.32 | 0.62 | 0.21 |
| Terminal marker | 2.77 | 3.38 | 2.48 |
| Blendshape input model | 0.30 | 0.44 | 0.40 |
| Blendshape inference | 2.88 | 3.79 | 2.78 |
| Landmark preprocessing | 86.15 | 89.31 | 82.84 |
| Landmark inference | 2.73 | 2.94 | 2.56 |
| Sparse landmark preparation | 16.86 | 18.00 | 15.50 |
| Geometry fitting | 34.71 | 1.77 | 1.76 |
| Face pose and quality | 13.22 | 13.55 | 12.35 |
| Fit snapshot | 9.82 | 11.86 | 9.54 |
| RGB camera | 18.67 | 21.21 | 17.02 |
| Camera values | 4.29 | 4.76 | 3.89 |
| Camera pose | 0.47 | 0.22 | 0.24 |
| Detector preprocessing | 64.77 | 62.32 | 59.68 |
| Detector inference | 3.15 | 3.25 | 2.94 |
| Detection decode and ROI | 30.33 | 33.64 | 29.18 |
| Producer snapshot | 2.75 | 2.37 | 2.29 |


Means use 55 / 60 / 67 different live face chains for original / split / inline. Differences outside fitting include sequential workload variation and are not isolated effects of the fitting change. The CSV retains all 91 individual rows across the three graphs, including mean, median, p95 and sample counts.

## What happened to the SVD operations

| Variant | Fit pipeline index | Operation | Implementation | Mean ms | p95 ms |
| --- | --- | --- | --- | --- | --- |
| original | 6 | geometry_covariance | javascript | 4.563 | 8.124 |
| original | 7 | SVD | native | 0.232 | 0.657 |
| original | 8 | geometry_solve | javascript | 4.600 | 7.916 |
| original | 9 | geometry_unproject | javascript | 2.810 | 4.692 |
| original | 10 | geometry_covariance | javascript | 4.529 | 7.505 |
| original | 11 | SVD | native | 0.154 | 0.432 |
| original | 12 | geometry_solve | javascript | 5.025 | 10.197 |
| original | 13 | geometry_unproject | javascript | 3.175 | 6.631 |
| original | 14 | geometry_covariance | javascript | 4.673 | 7.492 |
| original | 15 | SVD | native | 0.403 | 1.045 |
| original | 16 | geometry_solve | javascript | 4.544 | 7.723 |
| split | 6 | face_fit_prepare | model | 0.327 | 1.402 |
| split | 7 | SVD | native | 0.217 | 0.724 |
| split | 8 | face_fit_bridge | model | 0.466 | 1.090 |
| split | 9 | SVD | native | 0.150 | 0.643 |
| split | 10 | face_fit_bridge | model | 0.318 | 1.389 |
| split | 11 | SVD | native | 0.118 | 0.435 |
| split | 12 | face_fit_finish | model | 0.172 | 0.427 |
| inline | 6 | face_fit_inline | model | 1.762 | 3.444 |


The original fit has 11 SpatialML operations, split has 7 and inline has 1. There are **35 / 31 / 25** total operations in the measured all-output paths. Split and inline fitting means differ by only **0.0053 ms**, which is not evidence of a repeatable performance improvement. Inline reduces model-boundary copies/accesses from **32 to 9**, with input/output payload **3,740 → 1,668 bytes**. It also computes the rotations with more internal arithmetic. This measurement captures the combined result; it does not isolate the cost of the individual saved boundaries.

## Service scheduling and final readback

| Inline boundary | Mean ms | p95 ms |
| --- | --- | --- |
| All 25 SpatialML operators | 245.67 | 262.60 |
| Within-task wrappers / gaps / tracing | 4.53 | 7.22 |
| Between dependent tasks | 2.08 | 4.16 |
| Submission, terminal polling and final-readback remainder | 10.66 | 18.16 |
| Submission → terminal readback, including preceding rows | 262.94 | 280.41 |


The first four mean rows sum to the last on the same 67 traced frames. Percentiles must not be summed. Terminal polling overlaps service computation; the outside-service remainder includes submission and final readback. Individual IPC/copy/poll delays are not separately isolated. The final all-output packet is **6,332 bytes**, plus a separate four-byte polling marker and IPC metadata.

## App-side computation and rendering

| App-side work | Implementation / boundary | Mean ms | p95 ms |
| --- | --- | --- | --- |
| Decode / final 478-point mesh reconstruction | Compiled Kotlin; packet validation, unprojection and inverse fitted pose; includes capture-pose lookup | 0.70 | 1.63 |
| Stage registration / frame checks | Compiled Kotlin; freshness, exposure pose and coordinate transforms | 1.31 | 2.63 |
| Readback → mesh-upload acknowledgement | Inclusive: decode, registration, StateFlow, normals, bounds, SDK mesh replacement and scheduling | 17.46 | 23.53 |
| Camera exposure → mesh-upload acknowledgement | Whole sensor-to-upload age; presentation is not measured | 291.64 | 324.18 |


App values use 149 eligible untraced inline frames. The 17.46 ms readback-to-upload interval **includes** the 0.70 ms decode/reconstruction and 1.31 ms registration rows. Normals, bounds, SDK mesh replacement and scheduling are not separately instrumented. Mesh-upload acknowledgement is not compositor presentation. The runner's post-frame delay also affects cadence. Geometry fitting stays in SpatialML; the app reconstructs the final dense mesh from the fitted result.

## Method, validity and trace association

Headset PB311XHGKC220141G, Registration Lab, all three outputs, native preprocessing, trained-model backend 2 requested. Original → split → inline → original; nine 20-second windows, six untraced and three with SpatialML operator tracing. Five warmup frames are excluded per window. Eligible timing frames require a detected face, a fresh camera frame, no rejection and sensor age in [-0.1, 2] seconds. No calibration or system recording was active. Ordinary small face/head motion was allowed. The lab forces detector execution and retains producer/fit diagnostic snapshots.

676 pipeline completions were captured. 182 complete eligible face chains (55 original / 60 split / 67 inline) back the operator tables. All 18 endpoint output probes contain 16 pose values, 478 vertices and 52 blendshape values; maximum reconstruction reprojection residual is 0.000161386 px. This checks mathematical output self-consistency, not physical camera/eye calibration. No new One check or Full trial was recorded.

| Trace window | Complete eligible face chains | Clock anchors | Anchor spread ms | Unmatched complete chains |
| --- | --- | --- | --- | --- |
| original-trace | 55 | 3 | 0.709 | 0 |
| split-trace | 60 | 4 | 1.588 | 0 |
| inline-trace | 67 | 4 | 4.477 | 0 |


Each task requires successful complete ordered operator events, expected type signatures, matching service/client ownership and exact dependency task IDs. Decimal dependency references are joined to hexadecimal task IDs. Same-client capture+age log anchors map wall-clock service events to monotonic journal intervals with 10 ms tolerance. Only unique frame/chain matches survive. Active layouts include only detector, landmark-fit, expressions and output_7. Unmatched, incomplete, warmup and ineligible frames are excluded.

| Window | Completions | Eligible faces after warmup | Untraced / traced | Median ms | p95 ms |
| --- | --- | --- | --- | --- | --- |
| original-before | 76 | 70 | untraced | 254.62 | 267.92 |
| original-trace | 62 | 57 | traced | 311.68 | 355.82 |
| split-before | 82 | 77 | untraced | 231.04 | 243.61 |
| split-trace | 66 | 61 | traced | 280.50 | 387.37 |
| split-after | 83 | 78 | untraced | 230.18 | 244.73 |
| inline-before | 77 | 72 | untraced | 247.60 | 274.70 |
| inline-trace | 74 | 69 | traced | 257.57 | 280.27 |
| inline-after | 82 | 77 | untraced | 232.90 | 253.40 |
| original-after | 74 | 69 | untraced | 259.57 | 271.25 |


## Conditions and limits

Thermal snapshots: `[{"label": "before", "status": ["Thermal Status: 2"]}, {"label": "split", "status": ["Thermal Status: 2"]}, {"label": "inline", "status": ["Thermal Status: 2"]}, {"label": "restored", "status": ["Thermal Status: 2"]}, {"label": "final", "status": ["Thermal Status: 2"]}]`. Environment doctor is usable/PARTIAL with no errors: CLI 0.6.0 public, plugin overview pico-unity-agentic-tools@0.1.0, knowledge 6.0; SDK project resolution and optional emulator/editor are unavailable in that overview. No KB-derived SDK guidance, environment repairs or tooling updates were used. Existing Gradle/source and device contracts drive this measurement.

- Native preprocessing is held constant to isolate fitting. This does not benchmark the combined GPU/RGB-first preprocessing experiment.
- Operator timings include service wrappers and tracing. Untraced whole-pipeline timings are a separate population; do not subtract one from the other to infer copies or synchronization.
- The model has 1,492 internal LiteRT nodes, but only one SpatialML invocation. There are no per-internal-node, individual memcpy or GPU-kernel timings in this run.
- Requested CPU/NPU targets are recorded. This run verifies model invocation success and output contracts, not full independent delegate-partition coverage.
- No controlled identical-frame legacy/inline device replay, optical acceptance, invalid-face recovery exercise or all-seven-mode switch sweep was performed. Host parity covers synthetic/recorded inputs and mode routing.
- No Perfetto scheduler, Binder caller/callee, CPU/GPU counter or compositor capture was taken; no hardware bottleneck or presentation latency is assigned.
- Thermal status was 2 in all five snapshots. This records the run condition; it does not identify the cause of timing variation.
- The first original trace window had no every-100-frame app clock anchor. Three retained anchors from the same original PID were recovered immediately from the log buffer; raw evidence is preserved in original-clock-buffer.log. Future driver runs retain continuous anchors.
- Model transport copy counts come from local service source, whose equivalence to the installed service revision is not established. Actual isolated copy time remains unmeasured.

## Build, assets and final state

The new inline model passes 126 full-fit OpenCV-referenced host cases and 7,001 rotation stress cases. Existing split parity, runtime completion/snapshot/profile regressions, production graph selection and 36 serialized model-call bindings pass. Both apps pass assembleDebug/lintDebug/spotlessCheck with inline enabled and with defaults; split APKs were rebuilt from the same current source. Default host Gradle outputs are restored.

Exact original APK **7ae804e2e3606d81eb7c2ab64f649abad940731d1feab5a7578d68afd99ef023** was restored and hash-verified. The original unset debug property and all-output selection were restored. Final frame 137 has a face and the camera is running; Custom mode 4 / revision 0 remains selected. Camera-calibration SHA-256 is unchanged; all **271** pre-existing external files remain present and nonshrinking. The device lease is released. No service restart, service/SDK APK replacement, clear/uninstall, calibration change, commit or push occurred.

Measured split APK: `5b7f9a8f32f29d41e38939efa0c8997500cc04858e6a885c9d48ad4ed0562363`. Measured inline APK: `1ba61dc7df220c363c5036c152b8a81c9a3326e72d2bec8ad6c6cc81bf36df1f`. Both candidates remain opt-in (`faceFusedGeometry` / `faceInlineGeometry`); measured device execution does not replace calibration acceptance.

Artifacts: `artifacts/facelandmarker/inline-geometry-20261102/session-output-20261102-151103/`. The manifest preserves windows, output probes and restoration; `performance-data/analysis.json`, `all-operator-face-timings.csv` and `inline-ordered-operations.csv` contain the full statistics. `analyze_run.py` and `write_report.py` reproduce the tables. The [implementation](INLINE_GEOMETRY_MODELS_2026-11-02.md) documents the numerical contract and model-boundary counts.
