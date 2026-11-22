# RGB-first face pipeline benchmark — 2026-11-02

RGB-first preprocessing (face-bearing workload) measured **281.33 ms median submission-to-completed-readback**, versus **277.33–295.98 ms** in the previous-GPU windows. The measured latency change is **-5.0% to +1.4% relative to the two controls; no consistent improvement**.

| Window, tracing off | Eligible face-bearing frames | Submit → terminal readback median | p95 | Completions/s |
| --- | ---: | ---: | ---: | ---: |
| native-baseline | 58 | 369.46 ms | 393.67 ms | 2.63 |
| gpu-baseline | 40 | 277.33 ms | 295.60 ms | 3.74 |
| rgb-baseline | 95 | 281.33 ms | 311.36 ms | 3.30 |
| gpu-after | 75 | 295.98 ms | 341.62 ms | 3.25 |
| native-after | 43 | 373.00 ms | 427.10 ms | 2.63 |


Fresh 30-second tracing-off windows compare native → previous GPU → RGB-first → repeated previous GPU → restored native. Each main variant has a 20-second operator trace. The camera had no detected face at initial readiness, so capture proceeds with explicit face/no-face stratification. GPU variants start with fresh SpatialML service processes because earlier session teardown caused input-buffer initialization failures. This runtime reset is recorded separately from code changes; no service APK or SDK was changed. App/profile/recording data are retained. Subject motion and sequential images/load vary.

## Population and end-to-end timing

Primary population: **face-bearing**. No-face timings do not establish full face-bearing geometry/packing latency.

| Window | Completions | Faces | Excluded warm-up | Eligible primary population |
| --- | ---: | ---: | ---: | ---: |
| native-baseline | 80 | 58 | 5 | 58 |
| native-operators | 49 | 43 | 5 | 38 |
| gpu-baseline | 113 | 45 | 5 | 40 |
| gpu-operators | 57 | 32 | 5 | 28 |
| rgb-baseline | 100 | 100 | 5 | 95 |
| rgb-operators | 64 | 34 | 5 | 29 |
| gpu-after | 99 | 80 | 5 | 75 |
| gpu-after-operators | 64 | 39 | 5 | 37 |
| native-after | 80 | 47 | 5 | 43 |


Five initial completions are excluded per window. Population latency additionally requires fresh, unrejected frames in the sensor-clock domain. Cadence counts all consumed work, including rejected/no-face frames, after warm-up. A startup or face-readiness failure is excluded, not a fast frame. Terminal completion is measured; upload acknowledgement is not compositor/display presentation.

| Primary-population tracing-off boundary | Native median | Previous GPU median | RGB-first median | RGB change |
| --- | ---: | ---: | ---: | ---: |
| Exposure → submission | 33.00 ms | 34.17 ms | 31.11 ms | -3.06 ms |
| Submission → terminal readback | 369.46 ms | 277.33 ms | 281.33 ms | +4.00 ms |
| Exposure → terminal readback | 401.93 ms | 305.83 ms | 312.80 ms | +6.97 ms |
| Terminal readback → upload acknowledgement | 11.73 ms | 12.92 ms | 14.31 ms | +1.39 ms |
| Exposure → upload acknowledgement | 412.49 ms | 322.18 ms | 328.70 ms | +6.52 ms |


Each boundary has its own paired frame population. Boundary medians are not added to infer total latency.

## Computation changes

Both control traces show lower preprocessing model-call means: detector 13.12–13.12 → 9.43 ms (28.1–28.1% lower); landmark_fit 11.42–11.81 → 8.59 ms (24.8–27.3% lower). The combined model-call saving is 6.51–6.91 ms. This measured component improvement has not produced a consistent tracing-off end-to-end improvement relative to both controls.

| Component, tracing-on mean | Native | Previous GPU | RGB-first | RGB change vs previous GPU |
| --- | ---: | ---: | ---: | ---: |
| RGB camera, camera values and pose | 18.66 ms | 22.85 ms | 19.25 ms | -3.60 ms |
| Detector affine, crop, conversion and normalization | 61.79 ms | 28.07 ms | 23.52 ms | -4.55 ms |
| Detector inference | 2.71 ms | 3.55 ms | 3.01 ms | -0.54 ms |
| Detection decode and ROI | 29.49 ms | 33.78 ms | 31.87 ms | -1.91 ms |
| Producer snapshot | 2.40 ms | 3.01 ms | 2.89 ms | -0.13 ms |
| Landmark affine, crop, conversion and normalization | 85.63 ms | 27.74 ms | 23.57 ms | -4.16 ms |
| Landmark inference | 2.56 ms | 3.55 ms | 2.97 ms | -0.58 ms |
| Tracking and geometry fits | 53.84 ms | 61.97 ms | 56.67 ms | -5.29 ms |
| Registration diagnostics | 5.60 ms | 6.99 ms | 6.93 ms | -0.06 ms |
| Fit snapshot | 9.75 ms | 11.16 ms | 9.46 ms | -1.70 ms |
| Mesh projection, unprojection and conversion | 36.58 ms | 42.22 ms | 39.90 ms | -2.32 ms |
| Blendshape inference | 2.69 ms | 3.37 ms | 3.00 ms | -0.36 ms |
| Result packing | 41.11 ms | 43.44 ms | 44.32 ms | +0.88 ms |
| Mesh snapshot | 34.84 ms | 39.52 ms | 36.76 ms | -2.76 ms |
| Terminal completion marker | 1.67 ms | 2.93 ms | 1.85 ms | -1.08 ms |


Component and operator rows use the uniquely matched eligible face chains. App periodic log entries anchor wall time to monotonic time; detector start and mesh completion must fit exactly one journal submit/readback interval within a 10 ms tolerance. The previous-GPU component column uses its first operator window. Its repeated control has a separate `gpu_after` entry in component JSON and a separate operator timing file; both tracing-off control windows appear above.

| Preprocessing detail, tracing-on mean | Previous detector | RGB detector | Previous landmark | RGB landmark |
| --- | ---: | ---: | ---: | ---: |
| Lab affine | 2.06 ms | 2.55 ms | 3.34 ms | 2.89 ms |
| GPU preprocessing model | 13.12 ms | 9.43 ms | 11.81 ms | 8.59 ms |
| Lab byte reconstruction | 6.03 ms | 4.67 ms | 5.13 ms | 4.81 ms |
| Lab byte conversion | 6.86 ms | 6.87 ms | 7.46 ms | 7.29 ms |


RGB-first feeds uint8 directly into Resampler and omits the explicit full-resolution float CAST. The full uint8 input payload copies and lab byte reconstruction/conversion still exist. Removing a logical graph tensor is not proof that the delegate avoids every full-image internal conversion or packing operation.

## Remaining time and what consumes it

| Remaining component | Mean | Median | p95 | Share of measured operator work |
| --- | ---: | ---: | ---: | ---: |
| Tracking and geometry fits | 56.67 ms | 56.39 ms | 64.76 ms | 18.5% |
| Result packing | 44.32 ms | 42.83 ms | 52.75 ms | 14.5% |
| Mesh projection, unprojection and conversion | 39.90 ms | 39.29 ms | 48.09 ms | 13.0% |
| Mesh snapshot | 36.76 ms | 36.58 ms | 42.79 ms | 12.0% |
| Detection decode and ROI | 31.87 ms | 31.65 ms | 37.83 ms | 10.4% |
| Landmark affine, crop, conversion and normalization | 23.57 ms | 23.75 ms | 29.23 ms | 7.7% |
| Detector affine, crop, conversion and normalization | 23.52 ms | 22.80 ms | 28.32 ms | 7.7% |
| RGB camera, camera values and pose | 19.25 ms | 18.82 ms | 23.81 ms | 6.3% |
| Fit snapshot | 9.46 ms | 9.33 ms | 13.43 ms | 3.1% |
| Registration diagnostics | 6.93 ms | 6.49 ms | 10.09 ms | 2.3% |
| Detector inference | 3.01 ms | 2.84 ms | 5.01 ms | 1.0% |
| Blendshape inference | 3.00 ms | 2.74 ms | 5.02 ms | 1.0% |
| Landmark inference | 2.97 ms | 2.62 ms | 4.90 ms | 1.0% |
| Producer snapshot | 2.89 ms | 2.56 ms | 6.88 ms | 0.9% |
| Terminal completion marker | 1.85 ms | 1.34 ms | 3.71 ms | 0.6% |


The operator budget is **305.99 ms mean** on the same linked RGB-first detector/fit/mesh chains. Percentages cover measured operator work; operator durations include service wrappers and tracing. This is distinct from untraced app latency, so no subtraction between unlike trace-off medians and trace-on means is used to invent transport time.

- native: 35 eligible face chains (40 uniquely matched total); service elapsed mean 398.13 ms; inter-task gap mean 1.71 ms.
- gpu: 27 eligible face chains (49 uniquely matched total); service elapsed mean 343.88 ms; inter-task gap mean 1.62 ms.
- rgb: 27 eligible face chains (56 uniquely matched total); service elapsed mean 314.44 ms; inter-task gap mean 1.61 ms.
- gpu_after: 35 eligible face chains (55 uniquely matched total); service elapsed mean 309.93 ms; inter-task gap mean 1.29 ms.

The large remaining JS geometry/packing/snapshot operations include JS runtime/context and tensor-array marshaling costs. Camera acquisition includes full-image CPU hardware-buffer access and RGBA→RGB materialization, lab K selection, and timestamped pose lookup. Preprocessing includes input/output buffer copies and lab export-crop copies. Trained model inference is measured separately. The current traces do not divide VST buffer lock/color conversion or LiteRT input copy/GPU execution/output copy into individually measured phases; their internal allocation remains unmeasured. Completion polling overlaps graph work; it is not an extra sequential block to add to the graph total.

The lab byte-crop reconstruction/conversion pairs total **23.64 ms**, included inside the two preprocessing groups above. The three nested snapshots total **49.11 ms**. Together these lab evidence paths account for **72.75 ms** of current measured operator work. A candidate next change is executing them only for selected diagnostic/export frames, preserving the exact frozen-frame snapshot/packet and terminal completion contracts. This is a measured current cost, not a guaranteed end-to-end saving.

| RGB-first same-face timing budget, tracing on | Mean |
| --- | ---: |
| All service operators | 305.99 ms |
| Within-task wrapper/gaps | 6.84 ms |
| Between dependent tasks | 1.61 ms |
| Combined submission/readback/polling outside service run span | 9.49 ms |
| Submission → terminal readback total | 323.93 ms |


These means reconcile on the same eligible face frames. They are measured with tracing on; the production comparison above uses tracing-off distributions.

## Every service operator

| Pipeline / element | Native mean | Previous GPU mean | RGB-first mean | RGB change |
| --- | ---: | ---: | ---: | ---: |
| detector / RectifiedVSTAccess | 15.00 ms | 18.76 ms | 15.07 ms | -3.70 ms |
| detector / lab_camera | 3.29 ms | 3.62 ms | 3.77 ms | +0.15 ms |
| detector / CameraSpaceToWorld | 0.37 ms | 0.47 ms | 0.41 ms | -0.05 ms |
| detector / lab_affine | 2.55 ms | 2.06 ms | 2.55 ms | +0.49 ms |
| detector / ApplyAffine → detector_preprocess_rgb_gpu | 48.55 ms | 13.12 ms | 9.43 ms | -3.69 ms |
| detector / Assignment | 6.90 ms | 6.86 ms | 6.87 ms | +0.01 ms |
| detector / Arithmetic | 3.79 ms | 6.03 ms | 4.67 ms | -1.36 ms |
| detector / face_detector | 2.71 ms | 3.55 ms | 3.01 ms | -0.54 ms |
| detector / decode_detection | 25.82 ms | 29.95 ms | 28.30 ms | -1.65 ms |
| detector / prepare_roi | 3.68 ms | 3.83 ms | 3.57 ms | -0.26 ms |
| detector / lab_frame_snapshot | 2.40 ms | 3.01 ms | 2.89 ms | -0.13 ms |
| landmark_fit / lab_affine | 3.07 ms | 3.34 ms | 2.89 ms | -0.45 ms |
| landmark_fit / ApplyAffine → landmark_preprocess_rgb_gpu | 72.34 ms | 11.81 ms | 8.59 ms | -3.22 ms |
| landmark_fit / Assignment | 6.78 ms | 7.46 ms | 7.29 ms | -0.17 ms |
| landmark_fit / Arithmetic | 3.43 ms | 5.13 ms | 4.81 ms | -0.32 ms |
| landmark_fit / face_landmarks_detector | 2.56 ms | 3.55 ms | 2.97 ms | -0.58 ms |
| landmark_fit / track_landmarks | 16.02 ms | 18.83 ms | 17.17 ms | -1.66 ms |
| landmark_fit / geometry_covariance | 4.23 ms | 5.27 ms | 4.69 ms | -0.58 ms |
| landmark_fit / SVD | 0.31 ms | 0.17 ms | 0.19 ms | +0.02 ms |
| landmark_fit / geometry_solve | 4.13 ms | 5.12 ms | 4.86 ms | -0.26 ms |
| landmark_fit / geometry_unproject | 2.48 ms | 2.61 ms | 2.80 ms | +0.19 ms |
| landmark_fit / geometry_covariance | 3.98 ms | 5.43 ms | 4.25 ms | -1.17 ms |
| landmark_fit / SVD | 0.26 ms | 0.27 ms | 0.18 ms | -0.10 ms |
| landmark_fit / geometry_solve | 4.35 ms | 5.01 ms | 4.35 ms | -0.66 ms |
| landmark_fit / geometry_unproject | 2.89 ms | 3.69 ms | 2.32 ms | -1.37 ms |
| landmark_fit / geometry_covariance | 4.52 ms | 4.18 ms | 4.22 ms | +0.04 ms |
| landmark_fit / SVD | 0.22 ms | 0.23 ms | 0.18 ms | -0.05 ms |
| landmark_fit / geometry_solve | 4.25 ms | 4.92 ms | 4.61 ms | -0.31 ms |
| landmark_fit / face_pose | 6.20 ms | 6.22 ms | 6.83 ms | +0.62 ms |
| landmark_fit / registration_diagnostics | 5.60 ms | 6.99 ms | 6.93 ms | -0.06 ms |
| landmark_fit / lab_geometry_snapshot | 9.75 ms | 11.16 ms | 9.46 ms | -1.70 ms |
| mesh / mesh_landmarks | 11.03 ms | 12.92 ms | 13.86 ms | +0.94 ms |
| mesh / geometry_project | 15.37 ms | 17.82 ms | 15.44 ms | -2.37 ms |
| mesh / geometry_unproject | 10.01 ms | 11.27 ms | 10.45 ms | -0.82 ms |
| mesh / Arithmetic | 0.16 ms | 0.21 ms | 0.14 ms | -0.07 ms |
| mesh / face_blendshapes | 2.69 ms | 3.37 ms | 3.00 ms | -0.36 ms |
| mesh / pack_service_result | 41.11 ms | 43.44 ms | 44.32 ms | +0.88 ms |
| mesh / lab_geometry_snapshot | 34.84 ms | 39.52 ms | 36.76 ms | -2.76 ms |
| mesh / lab_capture_marker | 1.67 ms | 2.93 ms | 1.85 ms | -1.08 ms |


CSV/JSON retain mean, median, p95, task counts and absolute/percentage changes. Operators match by semantic name and occurrence, including the native/GPU copy-order swap. Complete tasks require all expected events, matching native types and valid bounds; dependencies normalize hexadecimal task IDs and decimal `wait_for` references before joining. Missing/partial and warm-up tasks are excluded.

## Runtime validity and restoration

Recorded thermal snapshots: native-ready: Thermal Status: 1; gpu-startup: Thermal Status: 1; rgb-startup: Thermal Status: 1; gpu-repeat-startup: Thermal Status: 1; final: Thermal Status: 1. These snapshots describe conditions, not a measured throttling/CPU scheduling root cause. Today’s absolute times are compared within this run; earlier runs are not pooled.

Startup evidence confirms complete 48/68-node OpenCL delegation for RGB-first and complete 49/69-node delegation for both previous-GPU controls. Effective execution is supported by these runtime logs and completed tasks, rather than the requested backend integer alone. Live logs begin before each GPU install/launch and retain model/delegate startup evidence. Face detection is a workload check; this benchmark does not prove same-source GPU pixel equivalence, calibrated optical alignment or coherent One check exports. The RGB-first flag remains experimental pending those acceptance checks. Full startup logs, runtime errors, journals, source layouts and APK hashes are retained.

Original APK restored=True; native startup healthy=True; debug restored=True; original external files preserved=True; private calibration preserved=True; lease released=True.

No calibration capture/profile update, data clear, uninstall, commit or push occurred. Artifacts: `artifacts/facelandmarker/registration-lab/rgb-first-benchmark-20261102-193415/`, including reproducible capture/analysis/report scripts, all 39 operator changes, remaining-cost ranking, complete dependency chains, raw windows and restoration provenance.
